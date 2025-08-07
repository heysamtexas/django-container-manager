"""
Core queue and retry tests - focused on essential queue behavior only.
Trimmed from 18 retry tests + 13 command tests to ~10 essential tests.
"""

from unittest.mock import patch

from django.test import TestCase

from ..models import ContainerJob, ExecutorHost
from ..queue import JobQueueManager


class QueueManagerCoreTest(TestCase):
    """Essential queue management tests only"""

    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name="queue-test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            executor_type="mock",
        )
        self.job = ContainerJob.objects.create(
            name="queue-test-job",
            command="echo queue test",
            docker_image="python:3.9",
            docker_host=self.host,
        )
        self.queue_manager = JobQueueManager()

    def test_queue_job_basic(self):
        """Test basic job queuing"""
        self.queue_manager.queue_job(self.job)

        self.job.refresh_from_db()
        self.assertTrue(self.job.is_queued)
        self.assertEqual(self.job.status, "queued")

    def test_queue_job_with_priority(self):
        """Test job queuing with priority"""
        self.queue_manager.queue_job(self.job, priority=80)

        self.job.refresh_from_db()
        self.assertEqual(self.job.priority, 80)

    def test_get_ready_jobs(self):
        """Test getting ready jobs from queue"""
        # Queue the job
        self.queue_manager.queue_job(self.job)

        # Should be ready
        ready_jobs = self.queue_manager.get_ready_jobs()
        self.assertIn(self.job, ready_jobs)

    @patch("container_manager.services.launch_job")
    def test_launch_job_success(self, mock_launch):
        """Test successful job launch"""
        mock_launch.return_value = {
            "success": True,
            "execution_id": "queue-success-123",
        }

        self.queue_manager.queue_job(self.job)
        result = self.queue_manager.launch_job(self.job)

        self.assertTrue(result["success"])

    @patch("container_manager.services.launch_job")
    def test_launch_job_failure_with_retry(self, mock_launch):
        """Test job launch failure triggers retry logic"""
        mock_launch.return_value = {
            "success": False,
            "error": "Connection refused to Docker daemon",
        }

        self.queue_manager.queue_job(self.job)
        result = self.queue_manager.launch_job_with_retry(self.job)

        self.assertFalse(result["success"])
        self.assertTrue(result["retry_scheduled"])

        # Job should be scheduled for retry
        self.job.refresh_from_db()
        self.assertEqual(self.job.retry_count, 1)
        self.assertIsNotNone(self.job.scheduled_for)

    @patch("container_manager.services.launch_job")
    def test_permanent_error_no_retry(self, mock_launch):
        """Test permanent errors don't trigger retry"""
        mock_launch.return_value = {
            "success": False,
            "error": "Image not found: nonexistent:latest",
        }

        self.queue_manager.queue_job(self.job)
        result = self.queue_manager.launch_job_with_retry(self.job)

        self.assertFalse(result["success"])
        self.assertFalse(result["retry_scheduled"])

        # Job should be marked as failed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "failed")

    def test_queue_stats(self):
        """Test queue statistics"""
        # Initially empty
        stats = self.queue_manager.get_queue_stats()
        self.assertEqual(stats["queued"], 0)

        # Queue a job
        self.queue_manager.queue_job(self.job)

        stats = self.queue_manager.get_queue_stats()
        self.assertEqual(stats["queued"], 1)

    def test_retry_failed_job(self):
        """Test manual retry of failed job"""
        # Transition properly to failed state
        self.job.transition_to("running")
        self.job.transition_to("failed")

        # Retry it
        success = self.queue_manager.retry_failed_job(self.job)

        self.assertTrue(success)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "queued")

    def test_dequeue_job(self):
        """Test removing job from queue"""
        # Queue the job
        self.queue_manager.queue_job(self.job)
        self.assertTrue(self.job.is_queued)

        # Dequeue it
        self.queue_manager.dequeue_job(self.job)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_queued)

    @patch("container_manager.services.launch_job")
    def test_batch_launch(self, mock_launch):
        """Test launching multiple jobs in batch"""
        # Mock successful launch
        mock_launch.return_value = {"success": True, "execution_id": "batch-test"}

        # Create and queue multiple jobs
        jobs = []
        for i in range(3):
            job = ContainerJob.objects.create(
                name=f"batch-job-{i}",
                command=f"echo batch {i}",
                docker_image="python:3.9",
                docker_host=self.host,
            )
            self.queue_manager.queue_job(job)
            jobs.append(job)

        # Launch batch
        result = self.queue_manager.launch_next_batch(max_concurrent=3)

        self.assertEqual(result["launched"], 3)
        self.assertEqual(len(result["errors"]), 0)
