"""
Django tests for queue retry logic and error classification.

Tests the retry logic implementation including error classification,
exponential backoff, state transitions, and manual retry functionality.
"""

from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta

from ..models import ContainerJob, ExecutorHost
from ..queue import JobQueueManager
from ..retry import ErrorClassifier, ErrorType, RETRY_STRATEGIES


class ErrorClassificationTest(TestCase):
    """Test error classification system"""
    
    def test_transient_error_classification(self):
        """Test that transient errors are classified correctly"""
        transient_errors = [
            "Connection refused to Docker daemon",
            "Docker daemon not running",
            "Network timeout occurred",
            "Resource temporarily unavailable",
            "Out of memory",
            "No space left on device",
            "Too many open files",
        ]
        
        for error_msg in transient_errors:
            with self.subTest(error=error_msg):
                result = ErrorClassifier.classify_error(error_msg)
                self.assertEqual(result, ErrorType.TRANSIENT)
    
    def test_permanent_error_classification(self):
        """Test that permanent errors are classified correctly"""
        permanent_errors = [
            "Image not found: nonexistent:latest",
            "No such image: missing:tag",
            "Permission denied",
            "Authorization failed",
            "Command not found",
            "Executable not found",
        ]
        
        for error_msg in permanent_errors:
            with self.subTest(error=error_msg):
                result = ErrorClassifier.classify_error(error_msg)
                self.assertEqual(result, ErrorType.PERMANENT)
    
    def test_unknown_error_classification(self):
        """Test that unknown errors default to UNKNOWN type"""
        unknown_errors = [
            "Some completely unknown error",
            "Random system failure",
            "Unexpected behavior detected",
        ]
        
        for error_msg in unknown_errors:
            with self.subTest(error=error_msg):
                result = ErrorClassifier.classify_error(error_msg)
                self.assertEqual(result, ErrorType.UNKNOWN)


class RetryStrategyTest(TestCase):
    """Test retry strategy calculations"""
    
    def test_default_strategy(self):
        """Test default retry strategy behavior"""
        strategy = RETRY_STRATEGIES['default']
        
        # Should retry transient errors within limit
        self.assertTrue(strategy.should_retry(1, ErrorType.TRANSIENT))
        self.assertTrue(strategy.should_retry(2, ErrorType.TRANSIENT))
        self.assertFalse(strategy.should_retry(3, ErrorType.TRANSIENT))
        
        # Should never retry permanent errors
        self.assertFalse(strategy.should_retry(1, ErrorType.PERMANENT))
        
        # Test delay calculations
        self.assertEqual(strategy.get_retry_delay(1), 0.0)  # First attempt
        self.assertEqual(strategy.get_retry_delay(2), 2.0)  # Second attempt
        self.assertEqual(strategy.get_retry_delay(3), 4.0)  # Third attempt
    
    def test_high_priority_strategy(self):
        """Test high priority strategy has shorter delays"""
        strategy = RETRY_STRATEGIES['high_priority']
        
        self.assertEqual(strategy.get_retry_delay(2), 0.5)  # Faster than default
        self.assertEqual(strategy.max_attempts, 5)  # More attempts
    
    def test_conservative_strategy(self):
        """Test conservative strategy has fewer attempts and longer delays"""
        strategy = RETRY_STRATEGIES['conservative']
        
        self.assertEqual(strategy.max_attempts, 2)  # Fewer attempts
        self.assertEqual(strategy.get_retry_delay(2), 5.0)  # Longer delays


