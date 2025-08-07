# Task: Queue Operations and Integration Tests

## Objective
Comprehensive test suite for queue operations, integration scenarios, and end-to-end workflows.

## Success Criteria
- [ ] Test all queue manager operations work correctly
- [ ] Test retry logic with different error scenarios  
- [ ] Test priority ordering and FIFO behavior
- [ ] Test scheduled job execution
- [ ] Test admin actions and endpoints
- [ ] Test management command functionality
- [ ] All integration tests pass

## Implementation Details

### Core Queue Operations Tests

```python
# tests/test_queue_operations.py
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from unittest.mock import patch, MagicMock
from container_manager.models import ContainerJob
from container_manager.queue import queue_manager
from container_manager.retry import ErrorClassifier, RETRY_STRATEGIES

class QueueManagerTestCase(TestCase):
    """Test core queue manager operations"""
    
    def setUp(self):
        self.job = ContainerJob.objects.create(
            name="test-job",
            command="echo test",
            docker_image="python:3.9"
        )
    
    def test_queue_job_basic(self):
        """Test basic job queuing"""
        # Initially not queued
        self.assertFalse(self.job.is_queued)
        
        # Queue the job
        result = queue_manager.queue_job(self.job)
        
        # Verify job was queued
        self.assertEqual(result, self.job)
        self.assertTrue(self.job.is_queued)
        self.assertIsNotNone(self.job.queued_at)
        self.assertEqual(self.job.status, 'queued')
        
    def test_queue_job_with_priority(self):
        """Test queuing job with custom priority"""
        queue_manager.queue_job(self.job, priority=80)
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.priority, 80)
        
    def test_queue_job_with_schedule(self):
        """Test queuing job for future execution"""
        future_time = timezone.now() + timedelta(hours=2)
        queue_manager.queue_job(self.job, schedule_for=future_time)
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.scheduled_for, future_time)
        self.assertTrue(self.job.is_queued)
        self.assertFalse(self.job.is_ready_to_launch)  # Not ready yet
        
    def test_queue_job_already_queued_error(self):
        """Test error when queuing already queued job"""
        queue_manager.queue_job(self.job)
        
        with self.assertRaises(ValueError) as context:
            queue_manager.queue_job(self.job)
        
        self.assertIn('already queued', str(context.exception))
        
    def test_queue_job_completed_error(self):
        """Test error when queuing completed job"""
        self.job.transition_to('queued')
        self.job.transition_to('running')
        self.job.transition_to('completed')
        
        with self.assertRaises(ValueError) as context:
            queue_manager.queue_job(self.job)
        
        self.assertIn('Cannot queue completed', str(context.exception))
        
    def test_get_ready_jobs_priority_ordering(self):
        """Test jobs returned in priority order"""
        # Create jobs with different priorities
        jobs = []
        priorities = [20, 80, 50, 90, 30]
        
        for i, priority in enumerate(priorities):
            job = ContainerJob.objects.create(
                name=f"priority-job-{i}",
                command=f"echo priority-{priority}",
                priority=priority
            )
            queue_manager.queue_job(job)
            jobs.append(job)
        
        # Get ready jobs
        ready_jobs = list(queue_manager.get_ready_jobs())
        
        # Verify order: highest priority first
        expected_order = [90, 80, 50, 30, 20]
        actual_order = [job.priority for job in ready_jobs]
        
        self.assertEqual(actual_order, expected_order)
        
    def test_get_ready_jobs_fifo_within_priority(self):
        """Test FIFO ordering within same priority"""
        jobs = []
        
        # Create 5 jobs with same priority
        for i in range(5):
            job = ContainerJob.objects.create(
                name=f"fifo-job-{i}",
                command=f"echo fifo-{i}",
                priority=50
            )
            queue_manager.queue_job(job)
            jobs.append(job)
        
        # Get ready jobs
        ready_jobs = list(queue_manager.get_ready_jobs())
        
        # Verify FIFO order (first queued = first returned)
        expected_order = [job.id for job in jobs]
        actual_order = [job.id for job in ready_jobs]
        
        self.assertEqual(actual_order, expected_order)
        
    def test_get_ready_jobs_excludes_scheduled(self):
        """Test scheduled jobs not returned until time"""
        # Create job scheduled for future
        future_job = ContainerJob.objects.create(
            name="future-job",
            command="echo future"
        )
        queue_manager.queue_job(
            future_job, 
            schedule_for=timezone.now() + timedelta(hours=1)
        )
        
        # Create ready job
        ready_job = ContainerJob.objects.create(
            name="ready-job",
            command="echo ready"
        )
        queue_manager.queue_job(ready_job)
        
        # Get ready jobs
        ready_jobs = list(queue_manager.get_ready_jobs())
        
        # Only ready job should be returned
        self.assertEqual(len(ready_jobs), 1)
        self.assertEqual(ready_jobs[0].id, ready_job.id)
        
    def test_get_ready_jobs_limit(self):
        """Test limit parameter works correctly"""
        # Create 10 jobs
        for i in range(10):
            job = ContainerJob.objects.create(
                name=f"limit-job-{i}",
                command=f"echo limit-{i}"
            )
            queue_manager.queue_job(job)
        
        # Get limited results
        ready_jobs = list(queue_manager.get_ready_jobs(limit=5))
        
        self.assertEqual(len(ready_jobs), 5)
        
    def test_dequeue_job(self):
        """Test removing job from queue"""
        queue_manager.queue_job(self.job)
        self.assertTrue(self.job.is_queued)
        
        # Dequeue
        queue_manager.dequeue_job(self.job)
        
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_queued)
        self.assertIsNone(self.job.queued_at)
        self.assertIsNone(self.job.scheduled_for)
        self.assertEqual(self.job.retry_count, 0)
        
    def test_dequeue_job_not_queued_error(self):
        """Test error when dequeuing non-queued job"""
        with self.assertRaises(ValueError) as context:
            queue_manager.dequeue_job(self.job)
        
        self.assertIn('not queued', str(context.exception))
        
    def test_get_queue_stats(self):
        """Test queue statistics are accurate"""
        # Create various job states
        jobs = []
        
        # Queued job
        queued_job = ContainerJob.objects.create(name="queued", command="echo queued")
        queue_manager.queue_job(queued_job)
        
        # Scheduled job
        scheduled_job = ContainerJob.objects.create(name="scheduled", command="echo scheduled")
        queue_manager.queue_job(scheduled_job, schedule_for=timezone.now() + timedelta(hours=1))
        
        # Running job
        running_job = ContainerJob.objects.create(name="running", command="echo running")
        running_job.transition_to('queued')
        running_job.transition_to('running')
        
        # Launch failed job (exceeded retries)
        failed_job = ContainerJob.objects.create(name="failed", command="echo failed")
        queue_manager.queue_job(failed_job)
        failed_job.retry_count = 5  # Exceeds default max_retries
        failed_job.save()
        
        # Get stats
        stats = queue_manager.get_queue_stats()
        
        # Verify stats
        self.assertEqual(stats['queued'], 1)  # Only queued_job
        self.assertEqual(stats['scheduled'], 1)  # Only scheduled_job
        self.assertEqual(stats['running'], 1)  # Only running_job
        self.assertEqual(stats['launch_failed'], 1)  # Only failed_job

class RetryLogicTestCase(TestCase):
    """Test retry logic and error classification"""
    
    def setUp(self):
        self.job = ContainerJob.objects.create(
            name="retry-test-job",
            command="echo retry-test",
            max_retries=3
        )
        queue_manager.queue_job(self.job)
        
    def test_error_classification_transient(self):
        """Test transient errors are classified correctly"""
        transient_errors = [
            "Connection refused",
            "Docker daemon not running",
            "Network timeout occurred",
            "Out of memory",
            "Resource temporarily unavailable"
        ]
        
        for error in transient_errors:
            error_type = ErrorClassifier.classify_error(error)
            self.assertEqual(error_type.value, 'transient', f"'{error}' should be transient")
            
    def test_error_classification_permanent(self):
        """Test permanent errors are classified correctly"""
        permanent_errors = [
            "Image not found",
            "Repository not found", 
            "Permission denied",
            "Command not found",
            "Invalid configuration"
        ]
        
        for error in permanent_errors:
            error_type = ErrorClassifier.classify_error(error)
            self.assertEqual(error_type.value, 'permanent', f"'{error}' should be permanent")
            
    def test_launch_job_with_retry_success(self):
        """Test successful job launch"""
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=True)
            
            result = queue_manager.launch_job_with_retry(self.job)
            
            self.assertTrue(result['success'])
            self.assertFalse(result.get('retry_scheduled', False))
            
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, 'running')
            self.assertIsNotNone(self.job.launched_at)
            
    def test_launch_job_with_transient_error_retry(self):
        """Test transient error triggers retry"""
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=False, error="Connection refused")
            
            result = queue_manager.launch_job_with_retry(self.job)
            
            self.assertFalse(result['success'])
            self.assertTrue(result['retry_scheduled'])
            self.assertIn('retry_in_seconds', result)
            
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, 'retrying')
            self.assertEqual(self.job.retry_count, 1)
            self.assertIsNotNone(self.job.scheduled_for)
            
    def test_launch_job_with_permanent_error_no_retry(self):
        """Test permanent error doesn't trigger retry"""
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=False, error="Image not found")
            
            result = queue_manager.launch_job_with_retry(self.job)
            
            self.assertFalse(result['success'])
            self.assertFalse(result['retry_scheduled'])
            
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, 'failed')
            self.assertIsNone(self.job.queued_at)  # Removed from queue
            
    def test_retry_limit_exhausted(self):
        """Test job fails permanently after max retries"""
        self.job.retry_count = 3
        self.job.max_retries = 3
        self.job.save()
        
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=False, error="Connection refused")
            
            result = queue_manager.launch_job_with_retry(self.job)
            
            self.assertFalse(result['success'])
            self.assertFalse(result['retry_scheduled'])
            
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, 'failed')
            self.assertIsNone(self.job.queued_at)
            
    def test_retry_failed_job_manually(self):
        """Test manually retrying failed job"""
        # Set up failed job
        self.job.transition_to('running')
        self.job.transition_to('failed')
        
        # Retry manually
        result = queue_manager.retry_failed_job(self.job, reset_count=True)
        
        self.assertTrue(result)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'queued')
        self.assertEqual(self.job.retry_count, 0)  # Reset
        self.assertIsNotNone(self.job.queued_at)

class SchedulingTestCase(TestCase):
    """Test job scheduling functionality"""
    
    def test_scheduled_job_becomes_ready(self):
        """Test scheduled job becomes ready when time passes"""
        # Schedule job for 1 second in future
        future_time = timezone.now() + timedelta(seconds=1)
        
        job = ContainerJob.objects.create(
            name="scheduled-test",
            command="echo scheduled"
        )
        queue_manager.queue_job(job, schedule_for=future_time)
        
        # Initially not ready
        self.assertFalse(job.is_ready_to_launch)
        
        # Mock time passing
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = future_time + timedelta(seconds=1)
            
            # Now should be ready
            self.assertTrue(job.is_ready_to_launch)
            
            # Should appear in ready jobs
            ready_jobs = list(queue_manager.get_ready_jobs())
            self.assertIn(job, ready_jobs)
            
    def test_scheduled_jobs_not_in_ready_list(self):
        """Test scheduled jobs don't appear in ready list before time"""
        future_time = timezone.now() + timedelta(hours=1)
        
        job = ContainerJob.objects.create(
            name="future-scheduled",
            command="echo future"
        )
        queue_manager.queue_job(job, schedule_for=future_time)
        
        ready_jobs = list(queue_manager.get_ready_jobs())
        self.assertNotIn(job, ready_jobs)

class IntegrationTestCase(TransactionTestCase):
    """End-to-end integration tests"""
    
    def test_complete_job_workflow(self):
        """Test complete workflow from queue to completion"""
        # Create and queue job
        job = ContainerJob.objects.create(
            name="workflow-test",
            command="echo workflow",
            priority=70
        )
        queue_manager.queue_job(job)
        
        # Mock successful job execution
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=True)
            
            # Launch job
            result = queue_manager.launch_job_with_retry(job)
            self.assertTrue(result['success'])
            
            job.refresh_from_db()
            self.assertEqual(job.status, 'running')
            
            # Complete job
            job.mark_as_completed()
            self.assertEqual(job.status, 'completed')
            self.assertIsNotNone(job.completed_at)
            
    def test_batch_processing_workflow(self):
        """Test batch processing multiple jobs"""
        # Create multiple jobs
        jobs = []
        for i in range(10):
            job = ContainerJob.objects.create(
                name=f"batch-job-{i}",
                command=f"echo batch-{i}",
                priority=random.choice([20, 50, 80])
            )
            queue_manager.queue_job(job)
            jobs.append(job)
        
        # Process in batches
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=True)
            
            # First batch
            result = queue_manager.launch_next_batch(max_concurrent=3)
            self.assertEqual(result['launched'], 3)
            self.assertEqual(len(result['errors']), 0)
            
            # Second batch
            result = queue_manager.launch_next_batch(max_concurrent=5)
            self.assertEqual(result['launched'], 5)
            
            # Third batch (remaining)
            result = queue_manager.launch_next_batch(max_concurrent=5)
            self.assertEqual(result['launched'], 2)  # Only 2 remaining
            
    def test_priority_preemption(self):
        """Test high priority jobs are processed first"""
        # Create low priority job
        low_job = ContainerJob.objects.create(
            name="low-priority",
            command="echo low",
            priority=20
        )
        queue_manager.queue_job(low_job)
        
        # Add high priority job later
        high_job = ContainerJob.objects.create(
            name="high-priority", 
            command="echo high",
            priority=90
        )
        queue_manager.queue_job(high_job)
        
        # High priority should be first in ready jobs
        ready_jobs = list(queue_manager.get_ready_jobs())
        self.assertEqual(ready_jobs[0].id, high_job.id)
        self.assertEqual(ready_jobs[1].id, low_job.id)
```

