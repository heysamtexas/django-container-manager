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
from container_manager.models import ContainerJob, ExecutorHost


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

        # Templates no longer needed - using direct job configuration

        # Create test job
        self.job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Test Job",
            executor_type="docker",
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

        # Templates no longer needed - using direct job configuration

        self.job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Test Job",
            executor_type="docker",
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

        # Templates no longer needed - using direct job configuration

        self.job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Test Job",
            executor_type="docker",
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


class DockerServiceUncoveredMethodsTest(TestCase):
    """Test previously uncovered methods in DockerService"""

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

        self.job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Test Job",
            executor_type="docker",
            created_by=self.user,
            container_id="container_123",
        )

        self.service = DockerService()

    def test_get_container_logs_no_container_id(self):
        """Test get_container_logs with no container ID"""
        self.job.container_id = ""
        self.job.save()

        logs = list(self.service.get_container_logs(self.job))
        self.assertEqual(logs, [])

    def test_get_container_logs_streaming_mode(self):
        """Test get_container_logs in streaming mode"""
        mock_client = Mock()
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container

        # Mock streaming logs (generator of bytes)
        mock_container.logs.return_value = [b"log line 1\n", b"log line 2\n"]

        with patch.object(self.service, "get_client", return_value=mock_client):
            logs = list(self.service.get_container_logs(self.job, follow=True))

            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[0], "log line 1\n")
            self.assertEqual(logs[1], "log line 2\n")
            mock_container.logs.assert_called_once_with(
                stream=True, follow=True, tail="all", timestamps=True
            )

    def test_get_container_logs_non_streaming_bytes(self):
        """Test get_container_logs non-streaming mode with bytes"""
        mock_client = Mock()
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container

        # Mock non-streaming logs (single bytes object)
        mock_container.logs.return_value = b"Complete log output\n"

        with patch.object(self.service, "get_client", return_value=mock_client):
            logs = list(self.service.get_container_logs(self.job, follow=False))

            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0], "Complete log output\n")

    def test_get_container_logs_non_streaming_string(self):
        """Test get_container_logs non-streaming mode with string"""
        mock_client = Mock()
        mock_container = Mock()
        mock_client.containers.get.return_value = mock_container

        # Mock non-streaming logs (string)
        mock_container.logs.return_value = "String log output\n"

        with patch.object(self.service, "get_client", return_value=mock_client):
            logs = list(self.service.get_container_logs(self.job, follow=False))

            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0], "String log output\n")

    def test_get_container_logs_container_not_found(self):
        """Test get_container_logs when container not found"""
        from docker.errors import NotFound

        mock_client = Mock()
        mock_client.containers.get.side_effect = NotFound("Container not found")

        with patch.object(self.service, "get_client", return_value=mock_client):
            logs = list(self.service.get_container_logs(self.job))

            self.assertEqual(logs, [])

    def test_get_container_logs_general_exception(self):
        """Test get_container_logs with general exception"""
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("General error")

        with patch.object(self.service, "get_client", return_value=mock_client):
            logs = list(self.service.get_container_logs(self.job))

            self.assertEqual(logs, [])

    def test_get_container_stats_success(self):
        """Test get_container_stats success path"""
        mock_client = Mock()
        mock_container = Mock()
        expected_stats = {"memory": {"usage": 1024}, "cpu": {"usage": 50}}
        mock_container.stats.return_value = expected_stats
        mock_client.containers.get.return_value = mock_container

        with patch.object(self.service, "get_client", return_value=mock_client):
            stats = self.service.get_container_stats(self.job)

            self.assertEqual(stats, expected_stats)
            mock_container.stats.assert_called_once_with(stream=False)

    def test_get_container_stats_no_container_id(self):
        """Test get_container_stats with no container ID"""
        self.job.container_id = ""
        self.job.save()

        stats = self.service.get_container_stats(self.job)
        self.assertIsNone(stats)

    def test_get_container_stats_container_not_found(self):
        """Test get_container_stats when container not found"""
        from docker.errors import NotFound

        mock_client = Mock()
        mock_client.containers.get.side_effect = NotFound("Container not found")

        with patch.object(self.service, "get_client", return_value=mock_client):
            stats = self.service.get_container_stats(self.job)

            self.assertIsNone(stats)

    def test_get_container_stats_general_exception(self):
        """Test get_container_stats with general exception"""
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("General error")

        with patch.object(self.service, "get_client", return_value=mock_client):
            stats = self.service.get_container_stats(self.job)

            self.assertIsNone(stats)

    def test_wait_for_container_success(self):
        """Test wait_for_container success path"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_client.containers.get.return_value = mock_container

        with patch.object(self.service, "get_client", return_value=mock_client):
            with patch.object(self.service, "_collect_execution_data") as mock_collect:
                exit_code = self.service.wait_for_container(self.job)

                self.assertEqual(exit_code, 0)
                self.job.refresh_from_db()
                self.assertEqual(self.job.exit_code, 0)
                self.assertEqual(self.job.status, "completed")
                self.assertIsNotNone(self.job.completed_at)
                mock_collect.assert_called_once_with(self.job)

    def test_wait_for_container_failure(self):
        """Test wait_for_container with non-zero exit code"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_client.containers.get.return_value = mock_container

        with patch.object(self.service, "get_client", return_value=mock_client):
            with patch.object(self.service, "_collect_execution_data") as mock_collect:
                exit_code = self.service.wait_for_container(self.job)

                self.assertEqual(exit_code, 1)
                self.job.refresh_from_db()
                self.assertEqual(self.job.exit_code, 1)
                self.assertEqual(self.job.status, "failed")
                mock_collect.assert_called_once_with(self.job)

    def test_wait_for_container_no_container_id(self):
        """Test wait_for_container with no container ID"""
        self.job.container_id = ""
        self.job.save()

        exit_code = self.service.wait_for_container(self.job)
        self.assertIsNone(exit_code)

    def test_wait_for_container_not_found(self):
        """Test wait_for_container when container not found"""
        from docker.errors import NotFound

        mock_client = Mock()
        mock_client.containers.get.side_effect = NotFound("Container not found")

        with patch.object(self.service, "get_client", return_value=mock_client):
            exit_code = self.service.wait_for_container(self.job)

            self.assertIsNone(exit_code)

    def test_wait_for_container_general_exception(self):
        """Test wait_for_container with general exception"""
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("General error")

        with patch.object(self.service, "get_client", return_value=mock_client):
            exit_code = self.service.wait_for_container(self.job)

            self.assertIsNone(exit_code)

    def test_collect_execution_data_success(self):
        """Test _collect_execution_data delegates to executor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            self.service._collect_execution_data(self.job)

            mock_executor._collect_data.assert_called_once_with(self.job)

    def test_collect_execution_data_exception(self):
        """Test _collect_execution_data handles exceptions"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._collect_data.side_effect = Exception("Collection failed")
            mock_executor_class.return_value = mock_executor

            # Should not raise exception
            self.service._collect_execution_data(self.job)

    def test_cleanup_container_after_execution_success(self):
        """Test _cleanup_container_after_execution delegates to executor"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            self.service._cleanup_container_after_execution(self.job)

            mock_executor._immediate_cleanup.assert_called_once_with(self.job)

    def test_cleanup_container_after_execution_exception(self):
        """Test _cleanup_container_after_execution handles exceptions"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor._immediate_cleanup.side_effect = Exception("Cleanup failed")
            mock_executor_class.return_value = mock_executor

            # Should not raise exception
            self.service._cleanup_container_after_execution(self.job)

    def test_launch_job_success(self):
        """Test launch_job success path"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.launch_job.return_value = (True, "container_123")
            mock_executor_class.return_value = mock_executor

            result = self.service.launch_job(self.job)

            self.assertTrue(result)
            mock_executor.launch_job.assert_called_once_with(self.job)

    def test_launch_job_executor_failure(self):
        """Test launch_job when executor returns failure"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.launch_job.return_value = (False, "Launch failed")
            mock_executor_class.return_value = mock_executor

            result = self.service.launch_job(self.job)

            self.assertFalse(result)

    def test_launch_job_exception(self):
        """Test launch_job with exception"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.launch_job.side_effect = Exception("Launch exception")
            mock_executor_class.return_value = mock_executor

            result = self.service.launch_job(self.job)

            self.assertFalse(result)
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, "failed")
            self.assertIsNotNone(self.job.completed_at)

    def test_discover_running_containers_success(self):
        """Test discover_running_containers success path"""
        mock_client = Mock()
        expected_containers = [Mock(), Mock()]
        mock_client.containers.list.return_value = expected_containers

        with patch.object(self.service, "get_client", return_value=mock_client):
            containers = self.service.discover_running_containers(self.docker_host)

            self.assertEqual(containers, expected_containers)
            mock_client.containers.list.assert_called_once_with(
                filters={"label": "django.container_manager.job_id"}
            )

    def test_discover_running_containers_exception(self):
        """Test discover_running_containers with exception"""
        mock_client = Mock()
        mock_client.containers.list.side_effect = Exception("Discovery failed")

        with patch.object(self.service, "get_client", return_value=mock_client):
            containers = self.service.discover_running_containers(self.docker_host)

            self.assertEqual(containers, [])

    def test_check_container_status_success(self):
        """Test check_container_status success path"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "running"
            mock_executor_class.return_value = mock_executor

            status = self.service.check_container_status(self.job)

            self.assertEqual(status, "running")
            mock_executor.check_status.assert_called_once_with("container_123")

    def test_check_container_status_no_container_id(self):
        """Test check_container_status with no container ID"""
        self.job.container_id = ""
        self.job.save()

        status = self.service.check_container_status(self.job)
        self.assertEqual(status, "no-container")

    def test_check_container_status_not_found(self):
        """Test check_container_status maps not-found status"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "not-found"
            mock_executor_class.return_value = mock_executor

            status = self.service.check_container_status(self.job)

            self.assertEqual(status, "not-found")

    def test_check_container_status_failed_mapping(self):
        """Test check_container_status maps failed to error"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "failed"
            mock_executor_class.return_value = mock_executor

            status = self.service.check_container_status(self.job)

            self.assertEqual(status, "error")

    def test_check_container_status_exception(self):
        """Test check_container_status with exception"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.check_status.side_effect = Exception("Status check failed")
            mock_executor_class.return_value = mock_executor

            status = self.service.check_container_status(self.job)

            self.assertEqual(status, "error")

    def test_harvest_completed_job_success(self):
        """Test harvest_completed_job success path"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.harvest_job.return_value = True
            mock_executor_class.return_value = mock_executor

            result = self.service.harvest_completed_job(self.job)

            self.assertTrue(result)
            mock_executor.harvest_job.assert_called_once_with(self.job)

    def test_harvest_completed_job_exception(self):
        """Test harvest_completed_job with exception"""
        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.harvest_job.side_effect = Exception("Harvest failed")
            mock_executor_class.return_value = mock_executor

            result = self.service.harvest_completed_job(self.job)

            self.assertFalse(result)


