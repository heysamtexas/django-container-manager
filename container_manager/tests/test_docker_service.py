"""
Tests for docker_service module (backward compatibility layer).

This test file focuses on testing the legacy DockerService interface
that wraps the new DockerExecutor implementation.
"""

from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from container_manager.docker_service import (
    ContainerExecutionError,
    DockerConnectionError,
    DockerService,
    docker_service,
)
from container_manager.executors.exceptions import (
    ExecutorConnectionError,
    ExecutorError,
)
from container_manager.models import ContainerJob, ContainerTemplate, ExecutorHost


class DockerServiceTest(TestCase):
    """Test suite for DockerService backward compatibility layer"""

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
            auto_pull_images=True,
        )

        # Create test template
        self.template = ContainerTemplate.objects.create(
            name="test-template",
            description="Test template",
            docker_image="alpine:latest",
            command='echo "test"',
            timeout_seconds=300,
            created_by=self.user,
        )

        # Create test job
        self.job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Test Job",
            created_by=self.user,
        )

        # Create service instance
        self.service = DockerService()

    def test_docker_service_initialization(self):
        """Test DockerService initializes properly"""
        service = DockerService()
        self.assertIsInstance(service._executors, dict)
        self.assertEqual(len(service._executors), 0)

    def test_get_executor_creates_new_executor(self):
        """Test _get_executor creates new DockerExecutor for new host"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            executor = self.service._get_executor(self.docker_host)

            self.assertEqual(executor, mock_executor)
            mock_executor_class.assert_called_once_with(
                {"docker_host": self.docker_host}
            )
            # Should cache the executor
            self.assertIn(str(self.docker_host.id), self.service._executors)

    def test_get_executor_reuses_cached_executor(self):
        """Test _get_executor reuses cached DockerExecutor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            # First call
            executor1 = self.service._get_executor(self.docker_host)
            # Second call
            executor2 = self.service._get_executor(self.docker_host)

            self.assertEqual(executor1, executor2)
            # Should only create executor once
            mock_executor_class.assert_called_once()

    def test_should_auto_pull_images_delegates_to_executor(self):
        """Test _should_auto_pull_images delegates to executor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._should_pull_image.return_value = True
            mock_executor_class.return_value = mock_executor

            result = self.service._should_auto_pull_images(self.docker_host)

            self.assertTrue(result)
            mock_executor._should_pull_image.assert_called_once_with(self.docker_host)

    def test_build_container_labels_delegates_to_executor(self):
        """Test _build_container_labels delegates to executor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            expected_labels = {"test": "label"}
            mock_executor._build_labels.return_value = expected_labels
            mock_executor_class.return_value = mock_executor

            labels = self.service._build_container_labels(self.job)

            self.assertEqual(labels, expected_labels)
            mock_executor._build_labels.assert_called_once_with(self.job)

    def test_get_client_success(self):
        """Test get_client successful delegation to executor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_client = Mock()
            mock_executor = Mock()
            mock_executor._get_client.return_value = mock_client
            mock_executor_class.return_value = mock_executor

            client = self.service.get_client(self.docker_host)

            self.assertEqual(client, mock_client)
            mock_executor._get_client.assert_called_once_with(self.docker_host)

    def test_get_client_connection_error(self):
        """Test get_client raises DockerConnectionError on executor error"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._get_client.side_effect = ExecutorConnectionError(
                "Connection failed"
            )
            mock_executor_class.return_value = mock_executor

            with self.assertRaises(DockerConnectionError) as context:
                self.service.get_client(self.docker_host)

            self.assertIn("Connection failed", str(context.exception))

    def test_create_container_success(self):
        """Test create_container successful delegation to executor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            expected_container_id = "container_123"
            mock_executor._create_container.return_value = expected_container_id
            mock_executor_class.return_value = mock_executor

            container_id = self.service.create_container(self.job)

            self.assertEqual(container_id, expected_container_id)
            mock_executor._create_container.assert_called_once_with(self.job)

    def test_create_container_executor_error(self):
        """Test create_container raises ContainerExecutionError on executor error"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._create_container.side_effect = ExecutorError(
                "Creation failed"
            )
            mock_executor_class.return_value = mock_executor

            with self.assertRaises(ContainerExecutionError) as context:
                self.service.create_container(self.job)

            self.assertIn("Creation failed", str(context.exception))

    def test_start_container_success(self):
        """Test start_container successful delegation to executor"""
        self.job.container_id = "container_123"
        self.job.save()

        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._start_container.return_value = True
            mock_executor_class.return_value = mock_executor

            result = self.service.start_container(self.job)

            self.assertTrue(result)
            mock_executor._start_container.assert_called_once_with(
                self.job, "container_123"
            )

    def test_start_container_no_container_id(self):
        """Test start_container raises error when no container ID"""
        self.job.container_id = ""
        self.job.save()

        with self.assertRaises(ContainerExecutionError) as context:
            self.service.start_container(self.job)

        self.assertIn("No container ID", str(context.exception))

    def test_start_container_executor_error(self):
        """Test start_container handles executor error gracefully"""
        self.job.container_id = "container_123"
        self.job.save()

        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._start_container.side_effect = ExecutorError("Start failed")
            mock_executor_class.return_value = mock_executor

            result = self.service.start_container(self.job)

            self.assertFalse(result)
            # Job should be marked as failed
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, "failed")

    def test_backward_compatibility_exception_classes(self):
        """Test backward compatibility exception classes inherit properly"""
        # Test DockerConnectionError
        docker_error = DockerConnectionError("Docker connection failed")
        self.assertIsInstance(docker_error, ExecutorConnectionError)

        # Test ContainerExecutionError
        exec_error = ContainerExecutionError("Container execution failed")
        self.assertIsInstance(exec_error, ExecutorError)

    def test_global_docker_service_instance(self):
        """Test that docker_service global instance exists"""

        self.assertIsInstance(docker_service, DockerService)


