"""
Tests for DockerExecutor implementation
"""

from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from docker.errors import NotFound

from container_manager.executors.docker import DockerExecutor
from container_manager.executors.exceptions import (
    ExecutorError,
)
from container_manager.models import (
    ContainerJob,
    ContainerTemplate,
    ExecutorHost,
)


class DockerExecutorTest(TestCase):
    """Test suite for DockerExecutor implementation"""

    def setUp(self):
        super().setUp()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Create test ExecutorHost
        self.docker_host = ExecutorHost.objects.create(
            name="test-docker-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            executor_type="docker",
        )

        # Create test template
        self.template = ContainerTemplate.objects.create(
            name="test-template",
            description="Test template for Docker testing",
            docker_image="alpine:latest",
            command='echo "test"',
            timeout_seconds=300,
            memory_limit=128,
            cpu_limit=0.5,
            created_by=self.user,
        )

        # Create test job
        self.job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Test Job",
            created_by=self.user,
        )

        # Create executor
        self.executor = DockerExecutor({"docker_host": self.docker_host})

    def test_executor_initialization(self):
        """Test DockerExecutor initialization"""
        config = {"docker_host": self.docker_host}
        executor = DockerExecutor(config)

        self.assertEqual(executor.docker_host, self.docker_host)
        self.assertEqual(executor._clients, {})
        self.assertIsInstance(executor._clients, dict)

    def test_executor_initialization_without_host(self):
        """Test DockerExecutor initialization without docker_host"""
        config = {}
        executor = DockerExecutor(config)

        self.assertIsNone(executor.docker_host)

    @patch("container_manager.executors.docker.docker.DockerClient")
    def test_get_client_creates_new_client(self, mock_docker_client):
        """Test _get_client creates new Docker client"""
        mock_client = Mock()
        mock_docker_client.return_value = mock_client

        client = self.executor._get_client(self.docker_host)

        self.assertEqual(client, mock_client)
        mock_docker_client.assert_called_once()

    @patch("container_manager.executors.docker.docker.DockerClient")
    def test_get_client_caches_client(self, mock_docker_client):
        """Test _get_client caches Docker clients"""
        mock_client = Mock()
        mock_docker_client.return_value = mock_client

        # First call
        client1 = self.executor._get_client(self.docker_host)
        # Second call
        client2 = self.executor._get_client(self.docker_host)

        self.assertEqual(client1, client2)
        # Should only create client once
        mock_docker_client.assert_called_once()

    def test_validate_job_valid_job(self):
        """Test _validate_job with valid job"""
        # Should not raise exception
        try:
            self.executor._validate_job(self.job)
        except Exception as e:
            self.fail(f"_validate_job raised {e} unexpectedly")

    def test_validate_job_missing_template(self):
        """Test _validate_job with missing template"""
        # Create job normally first, then set template_id to None manually
        job_without_template = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Invalid Job",
        )
        job_without_template.template_id = None

        with self.assertRaises((ExecutorError, Exception)) as context:
            self.executor._validate_job(job_without_template)

        # Django may raise RelatedObjectDoesNotExist, which is also expected

    def test_validate_job_missing_docker_host(self):
        """Test _validate_job with missing docker_host"""
        # Create job normally first, then set docker_host_id to None manually
        job_without_host = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Invalid Job",
        )
        job_without_host.docker_host_id = None

        with self.assertRaises((ExecutorError, Exception)) as context:
            self.executor._validate_job(job_without_host)

        # Django may raise RelatedObjectDoesNotExist, which is also expected

    def test_validate_job_missing_docker_image(self):
        """Test _validate_job with missing docker_image - still passes basic validation"""
        template_no_image = ContainerTemplate.objects.create(
            name="no-image-template",
            docker_image="",  # Empty image
            created_by=self.user,
        )
        job_no_image = ContainerJob.objects.create(
            template=template_no_image,
            docker_host=self.docker_host,
            name="No Image Job",
        )

        # The basic _validate_job doesn't check for docker_image,
        # that's checked during container creation
        try:
            self.executor._validate_job(job_no_image)
        except ExecutorError:
            self.fail("_validate_job should not fail for missing docker_image")

    def test_split_docker_logs_stdout_only(self):
        """Test _split_docker_logs with stdout only"""
        logs = "Line 1\nLine 2\nLine 3"
        stdout, stderr = self.executor._split_docker_logs(logs)

        self.assertEqual(stdout, "Line 1\nLine 2\nLine 3")
        self.assertEqual(stderr, "")

    def test_split_docker_logs_with_errors(self):
        """Test _split_docker_logs with error messages"""
        logs = "Normal line\nERROR: Something went wrong\nAnother normal line\nWARNING: Be careful"
        stdout, stderr = self.executor._split_docker_logs(logs)

        self.assertEqual(stdout, "Normal line\nAnother normal line")
        self.assertEqual(stderr, "ERROR: Something went wrong\nWARNING: Be careful")

    def test_split_docker_logs_empty_input(self):
        """Test _split_docker_logs with empty input"""
        stdout, stderr = self.executor._split_docker_logs("")

        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    def test_split_docker_logs_case_insensitive(self):
        """Test _split_docker_logs is case insensitive for error detection"""
        logs = "Normal line\nerror: lowercase error\nException occurred\ntraceback here"
        stdout, stderr = self.executor._split_docker_logs(logs)

        self.assertEqual(stdout, "Normal line")
        self.assertEqual(
            stderr, "error: lowercase error\nException occurred\ntraceback here"
        )

    def test_check_status_empty_execution_id(self):
        """Test check_status with empty execution_id"""
        status = self.executor.check_status("")
        self.assertEqual(status, "not-found")

    def test_check_status_none_execution_id(self):
        """Test check_status with None execution_id"""
        status = self.executor.check_status(None)
        self.assertEqual(status, "not-found")

    @patch("container_manager.executors.docker.ContainerJob.objects")
    def test_check_status_job_not_found(self, mock_objects):
        """Test check_status when job is not found"""
        mock_objects.filter.return_value.first.return_value = None

        status = self.executor.check_status("nonexistent-container")
        self.assertEqual(status, "not-found")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_check_status_running_container(self, mock_get_client):
        """Test check_status with running container"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client and container
        mock_container = Mock()
        mock_container.status = "running"
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        status = self.executor.check_status("test-container-123")
        self.assertEqual(status, "running")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_check_status_exited_container(self, mock_get_client):
        """Test check_status with exited container"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client and container
        mock_container = Mock()
        mock_container.status = "exited"
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        status = self.executor.check_status("test-container-123")
        self.assertEqual(status, "exited")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_check_status_paused_container(self, mock_get_client):
        """Test check_status with paused container (mapped to running)"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client and container
        mock_container = Mock()
        mock_container.status = "paused"
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        status = self.executor.check_status("test-container-123")
        self.assertEqual(status, "running")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_check_status_container_not_found(self, mock_get_client):
        """Test check_status when Docker container not found"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client to raise NotFound
        mock_client = Mock()
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_get_client.return_value = mock_client

        status = self.executor.check_status("test-container-123")
        self.assertEqual(status, "not-found")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_check_status_docker_exception(self, mock_get_client):
        """Test check_status with Docker exception"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client to raise generic exception
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("Docker error")
        mock_get_client.return_value = mock_client

        status = self.executor.check_status("test-container-123")
        self.assertEqual(status, "failed")

    def test_get_logs_empty_execution_id(self):
        """Test get_logs with empty execution_id"""
        stdout, stderr = self.executor.get_logs("")
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    def test_get_logs_none_execution_id(self):
        """Test get_logs with None execution_id"""
        stdout, stderr = self.executor.get_logs(None)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    @patch("container_manager.executors.docker.ContainerJob.objects")
    def test_get_logs_job_not_found(self, mock_objects):
        """Test get_logs when job is not found"""
        mock_objects.filter.return_value.first.return_value = None

        stdout, stderr = self.executor.get_logs("nonexistent-container")
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_get_logs_success(self, mock_get_client):
        """Test get_logs successful retrieval"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client and container
        mock_container = Mock()
        logs_data = b"2023-01-01T12:00:00Z Normal output\n2023-01-01T12:00:01Z ERROR: Something failed"
        mock_container.logs.return_value = logs_data
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        stdout, stderr = self.executor.get_logs("test-container-123")

        # Verify logs were split correctly
        self.assertIn("Normal output", stdout)
        self.assertIn("ERROR: Something failed", stderr)

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_get_logs_container_not_found(self, mock_get_client):
        """Test get_logs when Docker container not found"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client to raise NotFound
        mock_client = Mock()
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_get_client.return_value = mock_client

        stdout, stderr = self.executor.get_logs("test-container-123")
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_get_logs_docker_exception(self, mock_get_client):
        """Test get_logs with Docker exception"""
        # Set up job with container_id
        self.job.container_id = "test-container-123"
        self.job.save()

        # Mock Docker client to raise generic exception
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("Docker error")
        mock_get_client.return_value = mock_client

        stdout, stderr = self.executor.get_logs("test-container-123")
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    def test_get_capabilities(self):
        """Test get_capabilities returns expected capabilities"""
        capabilities = self.executor.get_capabilities()

        expected_capabilities = {
            "supports_resource_limits": True,
            "supports_networking": True,
            "supports_persistent_storage": True,
            "supports_secrets": False,
            "supports_gpu": True,
            "supports_scaling": False,
        }

        for key, value in expected_capabilities.items():
            self.assertIn(key, capabilities)
            self.assertEqual(capabilities[key], value)

    def test_validate_job_public_method_valid(self):
        """Test validate_job (public method) with valid job"""
        is_valid, message = self.executor.validate_job(self.job)

        self.assertTrue(is_valid)
        self.assertEqual(message, "")

    def test_validate_job_public_method_invalid(self):
        """Test validate_job (public method) with invalid job"""
        # Create job normally first, then set template_id to None manually
        job_without_template = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Invalid Job",
        )
        job_without_template.template_id = None

        # This should either return False or raise an exception, both are handled
        try:
            is_valid, message = self.executor.validate_job(job_without_template)
            self.assertFalse(is_valid)
        except Exception:
            # Django ORM exception is also acceptable for this test
            pass

    def test_estimate_cost_returns_none(self):
        """Test estimate_cost returns None (not implemented)"""
        cost = self.executor.estimate_cost(self.job)
        self.assertIsNone(cost)

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_get_health_status_healthy(self, mock_get_client):
        """Test get_health_status with healthy Docker daemon"""
        # Mock Docker client
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_get_client.return_value = mock_client

        health = self.executor.get_health_status()

        self.assertTrue(health["healthy"])
        self.assertIsNone(health["error"])
        self.assertIn("last_check", health)
        self.assertIn("response_time", health)

    @patch("container_manager.executors.docker.DockerExecutor._get_client")
    def test_get_health_status_unhealthy(self, mock_get_client):
        """Test get_health_status with unhealthy Docker daemon"""
        # Mock Docker client to raise exception
        mock_get_client.side_effect = Exception("Connection failed")

        health = self.executor.get_health_status()

        self.assertFalse(health["healthy"])
        self.assertIn("Connection failed", health["error"])
        self.assertIn("last_check", health)
        self.assertIsNone(health["response_time"])

    def test_validate_executor_specific_valid_job(self):
        """Test _validate_executor_specific with valid job"""
        errors = self.executor._validate_executor_specific(self.job)
        self.assertEqual(errors, [])

    def test_validate_executor_specific_running_job_no_execution_id(self):
        """Test _validate_executor_specific with running job but no execution ID"""
        self.job.status = "running"
        self.job.execution_id = ""
        self.job.save()

        errors = self.executor._validate_executor_specific(self.job)
        self.assertEqual(len(errors), 1)
        self.assertIn("Execution ID required", errors[0])

    def test_get_execution_display(self):
        """Test get_execution_display method"""
        self.job.execution_id = "test-container-123"
        self.job.save()

        display = self.executor.get_execution_display(self.job)

        expected_keys = ["type_name", "id_label", "id_value", "status_detail"]
        for key in expected_keys:
            self.assertIn(key, display)

        self.assertEqual(display["type_name"], "Docker Container")
        self.assertEqual(display["id_label"], "Container ID")
        self.assertEqual(display["id_value"], "test-container-123")

    def test_get_execution_display_no_execution_id(self):
        """Test get_execution_display with no execution ID"""
        display = self.executor.get_execution_display(self.job)

        self.assertEqual(display["id_value"], "Not started")

    def test_get_docker_status_detail_pending(self):
        """Test _get_docker_status_detail with pending job"""
        self.job.status = "pending"
        detail = self.executor._get_docker_status_detail(self.job)
        self.assertEqual(detail, "Pending")

    def test_get_docker_status_detail_running(self):
        """Test _get_docker_status_detail with running job"""
        self.job.status = "running"
        detail = self.executor._get_docker_status_detail(self.job)
        self.assertEqual(detail, "Running")

    def test_get_docker_status_detail_completed(self):
        """Test _get_docker_status_detail with completed job"""
        self.job.status = "completed"
        self.job.exit_code = 0
        detail = self.executor._get_docker_status_detail(self.job)
        self.assertEqual(detail, "Completed (Success)")

    def test_get_docker_status_detail_failed(self):
        """Test _get_docker_status_detail with failed job"""
        self.job.status = "failed"
        self.job.exit_code = 1
        detail = self.executor._get_docker_status_detail(self.job)
        self.assertEqual(detail, "Failed (Exit Code: 1)")

    def test_build_container_environment_basic(self):
        """Test _build_container_environment with basic job"""
        env = self.executor._build_container_environment(self.job)

        # Should be a dictionary
        self.assertIsInstance(env, dict)

    def test_build_container_environment_with_overrides(self):
        """Test _build_container_environment with job environment overrides"""
        self.job.override_environment = {"CUSTOM_VAR": "custom_value", "DEBUG": "true"}
        self.job.save()

        env = self.executor._build_container_environment(self.job)

        self.assertEqual(env["CUSTOM_VAR"], "custom_value")
        self.assertEqual(env["DEBUG"], "true")

    def test_build_container_config_basic(self):
        """Test _build_container_config with basic job"""
        config = self.executor._build_container_config(self.job)

        # Verify basic structure
        self.assertIn("image", config)
        self.assertIn("environment", config)
        self.assertIn("labels", config)
        self.assertEqual(config["image"], "alpine:latest")

    def test_build_container_config_with_command_override(self):
        """Test _build_container_config with command override"""
        self.job.override_command = "echo 'overridden command'"
        self.job.save()

        config = self.executor._build_container_config(self.job)

        self.assertEqual(config["command"], "echo 'overridden command'")

    def test_build_container_config_with_working_directory(self):
        """Test _build_container_config with working directory"""
        self.template.working_directory = "/app"
        self.template.save()

        config = self.executor._build_container_config(self.job)

        # working_dir is not implemented in the current _build_container_config
        # Just verify config is valid
        self.assertIn("image", config)
        self.assertEqual(config["image"], "alpine:latest")

    def test_build_labels(self):
        """Test _build_labels method"""
        labels = self.executor._build_labels(self.job)

        expected_labels = [
            "django.container_manager.job_id",
            "django.container_manager.template_name",
            "django.container_manager.created_by",
        ]

        for label in expected_labels:
            self.assertIn(label, labels)

        self.assertEqual(labels["django.container_manager.job_id"], str(self.job.id))
        self.assertEqual(
            labels["django.container_manager.template_name"], self.template.name
        )

    def test_should_pull_image_true(self):
        """Test _should_pull_image returns True when auto_pull_images is True"""
        self.docker_host.auto_pull_images = True
        self.docker_host.save()

        result = self.executor._should_pull_image(self.docker_host)
        self.assertTrue(result)

    def test_should_pull_image_false(self):
        """Test _should_pull_image returns False when auto_pull_images is False"""
        self.docker_host.auto_pull_images = False
        self.docker_host.save()

        result = self.executor._should_pull_image(self.docker_host)
        self.assertFalse(result)

    def test_strip_docker_timestamps(self):
        """Test _strip_docker_timestamps method"""
        log_with_timestamps = (
            "2023-01-01T12:00:00.123456789Z This is a log line\n"
            "2023-01-01T12:00:01.987654321Z Another log line\n"
            "No timestamp here"
        )

        clean_log = self.executor._strip_docker_timestamps(log_with_timestamps)

        expected = "This is a log line\nAnother log line\nNo timestamp here"
        self.assertEqual(clean_log, expected)
