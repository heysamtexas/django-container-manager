"""
Tests for bulk operations.
"""

from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from ..bulk_operations import BulkJobManager
from ..models import ContainerJob, ExecutorHost


class BulkJobManagerTest(TestCase):
    """Test cases for BulkJobManager."""

    def setUp(self):
        self.manager = BulkJobManager()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Templates no longer exist - using direct job configuration

        # Create test hosts
        self.docker_host = ExecutorHost.objects.create(
            name="docker-host",
            # executor_type now determined by docker_host
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

        self.mock_host = ExecutorHost.objects.create(
            name="mock-host",
            executor_type="mock",
            connection_string="mock://test",
            is_active=True,
        )

    def test_create_jobs_bulk_success(self):
        """Test successful bulk job creation."""
        jobs, errors = self.manager.create_jobs_bulk(
            docker_image="alpine:latest",
            count=5,
            user=self.user,
            host=self.docker_host,
            name_pattern="batch-job-{index}",
        )

        self.assertEqual(len(jobs), 5)
        self.assertEqual(len(errors), 0)

        # Check job properties
        for i, job in enumerate(jobs):
            self.assertEqual(job.docker_host, self.docker_host)
            self.assertEqual(job.name, f"batch-job-{i}")
            self.assertEqual(job.created_by, self.user)
            self.assertEqual(job.status, "pending")
            self.assertEqual(job.docker_image, "alpine:latest")

    def test_create_jobs_bulk_with_environment(self):
        """Test bulk job creation with environment variables."""
        env_vars = {"TEST_VAR": "test_value", "BATCH_ID": "batch_001"}

        jobs, errors = self.manager.create_jobs_bulk(
            docker_image="alpine:latest",
            count=3,
            user=self.user,
            host=self.docker_host,
            command="echo 'test command'",
            environment_variables=env_vars,
        )

        self.assertEqual(len(jobs), 3)
        self.assertEqual(len(errors), 0)

        # Check environment variables
        for job in jobs:
            self.assertEqual(job.get_all_environment_variables(), env_vars)
            self.assertEqual(job.command, "echo 'test command'")

    def test_create_jobs_bulk_auto_host_selection(self):
        """Test bulk job creation with automatic host selection."""
        jobs, errors = self.manager.create_jobs_bulk(
            docker_image="alpine:latest",
            count=3,
            user=self.user,
            # No host specified - should select first available
        )

        self.assertEqual(len(jobs), 3)
        self.assertEqual(len(errors), 0)

        # Should have been assigned to an available host
        for job in jobs:
            self.assertIn(job.docker_host.executor_type, ["docker", "mock"])
            self.assertTrue(job.docker_host.is_active)

    def test_create_jobs_bulk_invalid_count(self):
        """Test bulk job creation with invalid count."""
        jobs, errors = self.manager.create_jobs_bulk(
            docker_image="alpine:latest",
            count=0,
            user=self.user,
        )

        self.assertEqual(len(jobs), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("Count must be positive", errors[0])

    def test_create_jobs_bulk_large_count(self):
        """Test bulk job creation with too large count."""
        jobs, errors = self.manager.create_jobs_bulk(
            docker_image="alpine:latest",
            count=15000,
            user=self.user,
        )

        self.assertEqual(len(jobs), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("Maximum bulk creation limit", errors[0])

    def test_bulk_start_jobs(self):
        """Test bulk job starting."""
        # Create pending jobs
        jobs = []
        for i in range(3):
            job = ContainerJob.objects.create(
                docker_image="alpine:latest",
                docker_host=self.mock_host,
                name=f"test-job-{i}",
                # executor_type now determined by docker_host
                status="pending",
                created_by=self.user,
            )
            jobs.append(job)

        with patch.object(
            self.manager.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.launch_job.return_value = (True, "exec_123")
            mock_get_executor.return_value = mock_executor

            started_jobs, errors = self.manager.bulk_start_jobs(jobs)

        self.assertEqual(len(started_jobs), 3)
        self.assertEqual(len(errors), 0)

        # Check job status
        for job in started_jobs:
            job.refresh_from_db()
            self.assertEqual(job.status, "running")
            self.assertIsNotNone(job.started_at)

    def test_bulk_stop_jobs(self):
        """Test bulk job stopping."""
        # Create running jobs
        jobs = []
        for i in range(3):
            job = ContainerJob.objects.create(
                docker_image="alpine:latest",
                docker_host=self.mock_host,
                name=f"test-job-{i}",
                # executor_type now determined by docker_host
                status="running",
                execution_id=f"container_{i}",
                created_by=self.user,
            )
            jobs.append(job)

        with patch.object(
            self.manager.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_get_executor.return_value = mock_executor

            stopped_jobs, errors = self.manager.bulk_stop_jobs(jobs)

        self.assertEqual(len(stopped_jobs), 3)
        self.assertEqual(len(errors), 0)

        # Check job status
        for job in stopped_jobs:
            job.refresh_from_db()
            self.assertEqual(job.status, "cancelled")
            self.assertIsNotNone(job.completed_at)

    def test_bulk_cancel_jobs(self):
        """Test bulk job cancellation."""
        # Create jobs in various states
        pending_job = ContainerJob.objects.create(
            docker_image="alpine:latest",
            docker_host=self.mock_host,
            name="pending-job",
            status="pending",
            created_by=self.user,
        )

        running_job = ContainerJob.objects.create(
            docker_image="alpine:latest",
            docker_host=self.mock_host,
            name="running-job",
            status="running",
            execution_id="container_1",
            created_by=self.user,
        )

        completed_job = ContainerJob.objects.create(
            docker_image="alpine:latest",
            docker_host=self.mock_host,
            name="completed-job",
            status="completed",
            created_by=self.user,
        )

        jobs = [pending_job, running_job, completed_job]

        with patch.object(
            self.manager.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_get_executor.return_value = mock_executor

            cancelled_jobs, errors = self.manager.bulk_cancel_jobs(jobs)

        # Should cancel pending and running jobs, but not completed
        self.assertEqual(len(cancelled_jobs), 2)
        self.assertEqual(len(errors), 0)

        # Check results
        pending_job.refresh_from_db()
        self.assertEqual(pending_job.status, "cancelled")

        running_job.refresh_from_db()
        self.assertEqual(running_job.status, "cancelled")

        completed_job.refresh_from_db()
        self.assertEqual(completed_job.status, "completed")  # Unchanged

    def test_bulk_restart_jobs(self):
        """Test bulk job restarting."""
        # Create completed job
        job = ContainerJob.objects.create(
            docker_image="alpine:latest",
            docker_host=self.mock_host,
            name="completed-job",
            status="completed",
            # executor_type now determined by docker_host
            execution_id="old_container",
            exit_code=0,
            created_by=self.user,
        )

        with patch.object(
            self.manager.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.launch_job.return_value = (True, "new_exec_123")
            mock_get_executor.return_value = mock_executor

            restarted_jobs, errors = self.manager.bulk_restart_jobs([job])

        self.assertEqual(len(restarted_jobs), 1)
        self.assertEqual(len(errors), 0)

        # Check job was reset and restarted
        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertIsNone(job.exit_code)

        # Job is on mock host, so execution_id should be set
        self.assertEqual(job.docker_host.executor_type, "mock")
        self.assertEqual(
            job.docker_host.executor_type, "mock"
        )  # Should match host type
        self.assertEqual(
            job.get_execution_identifier(), "new_exec_123"
        )  # Should be set
        self.assertIsNotNone(job.started_at)

    def test_get_bulk_status(self):
        """Test bulk status reporting."""
        # Create jobs with different statuses
        jobs = []
        statuses = ["pending", "running", "completed", "failed", "completed"]

        for i, status in enumerate(statuses):
            host = self.docker_host if i % 2 == 0 else self.mock_host
            job = ContainerJob.objects.create(
                docker_image="alpine:latest",
                docker_host=host,
                name=f"test-job-{i}",
                # executor_type is now determined by docker_host
                status=status,
                created_by=self.user,
            )
            jobs.append(job)

        status_report = self.manager.get_bulk_status(jobs)

        # Check report structure
        self.assertEqual(status_report["total_jobs"], 5)
        self.assertEqual(status_report["status_counts"]["completed"], 2)
        self.assertEqual(status_report["status_counts"]["pending"], 1)
        self.assertEqual(status_report["status_counts"]["running"], 1)
        self.assertEqual(status_report["status_counts"]["failed"], 1)

        # Check executor counts
        self.assertEqual(status_report["executor_counts"]["docker"], 3)
        self.assertEqual(status_report["executor_counts"]["mock"], 2)

        # Check success rate
        expected_success_rate = (2 / 5) * 100  # 2 completed out of 5 total
        self.assertEqual(status_report["success_rate"], expected_success_rate)

    def test_select_best_host(self):
        """Test host selection logic."""
        # Create hosts with different job counts
        host1 = ExecutorHost.objects.create(
            name="host1",
            # executor_type now determined by docker_host
            connection_string="host1:2376",
            is_active=True,
            current_job_count=5,
        )

        host2 = ExecutorHost.objects.create(
            name="host2",
            # executor_type now determined by docker_host
            connection_string="host2:2376",
            is_active=True,
            current_job_count=2,
        )

        job = ContainerJob.objects.create(
            docker_image="alpine:latest",
            docker_host=host1,
            name="test-job",
            # executor_type now determined by docker_host
            status="pending",
            created_by=self.user,
        )

        # Should select host with lowest job count
        best_host = self.manager._select_best_host([host1, host2], job)
        self.assertEqual(best_host, host2)
