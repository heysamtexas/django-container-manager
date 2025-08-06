"""
Tests for ExecutorProvider (formerly ExecutorFactory) executor instantiation.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ..executors.exceptions import ExecutorConfigurationError
from ..executors.factory import (
    ExecutorFactory,
    ExecutorProvider,
)  # Test backward compatibility
from ..models import ContainerJob, ExecutorHost


class ExecutorProviderTest(TestCase):
    """Test ExecutorProvider executor instantiation and caching"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Create test Docker host
        self.docker_host = ExecutorHost.objects.create(
            name="test-docker",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            max_concurrent_jobs=5,
            current_job_count=0,
        )

        # Create test CloudRun host
        self.cloudrun_host = ExecutorHost.objects.create(
            name="test-cloudrun",
            executor_type="cloudrun",
            connection_string="",
            is_active=True,
            max_concurrent_jobs=100,
            current_job_count=0,
        )

        # Create test Mock host
        self.mock_host = ExecutorHost.objects.create(
            name="test-mock",
            executor_type="mock",
            connection_string="",
            is_active=True,
            max_concurrent_jobs=10,
            current_job_count=0,
        )

        # Create provider instance
        self.provider = ExecutorProvider()

    def test_get_executor_docker(self):
        """Test getting Docker executor instance"""
        job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            docker_host=self.docker_host,
            created_by=self.user,
        )

        executor = self.provider.get_executor(job)

        self.assertEqual(executor.__class__.__name__, "DockerExecutor")

    def test_get_executor_docker_direct_host(self):
        """Test getting Docker executor instance with direct host"""
        executor = self.provider.get_executor(self.docker_host)

        self.assertEqual(executor.__class__.__name__, "DockerExecutor")

    @patch("container_manager.executors.cloudrun.CloudRunExecutor")
    def test_get_executor_cloudrun(self, mock_cloudrun_class):
        """Test getting CloudRun executor instance"""
        job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            docker_host=self.cloudrun_host,
            created_by=self.user,
        )

        executor = self.provider.get_executor(job)

        # Verify CloudRunExecutor was instantiated
        mock_cloudrun_class.assert_called_once()

    def test_get_executor_mock(self):
        """Test getting Mock executor instance"""
        job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            docker_host=self.mock_host,
            created_by=self.user,
        )

        executor = self.provider.get_executor(job)

        self.assertEqual(executor.__class__.__name__, "MockExecutor")

    def test_get_executor_unknown_type(self):
        """Test error handling for unknown executor type"""
        unknown_host = ExecutorHost.objects.create(
            name="test-unknown",
            executor_type="unknown",
            connection_string="",
            is_active=True,
            max_concurrent_jobs=1,
            current_job_count=0,
        )

        with self.assertRaises(ExecutorConfigurationError):
            self.provider.get_executor(unknown_host)

    # Test removed - docker_host is now required field on ContainerJob

    def test_executor_caching(self):
        """Test that executor instances are cached properly"""
        job1 = ContainerJob.objects.create(
            docker_image="nginx:latest",
            docker_host=self.docker_host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:latest",
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Get executors for both jobs (same host)
        executor1 = self.provider.get_executor(job1)
        executor2 = self.provider.get_executor(job2)

        # Should be the same cached instance
        self.assertIs(executor1, executor2)

    def test_clear_cache(self):
        """Test cache clearing functionality"""
        job = ContainerJob.objects.create(
            docker_image="nginx:latest",
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Get executor to populate cache
        executor1 = self.provider.get_executor(job)

        # Clear cache
        self.provider.clear_cache()

        # Get executor again - should be new instance
        executor2 = self.provider.get_executor(job)

        self.assertIsNot(executor1, executor2)

    def test_backward_compatibility_alias(self):
        """Test that ExecutorFactory alias still works"""
        # Should be the same class
        self.assertIs(ExecutorFactory, ExecutorProvider)

        # Should instantiate successfully
        factory = ExecutorFactory()
        self.assertIsInstance(factory, ExecutorProvider)
