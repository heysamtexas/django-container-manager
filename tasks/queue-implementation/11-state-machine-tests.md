# Task: State Machine Validation Tests

## Objective
Comprehensive test suite for state machine validation, covering all valid and invalid transitions, edge cases, and concurrent scenarios.

## Success Criteria
- [ ] Test all valid state transitions work
- [ ] Test all invalid transitions raise appropriate errors
- [ ] Test terminal states cannot transition
- [ ] Test concurrent state changes are handled safely
- [ ] Test helper methods work correctly
- [ ] Test database constraints enforce rules
- [ ] All tests pass consistently

## Implementation Details

### Core State Machine Tests

```python
# tests/test_state_machine.py
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import IntegrityError, transaction
from container_manager.models import ContainerJob
import threading
import time

class StateMachineTestCase(TestCase):
    """Test ContainerJob state machine validation"""
    
    def setUp(self):
        self.job = ContainerJob.objects.create(
            name="test-job",
            command="echo test",
            docker_image="python:3.9"
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
        job2 = ContainerJob.objects.create(name="test-job-2", command="echo test")
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
        self.job.transition_to('running')
        self.job.retry_count = 1
        self.job.max_retries = 3
        
        # Should transition to retrying
        self.job.mark_as_failed(should_retry=True)
        self.assertEqual(self.job.status, 'retrying')
        self.assertEqual(self.job.retry_count, 2)
        
    def test_mark_as_failed_no_more_retries(self):
        """Test mark_as_failed when retry limit reached"""
        self.job.transition_to('queued')
        self.job.transition_to('running')
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
        self.job = ContainerJob.objects.create(
            name="concurrent-test-job",
            command="echo test",
            docker_image="python:3.9"
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
        """Test concurrent completion and cancellation attempts"""
        self.job.transition_to('running')
        
        results = []
        
        def attempt_completion():
            try:
                with transaction.atomic():
                    job = ContainerJob.objects.select_for_update().get(id=self.job.id)
                    if job.can_transition_to('completed'):
                        job.transition_to('completed')
                        results.append('completed')
            except Exception:
                pass  # Expected for losing thread
                
        def attempt_cancellation():
            try:
                with transaction.atomic():
                    job = ContainerJob.objects.select_for_update().get(id=self.job.id)
                    if job.can_transition_to('cancelled'):
                        job.transition_to('cancelled')
                        results.append('cancelled')
            except Exception:
                pass  # Expected for losing thread
                
        # Start both operations simultaneously
        thread1 = threading.Thread(target=attempt_completion)
        thread2 = threading.Thread(target=attempt_cancellation)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Only one should succeed
        self.assertEqual(len(results), 1)
        self.assertIn(results[0], ['completed', 'cancelled'])
        
        # Verify job is in correct terminal state
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, results[0])

class StatePropertyTestCase(TestCase):
    """Test state-related properties and methods"""
    
    def setUp(self):
        self.job = ContainerJob.objects.create(
            name="property-test-job",
            command="echo test"
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
        future_time = timezone.now() + timezone.timedelta(hours=1)
        self.job.scheduled_for = future_time
        self.job.save()
        self.assertFalse(self.job.is_ready_to_launch)  # Not ready yet
        
        # Schedule for past
        past_time = timezone.now() - timezone.timedelta(hours=1)
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
        future_time = timezone.now() + timezone.timedelta(hours=1)
        self.job.scheduled_for = future_time
        self.job.save()
        self.assertEqual(self.job.queue_status, 'scheduled')
        
        # Exceed retry limit
        self.job.retry_count = 5
        self.job.max_retries = 3
        self.job.save()
        self.assertEqual(self.job.queue_status, 'launch_failed')
        
        # Launch job
        self.job.retry_count = 0
        self.job.scheduled_for = None
        self.job.mark_as_running()
        self.assertEqual(self.job.queue_status, 'launched')
```

### Error Message Tests

```python
# Add to existing test file
class StateTransitionErrorTestCase(TestCase):
    """Test error messages and validation"""
    
    def test_error_messages_are_informative(self):
        """Test error messages provide useful information"""
        job = ContainerJob.objects.create(name="error-test", command="echo test")
        
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
        job = ContainerJob.objects.create(name="error-test", command="echo test")
        job.transition_to('queued')
        
        try:
            job.transition_to('failed')  # Invalid from queued
        except ValueError as e:
            error_msg = str(e)
            self.assertIn('running', error_msg)  # Should list valid option
            self.assertIn('cancelled', error_msg)  # Should list valid option
```

## Files to Create
- `tests/test_state_machine.py` - Comprehensive state machine tests

## Testing Commands

```bash
# Run state machine tests specifically
python manage.py test tests.test_state_machine

# Run with verbose output
python manage.py test tests.test_state_machine --verbosity=2

# Run specific test case
python manage.py test tests.test_state_machine.StateMachineTestCase.test_valid_transitions

# Run concurrent tests (requires TransactionTestCase)
python manage.py test tests.test_state_machine.ConcurrentStateMachineTestCase
```

## Dependencies
- Depends on: `02-state-machine-validation.md` (state machine implementation)
- Depends on: `01-queue-model-fields.md` (model fields and properties)

## Test Coverage Requirements
- [ ] All valid transitions: 100% coverage
- [ ] All invalid transitions: 100% coverage  
- [ ] Helper methods: 100% coverage
- [ ] Properties: 100% coverage
- [ ] Concurrent scenarios: Critical paths covered
- [ ] Error messages: Validate clarity and completeness

## Performance Considerations
- Use `TransactionTestCase` for concurrent tests (slower but necessary)
- Use regular `TestCase` for non-concurrent tests (faster)
- Mock external dependencies in state transition tests
- Use `select_for_update()` in concurrent test scenarios

## Notes
- Comprehensive coverage prevents state corruption bugs
- Concurrent tests catch race condition issues
- Error message tests ensure good developer experience  
- Property tests validate business logic
- Helper method tests ensure clean API usage
- Database constraint tests add additional safety