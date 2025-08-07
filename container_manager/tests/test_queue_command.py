"""
Tests for queue mode functionality in process_container_jobs management command.

This module tests the enhanced management command with queue processing
capabilities while ensuring backward compatibility.
"""

from django.test import TestCase
from django.core.management import call_command, CommandError
from django.utils import timezone
from io import StringIO
from unittest.mock import patch, MagicMock
import threading
import time

from ..models import ContainerJob, ExecutorHost
from ..queue import queue_manager


class QueueCommandTest(TestCase):
    """Test queue mode functionality in management command"""
    
    def setUp(self):
        """Set up test data"""
        self.host = ExecutorHost.objects.create(
            name='test-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True,
            max_concurrent_jobs=5
        )
        
        # Create some test jobs
        self.queued_job = ContainerJob.objects.create(
            docker_image='nginx:test-queue',
            command='echo "queue test"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            priority=50,
            max_retries=3
        )
        
        self.scheduled_job = ContainerJob.objects.create(
            docker_image='nginx:test-scheduled',
            command='echo "scheduled test"',
            docker_host=self.host,
            status='queued',
            queued_at=timezone.now(),
            scheduled_for=timezone.now() + timezone.timedelta(hours=1),
            priority=60,
            max_retries=3
        )
        
        self.pending_job = ContainerJob.objects.create(
            docker_image='nginx:test-pending',
            command='echo "pending test"',
            docker_host=self.host,
            status='pending'
        )
    
    def test_queue_mode_dry_run(self):
        """Test queue mode dry run shows correct information"""
        out = StringIO()
        call_command(
            'process_container_jobs',
            '--queue-mode',
            '--dry-run',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Queue Status (dry run)', output)
        self.assertIn('Ready to launch now: 1', output)  # queued_job
        self.assertIn('Scheduled for future: 1', output)  # scheduled_job
        self.assertIn('Currently running: 0', output)
        self.assertIn('Next 1 job(s) that would be launched', output)
        self.assertIn(str(self.queued_job.id), output)
    
    def test_queue_mode_once(self):
        """Test queue mode processes once and exits"""
        out = StringIO()
        
        # Mock the queue manager launch to avoid actual execution
        with patch.object(queue_manager, 'launch_next_batch') as mock_launch:
            mock_launch.return_value = {'launched': 1, 'errors': []}
            
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--once',
                '--max-concurrent=2',
                stdout=out
            )
        
        output = out.getvalue()
        self.assertIn('Starting queue processor', output)
        self.assertIn('max_concurrent=2', output)
        self.assertIn('once=True', output)
        self.assertIn('Processed queue: launched 1 jobs', output)
        
        # Verify the mock was called with correct arguments
        mock_launch.assert_called_once_with(max_concurrent=2, timeout=30)
    
    def test_queue_mode_continuous_with_shutdown(self):
        """Test continuous queue mode with shutdown event"""
        out = StringIO()
        
        with patch.object(queue_manager, 'process_queue_continuous') as mock_continuous:
            mock_continuous.return_value = {
                'iterations': 3,
                'jobs_launched': 2,
                'errors': ['test error']
            }
            
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--max-concurrent=3',
                '--poll-interval=5',
                stdout=out
            )
        
        output = out.getvalue()
        self.assertIn('Starting queue processor', output)
        self.assertIn('max_concurrent=3', output)
        self.assertIn('poll_interval=5s', output)
        self.assertIn('once=False', output)
        self.assertIn('Processed 3 iterations', output)
        self.assertIn('launched 2 jobs', output)
        self.assertIn('Encountered 1 errors', output)
        
        # Verify mock was called with threading event
        mock_continuous.assert_called_once()
        args, kwargs = mock_continuous.call_args
        self.assertEqual(kwargs['max_concurrent'], 3)
        self.assertEqual(kwargs['poll_interval'], 5)
        self.assertIsInstance(kwargs['shutdown_event'], threading.Event)
    
    def test_legacy_mode_dry_run(self):
        """Test legacy mode dry run (backward compatibility)"""
        out = StringIO()
        call_command(
            'process_container_jobs',
            '--dry-run',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Legacy Mode - Would process', output)
        self.assertIn('pending jobs', output)
        self.assertIn(str(self.pending_job.id), output)
        self.assertIn('Would monitor 0 running jobs', output)
    
    def test_argument_validation_queue_mode_conflicts(self):
        """Test that queue mode conflicts with legacy arguments are caught"""
        conflicting_args = [
            ['--queue-mode', '--host=test'],
            ['--queue-mode', '--single-run'],
            ['--queue-mode', '--cleanup'],
            ['--queue-mode', '--use-factory'],
            ['--queue-mode', '--executor-type=docker'],
        ]
        
        for args in conflicting_args:
            with self.subTest(args=args):
                with self.assertRaises(CommandError) as cm:
                    call_command('process_container_jobs', *args, stdout=StringIO())
                
                self.assertIn('Cannot use', str(cm.exception))
    
    def test_argument_validation_ranges(self):
        """Test argument range validation"""
        invalid_args = [
            ['--max-concurrent=0'],
            ['--max-jobs=0'],
            ['--poll-interval=0'],
            ['--timeout=0'],
        ]
        
        for args in invalid_args:
            with self.subTest(args=args):
                with self.assertRaises(CommandError) as cm:
                    call_command('process_container_jobs', *args, stdout=StringIO())
                
                self.assertIn('must be at least 1', str(cm.exception))
    
    def test_verbose_logging(self):
        """Test that verbose flag enables debug logging"""
        out = StringIO()
        
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            with patch.object(queue_manager, 'launch_next_batch') as mock_launch:
                mock_launch.return_value = {'launched': 0, 'errors': []}
                
                call_command(
                    'process_container_jobs',
                    '--queue-mode',
                    '--once',
                    '--verbose',
                    stdout=out
                )
        
        # Verify logging level was set
        mock_get_logger.assert_called_with('container_manager')
        import logging
        mock_logger.setLevel.assert_called_with(logging.DEBUG)
    
    def test_help_output_includes_examples(self):
        """Test that help output includes usage examples"""
        out = StringIO()
        
        with self.assertRaises(SystemExit):  # Django exits after showing help
            call_command('process_container_jobs', '--help', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Queue Mode (recommended):', output)
        self.assertIn('--queue-mode', output)
        self.assertIn('Legacy Mode (existing behavior):', output)
        self.assertIn('kill -USR1', output)
        self.assertIn('Examples:', output)
    
    def test_queue_mode_with_errors(self):
        """Test queue mode handles errors correctly"""
        out = StringIO()
        
        with patch.object(queue_manager, 'launch_next_batch') as mock_launch:
            mock_launch.return_value = {
                'launched': 1, 
                'errors': ['Error 1: Connection failed', 'Error 2: Resource unavailable']
            }
            
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--once',
                stdout=out
            )
        
        output = out.getvalue()
        self.assertIn('Processed queue: launched 1 jobs', output)
        self.assertIn('Encountered 2 errors:', output)
        self.assertIn('Error 1: Connection failed', output)
        self.assertIn('Error 2: Resource unavailable', output)
    
    def test_signal_handlers_setup(self):
        """Test that appropriate signal handlers are set up for each mode"""
        # Test queue mode signal setup
        with patch('signal.signal') as mock_signal:
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--dry-run',
                stdout=StringIO()
            )
            
            # Should set up SIGTERM, SIGINT, and potentially SIGUSR1
            signal_calls = [call[0] for call in mock_signal.call_args_list]
            import signal
            self.assertIn((signal.SIGTERM,), [call[:1] for call in signal_calls])
            self.assertIn((signal.SIGINT,), [call[:1] for call in signal_calls])
    
    def test_backward_compatibility_legacy_mode(self):
        """Test that legacy mode works without queue arguments"""
        out = StringIO()
        
        # Mock the legacy processing methods
        with patch('container_manager.management.commands.process_container_jobs.Command._run_processing_loop') as mock_loop:
            mock_loop.return_value = (2, 0)  # processed_count, error_count
            
            with patch('container_manager.management.commands.process_container_jobs.Command._validate_host_filter'):
                call_command(
                    'process_container_jobs',
                    '--single-run',
                    '--max-jobs=5',
                    stdout=out
                )
        
        output = out.getvalue()
        # Should use legacy startup messages
        self.assertIn('Starting container job processor', output)
        self.assertIn('Direct Docker', output)  # routing mode
        self.assertIn('Job processor stopped', output)


