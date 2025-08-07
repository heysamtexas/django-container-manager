# Task: Implement Graceful Shutdown and Signal Handling

## Objective
Implement comprehensive graceful shutdown handling for queue processors to prevent job corruption and ensure clean termination.

## Success Criteria
- [ ] SIGTERM/SIGINT handling for graceful shutdown
- [ ] Running jobs complete before shutdown
- [ ] Queue processing stops cleanly
- [ ] Status reporting with SIGUSR1
- [ ] Timeout handling for stuck processes
- [ ] Proper cleanup of resources

## Implementation Details

### Enhanced Signal Handling

```python
# container_manager/signals.py
import signal
import threading
import logging
import time
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

class GracefulShutdown:
    """Handles graceful shutdown for queue processors"""
    
    def __init__(self, timeout=30):
        self.shutdown_event = threading.Event()
        self.timeout = timeout
        self.start_time = None
        self.stats = {
            'shutdown_initiated': None,
            'jobs_completed_during_shutdown': 0,
            'jobs_interrupted': 0,
            'clean_exit': False
        }
        
    def setup_signal_handlers(self, status_callback=None):
        """
        Set up signal handlers for graceful shutdown.
        
        Args:
            status_callback: Function to call for status reporting
        """
        def shutdown_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            
            self.stats['shutdown_initiated'] = timezone.now()
            self.start_time = time.time()
            self.shutdown_event.set()
            
        def status_handler(signum, frame):
            if status_callback:
                try:
                    status_callback()
                except Exception as e:
                    logger.error(f"Error in status callback: {e}")
            else:
                self._default_status_report()
        
        # Graceful shutdown signals
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)
        
        # Status reporting signal
        signal.signal(signal.SIGUSR1, status_handler)
        
        logger.info("Signal handlers configured (TERM/INT=shutdown, USR1=status)")
        
    def is_shutdown_requested(self):
        """Check if shutdown has been requested"""
        return self.shutdown_event.is_set()
        
    def wait_for_shutdown(self, poll_interval=1):
        """
        Wait for shutdown signal with timeout.
        
        Args:
            poll_interval: How often to check for shutdown
            
        Returns:
            bool: True if shutdown was requested, False if timeout
        """
        return self.shutdown_event.wait(poll_interval)
        
    def check_timeout(self):
        """
        Check if shutdown timeout has been exceeded.
        
        Returns:
            bool: True if timeout exceeded
        """
        if not self.start_time:
            return False
            
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout:
            logger.warning(f"Graceful shutdown timeout ({self.timeout}s) exceeded")
            return True
            
        return False
        
    def _default_status_report(self):
        """Default status reporting"""
        from container_manager.queue import queue_manager
        
        try:
            metrics = queue_manager.get_worker_metrics()
            logger.info(f"Queue status: {metrics}")
            print(f"Queue metrics: {metrics}")  # Also print to stdout for operators
        except Exception as e:
            logger.error(f"Error getting queue metrics: {e}")

class JobCompletionTracker:
    """Tracks job completion during shutdown"""
    
    def __init__(self):
        self.running_jobs = set()
        self.completed_jobs = set()
        self.lock = threading.Lock()
        
    def add_running_job(self, job_id):
        """Add a job to the running set"""
        with self.lock:
            self.running_jobs.add(job_id)
            
    def mark_job_completed(self, job_id):
        """Mark a job as completed"""
        with self.lock:
            if job_id in self.running_jobs:
                self.running_jobs.remove(job_id)
                self.completed_jobs.add(job_id)
                
    def get_running_count(self):
        """Get count of still-running jobs"""
        with self.lock:
            return len(self.running_jobs)
            
    def get_running_jobs(self):
        """Get list of running job IDs"""
        with self.lock:
            return list(self.running_jobs)
            
    def wait_for_completion(self, timeout=30, poll_interval=1):
        """
        Wait for all running jobs to complete.
        
        Args:
            timeout: Maximum time to wait
            poll_interval: How often to check
            
        Returns:
            bool: True if all jobs completed, False if timeout
        """
        start_time = time.time()
        
        while self.get_running_count() > 0:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(
                    f"Timeout waiting for {self.get_running_count()} jobs to complete"
                )
                return False
                
            logger.debug(f"Waiting for {self.get_running_count()} jobs to complete...")
            time.sleep(poll_interval)
            
        logger.info(f"All jobs completed in {time.time() - start_time:.1f}s")
        return True
```

