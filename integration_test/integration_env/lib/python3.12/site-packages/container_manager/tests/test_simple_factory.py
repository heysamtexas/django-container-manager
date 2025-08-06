"""
Tests for the simplified ExecutorProvider (formerly ExecutorFactory).
"""

from django.contrib.auth.models import User
from django.test import TestCase

from container_manager.executors.factory import ExecutorProvider
from container_manager.models import ContainerJob, ExecutorHost


class SimpleExecutorProviderTest(TestCase):
    """Test the simplified ExecutorProvider for executor creation."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Create test executor host
        self.host = ExecutorHost.objects.create(
            name="test-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            weight=100,
        )

        self.provider = ExecutorProvider()

    def test_get_executor_with_job(self):
        """Test getting executor instance via job."""
        job = ContainerJob.objects.create(
            docker_host=self.host,
            docker_image="nginx:latest",
            name="test-job",
            memory_limit=512,
            cpu_limit=1.0,
            created_by=self.user,
        )

        executor = self.provider.get_executor(job)

        self.assertIsNotNone(executor)
        self.assertEqual(executor.docker_host, self.host)

    def test_get_executor_with_host(self):
        """Test getting executor instance via host directly."""
        executor = self.provider.get_executor(self.host)

        self.assertIsNotNone(executor)
        self.assertEqual(executor.docker_host, self.host)

    def test_executor_consistency(self):
        """Test that same host produces same executor type."""
        job = ContainerJob.objects.create(
            docker_host=self.host,
            docker_image="nginx:latest",
            name="test-job",
            created_by=self.user,
        )

        executor1 = self.provider.get_executor(job)
        executor2 = self.provider.get_executor(self.host)

        # Should be same cached instance
        self.assertIs(executor1, executor2)
