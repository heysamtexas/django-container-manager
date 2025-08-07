"""
Tests for graceful shutdown and signal handling functionality.

This module tests the enhanced signal handling, job completion tracking,
and graceful shutdown coordination for queue processors.
"""

import threading
import time
import signal
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock, call
from io import StringIO

from ..models import ContainerJob, ExecutorHost
from ..signals import GracefulShutdown, JobCompletionTracker
from ..queue import queue_manager


class GracefulShutdownTest(TestCase):
    """Test GracefulShutdown signal handling"""
    
    def setUp(self):
        self.shutdown_handler = GracefulShutdown(timeout=5)
    
    def test_shutdown_event_initialization(self):
        """Test that shutdown handler initializes correctly"""
        self.assertFalse(self.shutdown_handler.is_shutdown_requested())
        self.assertEqual(self.shutdown_handler.timeout, 5)
        self.assertIsNone(self.shutdown_handler.stats['shutdown_initiated'])
    
    def test_manual_shutdown_trigger(self):
        """Test manual shutdown event triggering"""
        # Initially not requested
        self.assertFalse(self.shutdown_handler.is_shutdown_requested())
        
        # Manually trigger shutdown
        self.shutdown_handler.shutdown_event.set()
        
        # Should now be requested
        self.assertTrue(self.shutdown_handler.is_shutdown_requested())
    
    def test_wait_for_shutdown_timeout(self):
        """Test wait_for_shutdown returns False on timeout"""
        start_time = time.time()
        result = self.shutdown_handler.wait_for_shutdown(poll_interval=0.1)
        elapsed = time.time() - start_time
        
        self.assertFalse(result)
        self.assertLess(elapsed, 0.2)  # Should timeout quickly
    
    def test_wait_for_shutdown_triggered(self):
        """Test wait_for_shutdown returns True when triggered"""
        # Start shutdown in background after short delay
        def trigger_shutdown():
            time.sleep(0.1)
            self.shutdown_handler.shutdown_event.set()
        
        trigger_thread = threading.Thread(target=trigger_shutdown)
        trigger_thread.start()
        
        # Should return True when shutdown is triggered
        result = self.shutdown_handler.wait_for_shutdown(poll_interval=1.0)
        self.assertTrue(result)
        
        trigger_thread.join()
    
    def test_timeout_checking(self):
        """Test shutdown timeout detection"""
        # No start time set - no timeout
        self.assertFalse(self.shutdown_handler.check_timeout())
        
        # Set start time in the past
        self.shutdown_handler.start_time = time.time() - 10
        
        # Should detect timeout
        self.assertTrue(self.shutdown_handler.check_timeout())
    
    @patch('builtins.print')
    def test_default_status_report(self, mock_print):
        """Test default status reporting functionality"""
        with patch.object(queue_manager, 'get_worker_metrics') as mock_metrics:
            mock_metrics.return_value = {'ready_now': 5, 'running': 2}
            
            self.shutdown_handler._default_status_report()
            
            # Should call metrics and print status
            mock_metrics.assert_called_once()
            mock_print.assert_called_once()


