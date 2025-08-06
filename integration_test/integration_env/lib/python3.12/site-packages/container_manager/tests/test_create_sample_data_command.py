"""
Tests for create_sample_data management command
"""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from container_manager.models import (
    ContainerJob,
    EnvironmentVariableTemplate,
    ExecutorHost,
)


class CreateSampleDataCommandTest(TestCase):
    """Test suite for create_sample_data management command"""

    def setUp(self):
        super().setUp()
        # Clean slate for each test
        ExecutorHost.objects.all().delete()
        EnvironmentVariableTemplate.objects.all().delete()
        ContainerJob.objects.all().delete()
        User.objects.all().delete()

    def test_command_creates_sample_data_successfully(self):
        """Test that command creates all expected sample data"""
        out = StringIO()
        call_command("create_sample_data", stdout=out)

        output = out.getvalue()

        # Check that Docker host was created
        self.assertEqual(ExecutorHost.objects.count(), 1)
        docker_host = ExecutorHost.objects.first()
        self.assertEqual(docker_host.name, "local-docker")
        self.assertIn("Docker host: local-docker", output)

        # Check that environment variable templates were created
        env_templates = EnvironmentVariableTemplate.objects.all()
        self.assertEqual(env_templates.count(), 2)  # python and ubuntu templates

        template_names = [t.name for t in env_templates]
        self.assertIn("python-script-runner-env", template_names)
        self.assertIn("ubuntu-bash-test-env", template_names)

        # Check that sample jobs were created
        jobs = ContainerJob.objects.all()
        self.assertEqual(jobs.count(), 3)  # alpine, python, ubuntu jobs

        job_names = [j.name for j in jobs]
        self.assertIn("Sample Alpine Echo Test Job", job_names)
        self.assertIn("Sample Python Script Runner Job", job_names)
        self.assertIn("Sample Ubuntu Bash Test Job", job_names)

        # Verify jobs have correct docker images
        alpine_job = ContainerJob.objects.get(name="Sample Alpine Echo Test Job")
        self.assertEqual(alpine_job.docker_image, "alpine:latest")
        self.assertIsNone(alpine_job.environment_template)  # No env vars for alpine

        python_job = ContainerJob.objects.get(name="Sample Python Script Runner Job")
        self.assertEqual(python_job.docker_image, "python:3.11-slim")
        self.assertIsNotNone(python_job.environment_template)  # Has env template

        ubuntu_job = ContainerJob.objects.get(name="Sample Ubuntu Bash Test Job")
        self.assertEqual(ubuntu_job.docker_image, "ubuntu:22.04")
        self.assertIsNotNone(ubuntu_job.environment_template)  # Has env template

    def test_command_is_idempotent(self):
        """Test that running command twice doesn't create duplicates"""
        # First run
        call_command("create_sample_data")
        first_host_count = ExecutorHost.objects.count()
        first_env_template_count = EnvironmentVariableTemplate.objects.count()
        first_job_count = ContainerJob.objects.count()

        # Second run
        out = StringIO()
        call_command("create_sample_data", stdout=out)
        output = out.getvalue()

        # Counts should remain the same
        self.assertEqual(ExecutorHost.objects.count(), first_host_count)
        self.assertEqual(
            EnvironmentVariableTemplate.objects.count(), first_env_template_count
        )
        self.assertEqual(ContainerJob.objects.count(), first_job_count)

        # Output should indicate existing objects
        self.assertIn("already exists", output)

    def test_command_with_admin_user(self):
        """Test that admin user is assigned to created objects"""
        admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass"
        )

        call_command("create_sample_data")

        # Check that objects have correct created_by
        for template in EnvironmentVariableTemplate.objects.all():
            self.assertEqual(template.created_by, admin_user)

        for job in ContainerJob.objects.all():
            self.assertEqual(job.created_by, admin_user)

    def test_command_without_admin_user(self):
        """Test that command works when no admin user exists"""
        # Ensure no superusers exist
        User.objects.filter(is_superuser=True).delete()

        # Should not crash
        call_command("create_sample_data")

        # Data should still be created
        self.assertGreater(ContainerJob.objects.count(), 0)
        self.assertGreater(ExecutorHost.objects.count(), 0)

    def test_skip_host_option(self):
        """Test --skip-host option"""
        # Create existing host
        ExecutorHost.objects.create(
            name="local-docker",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

        out = StringIO()
        call_command("create_sample_data", "--skip-host", stdout=out)
        output = out.getvalue()

        self.assertIn("Using existing Docker host", output)
        # Should still create jobs and templates
        self.assertGreater(ContainerJob.objects.count(), 0)

    def test_environment_variable_templates_content(self):
        """Test that environment variable templates have correct content"""
        call_command("create_sample_data")

        python_template = EnvironmentVariableTemplate.objects.get(
            name="python-script-runner-env"
        )
        env_vars = python_template.get_environment_variables_dict()
        self.assertIn("TEST_VAR", env_vars)
        self.assertIn("PYTHONUNBUFFERED", env_vars)
        self.assertEqual(env_vars["TEST_VAR"], "Hello World")
        self.assertEqual(env_vars["PYTHONUNBUFFERED"], "1")

        ubuntu_template = EnvironmentVariableTemplate.objects.get(
            name="ubuntu-bash-test-env"
        )
        env_vars = ubuntu_template.get_environment_variables_dict()
        self.assertIn("TEST_ENV", env_vars)
        self.assertEqual(env_vars["TEST_ENV"], "production")
