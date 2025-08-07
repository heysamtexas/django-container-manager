"""
Core service tests - focused on essential service behavior only.
Trimmed from 28 tests to ~8 essential tests.
"""

from unittest.mock import Mock, patch

from django.test import TestCase

from ..models import ContainerJob, ExecutorHost
from ..services import JobManagementService, check_job_status, launch_job


class JobManagementServiceCoreTest(TestCase):
    """Essential JobManagementService tests only"""

    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            executor_type="mock",
        )
        self.job = ContainerJob.objects.create(
            name="test-service-job",
            command="echo service test",
            docker_image="python:3.9",
            docker_host=self.host,
        )
        self.service = JobManagementService()

    def test_job_validation_success(self):
        """Test successful job validation"""
        with patch.object(
            self.service.executor_factory, "get_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.validate_job_for_execution.return_value = []
            mock_executor_factory.return_value = mock_executor

            errors = self.service.validate_job_for_execution(self.job)
            self.assertEqual(errors, [])

    def test_job_validation_with_errors(self):
        """Test job validation with errors"""
        with patch.object(
            self.service.executor_factory, "get_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.validate_job_for_execution.return_value = ["Test error"]
            mock_executor_factory.return_value = mock_executor

            errors = self.service.validate_job_for_execution(self.job)
            self.assertEqual(errors, ["Test error"])

    def test_launch_job_success(self):
        """Test successful job launch"""
        with patch.object(
            self.service.executor_factory, "get_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.validate_job_for_execution.return_value = []
            mock_executor.launch_job.return_value = (True, "execution-123")
            mock_executor_factory.return_value = mock_executor

            result = self.service.launch_job(self.job)

            self.assertTrue(result["success"])
            self.assertEqual(result["execution_id"], "execution-123")

    def test_launch_job_failure(self):
        """Test job launch failure"""
        with patch.object(
            self.service.executor_factory, "get_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.validate_job_for_execution.return_value = []
            mock_executor.launch_job.return_value = (False, "Launch failed")
            mock_executor_factory.return_value = mock_executor

            result = self.service.launch_job(self.job)

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Launch failed")

    def test_check_job_status(self):
        """Test job status checking"""
        self.job.set_execution_identifier("test-execution-456")

        with patch.object(
            self.service.executor_factory, "get_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "running"
            mock_executor_factory.return_value = mock_executor

            result = self.service.check_job_status(self.job)

            self.assertEqual(result["status"], "running")
            self.assertEqual(result["execution_id"], "test-execution-456")

    def test_harvest_job_results(self):
        """Test job result harvesting"""
        self.job.set_execution_identifier("harvest-test-789")

        with patch.object(
            self.service.executor_factory, "get_executor"
        ) as mock_executor_factory:
            mock_executor = Mock()
            mock_executor.harvest_job.return_value = True
            mock_executor_factory.return_value = mock_executor

            result = self.service.harvest_job_results(self.job)

            self.assertTrue(result["success"])
            self.assertTrue(result["logs_collected"])


class ModuleLevelServiceFunctionsTest(TestCase):
    """Test module-level convenience functions"""

    def setUp(self):
        self.host = ExecutorHost.objects.create(
            name="module-test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            executor_type="mock",
        )
        self.job = ContainerJob.objects.create(
            name="module-test-job",
            command="echo module test",
            docker_image="python:3.9",
            docker_host=self.host,
        )

    @patch("container_manager.services.job_service")
    def test_module_level_launch_job(self, mock_service):
        """Test module-level launch_job function"""
        mock_service.launch_job.return_value = {
            "success": True,
            "execution_id": "module-123",
        }

        result = launch_job(self.job)

        self.assertTrue(result["success"])
        self.assertEqual(result["execution_id"], "module-123")
        mock_service.launch_job.assert_called_once_with(self.job)

    @patch("container_manager.services.job_service")
    def test_module_level_check_status(self, mock_service):
        """Test module-level check_job_status function"""
        mock_service.check_job_status.return_value = {"status": "completed"}

        result = check_job_status(self.job)

        self.assertEqual(result["status"], "completed")
        mock_service.check_job_status.assert_called_once_with(self.job)
