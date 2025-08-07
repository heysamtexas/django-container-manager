"""
Core state machine tests - focused on essential state transition behavior only.
Trimmed from 17 tests to ~8 essential tests, removing complex concurrency tests.
"""

from django.test import TestCase

from ..models import ContainerJob, ExecutorHost


class StateMachineBasicTest(TestCase):
    """Essential state machine tests only"""

    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name="test-state-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )
        self.job = ContainerJob.objects.create(
            name="state-test-job",
            command="echo state test",
            docker_image="python:3.9",
            docker_host=self.host,
        )

    def test_initial_state(self):
        """Test job starts in pending state"""
        self.assertEqual(self.job.status, "pending")

    def test_valid_state_transitions(self):
        """Test valid state transitions work"""
        # pending -> queued
        self.assertTrue(self.job.can_transition_to("queued"))
        self.job.transition_to("queued")
        self.assertEqual(self.job.status, "queued")

        # queued -> running
        self.assertTrue(self.job.can_transition_to("running"))
        self.job.transition_to("running")
        self.assertEqual(self.job.status, "running")

        # running -> completed
        self.assertTrue(self.job.can_transition_to("completed"))
        self.job.transition_to("completed")
        self.assertEqual(self.job.status, "completed")

    def test_invalid_state_transitions(self):
        """Test invalid state transitions are rejected"""
        # pending -> completed (skip intermediate states)
        self.assertFalse(self.job.can_transition_to("completed"))
        with self.assertRaises(ValueError):
            self.job.transition_to("completed")

    def test_terminal_states_cannot_transition(self):
        """Test terminal states (completed, cancelled, failed) cannot transition"""
        # Move to completed state
        self.job.transition_to("running")
        self.job.transition_to("completed")

        # Cannot transition from completed
        self.assertFalse(self.job.can_transition_to("running"))
        self.assertFalse(self.job.can_transition_to("queued"))

    def test_cancellation_from_various_states(self):
        """Test jobs can be cancelled from most states"""
        # From pending
        self.assertTrue(self.job.can_transition_to("cancelled"))

        # From queued
        self.job.transition_to("queued")
        self.assertTrue(self.job.can_transition_to("cancelled"))

        # From running
        self.job.transition_to("running")
        self.assertTrue(self.job.can_transition_to("cancelled"))

    def test_retry_transitions(self):
        """Test retry-related state transitions"""
        # Move to failed state
        self.job.transition_to("running")
        self.job.transition_to("failed")
        self.assertEqual(self.job.status, "failed")

        # Failed jobs can transition to retrying
        self.assertTrue(self.job.can_transition_to("retrying"))
        self.job.transition_to("retrying")
        self.assertEqual(self.job.status, "retrying")

        # Retrying jobs can be queued again
        self.assertTrue(self.job.can_transition_to("queued"))

    def test_queue_state_properties(self):
        """Test queue-related state properties"""
        # Initially not queued
        self.assertFalse(self.job.is_queued)

        # After queuing - need to actually queue it properly
        self.job.mark_as_queued()  # Use the proper queuing method
        self.assertTrue(self.job.is_queued)
        self.assertTrue(self.job.is_ready_to_launch)

        # After launching
        self.job.transition_to("running")
        self.assertFalse(self.job.is_ready_to_launch)  # Already launched

    def test_state_machine_validation_on_save(self):
        """Test state machine validation during model save"""
        # Direct invalid status assignment should be caught on save
        self.job.status = "completed"  # Invalid direct transition
        with self.assertRaises(ValueError):
            self.job.save()