### Admin Integration Tests

```python
# tests/test_admin_integration.py
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import JsonResponse
from container_manager.models import ContainerJob
from container_manager.queue import queue_manager
import json

class AdminQueueActionsTestCase(TestCase):
    """Test admin queue management actions"""
    
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client.login(username='admin', password='admin123')
        
        self.job = ContainerJob.objects.create(
            name="admin-test-job",
            command="echo admin-test"
        )
        
    def test_queue_job_admin_action(self):
        """Test queuing job via admin action"""
        url = reverse('admin:container_manager_containerjob_changelist')
        
        response = self.client.post(url, {
            'action': 'queue_selected_jobs',
            '_selected_action': [self.job.id]
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after action
        
        self.job.refresh_from_db()
        self.assertTrue(self.job.is_queued)
        
    def test_dequeue_job_ajax(self):
        """Test AJAX dequeue endpoint"""
        # First queue the job
        queue_manager.queue_job(self.job)
        
        url = reverse('admin:containerjob-dequeue', args=[self.job.id])
        
        response = self.client.post(url, 
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_queued)
        
    def test_requeue_job_ajax(self):
        """Test AJAX requeue endpoint"""
        # Set job to failed state
        self.job.transition_to('queued')
        self.job.transition_to('running')
        self.job.transition_to('failed')
        
        url = reverse('admin:containerjob-requeue', args=[self.job.id])
        
        response = self.client.post(url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        self.job.refresh_from_db()
        self.assertTrue(self.job.is_queued)
        
    def test_queue_stats_view(self):
        """Test queue statistics view"""
        # Create jobs in various states
        queue_manager.queue_job(self.job)
        
        running_job = ContainerJob.objects.create(name="running", command="echo running")
        running_job.transition_to('queued')
        running_job.transition_to('running')
        
        url = reverse('admin:containerjob-queue-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Queue Statistics')
        
        # Test JSON response
        response = self.client.get(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('queued', data)
        self.assertIn('running', data)

class ManagementCommandTestCase(TestCase):
    """Test management command functionality"""
    
    def setUp(self):
        self.job = ContainerJob.objects.create(
            name="command-test-job",
            command="echo command-test"
        )
        queue_manager.queue_job(self.job)
        
    def test_queue_mode_once(self):
        """Test --queue-mode --once option"""
        from django.core.management import call_command
        from io import StringIO
        
        with patch('container_manager.services.job_service.launch_job') as mock_launch:
            mock_launch.return_value = MagicMock(success=True)
            
            out = StringIO()
            call_command('process_container_jobs', 
                        '--queue-mode', '--once', '--max-concurrent=2',
                        stdout=out)
            
            output = out.getvalue()
            self.assertIn('launched', output)
            
    def test_queue_mode_dry_run(self):
        """Test --queue-mode --dry-run option"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('process_container_jobs',
                    '--queue-mode', '--dry-run',
                    stdout=out)
        
        output = out.getvalue()
        self.assertIn('Ready to launch now:', output)
        self.assertIn('dry run', output)
        
        # Job should still be queued (not actually processed)
        self.job.refresh_from_db()
        self.assertTrue(self.job.is_queued)
```

