"""
Tests for the ContainerExecutor base class.

Tests the abstract base class and its concrete methods that provide
common functionality for all executor implementations.
"""

from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from ..executors.base import ContainerExecutor
from ..models import ContainerJob, ExecutorHost


class TestExecutor(ContainerExecutor):
    """Test implementation of ContainerExecutor for testing base functionality."""

    def launch_job(self, job) -> tuple[bool, str]:
        return True, "test-execution-123"

    def check_status(self, execution_id: str) -> str:
        return "running"

    def get_logs(self, execution_id: str) -> tuple[str, str]:
        return "stdout logs", "stderr logs"

    def harvest_job(self, job) -> bool:
        return True

    def cleanup(self, execution_id: str) -> bool:
        return True


class ContainerExecutorBaseTest(TestCase):
    """Test cases for ContainerExecutor base class."""

    def setUp(self):
        """Set up test data and executor instance."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        self.host = ExecutorHost.objects.create(
            name="test-host",
            connection_string="tcp://localhost:2376",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )

        self.job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        # Create test executor instance
        self.config = {"test_setting": "test_value"}
        self.executor = TestExecutor(self.config)

    def test_init_basic(self):
        """Test basic initialization of executor."""
        self.assertEqual(self.executor.config, self.config)
        self.assertEqual(self.executor.name, "test")  # TestExecutor -> test

    def test_init_name_extraction(self):
        """Test name extraction from class name."""

        class DockerExecutor(ContainerExecutor):
            def launch_job(self, job):
                pass

            def check_status(self, execution_id: str):
                pass

            def get_logs(self, execution_id: str):
                pass

            def harvest_job(self, job):
                pass

            def cleanup(self, execution_id: str):
                pass

        executor = DockerExecutor({})
        self.assertEqual(executor.name, "docker")

    def test_get_capabilities_default(self):
        """Test default capabilities returned by base class."""
        capabilities = self.executor.get_capabilities()

        expected_capabilities = {
            "supports_resource_limits": False,
            "supports_networking": False,
            "supports_persistent_storage": False,
            "supports_secrets": False,
            "supports_gpu": False,
            "supports_scaling": False,
        }

        self.assertEqual(capabilities, expected_capabilities)

    def test_validate_job_success(self):
        """Test successful job validation."""
        valid, error = self.executor.validate_job(self.job)

        self.assertTrue(valid)
        self.assertEqual(error, "")

    def test_validate_job_none(self):
        """Test validation with None job."""
        valid, error = self.executor.validate_job(None)

        self.assertFalse(valid)
        self.assertEqual(error, "Job is None")

    def test_validate_job_no_docker_image(self):
        """Test validation with missing docker_image."""
        self.job.docker_image = ""
        valid, error = self.executor.validate_job(self.job)

        self.assertFalse(valid)
        self.assertEqual(error, "No docker_image")

    def test_validate_job_no_docker_host(self):
        """Test validation with missing docker_host."""
        self.job.docker_host = None
        valid, error = self.executor.validate_job(self.job)

        self.assertFalse(valid)
        self.assertEqual(error, "No docker_host")

    def test_validate_job_for_execution_success(self):
        """Test successful execution validation."""
        # Create job with template-like attribute to pass validation
        self.job.template = True  # Set directly as attribute
        errors = self.executor.validate_job_for_execution(self.job)
        self.assertEqual(errors, [])

    def test_validate_job_for_execution_none_job(self):
        """Test execution validation with None job."""
        errors = self.executor.validate_job_for_execution(None)

        self.assertEqual(errors, ["Job is None"])

    def test_validate_job_for_execution_no_template(self):
        """Test execution validation with no template."""
        self.job.template = None  # Set directly as attribute
        errors = self.executor.validate_job_for_execution(self.job)
        self.assertIn("Job must have a template", errors)

    def test_validate_job_for_execution_no_docker_host(self):
        """Test execution validation with no docker_host."""
        # Since docker_host is required in DB, mock the validation to test the logic
        mock_job = Mock()
        mock_job.template = True
        mock_job.docker_host = None  # Simulate missing docker_host

        errors = self.executor.validate_job_for_execution(mock_job)
        self.assertIn("Job must have a docker_host", errors)

    def test_validate_job_for_execution_with_different_host(self):
        """Test execution validation with a different executor host."""
        self.job.template = True  # Set directly as attribute
        # Create a cloudrun host - executor type is now determined by docker_host
        cloudrun_host = ExecutorHost.objects.create(
            name="cloudrun-host",
            connection_string="cloudrun://project/region",
            host_type="tcp",
            is_active=True,
            executor_type="cloudrun",
        )
        self.job.docker_host = cloudrun_host
        self.job.save()

        # Validation should pass since executor type is determined by docker_host
        errors = self.executor.validate_job_for_execution(self.job)
        self.assertEqual(errors, [])

    def test_validate_executor_specific_default(self):
        """Test default executor-specific validation returns empty list."""
        errors = self.executor._validate_executor_specific(self.job)
        self.assertEqual(errors, [])

    def test_get_execution_display_basic(self):
        """Test basic execution display information."""
        with patch.object(
            self.job, "get_execution_identifier", return_value="exec-123"
        ):
            display = self.executor.get_execution_display(self.job)

            expected = {
                "type_name": "Test Executor",
                "id_label": "Execution ID",
                "id_value": "exec-123",
                "status_detail": "Pending",
            }

            self.assertEqual(display, expected)

    def test_get_execution_display_no_identifier(self):
        """Test execution display with no identifier."""
        with patch.object(self.job, "get_execution_identifier", return_value=None):
            display = self.executor.get_execution_display(self.job)

            self.assertEqual(display["id_value"], "Not assigned")

    def test_get_status_detail_default(self):
        """Test default status detail formatting."""
        detail = self.executor._get_status_detail(self.job)
        self.assertEqual(detail, "Pending")  # job.status.title()

    def test_get_health_status_default(self):
        """Test default health status."""
        health = self.executor.get_health_status()

        expected = {
            "healthy": True,
            "error": None,
            "last_check": None,
            "response_time": None,
        }

        self.assertEqual(health, expected)

    def test_str_representation(self):
        """Test string representation of executor."""
        str_repr = str(self.executor)
        self.assertEqual(str_repr, "TestExecutor(test)")

    def test_repr_representation(self):
        """Test developer representation of executor."""
        repr_str = repr(self.executor)
        expected = f"TestExecutor(name='test', config={self.config})"
        self.assertEqual(repr_str, expected)


class ContainerExecutorSubclassTest(TestCase):
    """Test cases for ContainerExecutor subclass customization."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        self.host = ExecutorHost.objects.create(
            name="test-host",
            connection_string="tcp://localhost:2376",
            host_type="tcp",
            is_active=True,
            executor_type="custom",
        )

        self.job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
            exit_code=0,
        )

    def test_custom_capabilities(self):
        """Test executor with custom capabilities."""

        class CustomExecutor(ContainerExecutor):
            def launch_job(self, job):
                pass

            def check_status(self, execution_id: str):
                pass

            def get_logs(self, execution_id: str):
                pass

            def harvest_job(self, job):
                pass

            def cleanup(self, execution_id: str):
                pass

            def get_capabilities(self):
                return {
                    "supports_resource_limits": True,
                    "supports_networking": True,
                    "supports_persistent_storage": False,
                    "supports_secrets": True,
                    "supports_gpu": False,
                    "supports_scaling": True,
                }

        executor = CustomExecutor({})
        capabilities = executor.get_capabilities()

        self.assertTrue(capabilities["supports_resource_limits"])
        self.assertTrue(capabilities["supports_networking"])
        self.assertFalse(capabilities["supports_persistent_storage"])
        self.assertTrue(capabilities["supports_secrets"])
        self.assertFalse(capabilities["supports_gpu"])
        self.assertTrue(capabilities["supports_scaling"])

    def test_custom_executor_specific_validation(self):
        """Test executor with custom validation logic."""

        class ValidatingExecutor(ContainerExecutor):
            def launch_job(self, job):
                pass

            def check_status(self, execution_id: str):
                pass

            def get_logs(self, execution_id: str):
                pass

            def harvest_job(self, job):
                pass

            def cleanup(self, execution_id: str):
                pass

            def _validate_executor_specific(self, job):
                errors = []
                if job.memory_limit and job.memory_limit > 4096:
                    errors.append("Memory limit exceeds maximum of 4096MB")
                if job.cpu_limit and job.cpu_limit > 8.0:
                    errors.append("CPU limit exceeds maximum of 8.0 cores")
                return errors

        executor = ValidatingExecutor({})

        # Test with valid job
        self.job.template = True  # Set directly as attribute
        self.job.memory_limit = 2048
        self.job.cpu_limit = 4.0
        errors = executor.validate_job_for_execution(self.job)
        self.assertEqual(len(errors), 0)

        # Test with invalid memory
        self.job.memory_limit = 8192
        self.job.cpu_limit = 4.0
        errors = executor.validate_job_for_execution(self.job)
        self.assertIn("Memory limit exceeds maximum", errors[0])

        # Test with invalid CPU
        self.job.memory_limit = 2048
        self.job.cpu_limit = 16.0
        errors = executor.validate_job_for_execution(self.job)
        self.assertIn("CPU limit exceeds maximum", errors[0])

    def test_custom_status_detail(self):
        """Test executor with custom status detail formatting."""

        class DetailedExecutor(ContainerExecutor):
            def launch_job(self, job):
                pass

            def check_status(self, execution_id: str):
                pass

            def get_logs(self, execution_id: str):
                pass

            def harvest_job(self, job):
                pass

            def cleanup(self, execution_id: str):
                pass

            def _get_status_detail(self, job):
                status = job.status.title()
                if job.exit_code is not None:
                    if job.exit_code == 0:
                        status += " (Success)"
                    else:
                        status += f" (Exit: {job.exit_code})"
                return status

        executor = DetailedExecutor({})

        # Test with successful job
        self.job.status = "completed"
        self.job.exit_code = 0
        display = executor.get_execution_display(self.job)
        self.assertEqual(display["status_detail"], "Completed (Success)")

        # Test with failed job
        self.job.status = "failed"
        self.job.exit_code = 1
        display = executor.get_execution_display(self.job)
        self.assertEqual(display["status_detail"], "Failed (Exit: 1)")

        # Test with running job (no exit code)
        self.job.status = "running"
        self.job.exit_code = None
        display = executor.get_execution_display(self.job)
        self.assertEqual(display["status_detail"], "Running")

    def test_custom_execution_display(self):
        """Test executor with custom execution display."""

        class CustomDisplayExecutor(ContainerExecutor):
            def launch_job(self, job):
                pass

            def check_status(self, execution_id: str):
                pass

            def get_logs(self, execution_id: str):
                pass

            def harvest_job(self, job):
                pass

            def cleanup(self, execution_id: str):
                pass

            def get_execution_display(self, job):
                execution_id = job.get_execution_identifier()
                return {
                    "type_name": "Custom Cloud Executor",
                    "id_label": "Task ID",
                    "id_value": execution_id or "Not scheduled",
                    "status_detail": f"Cloud Status: {job.status.upper()}",
                }

        executor = CustomDisplayExecutor({})

        with patch.object(
            self.job, "get_execution_identifier", return_value="task-456"
        ):
            display = executor.get_execution_display(self.job)

            expected = {
                "type_name": "Custom Cloud Executor",
                "id_label": "Task ID",
                "id_value": "task-456",
                "status_detail": "Cloud Status: RUNNING",
            }

            self.assertEqual(display, expected)
