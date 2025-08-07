"""
Queue management system for django-container-manager.

This module provides high-level API for job queue operations including
job queuing, priority-based processing, and queue statistics.
"""

from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q
from datetime import timedelta
import logging
import time
import random

logger = logging.getLogger(__name__)


class JobQueueManager:
    """High-level API for job queue management"""
    
    def queue_job(self, job, schedule_for=None, priority=None):
        """
        Add job to queue for execution.
        
        Args:
            job: ContainerJob instance
            schedule_for: datetime for scheduled execution (optional)
            priority: job priority override (optional)
            
        Returns:
            ContainerJob: The queued job
            
        Raises:
            ValueError: If job cannot be queued
        """
        if job.is_queued:
            raise ValueError(f"Job {job.id} is already queued")
            
        if job.status in ['completed', 'cancelled']:
            raise ValueError(f"Cannot queue {job.status} job {job.id}")
        
        # Set priority if provided
        if priority is not None:
            job.priority = priority
            job.save(update_fields=['priority'])
            
        # Queue the job using the model's helper method
        job.mark_as_queued(scheduled_for=schedule_for)
        
        logger.info(f"Queued job {job.id} for execution" + 
                   (f" at {schedule_for}" if schedule_for else ""))
        return job
    
    def get_ready_jobs(self, limit=None, exclude_ids=None):
        """
        Get jobs ready for launching.
        
        Args:
            limit: Maximum number of jobs to return
            exclude_ids: List of job IDs to exclude
            
        Returns:
            QuerySet of ContainerJob instances ready to launch
        """
        from container_manager.models import ContainerJob
        
        queryset = ContainerJob.objects.filter(
            # Must be queued but not yet launched
            queued_at__isnull=False,
            launched_at__isnull=True,
            # Must not have exceeded retry limit
            retry_count__lt=F('max_retries')
        ).filter(
            # Either not scheduled or scheduled time has passed
            Q(scheduled_for__isnull=True) | 
            Q(scheduled_for__lte=timezone.now())
        ).order_by(
            # Order by priority (descending), then FIFO
            '-priority', 'queued_at'
        )
        
        if exclude_ids:
            queryset = queryset.exclude(id__in=exclude_ids)
            
        if limit:
            queryset = queryset[:limit]
            
        return queryset
    
    def launch_job(self, job):
        """
        Launch a queued job.
        
        Args:
            job: ContainerJob instance to launch
            
        Returns:
            dict: {'success': bool, 'error': str}
        """
        try:
            with transaction.atomic():
                # Refresh job to check current state
                job.refresh_from_db()
                
                # Verify job is still ready to launch
                if not job.is_ready_to_launch:
                    return {
                        'success': False, 
                        'error': f"Job {job.id} no longer ready to launch"
                    }
                
                # Import here to avoid circular imports
                # Note: We'll implement the actual job service integration later
                # For now, this is a placeholder that always succeeds
                result = self._mock_launch_job(job)
                
                if result.get('success', False):
                    # Mark as running
                    job.mark_as_running()
                    logger.info(f"Successfully launched job {job.id}")
                    return {'success': True}
                else:
                    # Launch failed - increment retry count
                    job.retry_count += 1
                    job.save(update_fields=['retry_count'])
                    
                    error_msg = f"Failed to launch job {job.id} (attempt {job.retry_count}): {result.get('error', 'Unknown error')}"
                    logger.warning(error_msg)
                    
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            # Handle unexpected errors
            job.retry_count += 1
            job.save(update_fields=['retry_count'])
            
            error_msg = f"Error launching job {job.id}: {str(e)}"
            logger.exception(error_msg)
            
            return {'success': False, 'error': error_msg}
    
    def _mock_launch_job(self, job):
        """
        Mock job launch for testing purposes.
        
        This will be replaced with actual job service integration.
        """
        # For now, always succeed to test the queue system
        return {'success': True}
    
    def get_queue_stats(self):
        """
        Get queue statistics.
        
        Returns:
            dict: Queue statistics
        """
        from container_manager.models import ContainerJob
        
        stats = {
            'queued': ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F('max_retries')
            ).filter(
                # Exclude jobs scheduled for future
                Q(scheduled_for__isnull=True) | 
                Q(scheduled_for__lte=timezone.now())
            ).count(),
            'scheduled': ContainerJob.objects.filter(
                scheduled_for__isnull=False,
                scheduled_for__gt=timezone.now(),
                launched_at__isnull=True
            ).count(),
            'running': ContainerJob.objects.filter(
                status='running'
            ).count(),
            'launch_failed': ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__gte=F('max_retries')
            ).count()
        }
        
        return stats
    
    def dequeue_job(self, job):
        """
        Remove job from queue.
        
        Args:
            job: ContainerJob instance to remove from queue
        """
        if not job.is_queued:
            raise ValueError(f"Job {job.id} is not queued")
            
        job.queued_at = None
        job.scheduled_for = None
        job.retry_count = 0
        job.save(update_fields=['queued_at', 'scheduled_for', 'retry_count'])
        
        logger.info(f"Removed job {job.id} from queue")
        
    def launch_next_batch(self, max_concurrent=5, timeout=30):
        """
        Launch up to max_concurrent ready jobs.
        
        Args:
            max_concurrent: Maximum number of jobs to launch
            timeout: Timeout in seconds for job acquisition
            
        Returns:
            dict: {'launched': int, 'errors': list}
        """
        from container_manager.models import ContainerJob
        
        launched_count = 0
        errors = []
        
        # Check current resource usage
        running_jobs = ContainerJob.objects.filter(status='running').count()
        available_slots = max(0, max_concurrent - running_jobs)
        
        if available_slots == 0:
            logger.debug(f"No available slots (running: {running_jobs}/{max_concurrent})")
            return {'launched': 0, 'errors': []}
        
        logger.info(f"Attempting to launch up to {available_slots} jobs")
        
        # Get ready jobs
        ready_jobs = self.get_ready_jobs(limit=available_slots)
        
        # Launch jobs
        for job in ready_jobs:
            result = self.launch_job(job)
            if result['success']:
                launched_count += 1
                logger.info(f"Launched job {job.id} ({launched_count}/{available_slots})")
            else:
                errors.append(f"Job {job.id}: {result['error']}")
        
        logger.info(f"Launched {launched_count} jobs from queue")
        return {'launched': launched_count, 'errors': errors}
    
    def launch_job_with_retry(self, job):
        """
        Launch job with sophisticated retry logic.
        
        Args:
            job: ContainerJob instance to launch
            
        Returns:
            dict: {'success': bool, 'error': str, 'retry_scheduled': bool}
        """
        from container_manager.retry import ErrorClassifier, RETRY_STRATEGIES
        
        try:
            with transaction.atomic():
                # Refresh job to check current state
                job.refresh_from_db()
                
                # Verify job is still ready to launch
                if not job.is_ready_to_launch:
                    return {
                        'success': False, 
                        'error': f"Job {job.id} no longer ready to launch",
                        'retry_scheduled': False
                    }
                
                # Get retry strategy for this job
                strategy = self._get_retry_strategy(job)
                
                # Mock job execution for now (will be replaced with actual job service)
                result = self._mock_launch_job_with_failure_simulation(job)
                
                if result.get('success', False):
                    # Launch successful
                    job.mark_as_running()
                    logger.info(f"Successfully launched job {job.id}")
                    return {'success': True, 'retry_scheduled': False}
                else:
                    # Launch failed - handle retry logic
                    return self._handle_launch_failure(job, result.get('error', 'Unknown error'), strategy)
                    
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error launching job {job.id}: {str(e)}"
            logger.exception(error_msg)
            
            strategy = self._get_retry_strategy(job)
            return self._handle_launch_failure(job, error_msg, strategy)
    
    def _handle_launch_failure(self, job, error_message, strategy):
        """
        Handle job launch failure with retry logic.
        
        Args:
            job: Failed ContainerJob
            error_message: Error message from launch attempt
            strategy: RetryStrategy instance
            
        Returns:
            dict: Launch result with retry information
        """
        from container_manager.retry import ErrorClassifier, ErrorType
        
        # Classify the error
        error_type = ErrorClassifier.classify_error(error_message)
        
        # Increment attempt count
        job.retry_count += 1
        
        # Store error information
        job.last_error = error_message
        job.last_error_at = timezone.now()
        
        # Determine if we should retry (use job's max_retries, not strategy's max_attempts)
        should_retry = (job.retry_count < job.max_retries) and strategy.should_retry(job.retry_count, error_type)
        
        if should_retry and error_type != ErrorType.PERMANENT:
            # Schedule retry
            retry_delay = strategy.get_retry_delay(job.retry_count)
            job.scheduled_for = timezone.now() + timedelta(seconds=retry_delay)
            
            # Only transition to retrying if not already in retrying state
            if job.status != 'retrying':
                job.transition_to('retrying', save=False)
            
            job.save(update_fields=[
                'retry_count', 'last_error', 'last_error_at', 
                'scheduled_for', 'status'
            ])
            
            logger.warning(
                f"Job {job.id} failed (attempt {job.retry_count}): {error_message}. "
                f"Retrying in {retry_delay:.1f}s"
            )
            
            return {
                'success': False,
                'error': error_message,
                'retry_scheduled': True,
                'retry_in_seconds': retry_delay
            }
        else:
            # No more retries - mark as permanently failed
            job.transition_to('failed', save=False)
            
            # Remove from queue
            job.queued_at = None
            
            job.save(update_fields=[
                'retry_count', 'last_error', 'last_error_at', 
                'status', 'queued_at'
            ])
            
            reason = "permanent error" if error_type == ErrorType.PERMANENT else "retry limit exceeded"
            logger.error(f"Job {job.id} permanently failed after {job.retry_count} attempts ({reason}): {error_message}")
            
            return {
                'success': False,
                'error': f"Permanently failed: {error_message}",
                'retry_scheduled': False
            }
    
    def _get_retry_strategy(self, job):
        """
        Get retry strategy for a job.
        
        Args:
            job: ContainerJob instance
            
        Returns:
            RetryStrategy: Strategy to use for this job
        """
        from container_manager.retry import RETRY_STRATEGIES
        
        # Check if job specifies a strategy
        strategy_name = getattr(job, 'retry_strategy', None) or 'default'
        
        # Priority-based strategy selection
        if job.priority >= 80:
            strategy_name = 'high_priority'
        elif job.priority <= 20:
            strategy_name = 'conservative'
        
        return RETRY_STRATEGIES.get(strategy_name, RETRY_STRATEGIES['default'])
    
    def _mock_launch_job_with_failure_simulation(self, job):
        """
        Mock job launch with occasional failures for testing retry logic.
        """
        import random
        
        # Simulate different types of failures occasionally
        failure_chance = 0.3  # 30% chance of failure for testing
        
        if random.random() < failure_chance:
            # Simulate different types of errors
            error_types = [
                "Connection refused to Docker daemon",  # Transient
                "Image not found: nonexistent:latest",   # Permanent
                "Network timeout occurred",              # Transient
                "Resource temporarily unavailable",      # Transient
                "Permission denied",                     # Permanent
            ]
            
            error = random.choice(error_types)
            logger.debug(f"Simulating failure for job {job.id}: {error}")
            return {'success': False, 'error': error}
        
        # Success case
        return {'success': True}
    
    def retry_failed_job(self, job, reset_count=False):
        """
        Manually retry a failed job.
        
        Args:
            job: ContainerJob to retry
            reset_count: Reset retry count to 0
            
        Returns:
            bool: True if job was queued for retry
        """
        if job.status not in ['failed', 'retrying']:
            raise ValueError(f"Cannot retry job in status: {job.status}")
        
        # First transition to retrying state if coming from failed
        if job.status == 'failed':
            job.transition_to('retrying', save=True)
            # Refresh to avoid stale state in memory
            job.refresh_from_db()
        
        # Now set the fields and transition to queued
        if reset_count:
            job.retry_count = 0
            
        job.queued_at = timezone.now()
        job.scheduled_for = None  # Retry immediately
        job.last_error = None
        job.last_error_at = None
        
        job.transition_to('queued', save=False)
        job.save(update_fields=[
            'status', 'queued_at', 'scheduled_for', 'retry_count',
            'last_error', 'last_error_at'
        ])
        
        logger.info(f"Manually retrying job {job.id} (retry_count={job.retry_count})")
        return True
    
    def get_failed_jobs(self, include_retrying=False):
        """
        Get jobs that have failed permanently.
        
        Args:
            include_retrying: Include jobs in retry state
            
        Returns:
            QuerySet: Failed jobs
        """
        from container_manager.models import ContainerJob
        
        queryset = ContainerJob.objects.filter(status='failed')
        
        if include_retrying:
            queryset = queryset | ContainerJob.objects.filter(status='retrying')
            
        return queryset.order_by('-last_error_at')
    
    def _acquire_next_job(self, timeout_remaining=30):
        """
        Atomically acquire the next available job.
        
        Args:
            timeout_remaining: Remaining timeout in seconds
            
        Returns:
            ContainerJob: Acquired job or None if none available
        """
        from container_manager.models import ContainerJob
        
        max_attempts = 5
        attempt = 0
        
        while attempt < max_attempts and timeout_remaining > 0:
            attempt += 1
            start_time = time.time()
            
            try:
                with transaction.atomic():
                    # Get the next ready job with row-level lock
                    job = ContainerJob.objects.select_for_update(
                        skip_locked=True  # Skip jobs locked by other processes
                    ).filter(
                        queued_at__isnull=False,
                        launched_at__isnull=True,
                        retry_count__lt=F('max_retries')
                    ).filter(
                        Q(scheduled_for__isnull=True) | 
                        Q(scheduled_for__lte=timezone.now())
                    ).order_by('-priority', 'queued_at').first()
                    
                    if job is None:
                        logger.debug("No jobs available for acquisition")
                        return None
                    
                    # Double-check job is still ready (race condition protection)
                    if not job.is_ready_to_launch:
                        logger.debug(f"Job {job.id} no longer ready, trying next")
                        continue
                    
                    # Job is locked and ready - return it
                    logger.debug(f"Acquired job {job.id} for launching")
                    return job
                    
            except Exception as e:
                elapsed = time.time() - start_time
                timeout_remaining -= elapsed
                
                if "deadlock" in str(e).lower():
                    # Handle deadlock with exponential backoff
                    backoff = min(2 ** attempt * 0.1, 1.0)  # Max 1 second backoff
                    logger.warning(f"Deadlock detected on attempt {attempt}, backing off {backoff:.2f}s")
                    time.sleep(backoff + random.uniform(0, 0.1))  # Add jitter
                else:
                    logger.error(f"Error acquiring job (attempt {attempt}): {e}")
                    if attempt >= max_attempts:
                        raise
        
        logger.debug("Could not acquire job within timeout/attempts")
        return None
    
    def launch_next_batch_atomic(self, max_concurrent=5, timeout=30):
        """
        Launch up to max_concurrent ready jobs atomically.
        
        Args:
            max_concurrent: Maximum concurrent jobs to launch
            timeout: Timeout in seconds for acquiring locks
            
        Returns:
            dict: {'launched': int, 'errors': list}
        """
        from container_manager.models import ContainerJob
        
        launched_count = 0
        errors = []
        
        # Check current resource usage
        running_jobs = ContainerJob.objects.filter(status='running').count()
        available_slots = max(0, max_concurrent - running_jobs)
        
        if available_slots == 0:
            logger.debug(f"No available slots (running: {running_jobs}/{max_concurrent})")
            return {'launched': 0, 'errors': []}
        
        logger.info(f"Attempting to launch up to {available_slots} jobs")
        
        # Get candidate jobs with timeout
        start_time = time.time()
        while launched_count < available_slots and (time.time() - start_time) < timeout:
            job = self._acquire_next_job(timeout_remaining=timeout - (time.time() - start_time))
            
            if job is None:
                break  # No more jobs available
                
            # Attempt to launch the acquired job
            result = self.launch_job(job)
            if result['success']:
                launched_count += 1
                logger.info(f"Launched job {job.id} ({launched_count}/{available_slots})")
            else:
                errors.append(f"Job {job.id}: {result['error']}")
                # Job launch failed, but we did acquire it, so it's handled
        
        return {'launched': launched_count, 'errors': errors}
    
    def get_worker_metrics(self):
        """
        Get metrics for worker coordination.
        
        Returns:
            dict: Worker coordination metrics
        """
        from container_manager.models import ContainerJob
        
        now = timezone.now()
        
        return {
            'queue_depth': ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F('max_retries')
            ).count(),
            'ready_now': ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F('max_retries')
            ).filter(
                Q(scheduled_for__isnull=True) | 
                Q(scheduled_for__lte=now)
            ).count(),
            'scheduled_future': ContainerJob.objects.filter(
                scheduled_for__isnull=False,
                scheduled_for__gt=now,
                launched_at__isnull=True
            ).count(),
            'running': ContainerJob.objects.filter(status='running').count(),
            'launch_failed': ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__gte=F('max_retries')
            ).count()
        }


# Module-level instance for easy importing
queue_manager = JobQueueManager()