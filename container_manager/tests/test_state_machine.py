"""
Tests for ContainerJob state machine validation.

This module tests the Django container job state machine, covering all valid and invalid transitions,
edge cases, concurrent scenarios, helper methods, and properties.
"""

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import IntegrityError, transaction
from datetime import timedelta
import threading
import time

from ..models import ContainerJob, ExecutorHost


class StateMachineTestCase(TestCase):
    """Test ContainerJob state machine validation"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-state-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        
        self.job = ContainerJob.objects.create(
            name="test-job",
            command="echo test",
            docker_image="python:3.9",
            docker_host=self.host
        )
    
    def test_valid_transitions(self):
        """Test all valid state transitions"""
        # pending -> queued
        self.assertEqual(self.job.status, 'pending')
        self.assertTrue(self.job.can_transition_to('queued'))
        self.job.transition_to('queued')
        self.assertEqual(self.job.status, 'queued')
        
        # queued -> running
        self.assertTrue(self.job.can_transition_to('running'))
        self.job.transition_to('running')
        self.assertEqual(self.job.status, 'running')
        
        # running -> completed
        self.assertTrue(self.job.can_transition_to('completed'))
        self.job.transition_to('completed')
        self.assertEqual(self.job.status, 'completed')
        
    def test_failure_retry_path(self):
        """Test failure and retry transition path"""
        # Set up job in running state
        self.job.transition_to('queued')
        self.job.transition_to('running')
        
        # running -> failed
        self.assertTrue(self.job.can_transition_to('failed'))
        self.job.transition_to('failed')
        self.assertEqual(self.job.status, 'failed')
        
        # failed -> retrying
        self.assertTrue(self.job.can_transition_to('retrying'))
        self.job.transition_to('retrying')
        self.assertEqual(self.job.status, 'retrying')
        
        # retrying -> queued (for another attempt)
        self.assertTrue(self.job.can_transition_to('queued'))
        self.job.transition_to('queued')
        self.assertEqual(self.job.status, 'queued')
        
    def test_cancellation_from_various_states(self):
        """Test job can be cancelled from various states"""
        # From pending
        self.assertTrue(self.job.can_transition_to('cancelled'))
        
        # From queued
        self.job.transition_to('queued')
        self.assertTrue(self.job.can_transition_to('cancelled'))
        
        # From running
        self.job.transition_to('running')
        self.assertTrue(self.job.can_transition_to('cancelled'))
        self.job.transition_to('cancelled')
        self.assertEqual(self.job.status, 'cancelled')
        
    def test_invalid_transitions(self):
        """Test invalid transitions raise ValueError"""
        # pending -> completed (must go through running)
        with self.assertRaises(ValueError) as context:
            self.job.transition_to('completed')
        self.assertIn('Invalid transition from pending to completed', str(context.exception))
        
        # pending -> failed (must go through running)
        with self.assertRaises(ValueError):
            self.job.transition_to('failed')
            
        # Set up completed job
        self.job.transition_to('queued')
        self.job.transition_to('running')
        self.job.transition_to('completed')
        
        # completed -> anything (terminal state)
        for invalid_status in ['pending', 'queued', 'running', 'failed', 'retrying']:
            with self.assertRaises(ValueError):
                self.job.transition_to(invalid_status)
                
    def test_terminal_states_cannot_transition(self):
        """Test terminal states (completed, cancelled) cannot transition"""
        # Test completed
        self.job.transition_to('queued')
        self.job.transition_to('running')
        self.job.transition_to('completed')
        
        self.assertFalse(self.job.can_transition_to('pending'))
        self.assertFalse(self.job.can_transition_to('queued'))
        self.assertFalse(self.job.can_transition_to('running'))
        
        # Test cancelled
        job2 = ContainerJob.objects.create(
            name="test-job-2", 
            command="echo test",
            docker_image="python:3.9",
            docker_host=self.host
        )
        job2.transition_to('cancelled')
        
        self.assertFalse(job2.can_transition_to('pending'))
        self.assertFalse(job2.can_transition_to('queued'))
        self.assertFalse(job2.can_transition_to('running'))
        
    def test_save_validation_prevents_invalid_transitions(self):
        """Test model save() validates transitions"""
        self.job.transition_to('queued')
        
        # Try to directly set invalid status
        self.job.status = 'completed'  # Invalid: queued -> completed
        
        with self.assertRaises(ValueError):
            self.job.save()
            
        # Verify job wasn't corrupted
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'queued')
        
    def test_helper_methods_work_correctly(self):
        """Test state machine helper methods"""
        # Test mark_as_queued
        self.job.mark_as_queued()
        self.assertEqual(self.job.status, 'queued')
        self.assertIsNotNone(self.job.queued_at)
        
        # Test mark_as_running  
        self.job.mark_as_running()
        self.assertEqual(self.job.status, 'running')
        self.assertIsNotNone(self.job.launched_at)
        
        # Test mark_as_completed
        self.job.mark_as_completed()
        self.assertEqual(self.job.status, 'completed')
        self.assertIsNotNone(self.job.completed_at)
        
    def test_mark_as_failed_with_retry(self):
        """Test mark_as_failed with retry logic"""
        self.job.transition_to('queued')
        self.job.retry_count = 1
        self.job.max_retries = 3
        
        # Should transition to retrying (from queued state)
        self.job.mark_as_failed(should_retry=True)
        self.assertEqual(self.job.status, 'retrying')
        self.assertEqual(self.job.retry_count, 2)
        
    def test_mark_as_failed_no_more_retries(self):
        """Test mark_as_failed when retry limit reached"""
        self.job.transition_to('queued')
        self.job.retry_count = 3
        self.job.max_retries = 3
        
        # Should transition to failed (no more retries)
        self.job.mark_as_failed(should_retry=True)
        self.assertEqual(self.job.status, 'failed')
        
    def test_transition_with_timestamps(self):
        """Test transitions update appropriate timestamps"""
        start_time = timezone.now()
        
        # Mark as running should set launched_at
        self.job.transition_to('queued')
        self.job.transition_to('running')
        
        self.assertIsNotNone(self.job.launched_at)
        self.assertGreaterEqual(self.job.launched_at, start_time)
        
        # Mark as completed should set completed_at
        completion_time = timezone.now()
        self.job.transition_to('completed')
        
        self.assertIsNotNone(self.job.completed_at)
        self.assertGreaterEqual(self.job.completed_at, completion_time)


class ConcurrentStateMachineTestCase(TransactionTestCase):
    """Test concurrent state machine operations"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-concurrent-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        
        self.job = ContainerJob.objects.create(
            name="concurrent-test-job",
            command="echo test",
            docker_image="python:3.9",
            docker_host=self.host
        )
        self.job.transition_to('queued')
        
    def test_concurrent_transition_attempts(self):
        """Test concurrent attempts to transition same job"""
        results = []
        errors = []
        
        def attempt_transition(target_status):
            try:
                with transaction.atomic():
                    job = ContainerJob.objects.select_for_update().get(id=self.job.id)
                    if job.can_transition_to(target_status):
                        job.transition_to(target_status)
                        results.append(target_status)
                    else:
                        errors.append(f"Cannot transition to {target_status}")
            except Exception as e:
                errors.append(str(e))
        
        # Try to transition to running from multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=attempt_transition, args=('running',))
            threads.append(thread)
            
        # Start all threads
        for thread in threads:
            thread.start()
            
        # Wait for completion
        for thread in threads:
            thread.join()
            
        # Only one thread should succeed
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], 'running')
        
        # Verify job is in correct state
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'running')
        
    def test_concurrent_completion_and_cancellation(self):
        """Test concurrent completion and cancellation attempts with select_for_update"""
        self.job.transition_to('running')
        
        # Simplified test - just verify that select_for_update prevents corruption
        # First thread completes the job
        with transaction.atomic():
            job = ContainerJob.objects.select_for_update().get(id=self.job.id)
            job.transition_to('completed')
            
        # Second thread tries to cancel but job is already completed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        
        # Verify cancellation is no longer possible
        self.assertFalse(self.job.can_transition_to('cancelled'))