### Enhanced Queue Manager with Graceful Shutdown

```python
# container_manager/queue.py (additions to existing class)

from container_manager.signals import GracefulShutdown, JobCompletionTracker

class JobQueueManager:
    # ... existing methods ...
    
    def process_queue_with_graceful_shutdown(self, max_concurrent=5, poll_interval=10, shutdown_timeout=30):
        """
        Process queue with comprehensive graceful shutdown handling.
        
        Args:
            max_concurrent: Maximum concurrent jobs
            poll_interval: Seconds between queue checks
            shutdown_timeout: Timeout for graceful shutdown
            
        Returns:
            dict: Processing statistics
        """
        # Initialize shutdown handler and job tracker
        shutdown_handler = GracefulShutdown(timeout=shutdown_timeout)
        job_tracker = JobCompletionTracker()
        
        # Set up signal handlers with status callback
        def status_callback():
            metrics = self.get_worker_metrics()
            running_jobs = job_tracker.get_running_count()
            logger.info(f"Queue metrics: {metrics}, Currently processing: {running_jobs} jobs")
            
        shutdown_handler.setup_signal_handlers(status_callback)
        
        logger.info(f"Starting graceful queue processor (max_concurrent={max_concurrent})")
        
        stats = {
            'iterations': 0,
            'jobs_launched': 0,
            'jobs_completed': 0,
            'errors': [],
            'shutdown_time': None,
            'clean_shutdown': False
        }
        
        try:
            while not shutdown_handler.is_shutdown_requested():
                stats['iterations'] += 1
                
                # Launch ready jobs
                result = self._launch_batch_with_tracking(
                    max_concurrent=max_concurrent,
                    job_tracker=job_tracker
                )
                
                stats['jobs_launched'] += result['launched']
                stats['errors'].extend(result['errors'])
                
                # Log activity
                if result['launched'] > 0 or result['errors']:
                    logger.info(
                        f"Iteration {stats['iterations']}: "
                        f"launched {result['launched']}, "
                        f"errors {len(result['errors'])}, "
                        f"running {job_tracker.get_running_count()}"
                    )
                
                # Wait with early shutdown detection
                shutdown_handler.wait_for_shutdown(poll_interval)
                
            # Shutdown requested - enter graceful shutdown phase
            stats['shutdown_time'] = timezone.now()
            logger.info("Graceful shutdown initiated")
            
            # Stop launching new jobs, wait for running jobs to complete
            if job_tracker.get_running_count() > 0:
                logger.info(f"Waiting for {job_tracker.get_running_count()} running jobs to complete...")
                
                completed = job_tracker.wait_for_completion(
                    timeout=shutdown_timeout,
                    poll_interval=1
                )
                
                if completed:
                    logger.info("All jobs completed successfully")
                    stats['clean_shutdown'] = True
                else:
                    running_jobs = job_tracker.get_running_jobs()
                    logger.warning(f"Forced shutdown with {len(running_jobs)} jobs still running: {running_jobs}")
                    stats['jobs_interrupted'] = len(running_jobs)
            else:
                logger.info("No running jobs, clean shutdown")
                stats['clean_shutdown'] = True
                
        except Exception as e:
            logger.exception(f"Error in graceful queue processing: {e}")
            stats['errors'].append(f"Fatal error: {str(e)}")
            
        finally:
            # Cleanup and final logging
            logger.info(f"Queue processor finished. Stats: {stats}")
            
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
        from container_manager.models import ContainerJob
        
        # Check available slots
        running_count = job_tracker.get_running_count()
        available_slots = max(0, max_concurrent - running_count)
        
        if available_slots == 0:
            return {'launched': 0, 'errors': []}
        
        # Get ready jobs
        ready_jobs = self.get_ready_jobs(limit=available_slots)
        
        launched_count = 0
        errors = []
        
        for job in ready_jobs:
            # Add to tracker before launching
            job_tracker.add_running_job(job.id)
            
            try:
                result = self.launch_job_with_retry(job)
                
                if result['success']:
                    launched_count += 1
                    logger.debug(f"Launched job {job.id}")
                    
                    # Start monitoring for completion in background
                    self._monitor_job_completion(job, job_tracker)
                else:
                    # Launch failed, remove from tracker
                    job_tracker.mark_job_completed(job.id)
                    errors.append(f"Job {job.id}: {result['error']}")
                    
            except Exception as e:
                # Launch error, remove from tracker
                job_tracker.mark_job_completed(job.id)
                errors.append(f"Job {job.id}: {str(e)}")
                logger.exception(f"Error launching job {job.id}")
                
        return {'launched': launched_count, 'errors': errors}
        
    def _monitor_job_completion(self, job, job_tracker):
        """
        Monitor job completion in background thread.
        
        Args:
            job: ContainerJob instance
            job_tracker: JobCompletionTracker instance
        """
        def monitor():
            try:
                # Poll job status until completion
                from container_manager.services import job_service
                
                while True:
                    time.sleep(5)  # Check every 5 seconds
                    
                    job.refresh_from_db()
                    
                    if job.status in ['completed', 'failed', 'cancelled']:
                        job_tracker.mark_job_completed(job.id)
                        logger.debug(f"Job {job.id} completed with status: {job.status}")
                        break
                        
            except Exception as e:
                logger.error(f"Error monitoring job {job.id}: {e}")
                # Assume completed to prevent hanging
                job_tracker.mark_job_completed(job.id)
                
        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
```