class DockerServiceIntegrationTest(TestCase):
    """Integration tests for DockerService with more complex scenarios"""

    def setUp(self):
        super().setUp()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Create multiple hosts
        self.host1 = ExecutorHost.objects.create(
            name="host1",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            executor_type="docker",
        )

        self.host2 = ExecutorHost.objects.create(
            name="host2",
            host_type="tcp",
            connection_string="tcp://localhost:2376",
            is_active=True,
            executor_type="docker",
        )

        self.service = DockerService()

    def test_multiple_hosts_separate_executors(self):
        """Test that different hosts get separate executor instances"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor1 = Mock()
            mock_executor2 = Mock()
            mock_executor_class.side_effect = [mock_executor1, mock_executor2]

            executor1 = self.service._get_executor(self.host1)
            executor2 = self.service._get_executor(self.host2)

            self.assertNotEqual(executor1, executor2)
            self.assertEqual(mock_executor_class.call_count, 2)
            # Check cache contains both
            self.assertEqual(len(self.service._executors), 2)

    def test_same_host_reuses_executor(self):
        """Test that same host reuses the same executor instance"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            executor1 = self.service._get_executor(self.host1)
            executor2 = self.service._get_executor(self.host1)

            self.assertEqual(executor1, executor2)
            mock_executor_class.assert_called_once()
            # Check cache contains only one entry
            self.assertEqual(len(self.service._executors), 1)


