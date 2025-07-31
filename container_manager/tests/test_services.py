"""
Tests for container_manager.services module.

Tests the service layer for job management operations using executor polymorphism.
"""

from unittest.mock import Mock, patch

from django.test import TestCase

from ..executors.factory import ExecutorFactory
from ..models import ContainerJob, ExecutorHost
from ..services import (
    JobManagementService,
    JobValidationService,
    job_service,
    job_validator,
)


class JobManagementServiceTest(TestCase):
    """Test JobManagementService class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test host
        self.docker_host = ExecutorHost.objects.create(
            name="test-docker-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            executor_type="docker",
            is_active=True,
        )

        # Create test job
        self.job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            command="echo 'hello world'",
            docker_host=self.docker_host,
        )

        # Mock executor factory
        self.mock_executor = Mock()
        self.mock_factory = Mock(spec=ExecutorFactory)
        self.mock_factory.get_executor.return_value = self.mock_executor

        # Create service with mocked factory
        self.service = JobManagementService(self.mock_factory)

    def test_init_with_factory(self):
        """Test service initialization with provided factory."""
        service = JobManagementService(self.mock_factory)
        self.assertEqual(service.executor_factory, self.mock_factory)

    def test_init_without_factory(self):
        """Test service initialization creates default factory."""
        service = JobManagementService()
        self.assertIsInstance(service.executor_factory, ExecutorFactory)

    def test_validate_job_for_execution_success(self):
        """Test successful job validation."""
        # Mock executor returns no errors
        self.mock_executor.validate_job_for_execution.return_value = []

        errors = self.service.validate_job_for_execution(self.job)

        self.assertEqual(errors, [])
        self.mock_factory.get_executor.assert_called_once_with(self.docker_host)
        self.mock_executor.validate_job_for_execution.assert_called_once_with(self.job)

    def test_validate_job_for_execution_with_errors(self):
        """Test job validation with validation errors."""
        expected_errors = ["Missing required field", "Invalid configuration"]
        self.mock_executor.validate_job_for_execution.return_value = expected_errors

        errors = self.service.validate_job_for_execution(self.job)

        self.assertEqual(errors, expected_errors)
        self.mock_factory.get_executor.assert_called_once_with(self.docker_host)
        self.mock_executor.validate_job_for_execution.assert_called_once_with(self.job)

    def test_validate_job_for_execution_executor_exception(self):
        """Test job validation when executor raises exception."""
        self.mock_factory.get_executor.side_effect = Exception("Executor error")

        errors = self.service.validate_job_for_execution(self.job)

        self.assertEqual(len(errors), 1)
        self.assertIn("Validation failed: Executor error", errors[0])

    def test_get_job_execution_details_success(self):
        """Test successful job execution details retrieval."""
        expected_details = {
            "type_name": "Docker",
            "id_label": "Container ID",
            "id_value": "container_123",
            "status_detail": "Running",
        }
        self.mock_executor.get_execution_display.return_value = expected_details

        details = self.service.get_job_execution_details(self.job)

        self.assertEqual(details, expected_details)
        self.mock_factory.get_executor.assert_called_once_with(self.docker_host)
        self.mock_executor.get_execution_display.assert_called_once_with(self.job)

    def test_get_job_execution_details_executor_exception(self):
        """Test job execution details when executor raises exception."""
        self.mock_factory.get_executor.side_effect = Exception("Display error")

        with patch.object(self.job, "get_execution_identifier", return_value="job_123"):
            details = self.service.get_job_execution_details(self.job)

        expected_details = {
            "type_name": "Unknown Executor",
            "id_label": "Execution ID",
            "id_value": "job_123",
            "status_detail": "Error: Display error",
        }
        self.assertEqual(details, expected_details)

    def test_get_job_execution_details_no_execution_id(self):
        """Test job execution details when no execution ID available."""
        self.mock_factory.get_executor.side_effect = Exception("Display error")

        with patch.object(self.job, "get_execution_identifier", return_value=None):
            details = self.service.get_job_execution_details(self.job)

        self.assertEqual(details["id_value"], "Not assigned")

    def test_prepare_job_for_launch_success(self):
        """Test successful job preparation for launch."""
        # Mock validation returns no errors
        self.mock_executor.validate_job_for_execution.return_value = []

        success, errors = self.service.prepare_job_for_launch(self.job)

        self.assertTrue(success)
        self.assertEqual(errors, [])

    def test_prepare_job_for_launch_validation_errors(self):
        """Test job preparation with validation errors."""
        validation_errors = ["Invalid image", "Missing command"]
        self.mock_executor.validate_job_for_execution.return_value = validation_errors

        success, errors = self.service.prepare_job_for_launch(self.job)

        self.assertFalse(success)
        self.assertEqual(errors, validation_errors)

    def test_prepare_job_for_launch_exception(self):
        """Test job preparation when exception occurs."""
        self.mock_factory.get_executor.side_effect = Exception("Preparation error")

        success, errors = self.service.prepare_job_for_launch(self.job)

        self.assertFalse(success)
        self.assertEqual(len(errors), 1)
        self.assertIn("Validation failed: Preparation error", errors[0])

    def test_prepare_job_for_launch_direct_exception(self):
        """Test job preparation when direct exception occurs in preparation logic."""
        # Mock validation to succeed but then cause an exception in the method itself
        self.mock_executor.validate_job_for_execution.return_value = []

        # Patch the method to raise an exception after validation succeeds
        with patch.object(
            self.service,
            "validate_job_for_execution",
            side_effect=Exception("Direct preparation error"),
        ):
            success, errors = self.service.prepare_job_for_launch(self.job)

        self.assertFalse(success)
        self.assertEqual(len(errors), 1)
        self.assertIn("Preparation failed: Direct preparation error", errors[0])

    def test_get_host_display_info_docker_host(self):
        """Test host display info for Docker host."""
        docker_host = ExecutorHost.objects.create(
            name="docker-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
        )

        info = self.service.get_host_display_info(docker_host)

        expected_info = {
            "name": "docker-host",
            "type_name": "Docker",
            "connection_info": "unix:///var/run/docker.sock",
        }
        self.assertEqual(info, expected_info)

    def test_get_host_display_info_cloudrun_host(self):
        """Test host display info for Cloud Run host."""
        cloudrun_host = ExecutorHost.objects.create(
            name="cloudrun-host",
            executor_type="cloudrun",
            executor_config={"region": "us-central1"},
        )

        info = self.service.get_host_display_info(cloudrun_host)

        expected_info = {
            "name": "cloudrun-host",
            "type_name": "Cloud Run",
            "connection_info": "Region: us-central1",
        }
        self.assertEqual(info, expected_info)

    def test_get_host_display_info_cloudrun_no_region(self):
        """Test host display info for Cloud Run host without region."""
        cloudrun_host = ExecutorHost.objects.create(
            name="cloudrun-host",
            executor_type="cloudrun",
            executor_config={},
        )

        info = self.service.get_host_display_info(cloudrun_host)

        self.assertEqual(info["connection_info"], "Region: unknown")

    def test_get_host_display_info_cloudrun_no_config(self):
        """Test host display info for Cloud Run host without config."""
        cloudrun_host = ExecutorHost.objects.create(
            name="cloudrun-host",
            executor_type="cloudrun",
            executor_config={},
        )

        info = self.service.get_host_display_info(cloudrun_host)

        self.assertEqual(info["connection_info"], "Region: unknown")

    def test_get_host_display_info_unknown_type(self):
        """Test host display info for unknown executor type."""
        unknown_host = ExecutorHost.objects.create(
            name="unknown-host",
            executor_type="custom",
            connection_string="custom://connection",
        )

        info = self.service.get_host_display_info(unknown_host)

        expected_info = {
            "name": "unknown-host",
            "type_name": "Custom",
            "connection_info": "custom://connection",
        }
        self.assertEqual(info, expected_info)

    def test_get_host_display_info_exception(self):
        """Test host display info when exception occurs."""
        # Mock the factory to raise an exception
        self.mock_factory.get_executor.side_effect = Exception("Display error")

        info = self.service.get_host_display_info(self.docker_host)

        expected_info = {
            "name": "test-docker-host",
            "type_name": "Unknown",
            "connection_info": "Error: Display error",
        }
        self.assertEqual(info, expected_info)


class JobValidationServiceTest(TestCase):
    """Test JobValidationService class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test host and job
        self.docker_host = ExecutorHost.objects.create(
            name="test-docker-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            executor_type="docker",
            is_active=True,
        )

        self.job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            command="echo 'hello world'",
            docker_host=self.docker_host,
        )

        # Mock executor factory
        self.mock_factory = Mock(spec=ExecutorFactory)
        self.validation_service = JobValidationService(self.mock_factory)

    def test_init_with_factory(self):
        """Test validation service initialization with provided factory."""
        service = JobValidationService(self.mock_factory)
        self.assertEqual(service.job_service.executor_factory, self.mock_factory)

    def test_init_without_factory(self):
        """Test validation service initialization creates default factory."""
        service = JobValidationService()
        self.assertIsInstance(service.job_service.executor_factory, ExecutorFactory)

    def test_validate_job_success(self):
        """Test successful job validation."""
        with patch.object(
            self.validation_service.job_service,
            "validate_job_for_execution",
            return_value=[],
        ):
            errors = self.validation_service.validate_job(self.job)

            self.assertEqual(errors, [])
            self.validation_service.job_service.validate_job_for_execution.assert_called_once_with(
                self.job
            )

    def test_validate_job_with_errors(self):
        """Test job validation with errors."""
        expected_errors = ["Validation error 1", "Validation error 2"]
        with patch.object(
            self.validation_service.job_service,
            "validate_job_for_execution",
            return_value=expected_errors,
        ):
            errors = self.validation_service.validate_job(self.job)

            self.assertEqual(errors, expected_errors)

    def test_is_job_valid_true(self):
        """Test is_job_valid returns True for valid job."""
        with patch.object(self.validation_service, "validate_job", return_value=[]):
            result = self.validation_service.is_job_valid(self.job)

            self.assertTrue(result)

    def test_is_job_valid_false(self):
        """Test is_job_valid returns False for invalid job."""
        with patch.object(
            self.validation_service, "validate_job", return_value=["Error"]
        ):
            result = self.validation_service.is_job_valid(self.job)

            self.assertFalse(result)