class JobCompletionTrackerTest(TestCase):
    """Test JobCompletionTracker functionality"""
    
    def setUp(self):
        self.tracker = JobCompletionTracker()
    
    def test_job_tracking_lifecycle(self):
        """Test full job tracking lifecycle"""
        # Initially empty
        self.assertEqual(self.tracker.get_running_count(), 0)
        self.assertEqual(len(self.tracker.get_running_jobs()), 0)
        
        # Add running jobs
        self.tracker.add_running_job('job-1')
        self.tracker.add_running_job('job-2')
        
        self.assertEqual(self.tracker.get_running_count(), 2)
        self.assertIn('job-1', self.tracker.get_running_jobs())
        self.assertIn('job-2', self.tracker.get_running_jobs())
        
        # Complete one job
        self.tracker.mark_job_completed('job-1')
        
        self.assertEqual(self.tracker.get_running_count(), 1)
        self.assertNotIn('job-1', self.tracker.get_running_jobs())
        self.assertIn('job-2', self.tracker.get_running_jobs())
        
        # Complete remaining job
        self.tracker.mark_job_completed('job-2')
        
        self.assertEqual(self.tracker.get_running_count(), 0)
        self.assertEqual(len(self.tracker.get_running_jobs()), 0)
    
    def test_job_id_string_conversion(self):
        """Test that job IDs are converted to strings consistently"""
        # Add with different types
        self.tracker.add_running_job(123)  # Integer
        self.tracker.add_running_job('456')  # String
        
        self.assertEqual(self.tracker.get_running_count(), 2)
        
        # Complete with different types
        self.tracker.mark_job_completed(123)  # Integer
        self.tracker.mark_job_completed('456')  # String
        
        self.assertEqual(self.tracker.get_running_count(), 0)
    
    def test_completion_unknown_job(self):
        """Test completing job that wasn't tracked"""
        # Should not crash
        self.tracker.mark_job_completed('unknown-job')
        self.assertEqual(self.tracker.get_running_count(), 0)
    
    def test_wait_for_completion_immediate(self):
        """Test wait_for_completion when no jobs are running"""
        start_time = time.time()
        result = self.tracker.wait_for_completion(timeout=5, poll_interval=0.1)
        elapsed = time.time() - start_time
        
        self.assertTrue(result)
        self.assertLess(elapsed, 0.5)  # Should return immediately
    
    def test_wait_for_completion_timeout(self):
        """Test wait_for_completion timeout"""
        self.tracker.add_running_job('slow-job')
        
        start_time = time.time()
        result = self.tracker.wait_for_completion(timeout=0.2, poll_interval=0.05)
        elapsed = time.time() - start_time
        
        self.assertFalse(result)  # Should timeout
        self.assertGreaterEqual(elapsed, 0.2)
        self.assertEqual(self.tracker.get_running_count(), 1)  # Job still running
    
    def test_wait_for_completion_success(self):
        """Test successful wait_for_completion"""
        self.tracker.add_running_job('completing-job')
        
        def complete_job():
            time.sleep(0.1)
            self.tracker.mark_job_completed('completing-job')
        
        complete_thread = threading.Thread(target=complete_job)
        complete_thread.start()
        
        result = self.tracker.wait_for_completion(timeout=1, poll_interval=0.05)
        
        self.assertTrue(result)
        self.assertEqual(self.tracker.get_running_count(), 0)
        
        complete_thread.join()
    
    def test_get_stats(self):
        """Test statistics reporting"""
        # Initially empty
        stats = self.tracker.get_stats()
        self.assertEqual(stats['running'], 0)
        self.assertEqual(stats['completed'], 0)
        self.assertEqual(stats['total_tracked'], 0)
        
        # Add and complete jobs
        self.tracker.add_running_job('job-1')
        self.tracker.add_running_job('job-2')
        stats = self.tracker.get_stats()
        self.assertEqual(stats['running'], 2)
        self.assertEqual(stats['completed'], 0)
        self.assertEqual(stats['total_tracked'], 2)
        
        self.tracker.mark_job_completed('job-1')
        stats = self.tracker.get_stats()
        self.assertEqual(stats['running'], 1)
        self.assertEqual(stats['completed'], 1)
        self.assertEqual(stats['total_tracked'], 2)


