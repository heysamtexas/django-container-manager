"""
Tests for the simplified ExecutorFactory with weight-based routing.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from container_manager.executors.factory import ExecutorFactory
from container_manager.models import ContainerJob, ExecutorHost


class SimpleExecutorFactoryTest(TestCase):
    """Test the simplified ExecutorFactory with weight-based routing."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Create test executor hosts with different weights
        self.host1 = ExecutorHost.objects.create(
            name="host-1",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            weight=100,
        )

        self.host2 = ExecutorHost.objects.create(
            name="host-2",
            executor_type="docker",
            connection_string="tcp://localhost:2376",
            is_active=True,
            weight=200,  # Higher weight = more preferred
        )

        self.factory = ExecutorFactory()

    def test_route_job_weight_based(self):
        """Test that routing respects weights."""
        job = ContainerJob.objects.create(
            docker_host=self.host1,  # Initial assignment
            docker_image="nginx:latest",
            name="test-job",
            memory_limit=512,
            cpu_limit=1.0,
            created_by=self.user,
        )

        # Route the job - should return a ExecutorHost
        selected_host = self.factory.route_job(job)

        self.assertIsNotNone(selected_host)
        self.assertIsInstance(selected_host, ExecutorHost)
        self.assertIn(selected_host, [self.host1, self.host2])

    def test_route_job_no_active_hosts(self):
        """Test routing when no hosts are active."""
        # Deactivate all hosts
        ExecutorHost.objects.all().update(is_active=False)

        job = ContainerJob.objects.create(
            docker_host=self.host1,
            docker_image="nginx:latest",
            name="test-job",
            created_by=self.user,
        )

        selected_host = self.factory.route_job(job)
        self.assertIsNone(selected_host)

    def test_get_executor_docker(self):
        """Test getting Docker executor instance."""
        executor = self.factory.get_executor(self.host1)

        self.assertIsNotNone(executor)
        # Should have the docker host in config
        self.assertEqual(executor.docker_host, self.host1)

    def test_weight_distribution(self):
        """Test that higher weights are more likely to be selected."""
        job = ContainerJob.objects.create(
            docker_host=self.host1,
            docker_image="nginx:latest",
            name="test-job",
            created_by=self.user,
        )

        # Run multiple routing attempts and track results
        selections = []
        for _ in range(100):
            selected_host = self.factory.route_job(job)
            selections.append(selected_host)

        # host2 has weight 200, host1 has weight 100
        # So host2 should be selected roughly 2/3 of the time
        host2_count = sum(1 for h in selections if h == self.host2)
        host1_count = sum(1 for h in selections if h == self.host1)

        # Allow for some randomness, but host2 should be selected more often
        self.assertGreater(host2_count, host1_count)