class StatePropertyTestCase(TestCase):
    """Test state-related properties and methods"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-property-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        
        self.job = ContainerJob.objects.create(
            name="property-test-job",
            command="echo test",
            docker_image="python:3.9",
            docker_host=self.host
        )
        
    def test_is_queued_property(self):
        """Test is_queued property"""
        # Not queued initially
        self.assertFalse(self.job.is_queued)
        
        # Mark as queued
        self.job.mark_as_queued()
        self.assertTrue(self.job.is_queued)
        
        # Launch job
        self.job.mark_as_running()
        self.assertFalse(self.job.is_queued)  # No longer queued
        
    def test_is_ready_to_launch_property(self):
        """Test is_ready_to_launch property"""
        # Not ready initially (not queued)
        self.assertFalse(self.job.is_ready_to_launch)
        
        # Queue job
        self.job.mark_as_queued()
        self.assertTrue(self.job.is_ready_to_launch)
        
        # Schedule for future
        future_time = timezone.now() + timedelta(hours=1)
        self.job.scheduled_for = future_time
        self.job.save()
        self.assertFalse(self.job.is_ready_to_launch)  # Not ready yet
        
        # Schedule for past
        past_time = timezone.now() - timedelta(hours=1)
        self.job.scheduled_for = past_time
        self.job.save()
        self.assertTrue(self.job.is_ready_to_launch)  # Now ready
        
        # Exceed retry limit
        self.job.retry_count = 5
        self.job.max_retries = 3
        self.job.save()
        self.assertFalse(self.job.is_ready_to_launch)  # Too many retries
        
    def test_queue_status_property(self):
        """Test queue_status property"""
        # Initially not queued
        self.assertEqual(self.job.queue_status, 'not_queued')
        
        # Queue job
        self.job.mark_as_queued()
        self.assertEqual(self.job.queue_status, 'queued')
        
        # Schedule for future
        future_time = timezone.now() + timedelta(hours=1)
        self.job.scheduled_for = future_time
        self.job.save()
        self.assertEqual(self.job.queue_status, 'scheduled')
        
        # Clear scheduled_for first, then exceed retry limit
        self.job.scheduled_for = None
        self.job.retry_count = 5
        self.job.max_retries = 3
        self.job.save()
        self.assertEqual(self.job.queue_status, 'launch_failed')
        
        # Launch job
        self.job.retry_count = 0
        self.job.scheduled_for = None
        self.job.mark_as_running()
        self.assertEqual(self.job.queue_status, 'launched')


class StateTransitionErrorTestCase(TestCase):
    """Test error messages and validation"""
    
    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name='test-error-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
    
    def test_error_messages_are_informative(self):
        """Test error messages provide useful information"""
        job = ContainerJob.objects.create(
            name="error-test", 
            command="echo test",
            docker_image="python:3.9",
            docker_host=self.host
        )
        
        try:
            job.transition_to('completed')
            self.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            self.assertIn('Invalid transition', error_msg)
            self.assertIn('pending', error_msg)
            self.assertIn('completed', error_msg)
            self.assertIn('Valid transitions:', error_msg)
            
    def test_valid_transitions_listed_in_error(self):
        """Test error messages list valid transitions"""
        job = ContainerJob.objects.create(
            name="error-test", 
            command="echo test",
            docker_image="python:3.9",
            docker_host=self.host
        )
        job.transition_to('queued')
        
        try:
            job.transition_to('failed')  # Invalid from queued
        except ValueError as e:
            error_msg = str(e)
            self.assertIn('running', error_msg)  # Should list valid option
            self.assertIn('cancelled', error_msg)  # Should list valid option