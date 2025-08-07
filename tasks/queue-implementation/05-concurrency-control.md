# Task: Implement Concurrency Control and Atomic Job Acquisition

## Objective
Add robust concurrency control to JobQueueManager to handle multiple workers safely acquiring jobs without race conditions or duplicate processing.

## Success Criteria
- [ ] Atomic job acquisition using database locks
- [ ] Race condition prevention for multiple workers
- [ ] Deadlock detection and recovery
- [ ] Slot-based concurrency limits
- [ ] Comprehensive concurrency tests pass

## Implementation Details

### Enhanced JobQueueManager with Concurrency Control

```python
# container_manager/queue.py (additions to existing class)

from django.db import transaction
from django.db.models import F
import logging
import time
import random

logger = logging.getLogger(__name__)

class JobQueueManager:
    # ... existing methods ...
    
    def launch_next_batch(self, max_concurrent=5, timeout=30):
        """
        Launch up to max_concurrent ready jobs atomically.
        
        Args:
            max_concurrent: Maximum number of jobs to launch
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
                        models.Q(scheduled_for__isnull=True) | 
                        models.Q(scheduled_for__lte=timezone.now())
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
    
    def process_queue_continuous(self, max_concurrent=5, poll_interval=10, shutdown_event=None):
        """
        Continuously process job queue.
        
        Args:
            max_concurrent: Maximum concurrent jobs
            poll_interval: Seconds between queue checks
            shutdown_event: threading.Event to signal shutdown
            
        Returns:
            dict: Processing statistics
        """
        import signal
        import threading
        
        logger.info(f"Starting continuous queue processor (max_concurrent={max_concurrent})")
        
        stats = {
            'iterations': 0,
            'jobs_launched': 0,
            'errors': []
        }
        
        # Create shutdown event if not provided
        if shutdown_event is None:
            shutdown_event = threading.Event()
            
            # Set up signal handlers
            def signal_handler(sig, frame):
                logger.info(f"Received signal {sig}, shutting down gracefully")
                shutdown_event.set()
                
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        
        while not shutdown_event.is_set():
            try:
                stats['iterations'] += 1
                
                # Launch ready jobs
                result = self.launch_next_batch(max_concurrent=max_concurrent)
                
                stats['jobs_launched'] += result['launched']
                stats['errors'].extend(result['errors'])
                
                # Log activity
                if result['launched'] > 0:
                    logger.info(f"Iteration {stats['iterations']}: launched {result['launched']} jobs")
                elif result['errors']:
                    logger.warning(f"Iteration {stats['iterations']}: {len(result['errors'])} errors")
                
                # Wait before next iteration (with early exit on shutdown)
                shutdown_event.wait(poll_interval)
                
            except Exception as e:
                logger.exception(f"Error in queue processing iteration {stats['iterations']}: {e}")
                stats['errors'].append(f"Iteration {stats['iterations']}: {str(e)}")
                
                # Wait before retrying (with early exit on shutdown)
                shutdown_event.wait(min(poll_interval, 5))  # Max 5s error backoff
        
        logger.info(f"Queue processor stopped. Stats: {stats}")
        return stats
    
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
                models.Q(scheduled_for__isnull=True) | 
                models.Q(scheduled_for__lte=now)
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
```

### Database Lock Configuration

```python
# container_manager/settings.py (or add to project settings)

# Database configuration for optimal locking
DATABASES = {
    'default': {
        # ... existing config ...
        'OPTIONS': {
            # PostgreSQL-specific optimizations
            'isolation_level': psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED,
            'options': '-c lock_timeout=10s',  # Prevent indefinite lock waits
        }
    }
}
```

## Files to Modify
- `container_manager/queue.py` - Add concurrency control methods
- Project settings - Add database lock configuration

## Testing Requirements
- [ ] Test single worker can acquire and launch jobs
- [ ] Test multiple workers don't acquire same job
- [ ] Test skip_locked prevents blocking
- [ ] Test deadlock recovery with exponential backoff
- [ ] Test graceful shutdown with signal handling
- [ ] Test worker metrics accuracy
- [ ] Load test with multiple concurrent workers

### Critical Concurrency Tests

```python
# tests/test_queue_concurrency.py
import threading
import time
from django.test import TestCase
from container_manager.queue import queue_manager

class QueueConcurrencyTestCase(TestCase):
    
    def test_multiple_workers_no_duplicate_acquisition(self):
        """Test multiple workers don't acquire the same job"""
        # Create 10 jobs
        jobs = [self.create_test_job() for _ in range(10)]
        for job in jobs:
            queue_manager.queue_job(job)
        
        # Launch 5 workers to acquire jobs
        acquired_jobs = []
        errors = []
        
        def worker():
            try:
                job = queue_manager._acquire_next_job(timeout_remaining=5)
                if job:
                    acquired_jobs.append(job.id)
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Assert no duplicates and no errors
        self.assertEqual(len(acquired_jobs), len(set(acquired_jobs)), "Duplicate job acquisition detected")
        self.assertEqual(len(errors), 0, f"Errors during acquisition: {errors}")
        self.assertLessEqual(len(acquired_jobs), 10, "More jobs acquired than available")
    
    def test_concurrent_launch_batch(self):
        """Test concurrent launch_next_batch calls"""
        # Create 20 jobs
        jobs = [self.create_test_job() for _ in range(20)]
        for job in jobs:
            queue_manager.queue_job(job)
        
        results = []
        
        def worker():
            result = queue_manager.launch_next_batch(max_concurrent=5)
            results.append(result)
        
        # Launch 3 workers concurrently
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify total launched doesn't exceed max_concurrent
        total_launched = sum(r['launched'] for r in results)
        self.assertLessEqual(total_launched, 5, f"Launched {total_launched} > max_concurrent=5")
```

## Dependencies
- Depends on: `04-queue-manager-basic.md` (basic queue manager implementation)
- Requires: Database with proper locking support (PostgreSQL recommended)

## Performance Considerations

1. **skip_locked Parameter**: Prevents workers from blocking on locked rows
2. **Row-Level Locking**: Only locks specific jobs, not entire table
3. **Deadlock Recovery**: Exponential backoff prevents thundering herd
4. **Timeout Handling**: Prevents infinite waiting for locks
5. **Batch Processing**: Reduces transaction overhead

## Notes
- Uses `select_for_update(skip_locked=True)` for non-blocking acquisition
- Implements exponential backoff for deadlock recovery
- Provides graceful shutdown with signal handling
- Includes comprehensive metrics for monitoring
- Handles edge cases like job state changes during acquisition