## Files to Create
- `tests/test_queue_operations.py` - Core queue operations tests
- `tests/test_admin_integration.py` - Admin interface integration tests

## Testing Commands

```bash
# Run all queue operation tests
python manage.py test tests.test_queue_operations --verbosity=2

# Run admin integration tests
python manage.py test tests.test_admin_integration

# Run specific test case
python manage.py test tests.test_queue_operations.QueueManagerTestCase

# Run with coverage
coverage run --source='.' manage.py test tests.test_queue_operations
coverage report
```

## Dependencies
- Depends on: All previous queue implementation tasks
- Requires: Admin interface enhancements
- Requires: Management command modifications

## Test Coverage Requirements
- [ ] Queue manager operations: 100% coverage
- [ ] Retry logic: 100% coverage
- [ ] Priority/FIFO ordering: 100% coverage
- [ ] Scheduling: 100% coverage
- [ ] Admin actions: 90% coverage (UI logic exempt)
- [ ] Management commands: 85% coverage

## Mock Strategy
- Mock `job_service.launch_job` for controlled testing
- Mock `timezone.now` for time-based testing
- Mock external dependencies but test queue logic thoroughly
- Use real database for integration tests

## Notes
- Integration tests verify complete workflows
- Admin tests ensure UI functionality works
- Command tests verify CLI interface
- Priority tests ensure job ordering is correct
- Retry tests cover all error scenarios
- Scheduling tests verify time-based execution