class ModuleLevelInstancesTest(TestCase):
    """Test module-level service instances."""

    def test_job_service_instance(self):
        """Test that job_service is properly initialized."""
        self.assertIsInstance(job_service, JobManagementService)
        self.assertIsInstance(job_service.executor_factory, ExecutorFactory)

    def test_job_validator_instance(self):
        """Test that job_validator is properly initialized."""
        self.assertIsInstance(job_validator, JobValidationService)
        self.assertIsInstance(
            job_validator.job_service.executor_factory, ExecutorFactory
        )

    def test_module_instances_share_factory(self):
        """Test that module-level instances share the same factory instance."""
        # Both should use the same _default_factory instance
        self.assertEqual(
            job_service.executor_factory, job_validator.job_service.executor_factory
        )


class ServiceIntegrationTest(TestCase):
    """Test service integration with real models and minimal mocking."""

    def setUp(self):
        """Set up integration test fixtures."""
        # Create test user
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="integration-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            executor_type="docker",
            is_active=True,
        )

        self.job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            command="echo 'integration test'",
            docker_host=self.docker_host,
            created_by=self.user,
        )

    def test_host_display_info_integration(self):
        """Test host display info integration with real models."""
        # Create a fresh service instance with a real factory to avoid test pollution
        from ..executors.factory import ExecutorFactory

        service = JobManagementService(ExecutorFactory())

        info = service.get_host_display_info(self.docker_host)

        self.assertEqual(info["name"], "integration-host")
        self.assertEqual(info["type_name"], "Docker")
        self.assertEqual(info["connection_info"], "unix:///var/run/docker.sock")
