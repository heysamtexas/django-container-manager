"""
Tests for job service integration with queue system.

This module tests the end-to-end integration of the job service
with the queue manager, ensuring jobs are launched, monitored,
and results harvested correctly.
"""

from unittest.mock import patch

from django.test import TestCase

from ..models import ContainerJob, ExecutorHost
from ..queue import queue_manager
from ..services import check_job_status, harvest_job_results, launch_job


class JobServiceIntegrationTest(TestCase):
    """Test integration between job service and queue system"""

    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name="test-integration-host",
            host_type="tcp",  # host_type for connection method
            executor_type="mock",  # executor_type for choosing executor class
            connection_string="mock://localhost",
            is_active=True,
            executor_config={"test": True},
        )

        self.job = ContainerJob.objects.create(
            name="integration-test-job",
            command="echo 'Hello Integration'",
            docker_image="python:3.9",
            docker_host=self.host,
        )

    def test_launch_job_service_integration(self):
        """Test job service launch_job function works"""
        with patch(
            "container_manager.executors.mock.MockExecutor.launch_job"
        ) as mock_launch:
            mock_launch.return_value = (True, "mock-execution-123")

            result = launch_job(self.job)

            self.assertTrue(result["success"])
            self.assertEqual(result["execution_id"], "mock-execution-123")
            self.assertIsNone(result.get("error"))

            # Verify executor's launch_job was called
            mock_launch.assert_called_once_with(self.job)

    def test_check_job_status_integration(self):
        """Test job status checking integration"""
        # Set up job with execution identifier
        self.job.set_execution_identifier("mock-execution-123")
        self.job.save()

        with patch(
            "container_manager.executors.mock.MockExecutor.check_status"
        ) as mock_check:
            mock_check.return_value = "running"

            result = check_job_status(self.job)

            self.assertEqual(result["status"], "running")
            self.assertEqual(result["execution_id"], "mock-execution-123")
            self.assertIsNone(result["error"])

            # Verify executor's check_status was called
            mock_check.assert_called_once_with("mock-execution-123")

    def test_harvest_job_results_integration(self):
        """Test job result harvesting integration"""
        # Set up completed job
        self.job.set_execution_identifier("mock-execution-123")
        self.job.mark_as_running()
        self.job.save()

        with patch(
            "container_manager.executors.mock.MockExecutor.harvest_job"
        ) as mock_harvest:
            mock_harvest.return_value = True

            result = harvest_job_results(self.job)

            self.assertTrue(result["success"])
            self.assertTrue(result["logs_collected"])
            self.assertIsNone(result["error"])

            # Verify executor's harvest_job was called
            mock_harvest.assert_called_once_with(self.job)

    def test_queue_manager_job_launch_integration(self):
        """Test queue manager uses job service for launching"""
        # Queue the job first
        queue_manager.queue_job(self.job)

        with patch(
            "container_manager.executors.mock.MockExecutor.launch_job"
        ) as mock_launch:
            # Mock needs to simulate executor behavior: update job status and return execution_id
            def mock_launch_side_effect(job):
                job.status = "running"
                job.set_execution_identifier("mock-execution-456")
                job.save()
                return True, "mock-execution-456"

            mock_launch.side_effect = mock_launch_side_effect

            # Launch job through queue manager
            result = queue_manager.launch_job(self.job)

            self.assertTrue(result["success"])

            # Verify job state was updated
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, "running")
            self.assertEqual(self.job.get_execution_identifier(), "mock-execution-456")

            # Verify executor was called
            mock_launch.assert_called_once_with(self.job)

    def test_queue_batch_launch_integration(self):
        """Test queue batch launch uses job service"""
        # Create multiple jobs
        jobs = []
        for i in range(3):
            job = ContainerJob.objects.create(
                name=f"batch-test-job-{i}",
                command=f"echo 'Batch job {i}'",
                docker_image="python:3.9",
                docker_host=self.host,
            )
            queue_manager.queue_job(job)
            jobs.append(job)

        with patch(
            "container_manager.executors.mock.MockExecutor.launch_job"
        ) as mock_launch:
            # Mock successful launches with job state updates
            def batch_mock_side_effect(job):
                execution_id = f"mock-execution-{job.id}"
                job.status = "running"
                job.set_execution_identifier(execution_id)
                job.save()
                return True, execution_id

            mock_launch.side_effect = batch_mock_side_effect

            # Launch batch
            result = queue_manager.launch_next_batch(max_concurrent=3)

            self.assertEqual(result["launched"], 3)
            self.assertEqual(len(result["errors"]), 0)

            # Verify all jobs were launched
            for job in jobs:
                job.refresh_from_db()
                self.assertEqual(job.status, "running")
                self.assertEqual(
                    job.get_execution_identifier(), f"mock-execution-{job.id}"
                )

            # Verify executor was called for each job
            self.assertEqual(mock_launch.call_count, 3)

    def test_error_handling_integration(self):
        """Test error handling in job service integration"""
        with patch(
            "container_manager.executors.mock.MockExecutor.launch_job"
        ) as mock_launch:
            mock_launch.return_value = (False, "Mock launch error")

            result = launch_job(self.job)

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Mock launch error")
            self.assertNotIn("execution_id", result)

    def test_job_without_execution_id_status_check(self):
        """Test status check for job without execution identifier"""
        result = check_job_status(self.job)

        self.assertEqual(result["status"], "not-found")
        self.assertIsNone(result["execution_id"])
        self.assertEqual(result["error"], "No execution identifier found")

    def test_job_service_validation_integration(self):
        """Test job validation in service integration"""
        # Create job with valid docker_host but invalid state for testing validation
        invalid_job = ContainerJob.objects.create(
            name="invalid-job",
            command="echo invalid",
            docker_image="python:3.9",
            docker_host=self.host,
        )

        # Use transition_to to properly change to completed state (via running)
        invalid_job.transition_to("running")
        invalid_job.transition_to("completed")

        result = launch_job(invalid_job)

        self.assertFalse(result["success"])
        self.assertIn("preparation failed", result["error"].lower())


