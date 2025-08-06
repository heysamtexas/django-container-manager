import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ..models import (
    ContainerJob,
    ExecutorHost,
)

# Additional test modules are in the tests/ package directory


class ExecutorHostModelTest(TestCase):
    """Test cases for ExecutorHost model"""

    def setUp(self):
        self.docker_host = ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

    def test_docker_host_creation(self):
        """Test Docker host creation with valid data"""
        self.assertEqual(self.docker_host.name, "test-host")
        self.assertEqual(self.docker_host.host_type, "unix")
        self.assertTrue(self.docker_host.is_active)
        self.assertFalse(self.docker_host.tls_enabled)

    def test_docker_host_str_representation(self):
        """Test string representation of ExecutorHost"""
        expected = self.docker_host.name
        self.assertEqual(str(self.docker_host), expected)

    def test_tcp_docker_host(self):
        """Test creation of TCP Docker host"""
        tcp_host = ExecutorHost.objects.create(
            name="tcp-host",
            host_type="tcp",
            connection_string="tcp://192.168.1.100:2376",
            tls_enabled=True,
            tls_verify=True,
            is_active=True,
        )

        self.assertEqual(tcp_host.host_type, "tcp")
        self.assertTrue(tcp_host.tls_enabled)
        self.assertTrue(tcp_host.tls_verify)


class ContainerJobModelTest(TestCase):
    """Test cases for ContainerJob model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

        self.job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="ubuntu:latest",
            command='echo "Hello World"',
            name="test-job",
            created_by=self.user,
        )

    def test_job_creation(self):
        """Test container job creation"""
        self.assertEqual(self.job.docker_host, self.docker_host)
        self.assertEqual(self.job.docker_image, "ubuntu:latest")
        self.assertEqual(self.job.command, 'echo "Hello World"')
        self.assertEqual(self.job.name, "test-job")
        self.assertEqual(self.job.status, "pending")
        self.assertIsInstance(self.job.id, uuid.UUID)

    def test_job_str_representation(self):
        """Test string representation of ContainerJob"""
        expected = f"{self.job.name} ({self.job.status})"
        self.assertEqual(str(self.job), expected)

    def test_job_duration_calculation(self):
        """Test job duration calculation"""
        # Job without start/end time
        self.assertIsNone(self.job.duration)

        # Job with start and end time
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=5)

        self.job.started_at = start_time
        self.job.completed_at = end_time

        duration = self.job.duration
        self.assertIsNotNone(duration)
        self.assertEqual(duration.total_seconds(), 300)  # 5 minutes

    def test_job_with_override_environment(self):
        """Test job with override environment variables"""
        override_env_text = "TEST_VAR=override_value\nNEW_VAR=new_value"

        job_with_override = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="ubuntu:latest",
            command='echo "Hello World"',
            name="override-job",
            override_environment=override_env_text,
            created_by=self.user,
        )

        self.assertEqual(job_with_override.override_environment, override_env_text)

        # Test that the parsed environment variables work correctly
        expected_env = {"TEST_VAR": "override_value", "NEW_VAR": "new_value"}
        self.assertEqual(
            job_with_override.get_override_environment_variables_dict(), expected_env
        )


class ManagementCommandTest(TestCase):
    """Test cases for management commands"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )


class IntegrationTest(TestCase):
    """Integration tests for the complete workflow"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="integration-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

    def test_complete_job_workflow(self):
        """Test complete job creation and execution workflow"""
        # Create job
        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="ubuntu:latest",
            command='echo "Hello World"',
            name="integration-job",
            created_by=self.user,
        )

        # Verify initial state
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.get_execution_identifier(), "")
        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)

        # Verify execution fields are available on job
        self.assertEqual(job.stdout_log, "")
        self.assertEqual(job.stderr_log, "")
        self.assertEqual(job.docker_log, "")

        # Test job state transitions
        job.status = "running"
        job.started_at = timezone.now()
        job.set_execution_identifier("test-container-id")
        job.save()

        self.assertEqual(job.status, "running")
        self.assertIsNotNone(job.started_at)

        # Complete job
        job.status = "completed"
        job.completed_at = timezone.now()
        job.exit_code = 0
        job.save()

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.exit_code, 0)
        self.assertIsNotNone(job.duration)
