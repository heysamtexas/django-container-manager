# Task: Concurrency and Multi-Worker Tests

## Objective
Comprehensive test suite for concurrent queue operations, multi-worker scenarios, and race condition prevention.

## Success Criteria
- [ ] Test multiple workers don't acquire same job
- [ ] Test atomic job acquisition works correctly
- [ ] Test deadlock detection and recovery
- [ ] Test graceful shutdown with running jobs
- [ ] Test worker coordination and metrics
- [ ] Test performance under concurrent load
- [ ] All concurrency tests pass consistently

## Implementation Details

### Core Concurrency Tests

```python
# tests/test_concurrency.py
from django.test import TransactionTestCase
from django.utils import timezone
from django.db import transaction
from container_manager.models import ContainerJob
from container_manager.queue import queue_manager
import threading
import time
import random
from unittest.mock import patch, MagicMock

class JobAcquisitionTestCase(TransactionTestCase):
    """Test atomic job acquisition and race condition prevention"""
    
    def setUp(self):
        self.jobs = []
        for i in range(10):
            job = ContainerJob.objects.create(
                name=f"test-job-{i}",
                command=f"echo job-{i}",
                docker_image="python:3.9"
            )
            queue_manager.queue_job(job)
            self.jobs.append(job)
    
    def test_multiple_workers_no_duplicate_acquisition(self):
        """Test multiple workers don't acquire the same job"""
        acquired_jobs = []
        acquisition_errors = []
        lock = threading.Lock()
        
        def worker_acquire_job(worker_id):
            """Simulate worker acquiring next job"""
            try:
                job = queue_manager._acquire_next_job(timeout_remaining=5)
                with lock:
                    if job:
                        acquired_jobs.append((worker_id, job.id))
                    else:
                        acquired_jobs.append((worker_id, None))
            except Exception as e:
                with lock:
                    acquisition_errors.append((worker_id, str(e)))
        
        # Launch 5 workers to compete for jobs
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=worker_acquire_job, args=(worker_id,))
            threads.append(thread)
        
        # Start all workers simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        self.assertEqual(len(acquisition_errors), 0, f"Acquisition errors: {acquisition_errors}")
        
        # Verify no duplicate acquisitions
        job_ids = [job_id for worker_id, job_id in acquired_jobs if job_id is not None]
        self.assertEqual(len(job_ids), len(set(job_ids)), "Duplicate job acquisition detected")
        
        # Verify all acquired jobs are unique
        self.assertLessEqual(len(job_ids), len(self.jobs), "More jobs acquired than available")
    
    def test_concurrent_launch_batch_operations(self):
        """Test concurrent launch_next_batch calls don't over-allocate"""
        results = []
        errors = []
        lock = threading.Lock()
        
        def worker_launch_batch():
            """Simulate worker launching batch of jobs"""
            try:
                result = queue_manager.launch_next_batch(max_concurrent=3, timeout=10)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(str(e))
        
        # Mock job launching to always succeed quickly
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=True)
            
            # Launch 4 workers concurrently
            threads = []
            for _ in range(4):
                thread = threading.Thread(target=worker_launch_batch)
                threads.append(thread)
            
            for thread in threads:
                thread.start()
            
            for thread in threads:
                thread.join()
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"Launch errors: {errors}")
        
        # Verify total launched doesn't exceed max_concurrent
        total_launched = sum(result['launched'] for result in results)
        self.assertLessEqual(total_launched, 3, f"Over-allocated: launched {total_launched} > max 3")
        
        # Verify at least some jobs were launched
        self.assertGreater(total_launched, 0, "No jobs were launched")
    
    def test_job_acquisition_with_skip_locked(self):
        """Test skip_locked prevents blocking on locked jobs"""
        acquisition_times = []
        lock = threading.Lock()
        
        def worker_with_delay(delay_seconds):
            """Worker that holds job lock for specified time"""
            start_time = time.time()
            
            try:
                with transaction.atomic():
                    # Acquire job with lock
                    job = ContainerJob.objects.select_for_update().filter(
                        queued_at__isnull=False,
                        launched_at__isnull=True
                    ).first()
                    
                    if job:
                        # Hold the lock for delay_seconds
                        time.sleep(delay_seconds)
                        job.launched_at = timezone.now()
                        job.save()
                    
                    end_time = time.time()
                    with lock:
                        acquisition_times.append(end_time - start_time)
            except Exception as e:
                with lock:
                    acquisition_times.append(f"Error: {e}")
        
        def worker_with_skip_locked():
            """Worker using skip_locked for non-blocking acquisition"""
            start_time = time.time()
            
            try:
                job = queue_manager._acquire_next_job(timeout_remaining=2)
                end_time = time.time()
                
                with lock:
                    acquisition_times.append(end_time - start_time)
            except Exception as e:
                with lock:
                    acquisition_times.append(f"Error: {e}")
        
        # Start worker that will hold lock for 3 seconds
        blocking_thread = threading.Thread(target=worker_with_delay, args=(3,))
        blocking_thread.start()
        
        # Give it time to acquire lock
        time.sleep(0.5)
        
        # Start non-blocking worker
        non_blocking_thread = threading.Thread(target=worker_with_skip_locked)
        non_blocking_thread.start()
        
        # Wait for completion
        blocking_thread.join()
        non_blocking_thread.join()
        
        # Verify skip_locked worker completed quickly (within 2.5 seconds)
        self.assertEqual(len(acquisition_times), 2)
        non_blocking_time = acquisition_times[1]
        
        if isinstance(non_blocking_time, float):
            self.assertLess(non_blocking_time, 2.5, "skip_locked didn't prevent blocking")

class DeadlockRecoveryTestCase(TransactionTestCase):
    """Test deadlock detection and recovery"""
    
    def test_deadlock_recovery_with_backoff(self):
        """Test deadlock recovery with exponential backoff"""
        # This test simulates deadlock conditions
        deadlock_count = 0
        recovery_count = 0
        lock = threading.Lock()
        
        def simulate_deadlock_worker():
            nonlocal deadlock_count, recovery_count
            
            for attempt in range(3):  # Max 3 attempts
                try:
                    with transaction.atomic():
                        # Try to acquire multiple jobs in different order to force deadlock
                        jobs = list(ContainerJob.objects.select_for_update().filter(
                            queued_at__isnull=False
                        )[:2])
                        
                        if len(jobs) >= 2:
                            # Simulate some processing time
                            time.sleep(random.uniform(0.1, 0.3))
                            
                            for job in jobs:
                                job.launched_at = timezone.now()
                                job.save()
                        
                        # If we get here, no deadlock occurred
                        with lock:
                            recovery_count += 1
                        break
                        
                except Exception as e:
                    if "deadlock" in str(e).lower():
                        with lock:
                            deadlock_count += 1
                        
                        # Exponential backoff
                        backoff = 0.1 * (2 ** attempt)
                        time.sleep(backoff + random.uniform(0, 0.1))
                    else:
                        # Other error, don't retry
                        break
        
        # Create jobs for deadlock testing
        for i in range(6):
            job = ContainerJob.objects.create(
                name=f"deadlock-test-{i}",
                command=f"echo deadlock-{i}"
            )
            queue_manager.queue_job(job)
        
        # Launch multiple workers that might deadlock
        threads = []
        for _ in range(4):
            thread = threading.Thread(target=simulate_deadlock_worker)
            threads.append(thread)
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # We expect some deadlocks might occur, but recovery should happen
        self.assertGreaterEqual(recovery_count, 1, "No successful recoveries")
        
        # If deadlocks occurred, verify they were handled
        if deadlock_count > 0:
            self.assertGreater(recovery_count, 0, "Deadlocks occurred but no recoveries")

class WorkerCoordinationTestCase(TransactionTestCase):
    """Test multi-worker coordination and metrics"""
    
    def setUp(self):
        # Create a mix of jobs
        for i in range(20):
            job = ContainerJob.objects.create(
                name=f"worker-coord-{i}",
                command=f"echo coordination-{i}",
                priority=random.choice([20, 50, 80])  # Mix of priorities
            )
            queue_manager.queue_job(job)
    
    def test_worker_metrics_accuracy(self):
        """Test worker metrics reflect accurate queue state"""
        # Get initial metrics
        metrics = queue_manager.get_worker_metrics()
        
        self.assertEqual(metrics['queue_depth'], 20)
        self.assertEqual(metrics['ready_now'], 20)
        self.assertEqual(metrics['running'], 0)
        
        # Launch some jobs
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=True)
            
            result = queue_manager.launch_next_batch(max_concurrent=5)
            
            # Verify metrics update
            updated_metrics = queue_manager.get_worker_metrics()
            
            self.assertEqual(updated_metrics['queue_depth'], 15)  # 20 - 5 launched
            self.assertEqual(result['launched'], 5)
    
    def test_multiple_workers_coordinate_properly(self):
        """Test multiple workers coordinate without conflicts"""
        worker_results = []
        worker_errors = []
        lock = threading.Lock()
        
        def coordinated_worker(worker_id, max_jobs=3):
            """Worker that processes jobs with coordination"""
            jobs_processed = 0
            
            try:
                with patch('container_manager.services.job_service.launch_job') as mock_launch:
                    mock_launch.return_value = MagicMock(success=True)
                    
                    while jobs_processed < max_jobs:
                        result = queue_manager.launch_next_batch(max_concurrent=2, timeout=5)
                        
                        if result['launched'] == 0:
                            break  # No more jobs available
                            
                        jobs_processed += result['launched']
                        time.sleep(0.1)  # Simulate processing time
                
                with lock:
                    worker_results.append((worker_id, jobs_processed))
                    
            except Exception as e:
                with lock:
                    worker_errors.append((worker_id, str(e)))
        
        # Launch 4 coordinated workers
        threads = []
        for worker_id in range(4):
            thread = threading.Thread(target=coordinated_worker, args=(worker_id,))
            threads.append(thread)
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors
        self.assertEqual(len(worker_errors), 0, f"Worker errors: {worker_errors}")
        
        # Verify total jobs processed doesn't exceed available
        total_processed = sum(jobs for worker_id, jobs in worker_results)
        self.assertLessEqual(total_processed, 20, "Over-processed jobs")
        
        # Verify all workers got some work (load balancing)
        worker_job_counts = [jobs for worker_id, jobs in worker_results]
        self.assertGreater(len([count for count in worker_job_counts if count > 0]), 1, 
                          "Only one worker got jobs - poor load balancing")

class GracefulShutdownTestCase(TransactionTestCase):
    """Test graceful shutdown scenarios"""
    
    def test_shutdown_waits_for_running_jobs(self):
        """Test shutdown waits for running jobs to complete"""
        from container_manager.signals import JobCompletionTracker
        
        # Create job tracker
        job_tracker = JobCompletionTracker()
        
        # Add some "running" jobs to tracker
        for i in range(3):
            job_tracker.add_running_job(i + 1)
        
        # Simulate job completion in background
        def complete_jobs():
            time.sleep(1)  # Simulate job runtime
            job_tracker.mark_job_completed(1)
            time.sleep(0.5)
            job_tracker.mark_job_completed(2)
            time.sleep(0.5)
            job_tracker.mark_job_completed(3)
        
        completion_thread = threading.Thread(target=complete_jobs)
        completion_thread.start()
        
        # Test waiting for completion
        start_time = time.time()
        completed = job_tracker.wait_for_completion(timeout=5, poll_interval=0.1)
        end_time = time.time()
        
        completion_thread.join()
        
        # Verify all jobs completed
        self.assertTrue(completed, "Jobs didn't complete within timeout")
        self.assertEqual(job_tracker.get_running_count(), 0)
        
        # Verify it took reasonable time (should be ~2 seconds)
        elapsed = end_time - start_time
        self.assertGreater(elapsed, 1.8, "Completed too quickly")
        self.assertLess(elapsed, 3.0, "Took too long to complete")
    
    def test_shutdown_timeout_handling(self):
        """Test shutdown timeout when jobs don't complete"""
        from container_manager.signals import JobCompletionTracker
        
        job_tracker = JobCompletionTracker()
        
        # Add jobs that won't complete
        for i in range(3):
            job_tracker.add_running_job(i + 1)
        
        # Test timeout
        start_time = time.time()
        completed = job_tracker.wait_for_completion(timeout=1, poll_interval=0.1)
        end_time = time.time()
        
        # Verify timeout occurred
        self.assertFalse(completed, "Should have timed out")
        self.assertEqual(job_tracker.get_running_count(), 3, "Jobs should still be running")
        
        # Verify timeout was respected
        elapsed = end_time - start_time
        self.assertGreater(elapsed, 0.9, "Timeout occurred too early")
        self.assertLess(elapsed, 1.5, "Timeout took too long")

class LoadTestCase(TransactionTestCase):
    """Load testing for concurrent operations"""
    
    def test_high_concurrency_job_processing(self):
        """Test system under high concurrency load"""
        # Create many jobs
        job_count = 50
        for i in range(job_count):
            job = ContainerJob.objects.create(
                name=f"load-test-{i}",
                command=f"echo load-{i}",
                priority=random.randint(1, 100)
            )
            queue_manager.queue_job(job)
        
        # Process with many concurrent workers
        worker_count = 8
        results = []
        errors = []
        lock = threading.Lock()
        
        def load_worker(worker_id):
            worker_results = []
            worker_errors = []
            
            try:
                with patch('container_manager.services.job_service.launch_job') as mock_launch:
                    mock_launch.return_value = MagicMock(success=True)
                    
                    # Each worker tries to process jobs for 5 seconds
                    end_time = time.time() + 5
                    
                    while time.time() < end_time:
                        result = queue_manager.launch_next_batch(max_concurrent=3, timeout=1)
                        worker_results.append(result)
                        
                        if result['launched'] == 0:
                            time.sleep(0.1)  # Brief pause if no jobs available
                            
                        if result['errors']:
                            worker_errors.extend(result['errors'])
                
            except Exception as e:
                worker_errors.append(f"Worker {worker_id} error: {e}")
            
            with lock:
                results.extend(worker_results)
                errors.extend(worker_errors)
        
        # Launch all workers
        threads = []
        for worker_id in range(worker_count):
            thread = threading.Thread(target=load_worker, args=(worker_id,))
            threads.append(thread)
        
        start_time = time.time()
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # Analyze results
        total_launched = sum(result['launched'] for result in results if result['launched'] > 0)
        
        self.assertGreater(total_launched, 0, "No jobs were launched under load")
        self.assertLessEqual(total_launched, job_count, "Over-processed jobs")
        
        # Check for excessive errors
        error_rate = len(errors) / max(len(results), 1)
        self.assertLess(error_rate, 0.1, f"Too many errors: {error_rate:.2%}")
        
        # Performance check - should process jobs reasonably quickly
        processing_time = end_time - start_time
        jobs_per_second = total_launched / processing_time
        
        self.assertGreater(jobs_per_second, 5, f"Too slow: {jobs_per_second:.1f} jobs/sec")
```