class QueueCommandIntegrationTest(TestCase):
    """Integration tests for queue command with actual queue operations"""
    
    def setUp(self):
        """Set up test data"""
        self.host = ExecutorHost.objects.create(
            name='test-integration-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True,
            max_concurrent_jobs=3
        )
    
    def test_queue_mode_integration_dry_run(self):
        """Integration test: queue mode dry run with real queue operations"""
        # Create a job and queue it
        job = ContainerJob.objects.create(
            docker_image='nginx:integration-test',
            command='echo "integration test"',
            docker_host=self.host,
            priority=70,
            max_retries=2
        )
        
        # Queue the job using the queue manager
        queue_manager.queue_job(job)
        
        # Run dry run and verify output
        out = StringIO()
        call_command(
            'process_container_jobs',
            '--queue-mode',
            '--dry-run',
            '--max-concurrent=1',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Ready to launch now: 1', output)
        self.assertIn('Next 1 job(s) that would be launched', output)
        self.assertIn(f'Job {job.id}', output)
        self.assertIn('priority=70', output)
    
    def test_queue_metrics_in_dry_run(self):
        """Test that queue metrics are correctly displayed in dry run"""
        # Create different types of jobs
        ready_job = ContainerJob.objects.create(
            docker_image='nginx:ready',
            command='echo "ready"',
            docker_host=self.host
        )
        queue_manager.queue_job(ready_job)  # Ready now
        
        scheduled_job = ContainerJob.objects.create(
            docker_image='nginx:scheduled',
            command='echo "scheduled"',
            docker_host=self.host
        )
        queue_manager.queue_job(scheduled_job, schedule_for=timezone.now() + timezone.timedelta(hours=1))
        
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
            retry_count=3,  # Exceeds max_retries (default 3)
            max_retries=3
        )
        queue_manager.queue_job(failed_job)  # Will be launch_failed
        
        out = StringIO()
        call_command(
            'process_container_jobs',
            '--queue-mode',
            '--dry-run',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Ready to launch now: 1', output)  # ready_job
        self.assertIn('Scheduled for future: 1', output)  # scheduled_job  
        self.assertIn('Currently running: 1', output)  # running_job
        self.assertIn('Launch failed: 1', output)  # failed_job