class DockerServiceCleanupTest(TestCase):
    """Test cleanup operations in DockerService"""

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

        self.service = DockerService()

    def test_cleanup_old_containers_success(self):
        """Test cleanup_old_containers with successful cleanup"""
        from datetime import timedelta

        from django.utils import timezone

        # Create old completed job
        old_time = timezone.now() - timedelta(hours=25)

        old_job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Old Job",
            executor_type="docker",
            status="completed",
            container_id="old_container_123",
            completed_at=old_time,
            created_by=self.user,
        )

        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.cleanup.return_value = True
            mock_executor_class.return_value = mock_executor

            count = self.service.cleanup_old_containers(orphaned_hours=24)

            self.assertEqual(count, 1)
            mock_executor.cleanup.assert_called_once_with("old_container_123")

            # Check that container_id was cleared
            old_job.refresh_from_db()
            self.assertEqual(old_job.container_id, "")

    def test_cleanup_old_containers_no_orphaned_jobs(self):
        """Test cleanup_old_containers with no orphaned jobs"""
        count = self.service.cleanup_old_containers(orphaned_hours=24)
        self.assertEqual(count, 0)

    def test_cleanup_old_containers_cleanup_failure(self):
        """Test cleanup_old_containers with cleanup failure"""
        from datetime import timedelta

        from django.utils import timezone

        # Create old completed job
        old_time = timezone.now() - timedelta(hours=25)

        old_job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Old Job",
            executor_type="docker",
            status="completed",
            container_id="old_container_123",
            completed_at=old_time,
            created_by=self.user,
        )

        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.cleanup.side_effect = Exception("Cleanup failed")
            mock_executor_class.return_value = mock_executor

            count = self.service.cleanup_old_containers(orphaned_hours=24)

            self.assertEqual(count, 0)  # No successful cleanups

            # Check that container_id was NOT cleared due to failure
            old_job.refresh_from_db()
            self.assertEqual(old_job.container_id, "old_container_123")

    def test_cleanup_old_containers_empty_container_id(self):
        """Test cleanup_old_containers skips jobs with empty container_id"""
        from datetime import timedelta

        from django.utils import timezone

        # Create old completed job with no container_id
        old_time = timezone.now() - timedelta(hours=25)

        ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            name="Old Job",
            executor_type="docker",
            status="completed",
            container_id="",  # Empty container_id
            completed_at=old_time,
            created_by=self.user,
        )

        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            count = self.service.cleanup_old_containers(orphaned_hours=24)

            self.assertEqual(count, 0)
            # Should not attempt cleanup for empty container_id
            mock_executor.cleanup.assert_not_called()

    def test_cleanup_old_containers_multiple_statuses(self):
        """Test cleanup_old_containers handles multiple completion statuses"""
        from datetime import timedelta

        from django.utils import timezone

        old_time = timezone.now() - timedelta(hours=25)

        # Create jobs in different completion states
        statuses = ["completed", "failed", "timeout", "cancelled"]
        jobs = []

        for i, status in enumerate(statuses):
            job = ContainerJob.objects.create(
                docker_host=self.docker_host,
                docker_image="alpine:latest",
                name=f"Job {i}",
                executor_type="docker",
                status=status,
                container_id=f"container_{i}",
                completed_at=old_time,
                created_by=self.user,
            )
            jobs.append(job)

        with patch(
            "container_manager.docker_service.DockerExecutor"
        ) as mock_executor_class:
            mock_executor = Mock()
            mock_executor.cleanup.return_value = True
            mock_executor_class.return_value = mock_executor

            count = self.service.cleanup_old_containers(orphaned_hours=24)

            self.assertEqual(count, 4)  # All 4 jobs should be cleaned
            self.assertEqual(mock_executor.cleanup.call_count, 4)