class QueueRetryLogicTest(TestCase):
    """Test queue retry logic with jobs"""
    
    def setUp(self):
        """Set up test data"""
        self.host = ExecutorHost.objects.create(
            name='test-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True,
            max_concurrent_jobs=5
        )
        
        self.queue_manager = JobQueueManager()
    
    def test_successful_job_launch(self):
        """Test successful job launch without retries"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "success"',
            docker_host=self.host,
            max_retries=3
        )
        
        # Queue the job
        self.queue_manager.queue_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        
        # Mock successful launch
        with patch.object(self.queue_manager, '_mock_launch_job_with_failure_simulation') as mock_launch:
            mock_launch.return_value = {'success': True}
            
            result = self.queue_manager.launch_job_with_retry(job)
            
            self.assertTrue(result['success'])
            self.assertFalse(result['retry_scheduled'])
            
            job.refresh_from_db()
            self.assertEqual(job.status, 'running')
            self.assertEqual(job.retry_count, 0)
    
    def test_transient_error_retry(self):
        """Test job retry with transient error"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "retry test"',
            docker_host=self.host,
            max_retries=3
        )
        
        self.queue_manager.queue_job(job)
        
        # Mock transient failure
        with patch.object(self.queue_manager, '_mock_launch_job_with_failure_simulation') as mock_launch:
            mock_launch.return_value = {
                'success': False, 
                'error': 'Connection refused to Docker daemon'
            }
            
            result = self.queue_manager.launch_job_with_retry(job)
            
            self.assertFalse(result['success'])
            self.assertTrue(result['retry_scheduled'])
            self.assertIn('retry_in_seconds', result)
            
            job.refresh_from_db()
            self.assertEqual(job.status, 'retrying')
            self.assertEqual(job.retry_count, 1)
            self.assertEqual(job.last_error, 'Connection refused to Docker daemon')
            self.assertIsNotNone(job.scheduled_for)
    
    def test_permanent_error_no_retry(self):
        """Test job fails permanently with permanent error"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "permanent failure"',
            docker_host=self.host,
            max_retries=3
        )
        
        self.queue_manager.queue_job(job)
        
        # Mock permanent failure
        with patch.object(self.queue_manager, '_mock_launch_job_with_failure_simulation') as mock_launch:
            mock_launch.return_value = {
                'success': False,
                'error': 'Image not found: nonexistent:latest'
            }
            
            result = self.queue_manager.launch_job_with_retry(job)
            
            self.assertFalse(result['success'])
            self.assertFalse(result['retry_scheduled'])
            
            job.refresh_from_db()
            self.assertEqual(job.status, 'failed')
            self.assertEqual(job.retry_count, 1)
            self.assertEqual(job.last_error, 'Image not found: nonexistent:latest')
            self.assertIsNone(job.queued_at)  # Removed from queue
    
    def test_retry_limit_exceeded(self):
        """Test job fails permanently when retry limit exceeded"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "retry limit test"',
            docker_host=self.host,
            max_retries=2  # Job can be attempted maximum 2 times
        )
        
        self.queue_manager.queue_job(job)
        
        # Mock repeated transient failures
        with patch.object(self.queue_manager, '_mock_launch_job_with_failure_simulation') as mock_launch:
            mock_launch.return_value = {
                'success': False,
                'error': 'Network timeout occurred'
            }
            
            # First failure - should retry (retry_count becomes 1, 1 < 2)
            result1 = self.queue_manager.launch_job_with_retry(job)
            self.assertTrue(result1['retry_scheduled'])
            
            job.refresh_from_db()
            self.assertEqual(job.retry_count, 1)
            self.assertEqual(job.status, 'retrying')
            
            # Second failure - should NOT retry (retry_count becomes 2, 2 >= 2)
            result2 = self.queue_manager.launch_job_with_retry(job)
            self.assertFalse(result2['retry_scheduled'])
            
            job.refresh_from_db()
            self.assertEqual(job.retry_count, 2)
            self.assertEqual(job.status, 'failed')
            self.assertIsNone(job.queued_at)  # Removed from queue
    
    def test_manual_retry_failed_job(self):
        """Test manual retry of failed job"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "manual retry"',
            docker_host=self.host,
            status='failed',
            retry_count=2,
            max_retries=3
        )
        
        # Test manual retry without reset
        success = self.queue_manager.retry_failed_job(job, reset_count=False)
        self.assertTrue(success)
        
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.retry_count, 2)  # Count not reset
        self.assertIsNotNone(job.queued_at)
        self.assertIsNone(job.scheduled_for)  # Immediate retry
        self.assertIsNone(job.last_error)  # Error cleared
    
    def test_manual_retry_with_reset(self):
        """Test manual retry with count reset"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "manual retry with reset"',
            docker_host=self.host,
            status='failed',
            retry_count=2,
            max_retries=3
        )
        
        # Test manual retry with reset
        success = self.queue_manager.retry_failed_job(job, reset_count=True)
        self.assertTrue(success)
        
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.retry_count, 0)  # Count reset
        self.assertIsNotNone(job.queued_at)
    
    def test_cannot_retry_running_job(self):
        """Test that running jobs cannot be manually retried"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "running job"',
            docker_host=self.host,
            status='running'
        )
        
        with self.assertRaises(ValueError) as cm:
            self.queue_manager.retry_failed_job(job)
        
        self.assertIn("Cannot retry job in status: running", str(cm.exception))
    
    def test_priority_based_retry_strategy(self):
        """Test that job priority affects retry strategy selection"""
        # High priority job
        high_priority_job = ContainerJob.objects.create(
            docker_image='nginx:high',
            command='echo "high priority"',
            docker_host=self.host,
            priority=85,  # High priority
            max_retries=3
        )
        
        strategy = self.queue_manager._get_retry_strategy(high_priority_job)
        self.assertEqual(strategy, RETRY_STRATEGIES['high_priority'])
        
        # Low priority job
        low_priority_job = ContainerJob.objects.create(
            docker_image='nginx:low',
            command='echo "low priority"',
            docker_host=self.host,
            priority=15,  # Low priority
            max_retries=3
        )
        
        strategy = self.queue_manager._get_retry_strategy(low_priority_job)
        self.assertEqual(strategy, RETRY_STRATEGIES['conservative'])
        
        # Normal priority job
        normal_priority_job = ContainerJob.objects.create(
            docker_image='nginx:normal',
            command='echo "normal priority"',
            docker_host=self.host,
            priority=50,  # Normal priority
            max_retries=3
        )
        
        strategy = self.queue_manager._get_retry_strategy(normal_priority_job)
        self.assertEqual(strategy, RETRY_STRATEGIES['default'])


class StateTransitionTest(TestCase):
    """Test job state transitions during retry logic"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
    
    def test_valid_state_transitions_for_retries(self):
        """Test that retry logic follows valid state transitions"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "state test"',
            docker_host=self.host
        )
        
        # pending -> queued
        self.assertTrue(job.can_transition_to('queued'))
        job.transition_to('queued')
        
        # queued -> retrying
        self.assertTrue(job.can_transition_to('retrying'))
        job.transition_to('retrying')
        
        # retrying -> queued
        self.assertTrue(job.can_transition_to('queued'))
        job.transition_to('queued')
        
        # queued -> failed
        self.assertTrue(job.can_transition_to('failed'))
        job.transition_to('failed')
        
        # failed -> retrying
        self.assertTrue(job.can_transition_to('retrying'))
        job.transition_to('retrying')
    
    def test_invalid_state_transitions(self):
        """Test that invalid state transitions are prevented"""
        job = ContainerJob.objects.create(
            docker_image='nginx:test',
            command='echo "invalid state test"',
            docker_host=self.host,
            status='completed'
        )
        
        # completed is terminal - cannot transition anywhere
        self.assertFalse(job.can_transition_to('retrying'))
        self.assertFalse(job.can_transition_to('queued'))
        
        with self.assertRaises(ValueError):
            job.transition_to('queued')


class QueueMetricsTest(TestCase):
    """Test queue metrics and statistics"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        self.queue_manager = JobQueueManager()
    
    def test_queue_statistics(self):
        """Test queue statistics calculation"""
        # Create jobs in different states
        queued_job = ContainerJob.objects.create(
            docker_image='nginx:queued',
            command='echo "queued"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            retry_count=0,
            max_retries=3
        )
        
        scheduled_job = ContainerJob.objects.create(
            docker_image='nginx:scheduled',
            command='echo "scheduled"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            scheduled_for=timezone.now() + timedelta(hours=1),
            retry_count=0,
            max_retries=3
        )
        
        running_job = ContainerJob.objects.create(
            docker_image='nginx:running',
            command='echo "running"',
            docker_host=self.host,
            status='running'
        )
        
        failed_job = ContainerJob.objects.create(
            docker_image='nginx:failed',
            command='echo "failed"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            retry_count=3,
            max_retries=3  # Exceeded retry limit
        )
        
        stats = self.queue_manager.get_queue_stats()
        
        self.assertEqual(stats['queued'], 1)  # Only queued_job
        self.assertEqual(stats['scheduled'], 1)  # Only scheduled_job
        self.assertEqual(stats['running'], 1)  # Only running_job
        self.assertEqual(stats['launch_failed'], 1)  # Only failed_job
    
    def test_worker_metrics(self):
        """Test worker coordination metrics"""
        # Create jobs for metrics testing
        ContainerJob.objects.create(
            docker_image='nginx:ready',
            command='echo "ready"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            retry_count=0,
            max_retries=3
        )
        
        ContainerJob.objects.create(
            docker_image='nginx:future',
            command='echo "future"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            scheduled_for=timezone.now() + timedelta(hours=1),
            retry_count=0,
            max_retries=3
        )
        
        metrics = self.queue_manager.get_worker_metrics()
        
        self.assertEqual(metrics['queue_depth'], 2)  # Both jobs are queued
        self.assertEqual(metrics['ready_now'], 1)    # Only one ready now
        self.assertEqual(metrics['scheduled_future'], 1)  # One scheduled for future
        self.assertEqual(metrics['running'], 0)     # No running jobs
        self.assertEqual(metrics['launch_failed'], 0)  # No failed jobs