class GracefulShutdownIntegrationTest(TestCase):
    """Integration tests for graceful shutdown with queue processing"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-graceful-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True,
            max_concurrent_jobs=3
        )
    
    def test_graceful_shutdown_with_no_running_jobs(self):
        """Test graceful shutdown when no jobs are running"""
        # Mock the queue manager methods
        with patch.object(queue_manager, 'get_worker_metrics') as mock_metrics:
            mock_metrics.return_value = {'ready_now': 0, 'running': 0}
            
            with patch.object(queue_manager, 'get_ready_jobs') as mock_ready:
                mock_ready.return_value = []
                
                # Create shutdown handler
                from container_manager.signals import GracefulShutdown
                shutdown_handler = GracefulShutdown(timeout=5)
                
                # Trigger shutdown immediately
                shutdown_handler.shutdown_event.set()
                
                # Process queue with graceful shutdown - should exit cleanly
                stats = queue_manager.process_queue_with_graceful_shutdown(
                    max_concurrent=2,
                    poll_interval=1,
                    shutdown_timeout=5
                )
                
                self.assertEqual(stats['iterations'], 0)  # No iterations since immediate shutdown
                self.assertTrue(stats['clean_shutdown'])
                self.assertEqual(stats['jobs_interrupted'], 0)
    
    def test_graceful_shutdown_coordination(self):
        """Test graceful shutdown signal coordination"""
        # Test that shutdown can be triggered and detected
        shutdown_event = threading.Event()
        
        # Simulate signal handler setting the event
        def trigger_shutdown():
            time.sleep(0.1)
            shutdown_event.set()
        
        trigger_thread = threading.Thread(target=trigger_shutdown)
        trigger_thread.start()
        
        # Wait for shutdown event
        start_time = time.time()
        result = shutdown_event.wait(1.0)
        elapsed = time.time() - start_time
        
        self.assertTrue(result)
        self.assertLess(elapsed, 0.5)  # Should be triggered quickly
        
        trigger_thread.join()
    
    @patch.object(queue_manager, 'launch_job_with_retry')
    @patch.object(queue_manager, 'get_ready_jobs')
    def test_launch_batch_with_tracking(self, mock_get_ready, mock_launch):
        """Test job launching with completion tracking"""
        from container_manager.signals import JobCompletionTracker
        
        # Create test job
        job = ContainerJob.objects.create(
            docker_image='nginx:test-tracking',
            command='echo "tracking test"',
            docker_host=self.host
        )
        
        # Mock ready jobs and successful launch
        mock_get_ready.return_value = [job]
        mock_launch.return_value = {'success': True}
        
        # Create tracker and launch batch
        job_tracker = JobCompletionTracker()
        
        result = queue_manager._launch_batch_with_tracking(
            max_concurrent=5,
            job_tracker=job_tracker
        )
        
        # Verify launch result
        self.assertEqual(result['launched'], 1)
        self.assertEqual(len(result['errors']), 0)
        
        # Verify job is being tracked
        self.assertEqual(job_tracker.get_running_count(), 1)
        self.assertIn(str(job.id), job_tracker.get_running_jobs())
        
        # Verify launch was called
        mock_launch.assert_called_once_with(job)
    
    @patch.object(queue_manager, 'launch_job_with_retry')
    @patch.object(queue_manager, 'get_ready_jobs')
    def test_launch_batch_with_tracking_failure(self, mock_get_ready, mock_launch):
        """Test job launching with tracking when launch fails"""
        from container_manager.signals import JobCompletionTracker
        
        # Create test job
        job = ContainerJob.objects.create(
            docker_image='nginx:test-tracking-fail',
            command='echo "tracking fail test"',
            docker_host=self.host
        )
        
        # Mock ready jobs and failed launch
        mock_get_ready.return_value = [job]
        mock_launch.return_value = {'success': False, 'error': 'Launch failed'}
        
        # Create tracker and launch batch
        job_tracker = JobCompletionTracker()
        
        result = queue_manager._launch_batch_with_tracking(
            max_concurrent=5,
            job_tracker=job_tracker
        )
        
        # Verify launch result
        self.assertEqual(result['launched'], 0)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('Launch failed', result['errors'][0])
        
        # Verify job was removed from tracking after failure
        self.assertEqual(job_tracker.get_running_count(), 0)
        
        # Verify launch was called
        mock_launch.assert_called_once_with(job)


class GracefulShutdownCommandTest(TestCase):
    """Test graceful shutdown functionality in management command"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-command-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
    
    def test_graceful_shutdown_argument_parsing(self):
        """Test that graceful shutdown arguments are parsed correctly"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        
        with patch.object(queue_manager, 'process_queue_with_graceful_shutdown') as mock_graceful:
            mock_graceful.return_value = {
                'iterations': 0,
                'jobs_launched': 0,
                'errors': [],
                'clean_shutdown': True,
                'jobs_interrupted': 0
            }
            
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--graceful-shutdown',
                '--shutdown-timeout=45',
                stdout=out
            )
            
            # Verify graceful shutdown was called with correct timeout
            mock_graceful.assert_called_once()
            args, kwargs = mock_graceful.call_args
            self.assertEqual(kwargs['shutdown_timeout'], 45)
        
        output = out.getvalue()
        self.assertIn('graceful shutdown', output)
        self.assertIn('Clean shutdown completed', output)
    
    def test_basic_vs_graceful_shutdown_modes(self):
        """Test command chooses correct shutdown mode based on flag"""
        from django.core.management import call_command
        from io import StringIO
        
        # Test basic shutdown mode (default)
        with patch.object(queue_manager, 'process_queue_continuous') as mock_basic:
            mock_basic.return_value = {
                'iterations': 1,
                'jobs_launched': 0,
                'errors': []
            }
            
            out = StringIO()
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--once',  # Use once to avoid hanging
                stdout=out
            )
            
            output = out.getvalue()
            self.assertIn('basic shutdown', output)
        
        # Test graceful shutdown mode
        with patch.object(queue_manager, 'process_queue_with_graceful_shutdown') as mock_graceful:
            mock_graceful.return_value = {
                'iterations': 1,
                'jobs_launched': 0,
                'errors': [],
                'clean_shutdown': True,
                'jobs_interrupted': 0
            }
            
            out = StringIO()
            call_command(
                'process_container_jobs',
                '--queue-mode',
                '--graceful-shutdown',
                '--once',  # Use once to avoid hanging
                stdout=out
            )
            
            output = out.getvalue()
            self.assertIn('graceful shutdown', output)
    
    def test_shutdown_timeout_validation(self):
        """Test shutdown timeout argument validation"""
        from django.core.management import call_command, CommandError
        from io import StringIO
        
        with self.assertRaises(CommandError) as cm:
            call_command(
                'process_container_jobs',
                '--shutdown-timeout=0',
                stdout=StringIO()
            )
        
        self.assertIn('--shutdown-timeout must be at least 1', str(cm.exception))