## Files to Create/Modify
- `container_manager/signals.py` - New file with graceful shutdown handling
- `container_manager/queue.py` - Add graceful shutdown methods
- `container_manager/management/commands/process_container_jobs.py` - Use graceful shutdown

## Testing Requirements
- [ ] Test SIGTERM triggers graceful shutdown
- [ ] Test SIGINT (Ctrl+C) triggers graceful shutdown
- [ ] Test SIGUSR1 provides status information
- [ ] Test running jobs complete before shutdown
- [ ] Test timeout handling for stuck processes
- [ ] Test cleanup of resources
- [ ] Test signal handling doesn't interfere with normal operation

### Signal Testing Script

```python
# scripts/test_graceful_shutdown.py
import subprocess
import signal
import time
import os

def test_graceful_shutdown():
    """Test graceful shutdown functionality"""
    
    # Start queue processor
    process = subprocess.Popen([
        'python', 'manage.py', 'process_container_jobs', 
        '--queue-mode', '--verbose'
    ])
    
    print(f"Started queue processor with PID {process.pid}")
    
    # Let it run for a bit
    time.sleep(5)
    
    # Request status
    print("Requesting status with SIGUSR1...")
    os.kill(process.pid, signal.SIGUSR1)
    time.sleep(2)
    
    # Request graceful shutdown
    print("Requesting graceful shutdown with SIGTERM...")
    os.kill(process.pid, signal.SIGTERM)
    
    # Wait for shutdown
    try:
        process.wait(timeout=60)  # Give it up to 60 seconds
        print(f"Process exited with code: {process.returncode}")
    except subprocess.TimeoutExpired:
        print("Process didn't exit within timeout, force killing...")
        process.kill()
        process.wait()

if __name__ == '__main__':
    test_graceful_shutdown()
```

## Dependencies
- Depends on: `07-queue-mode-command.md` (management command)
- Depends on: `05-concurrency-control.md` (concurrent job processing)

## Deployment Integration

### Kubernetes Example

```yaml
# kubernetes/queue-processor.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-queue-processor
spec:
  replicas: 2
  selector:
    matchLabels:
      app: django-queue-processor
  template:
    metadata:
      labels:
        app: django-queue-processor
    spec:
      containers:
      - name: queue-processor
        image: myproject:latest
        command: ["python", "manage.py", "process_container_jobs", "--queue-mode"]
        env:
        - name: DJANGO_SETTINGS_MODULE
          value: "myproject.settings"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        # Graceful shutdown configuration
        terminationGracePeriodSeconds: 45
        lifecycle:
          preStop:
            exec:
              command: ["kill", "-TERM", "1"]
```

## Notes
- Comprehensive signal handling prevents data corruption
- Job completion tracking ensures clean shutdowns
- Timeout handling prevents hanging processes
- Status reporting provides operational visibility
- Background monitoring prevents resource leaks
- Compatible with container orchestration platforms
- Provides clear feedback to operators about shutdown process