# Task: Create JobQueueManager Class with Basic Operations

## Objective
Implement the core `JobQueueManager` class that provides high-level API for queue operations with clean separation of concerns.

## Success Criteria
- [ ] JobQueueManager class created with basic operations
- [ ] Clean API for queue_job(), get_ready_jobs(), launch_job()
- [ ] Proper error handling and logging
- [ ] Integration with ContainerJob state machine
- [ ] Unit tests for all basic operations

## Implementation Details

### JobQueueManager Class Structure

```python
# container_manager/queue.py
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q
import logging

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
            
        if job.status in [job.Status.COMPLETED, job.Status.CANCELLED]:
            raise ValueError(f"Cannot queue {job.status} job {job.id}")
        
        # Set queue fields
        job.queued_at = timezone.now()
        if schedule_for:
            job.scheduled_for = schedule_for
        if priority is not None:
            job.priority = priority
            
        # Transition to queued status
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
                from container_manager.services import job_service
                
                # Attempt to launch
                result = job_service.launch_job(job)
                
                if result.success:
                    # Mark as running
                    job.mark_as_running()
                    logger.info(f"Successfully launched job {job.id}")
                    return {'success': True}
                else:
                    # Launch failed - increment retry count
                    job.retry_count += 1
                    job.save(update_fields=['retry_count'])
                    
                    error_msg = f"Failed to launch job {job.id} (attempt {job.retry_count}): {result.error}"
                    logger.warning(error_msg)
                    
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            # Handle unexpected errors
            job.retry_count += 1
            job.save(update_fields=['retry_count'])
            
            error_msg = f"Error launching job {job.id}: {str(e)}"
            logger.exception(error_msg)
            
            return {'success': False, 'error': error_msg}
    
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


# Module-level instance for easy importing
queue_manager = JobQueueManager()
```

### Error Handling Classes

```python
# container_manager/exceptions.py (or add to existing exceptions file)

class QueueError(Exception):
    """Base exception for queue operations"""
    pass

class JobNotQueuedError(QueueError):
    """Raised when trying to operate on non-queued job"""
    pass

class JobAlreadyQueuedError(QueueError):
    """Raised when trying to queue already queued job"""
    pass

class QueueCapacityError(QueueError):
    """Raised when queue is at capacity"""
    pass
```

## Files to Create/Modify
- `container_manager/queue.py` - New file with JobQueueManager
- `container_manager/exceptions.py` - Add queue-related exceptions (or modify existing)
- `container_manager/__init__.py` - Export queue_manager for easy imports

## Testing Requirements
- [ ] Test queue_job() with valid jobs
- [ ] Test queue_job() with invalid jobs (already queued, completed, etc.)
- [ ] Test get_ready_jobs() returns correct jobs in priority order
- [ ] Test get_ready_jobs() respects scheduling times
- [ ] Test launch_job() with successful launches
- [ ] Test launch_job() with failed launches and retry logic
- [ ] Test get_queue_stats() returns accurate counts
- [ ] Test dequeue_job() removes jobs properly

## Dependencies
- Depends on: `01-queue-model-fields.md` (needs queue fields)
- Depends on: `02-state-machine-validation.md` (needs state machine methods)

## Usage Examples

```python
from container_manager.queue import queue_manager
from container_manager.models import ContainerJob

# Queue a job immediately
job = ContainerJob.objects.create(command="echo hello")
queue_manager.queue_job(job)

# Queue a job for later
job = ContainerJob.objects.create(command="echo scheduled")
queue_manager.queue_job(job, schedule_for=timezone.now() + timedelta(hours=1))

# Get ready jobs
ready_jobs = queue_manager.get_ready_jobs(limit=5)

# Launch a job
for job in ready_jobs:
    result = queue_manager.launch_job(job)
    if result['success']:
        print(f"Launched job {job.id}")
    else:
        print(f"Failed: {result['error']}")
```

## Notes
- Clean separation between queue management and job execution
- Proper error handling with meaningful messages
- Logging for operational visibility
- Atomic operations prevent race conditions
- Priority-based ordering with FIFO fallback
- Module-level instance for convenient access