class JobLifecycleIntegrationTest(TestCase):
    """Test complete job lifecycle through integrated services"""

    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name="lifecycle-test-host",
            host_type="tcp",  # host_type for connection method
            executor_type="mock",  # executor_type for choosing executor class
            connection_string="mock://localhost",
            is_active=True,
            executor_config={"test": True},
        )

        self.job = ContainerJob.objects.create(
            name="lifecycle-test-job",
            command="echo 'Lifecycle Test'",
            docker_image="python:3.9",
            docker_host=self.host,
        )

    def test_complete_job_lifecycle(self):
        """Test complete job lifecycle: queue -> launch -> monitor -> harvest"""

        # Step 1: Queue job
        queue_manager.queue_job(self.job)
        self.job.refresh_from_db()
        self.assertTrue(self.job.is_queued)

        # Step 2: Launch job
        with patch(
            "container_manager.executors.mock.MockExecutor.launch_job"
        ) as mock_launch:
            # Mock needs to simulate executor behavior: update job status and return execution_id
            def mock_launch_side_effect(job):
                job.status = "running"
                job.set_execution_identifier("lifecycle-execution-123")
                job.save()
                return True, "lifecycle-execution-123"

            mock_launch.side_effect = mock_launch_side_effect

            result = queue_manager.launch_job(self.job)
            self.assertTrue(result["success"])

            self.job.refresh_from_db()
            self.assertEqual(self.job.status, "running")
            self.assertEqual(
                self.job.get_execution_identifier(), "lifecycle-execution-123"
            )

        # Step 3: Check job status
        with patch(
            "container_manager.executors.mock.MockExecutor.check_status"
        ) as mock_status:
            mock_status.return_value = "running"

            status_result = check_job_status(self.job)
            self.assertEqual(status_result["status"], "running")

            # Simulate job completion
            mock_status.return_value = "exited"
            status_result = check_job_status(self.job)
            self.assertEqual(status_result["status"], "exited")

        # Step 4: Harvest job results
        with patch(
            "container_manager.executors.mock.MockExecutor.harvest_job"
        ) as mock_harvest:
            mock_harvest.return_value = True

            harvest_result = harvest_job_results(self.job)
            self.assertTrue(harvest_result["success"])
            self.assertTrue(harvest_result["logs_collected"])

        # Lifecycle complete
        self.job.refresh_from_db()
        # Note: Job status would be updated by harvest_job in real executor