class DockerServiceLegacyMethodsTest(TestCase):
    """Test legacy methods in DockerService for backward compatibility"""

    def setUp(self):
        super().setUp()

        # Create test data
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            executor_type="docker",
        )

        self.template = ContainerTemplate.objects.create(
            name="test-template",
            docker_image="alpine:latest",
            command='echo "test"',
            created_by=self.user,
        )

        self.job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Test Job",
            created_by=self.user,
        )

        self.service = DockerService()

    def test_create_container_with_environment_parameter(self):
        """Test create_container accepts environment parameter for backward compatibility"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._create_container.return_value = "container_123"
            mock_executor_class.return_value = mock_executor

            # Legacy interface accepts environment parameter but ignores it
            container_id = self.service.create_container(
                self.job, environment={"TEST": "value"}
            )

            self.assertEqual(container_id, "container_123")
            # Environment parameter is ignored in current implementation
            mock_executor._create_container.assert_called_once_with(self.job)

    def test_service_maintains_state_across_calls(self):
        """Test that DockerService maintains executor cache across multiple calls"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            # Make multiple calls that should reuse the same executor
            self.service._get_executor(self.docker_host)
            self.service._should_auto_pull_images(self.docker_host)
            self.service._build_container_labels(self.job)

            # Should only create one executor instance
            mock_executor_class.assert_called_once()
            self.assertEqual(len(self.service._executors), 1)


class DockerServiceAdditionalMethodsTest(TestCase):
    """Test additional methods in DockerService for better coverage"""

    def setUp(self):
        super().setUp()

        # Create test data
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            executor_type="docker",
        )

        self.template = ContainerTemplate.objects.create(
            name="test-template",
            docker_image="alpine:latest",
            command='echo "test"',
            created_by=self.user,
        )

        self.job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Test Job",
            created_by=self.user,
            container_id="container_123",
        )

        self.service = DockerService()

    @patch("container_manager.docker_service.docker.DockerClient")
    def test_stop_container_success(self, mock_docker_client):
        """Test stop_container success path"""
        # Mock container and client
        mock_container = Mock()
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container

        with patch.object(self.service, "get_client", return_value=mock_client):
            result = self.service.stop_container(self.job)

            self.assertTrue(result)
            mock_client.containers.get.assert_called_once_with("container_123")
            mock_container.stop.assert_called_once_with(timeout=10)

    @patch("container_manager.docker_service.docker.DockerClient")
    def test_stop_container_custom_timeout(self, mock_docker_client):
        """Test stop_container with custom timeout"""
        mock_container = Mock()
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container

        with patch.object(self.service, "get_client", return_value=mock_client):
            result = self.service.stop_container(self.job, timeout=30)

            self.assertTrue(result)
            mock_container.stop.assert_called_once_with(timeout=30)

    def test_stop_container_no_container_id(self):
        """Test stop_container with no container ID"""
        self.job.container_id = ""
        self.job.save()

        result = self.service.stop_container(self.job)

        self.assertFalse(result)

    def test_stop_container_not_found(self):
        """Test stop_container when container not found"""
        from docker.errors import NotFound

        mock_client = Mock()
        mock_client.containers.get.side_effect = NotFound("Container not found")

        with patch.object(self.service, "get_client", return_value=mock_client):
            result = self.service.stop_container(self.job)

            self.assertFalse(result)

    def test_stop_container_exception(self):
        """Test stop_container with general exception"""
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("General error")

        with patch.object(self.service, "get_client", return_value=mock_client):
            result = self.service.stop_container(self.job)

            self.assertFalse(result)

    def test_remove_container_success(self):
        """Test remove_container success path"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.cleanup.return_value = True
            mock_executor_class.return_value = mock_executor

            result = self.service.remove_container(self.job)

            self.assertTrue(result)
            mock_executor.cleanup.assert_called_once_with("container_123")

    def test_remove_container_no_container_id(self):
        """Test remove_container with no container ID"""
        self.job.container_id = ""
        self.job.save()

        result = self.service.remove_container(self.job)

        self.assertFalse(result)

    def test_remove_container_force_parameter(self):
        """Test remove_container with force parameter (legacy compatibility)"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.cleanup.return_value = True
            mock_executor_class.return_value = mock_executor

            # Force parameter is accepted but not used in current implementation
            result = self.service.remove_container(self.job, force=True)

            self.assertTrue(result)
            mock_executor.cleanup.assert_called_once_with("container_123")

    def test_remove_container_exception(self):
        """Test remove_container with exception"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.cleanup.side_effect = Exception("Cleanup failed")
            mock_executor_class.return_value = mock_executor

            result = self.service.remove_container(self.job)

            self.assertFalse(result)
