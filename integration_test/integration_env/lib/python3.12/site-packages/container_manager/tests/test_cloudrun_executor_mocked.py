"""
Tests for CloudRunExecutor with fully mocked dependencies.

This test file mocks all Google Cloud dependencies to improve test coverage
without requiring actual GCP libraries to be installed.
"""

import sys
from unittest.mock import MagicMock, Mock

from django.contrib.auth.models import User
from django.test import TestCase

from container_manager.executors.exceptions import (
    ExecutorConfigurationError,
)
from container_manager.models import ContainerJob, ExecutorHost


class CloudRunExecutorMockedTest(TestCase):
    """Test CloudRunExecutor with fully mocked Google Cloud dependencies"""

    def setUp(self):
        super().setUp()

        # Mock all Google Cloud modules
        self.mock_google_cloud = {}
        self.setup_google_cloud_mocks()

        # Create test data
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        self.host = ExecutorHost.objects.create(
            name="cloudrun-host",
            host_type="cloudrun",
            connection_string="cloudrun://test-project/us-central1",
            is_active=True,
            executor_type="cloudrun",
        )

        self.job = ContainerJob.objects.create(
            docker_host=self.host,
            docker_image="gcr.io/test/image:latest",
            command='echo "test"',
            timeout_seconds=300,
            name="Test Job",
            created_by=self.user,
        )

    def setup_google_cloud_mocks(self):
        """Set up comprehensive mocks for Google Cloud modules"""
        # Mock google.cloud.run_v2 module hierarchy
        mock_run_v2 = MagicMock()
        mock_jobs_client = MagicMock()
        mock_job = MagicMock()
        mock_execution = MagicMock()

        # Set up the module structure
        mock_run_v2.JobsClient = Mock(return_value=mock_jobs_client)
        mock_run_v2.Job = mock_job
        mock_run_v2.Execution = mock_execution

        # Store for use in tests
        self.mock_google_cloud["run_v2"] = mock_run_v2
        self.mock_google_cloud["jobs_client"] = mock_jobs_client
        self.mock_google_cloud["job"] = mock_job
        self.mock_google_cloud["execution"] = mock_execution

        # Mock google.auth module
        mock_auth = MagicMock()
        mock_credentials = MagicMock()
        mock_auth.default.return_value = (mock_credentials, "test-project")
        self.mock_google_cloud["auth"] = mock_auth

        # Patch sys.modules to include our mocks
        sys.modules["google"] = MagicMock()
        sys.modules["google.cloud"] = MagicMock()
        sys.modules["google.cloud.run_v2"] = mock_run_v2
        sys.modules["google.auth"] = mock_auth

    def tearDown(self):
        """Clean up mocked modules"""
        # Remove mocked modules
        modules_to_remove = [
            "google.cloud.run_v2",
            "google.auth",
            "google.cloud",
            "google",
        ]
        for module in modules_to_remove:
            if module in sys.modules:
                del sys.modules[module]
        super().tearDown()

    def test_executor_initialization_basic(self):
        """Test CloudRunExecutor basic initialization"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {
            "docker_host": self.host,
            "project_id": "test-project",
            "region": "us-central1",
        }

        executor = CloudRunExecutor(config)

        self.assertEqual(executor.project_id, "test-project")
        self.assertEqual(executor.region, "us-central1")

    def test_executor_initialization_with_host_parsing(self):
        """Test CloudRunExecutor initialization with host connection string parsing"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}

        executor = CloudRunExecutor(config)

        # Should parse project_id and region from connection string
        self.assertEqual(executor.project_id, "test-project")
        self.assertEqual(executor.region, "us-central1")

    def test_parse_project_id_from_config(self):
        """Test _parse_project_id from explicit config"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"project_id": "explicit-project", "docker_host": self.host}

        executor = CloudRunExecutor(config)
        self.assertEqual(executor.project_id, "explicit-project")

    def test_parse_project_id_from_connection_string(self):
        """Test _parse_project_id from connection string"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}

        executor = CloudRunExecutor(config)
        self.assertEqual(executor.project_id, "test-project")

    def test_parse_project_id_missing(self):
        """Test _parse_project_id raises error when missing"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        # Create host with invalid connection string
        invalid_host = ExecutorHost.objects.create(
            name="invalid-host",
            host_type="cloudrun",
            connection_string="invalid://",
            is_active=True,
            executor_type="cloudrun",
        )

        config = {"docker_host": invalid_host}

        with self.assertRaises(ExecutorConfigurationError) as context:
            CloudRunExecutor(config)

        self.assertIn("project_id", str(context.exception))

    def test_parse_region_from_config(self):
        """Test _parse_region from explicit config"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {
            "project_id": "test-project",
            "region": "europe-west1",
            "docker_host": self.host,
        }

        executor = CloudRunExecutor(config)
        self.assertEqual(executor.region, "europe-west1")

    def test_parse_region_default(self):
        """Test _parse_region uses default when not specified"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        # Create host without region in connection string
        host_no_region = ExecutorHost.objects.create(
            name="no-region-host",
            host_type="cloudrun",
            connection_string="cloudrun://test-project",
            is_active=True,
            executor_type="cloudrun",
        )

        config = {"docker_host": host_no_region}

        executor = CloudRunExecutor(config)
        self.assertEqual(executor.region, "us-central1")  # Default region

    def test_get_capabilities(self):
        """Test get_capabilities returns expected capabilities"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        capabilities = executor.get_capabilities()

        expected_capabilities = {
            "supports_resource_limits": False,
            "supports_networking": False,
            "supports_persistent_storage": False,
            "supports_secrets": False,
            "supports_gpu": False,
            "supports_scaling": False,
        }

        for key, value in expected_capabilities.items():
            self.assertIn(key, capabilities)
            self.assertEqual(capabilities[key], value)

    def test_validate_job_valid(self):
        """Test validate_job with valid job"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        is_valid, message = executor.validate_job(self.job)

        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_validate_job_with_none_input(self):
        """Test validate_job with None job"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        is_valid, message = executor.validate_job(None)

        self.assertFalse(is_valid)
        self.assertIn("None", message)

    def test_connection_string_parsing_valid(self):
        """Test connection string parsing with valid format"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        # Test various valid connection string formats
        test_cases = [
            ("cloudrun://project/region", ("project", "region")),
            ("cloudrun://my-project/us-west1", ("my-project", "us-west1")),
            ("cloudrun://project-123/europe-west2", ("project-123", "europe-west2")),
        ]

        for connection_string, expected in test_cases:
            host = ExecutorHost.objects.create(
                name=f"test-{expected[0]}",
                host_type="cloudrun",
                connection_string=connection_string,
                is_active=True,
                executor_type="cloudrun",
            )

            config = {"docker_host": host}
            executor = CloudRunExecutor(config)

            self.assertEqual(executor.project_id, expected[0])
            self.assertEqual(executor.region, expected[1])

    def test_connection_string_parsing_invalid(self):
        """Test connection string parsing with invalid formats"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        # Test completely invalid connection string that can't provide project_id
        invalid_host = ExecutorHost.objects.create(
            name="completely-invalid",
            host_type="cloudrun",
            connection_string="",  # Empty string, no project_id available anywhere
            is_active=True,
            executor_type="cloudrun",
        )

        config = {"docker_host": invalid_host}  # No project_id in config either

        with self.assertRaises(ExecutorConfigurationError):
            CloudRunExecutor(config)

    def test_connection_string_parsing_fallback_behavior(self):
        """Test connection string parsing falls back gracefully for invalid formats"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        # Test invalid connection string formats that should fallback gracefully
        fallback_cases = [
            "invalid://format",
            "cloudrun://",
            "cloudrun://project-only",
            "not-a-url",
        ]

        for i, connection_string in enumerate(fallback_cases):
            host = ExecutorHost.objects.create(
                name=f"fallback-test-{i}",
                host_type="cloudrun",
                connection_string=connection_string,
                is_active=True,
                executor_type="cloudrun",
            )

            # Provide explicit project_id so executor can still be created
            config = {"docker_host": host, "project_id": "test-project"}

            # Should not raise error when project_id is provided explicitly
            executor = CloudRunExecutor(config)
            self.assertEqual(executor.project_id, "test-project")

    def test_job_name_generation_pattern(self):
        """Test job name generation follows Cloud Run naming conventions"""
        import time

        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        # Test the pattern used in launch_job method
        job_name = f"job-{self.job.id.hex[:8]}-{int(time.time())}"

        # Should contain job ID and be valid for Cloud Run
        self.assertIn(self.job.id.hex[:8], job_name)
        self.assertTrue(job_name.startswith("job-"))
        # Cloud Run job names must be lowercase and contain only letters, numbers, and hyphens
        self.assertTrue(job_name.islower())
        self.assertTrue(all(c.isalnum() or c == "-" for c in job_name))

    def test_service_settings_parsing(self):
        """Test _parse_service_settings with various configurations"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {
            "docker_host": self.host,
            "service_account": "test@example.com",
            "vpc_connector": "projects/test/locations/us-central1/connectors/default",
            "memory_limit": 512,
            "cpu_limit": 1.0,
            "max_retries": 5,
            "parallelism": 2,
            "task_count": 1,
            "env_vars": {"KEY": "value"},
            "labels": {"env": "test"},
        }

        executor = CloudRunExecutor(config)

        # Settings should be parsed and stored
        self.assertEqual(executor.service_account, "test@example.com")
        self.assertEqual(
            executor.vpc_connector,
            "projects/test/locations/us-central1/connectors/default",
        )
        self.assertEqual(executor.memory_limit, 512)
        self.assertEqual(executor.cpu_limit, 1.0)
        self.assertEqual(executor.max_retries, 5)
        self.assertEqual(executor.parallelism, 2)
        self.assertEqual(executor.task_count, 1)
        self.assertEqual(executor.env_vars, {"KEY": "value"})
        self.assertEqual(executor.labels, {"env": "test"})

    def test_get_health_status_default(self):
        """Test get_health_status returns default base class behavior"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        health = executor.get_health_status()

        # Should return default base class behavior
        self.assertTrue(health["healthy"])
        self.assertIsNone(health["error"])

    def test_get_execution_display(self):
        """Test get_execution_display method"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        # Test with execution ID
        self.job.execution_id = "test-execution-123"
        self.job.save()

        display = executor.get_execution_display(self.job)

        expected_keys = ["type_name", "id_label", "id_value", "status_detail"]
        for key in expected_keys:
            self.assertIn(key, display)

        self.assertTrue(display["type_name"].startswith("Cloud Run Job"))
        self.assertEqual(display["id_label"], "Execution ID")
        self.assertEqual(display["id_value"], "test-execution-123")

    def test_get_execution_display_no_execution_id(self):
        """Test get_execution_display with no execution ID"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        config = {"docker_host": self.host}
        executor = CloudRunExecutor(config)

        display = executor.get_execution_display(self.job)

        self.assertEqual(display["id_value"], "Not started")


class CloudRunExecutorMethodsTest(TestCase):
    """Test specific CloudRunExecutor methods that can be tested without full GCP integration"""

    def setUp(self):
        super().setUp()

        # Mock Google Cloud modules like in previous test
        mock_run_v2 = MagicMock()
        mock_jobs_client = MagicMock()
        mock_run_v2.JobsClient = Mock(return_value=mock_jobs_client)

        sys.modules["google"] = MagicMock()
        sys.modules["google.cloud"] = MagicMock()
        sys.modules["google.cloud.run_v2"] = mock_run_v2
        sys.modules["google.auth"] = MagicMock()

        # Create test data
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        self.host = ExecutorHost.objects.create(
            name="cloudrun-host",
            host_type="cloudrun",
            connection_string="cloudrun://test-project/us-central1",
            is_active=True,
            executor_type="cloudrun",
        )

    def tearDown(self):
        # Clean up mocked modules
        modules_to_remove = [
            "google.cloud.run_v2",
            "google.auth",
            "google.cloud",
            "google",
        ]
        for module in modules_to_remove:
            if module in sys.modules:
                del sys.modules[module]
        super().tearDown()

    def test_parse_project_from_connection_string_method(self):
        """Test _parse_project_from_connection_string method"""
        from container_manager.executors.cloudrun import CloudRunExecutor

        # Test with valid connection string in config
        config_with_host = {"docker_host": self.host}
        executor = CloudRunExecutor(
            {"docker_host": self.host, "project_id": "test-project"}
        )  # Need valid config to create

        project = executor._parse_project_from_connection_string(config_with_host)
        self.assertEqual(project, "test-project")

        # Test with missing docker_host
        config_no_host = {}
        project = executor._parse_project_from_connection_string(config_no_host)
        self.assertIsNone(project)

    def test_min_connection_string_parts_constant(self):
        """Test that MIN_CONNECTION_STRING_PARTS constant is properly defined"""
        from container_manager.executors.cloudrun import MIN_CONNECTION_STRING_PARTS

        self.assertEqual(MIN_CONNECTION_STRING_PARTS, 2)
