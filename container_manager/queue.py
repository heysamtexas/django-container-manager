"""
Queue management system for django-container-manager.

This module provides high-level API for job queue operations including
job queuing, priority-based processing, and queue statistics.
"""

import logging
import random
import time
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

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

        if job.status in ["completed", "cancelled"]:
            raise ValueError(f"Cannot queue {job.status} job {job.id}")

        # Set priority if provided
        if priority is not None:
            job.priority = priority
            job.save(update_fields=["priority"])

        # Queue the job using the model's helper method
        job.mark_as_queued(scheduled_for=schedule_for)

        logger.info(
            f"Queued job {job.id} for execution"
            + (f" at {schedule_for}" if schedule_for else "")
        )
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

        queryset = (
            ContainerJob.objects.filter(
                # Must be queued but not yet launched
                queued_at__isnull=False,
                launched_at__isnull=True,
                # Must not have exceeded retry limit
                retry_count__lt=F("max_retries"),
            )
            .filter(
                # Either not scheduled or scheduled time has passed
                Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now())
            )
            .order_by(
                # Order by priority (descending), then FIFO
                "-priority",
                "queued_at",
            )
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
                        "success": False,
                        "error": f"Job {job.id} no longer ready to launch",
                    }

                # Use the actual job service to launch the job
                from container_manager.services import launch_job

                result = launch_job(job)

                if result.get("success", False):
                    # Job service has already handled status transitions and execution_id
                    # No need to call mark_as_running() again since executor already did it
                    logger.info(f"Successfully launched job {job.id}")
                    return {"success": True}
                else:
                    # Launch failed - increment retry count
                    job.retry_count += 1
                    job.save(update_fields=["retry_count"])

                    error_msg = f"Failed to launch job {job.id} (attempt {job.retry_count}): {result.get('error', 'Unknown error')}"
                    logger.warning(error_msg)

                    return {"success": False, "error": error_msg}

        except Exception as e:
            # Handle unexpected errors
            job.retry_count += 1
            job.save(update_fields=["retry_count"])

            error_msg = f"Error launching job {job.id}: {e!s}"
            logger.exception(error_msg)

            return {"success": False, "error": error_msg}

    # Removed _mock_launch_job - now using actual job service integration

    def get_queue_stats(self):
        """
        Get queue statistics.

        Returns:
            dict: Queue statistics
        """
        from container_manager.models import ContainerJob

        stats = {
            "queued": ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F("max_retries"),
            )
            .filter(
                # Exclude jobs scheduled for future
                Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now())
            )
            .count(),
            "scheduled": ContainerJob.objects.filter(
                scheduled_for__isnull=False,
                scheduled_for__gt=timezone.now(),
                launched_at__isnull=True,
            ).count(),
            "running": ContainerJob.objects.filter(status="running").count(),
            "launch_failed": ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__gte=F("max_retries"),
            ).count(),
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
        job.save(update_fields=["queued_at", "scheduled_for", "retry_count"])

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
        running_jobs = ContainerJob.objects.filter(status="running").count()
        available_slots = max(0, max_concurrent - running_jobs)

        if available_slots == 0:
            logger.debug(
                f"No available slots (running: {running_jobs}/{max_concurrent})"
            )
            return {"launched": 0, "errors": []}

        logger.info(f"Attempting to launch up to {available_slots} jobs")

        # Get ready jobs
        ready_jobs = self.get_ready_jobs(limit=available_slots)

        # Launch jobs
        for job in ready_jobs:
            result = self.launch_job(job)
            if result["success"]:
                launched_count += 1
                logger.info(
                    f"Launched job {job.id} ({launched_count}/{available_slots})"
                )
            else:
                errors.append(f"Job {job.id}: {result['error']}")

        logger.info(f"Launched {launched_count} jobs from queue")
        return {"launched": launched_count, "errors": errors}

    def launch_job_with_retry(self, job):
        """
        Launch job with sophisticated retry logic.

        Args:
            job: ContainerJob instance to launch

        Returns:
            dict: {'success': bool, 'error': str, 'retry_scheduled': bool}
        """

        try:
            with transaction.atomic():
                # Refresh job to check current state
                job.refresh_from_db()

                # Verify job is still ready to launch
                if not job.is_ready_to_launch:
                    return {
                        "success": False,
                        "error": f"Job {job.id} no longer ready to launch",
                        "retry_scheduled": False,
                    }

                # Get retry strategy for this job
                strategy = self._get_retry_strategy(job)

                # Use the actual job service to launch the job
                from container_manager.services import launch_job

                result = launch_job(job)

                if result.get("success", False):
                    # Launch successful - job service has already handled status and execution_id
                    logger.info(f"Successfully launched job {job.id}")
                    return {"success": True, "retry_scheduled": False}
                else:
                    # Launch failed - handle retry logic
                    return self._handle_launch_failure(
                        job, result.get("error", "Unknown error"), strategy
                    )

        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error launching job {job.id}: {e!s}"
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
        should_retry = (job.retry_count < job.max_retries) and strategy.should_retry(
            job.retry_count, error_type
        )

        if should_retry and error_type != ErrorType.PERMANENT:
            # Schedule retry
            retry_delay = strategy.get_retry_delay(job.retry_count)
            job.scheduled_for = timezone.now() + timedelta(seconds=retry_delay)

            # Only transition to retrying if not already in retrying state
            if job.status != "retrying":
                job.transition_to("retrying", save=False)

            job.save(
                update_fields=[
                    "retry_count",
                    "last_error",
                    "last_error_at",
                    "scheduled_for",
                    "status",
                ]
            )

            logger.warning(
                f"Job {job.id} failed (attempt {job.retry_count}): {error_message}. "
                f"Retrying in {retry_delay:.1f}s"
            )

            return {
                "success": False,
                "error": error_message,
                "retry_scheduled": True,
                "retry_in_seconds": retry_delay,
            }
        else:
            # No more retries - mark as permanently failed
            job.transition_to("failed", save=False)

            # Remove from queue
            job.queued_at = None

            job.save(
                update_fields=[
                    "retry_count",
                    "last_error",
                    "last_error_at",
                    "status",
                    "queued_at",
                ]
            )

            reason = (
                "permanent error"
                if error_type == ErrorType.PERMANENT
                else "retry limit exceeded"
            )
            logger.error(
                f"Job {job.id} permanently failed after {job.retry_count} attempts ({reason}): {error_message}"
            )

            return {
                "success": False,
                "error": f"Permanently failed: {error_message}",
                "retry_scheduled": False,
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
        strategy_name = getattr(job, "retry_strategy", None) or "default"

        # Priority-based strategy selection
        if job.priority >= 80:
            strategy_name = "high_priority"
        elif job.priority <= 20:
            strategy_name = "conservative"

        return RETRY_STRATEGIES.get(strategy_name, RETRY_STRATEGIES["default"])

    # Removed _mock_launch_job_with_failure_simulation - now using actual job service integration

    def retry_failed_job(self, job, reset_count=False):
        """
        Manually retry a failed job.

        Args:
            job: ContainerJob to retry
            reset_count: Reset retry count to 0

        Returns:
            bool: True if job was queued for retry
        """
        if job.status not in ["failed", "retrying"]:
            raise ValueError(f"Cannot retry job in status: {job.status}")

        # First transition to retrying state if coming from failed
        if job.status == "failed":
            job.transition_to("retrying", save=True)
            # Refresh to avoid stale state in memory
            job.refresh_from_db()

        # Now set the fields and transition to queued
        if reset_count:
            job.retry_count = 0

        job.queued_at = timezone.now()
        job.scheduled_for = None  # Retry immediately
        job.last_error = None
        job.last_error_at = None

        job.transition_to("queued", save=False)
        job.save(
            update_fields=[
                "status",
                "queued_at",
                "scheduled_for",
                "retry_count",
                "last_error",
                "last_error_at",
            ]
        )

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

        queryset = ContainerJob.objects.filter(status="failed")

        if include_retrying:
            queryset = queryset | ContainerJob.objects.filter(status="retrying")

        return queryset.order_by("-last_error_at")

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
                    job = (
                        ContainerJob.objects.select_for_update(
                            skip_locked=True  # Skip jobs locked by other processes
                        )
                        .filter(
                            queued_at__isnull=False,
                            launched_at__isnull=True,
                            retry_count__lt=F("max_retries"),
                        )
                        .filter(
                            Q(scheduled_for__isnull=True)
                            | Q(scheduled_for__lte=timezone.now())
                        )
                        .order_by("-priority", "queued_at")
                        .first()
                    )

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
                    backoff = min(2**attempt * 0.1, 1.0)  # Max 1 second backoff
                    logger.warning(
                        f"Deadlock detected on attempt {attempt}, backing off {backoff:.2f}s"
                    )
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
        running_jobs = ContainerJob.objects.filter(status="running").count()
        available_slots = max(0, max_concurrent - running_jobs)

        if available_slots == 0:
            logger.debug(
                f"No available slots (running: {running_jobs}/{max_concurrent})"
            )
            return {"launched": 0, "errors": []}

        logger.info(f"Attempting to launch up to {available_slots} jobs")

        # Get candidate jobs with timeout
        start_time = time.time()
        while launched_count < available_slots and (time.time() - start_time) < timeout:
            job = self._acquire_next_job(
                timeout_remaining=timeout - (time.time() - start_time)
            )

            if job is None:
                break  # No more jobs available

            # Attempt to launch the acquired job
            result = self.launch_job(job)
            if result["success"]:
                launched_count += 1
                logger.info(
                    f"Launched job {job.id} ({launched_count}/{available_slots})"
                )
            else:
                errors.append(f"Job {job.id}: {result['error']}")
                # Job launch failed, but we did acquire it, so it's handled

        return {"launched": launched_count, "errors": errors}

    def get_worker_metrics(self):
        """
        Get metrics for worker coordination.

        Returns:
            dict: Worker coordination metrics
        """
        from container_manager.models import ContainerJob

        now = timezone.now()

        return {
            "queue_depth": ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F("max_retries"),
            ).count(),
            "ready_now": ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F("max_retries"),
            )
            .filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now))
            .count(),
            "scheduled_future": ContainerJob.objects.filter(
                scheduled_for__isnull=False,
                scheduled_for__gt=now,
                launched_at__isnull=True,
            ).count(),
            "running": ContainerJob.objects.filter(status="running").count(),
            "launch_failed": ContainerJob.objects.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__gte=F("max_retries"),
            ).count(),
        }

    def process_queue_continuous(
        self, max_concurrent=5, poll_interval=10, shutdown_event=None
    ):
        """
        Process queue continuously until shutdown event is set.

        Args:
            max_concurrent: Maximum concurrent jobs to launch
            poll_interval: Polling interval in seconds
            shutdown_event: Threading event to signal shutdown

        Returns:
            dict: Processing statistics
        """
        import time

        stats = {"iterations": 0, "jobs_launched": 0, "errors": []}

        logger.info(
            f"Starting continuous queue processing (max_concurrent={max_concurrent}, poll_interval={poll_interval})"
        )

        try:
            while not (shutdown_event and shutdown_event.is_set()):
                try:
                    # Process one batch
                    result = self.launch_next_batch(max_concurrent=max_concurrent)

                    stats["iterations"] += 1
                    stats["jobs_launched"] += result["launched"]

                    if result["errors"]:
                        stats["errors"].extend(result["errors"])

                    # Log progress if jobs were launched
                    if result["launched"] > 0:
                        logger.info(
                            f"Launched {result['launched']} jobs (iteration {stats['iterations']})"
                        )

                    # Check shutdown before sleeping
                    if shutdown_event and shutdown_event.is_set():
                        break

                    # Sleep with interrupt checking
                    for _ in range(poll_interval):
                        if shutdown_event and shutdown_event.is_set():
                            break
                        time.sleep(1)

                except Exception as e:
                    error_msg = f"Error in queue processing iteration {stats['iterations']}: {e!s}"
                    logger.exception(error_msg)
                    stats["errors"].append(error_msg)

                    # Sleep longer after errors
                    for _ in range(poll_interval * 2):
                        if shutdown_event and shutdown_event.is_set():
                            break
                        time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Queue processing interrupted by keyboard")

        logger.info(
            f"Queue processing stopped after {stats['iterations']} iterations, launched {stats['jobs_launched']} jobs"
        )
        return stats

    def process_queue_with_graceful_shutdown(
        self, max_concurrent=5, poll_interval=10, shutdown_timeout=30
    ):
        """
        Process queue with comprehensive graceful shutdown handling.

        Args:
            max_concurrent: Maximum concurrent jobs
            poll_interval: Seconds between queue checks
            shutdown_timeout: Timeout for graceful shutdown

        Returns:
            dict: Processing statistics
        """
        from container_manager.signals import GracefulShutdown, JobCompletionTracker

        # Initialize shutdown handler and job tracker
        shutdown_handler = GracefulShutdown(timeout=shutdown_timeout)
        job_tracker = JobCompletionTracker()

        # Set up signal handlers with status callback
        def status_callback():
            metrics = self.get_worker_metrics()
            tracking_stats = job_tracker.get_stats()
            logger.info(f"Queue metrics: {metrics}, Job tracking: {tracking_stats}")
            print(f"Status: Queue={metrics}, Jobs={tracking_stats}")  # For operators

        shutdown_handler.setup_signal_handlers(status_callback)

        logger.info(
            f"Starting graceful queue processor (max_concurrent={max_concurrent}, shutdown_timeout={shutdown_timeout}s)"
        )

        stats = {
            "iterations": 0,
            "jobs_launched": 0,
            "jobs_completed": 0,
            "errors": [],
            "shutdown_time": None,
            "clean_shutdown": False,
            "jobs_interrupted": 0,
        }

        try:
            while not shutdown_handler.is_shutdown_requested():
                stats["iterations"] += 1

                try:
                    # Launch ready jobs with tracking
                    result = self._launch_batch_with_tracking(
                        max_concurrent=max_concurrent, job_tracker=job_tracker
                    )

                    stats["jobs_launched"] += result["launched"]
                    if result["errors"]:
                        stats["errors"].extend(result["errors"])

                    # Log activity
                    if result["launched"] > 0 or result["errors"]:
                        logger.info(
                            f"Iteration {stats['iterations']}: "
                            f"launched {result['launched']}, "
                            f"errors {len(result['errors'])}, "
                            f"running {job_tracker.get_running_count()}"
                        )

                except Exception as e:
                    error_msg = f"Error in iteration {stats['iterations']}: {e!s}"
                    logger.exception(error_msg)
                    stats["errors"].append(error_msg)

                # Wait with early shutdown detection
                shutdown_handler.wait_for_shutdown(poll_interval)

            # Shutdown requested - enter graceful shutdown phase
            stats["shutdown_time"] = timezone.now()
            logger.info("Graceful shutdown initiated")

            # Stop launching new jobs, wait for running jobs to complete
            running_count = job_tracker.get_running_count()
            if running_count > 0:
                logger.info(
                    f"Waiting for {running_count} running jobs to complete (timeout: {shutdown_timeout}s)..."
                )

                completed = job_tracker.wait_for_completion(
                    timeout=shutdown_timeout, poll_interval=1
                )

                if completed:
                    logger.info("All jobs completed successfully during shutdown")
                    stats["clean_shutdown"] = True
                else:
                    running_jobs = job_tracker.get_running_jobs()
                    logger.warning(
                        f"Forced shutdown with {len(running_jobs)} jobs still running: {running_jobs}"
                    )
                    stats["jobs_interrupted"] = len(running_jobs)
            else:
                logger.info("No running jobs, clean shutdown")
                stats["clean_shutdown"] = True

        except KeyboardInterrupt:
            logger.info("Queue processing interrupted by keyboard")
            stats["shutdown_time"] = timezone.now()
        except Exception as e:
            logger.exception(f"Fatal error in graceful queue processing: {e}")
            stats["errors"].append(f"Fatal error: {e!s}")

        finally:
            # Final cleanup and logging
            final_tracking_stats = job_tracker.get_stats()
            logger.info(
                f"Queue processor finished. Stats: {stats}, Job tracking: {final_tracking_stats}"
            )

        return stats

    def _launch_batch_with_tracking(self, max_concurrent, job_tracker):
        """
        Launch jobs with completion tracking.

        Args:
            max_concurrent: Maximum concurrent jobs
            job_tracker: JobCompletionTracker instance

        Returns:
            dict: Launch results
        """

        # Check available slots (account for jobs we're tracking)
        running_count = job_tracker.get_running_count()
        available_slots = max(0, max_concurrent - running_count)

        if available_slots == 0:
            return {"launched": 0, "errors": []}

        # Get ready jobs
        ready_jobs = self.get_ready_jobs(limit=available_slots)

        launched_count = 0
        errors = []

        for job in ready_jobs:
            try:
                # Add to tracker before launching
                job_tracker.add_running_job(job.id)

                # Use existing launch method with retry logic
                result = self.launch_job_with_retry(job)

                if result["success"]:
                    launched_count += 1
                    logger.debug(f"Launched job {job.id} successfully")

                    # Start monitoring for completion in background
                    self._monitor_job_completion_background(job, job_tracker)
                else:
                    # Launch failed, remove from tracker
                    job_tracker.mark_job_completed(job.id)
                    error_msg = f"Job {job.id}: {result['error']}"
                    errors.append(error_msg)
                    logger.warning(error_msg)

            except Exception as e:
                # Launch error, remove from tracker
                job_tracker.mark_job_completed(job.id)
                error_msg = f"Job {job.id}: {e!s}"
                errors.append(error_msg)
                logger.exception(f"Error launching job {job.id}")

        return {"launched": launched_count, "errors": errors}

    def _monitor_job_completion_background(self, job, job_tracker):
        """
        Monitor job completion in background thread.

        Args:
            job: ContainerJob instance
            job_tracker: JobCompletionTracker instance
        """

        def monitor():
            try:
                logger.debug(f"Starting background monitoring for job {job.id}")

                # Poll job status until completion
                max_checks = 1200  # 5 seconds * 1200 = 1 hour max
                check_count = 0

                while check_count < max_checks:
                    time.sleep(5)  # Check every 5 seconds
                    check_count += 1

                    try:
                        job.refresh_from_db()

                        if job.status in [
                            "completed",
                            "failed",
                            "cancelled",
                            "timeout",
                        ]:
                            job_tracker.mark_job_completed(job.id)
                            logger.debug(
                                f"Job {job.id} completed with status: {job.status}"
                            )
                            return

                    except Exception as e:
                        logger.error(f"Error refreshing job {job.id} status: {e}")
                        # Continue monitoring, might be temporary DB issue

                # If we get here, job has been running too long
                logger.warning(
                    f"Job {job.id} monitoring timeout after {max_checks} checks, assuming completed"
                )
                job_tracker.mark_job_completed(job.id)

            except Exception as e:
                logger.error(f"Error in background monitoring for job {job.id}: {e}")
                # Mark as completed to prevent hanging
                job_tracker.mark_job_completed(job.id)

        # Start monitoring thread
        import threading

        monitor_thread = threading.Thread(
            target=monitor, daemon=True, name=f"JobMonitor-{job.id}"
        )
        monitor_thread.start()
        logger.debug(f"Started background monitoring thread for job {job.id}")


# Module-level instance for easy importing
queue_manager = JobQueueManager()