## Files to Create
- `tests/test_concurrency.py` - Comprehensive concurrency tests

## Testing Commands

```bash
# Run concurrency tests (warning: these are slow)
python manage.py test tests.test_concurrency --verbosity=2

# Run specific concurrency test case
python manage.py test tests.test_concurrency.JobAcquisitionTestCase

# Run load tests (may take 30+ seconds)
python manage.py test tests.test_concurrency.LoadTestCase

# Run with failfast to stop on first failure
python manage.py test tests.test_concurrency --failfast
```

## Dependencies
- Depends on: `04-queue-manager-basic.md` (queue manager implementation)
- Depends on: `05-concurrency-control.md` (atomic job acquisition)
- Depends on: `08-graceful-shutdown.md` (shutdown handling)

## Performance Considerations
- Tests use `TransactionTestCase` (slower but necessary for concurrency)
- Mock external services to focus on concurrency logic
- Use timeouts to prevent hanging tests
- Load tests verify system can handle realistic concurrent load

## Test Environment Requirements
- Database that supports row-level locking (PostgreSQL recommended)
- Sufficient test database connection pool
- Reasonable test timeout settings

## Notes
- Concurrency tests catch race conditions that unit tests miss
- Load tests verify performance under realistic conditions
- Deadlock tests ensure recovery mechanisms work
- Graceful shutdown tests prevent data corruption
- Worker coordination tests ensure proper load balancing
- All tests should pass consistently (no flaky behavior)