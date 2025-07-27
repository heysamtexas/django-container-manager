"""
Tests for create_sample_data management command
"""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from container_manager.models import (
    ContainerJob,
    ContainerTemplate,
    ExecutorHost,
)


class CreateSampleDataCommandTest(TestCase):
    """Test suite for create_sample_data management command"""

    def setUp(self):
        super().setUp()
        # Clean slate for each test
        ExecutorHost.objects.all().delete()
        ContainerTemplate.objects.all().delete()
        ContainerJob.objects.all().delete()
        User.objects.all().delete()

    def test_command_creates_docker_host_by_default(self):
        """Test that command creates a Docker host with default settings"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Created Docker host: local-docker", output)
        
        # Verify host was created
        host = ExecutorHost.objects.get(name="local-docker")
        self.assertEqual(host.host_type, "unix")
        self.assertEqual(host.connection_string, "unix:///var/run/docker.sock")
        self.assertTrue(host.is_active)
        self.assertTrue(host.auto_pull_images)

    def test_command_with_custom_host_name(self):
        """Test command with custom host name"""
        out = StringIO()
        call_command('create_sample_data', '--host-name=custom-docker', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Created Docker host: custom-docker", output)
        
        # Verify host was created with custom name
        host = ExecutorHost.objects.get(name="custom-docker")
        self.assertEqual(host.name, "custom-docker")

    def test_command_uses_existing_docker_host(self):
        """Test that command uses existing Docker host instead of creating duplicate"""
        # Create existing host
        existing_host = ExecutorHost.objects.create(
            name="local-docker",
            host_type="tcp",
            connection_string="tcp://localhost:2376",
            is_active=True,
        )
        
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Using existing Docker host: local-docker", output)
        
        # Verify no duplicate was created
        self.assertEqual(ExecutorHost.objects.count(), 1)
        # Verify existing host wasn't modified
        host = ExecutorHost.objects.get(name="local-docker")
        self.assertEqual(host.host_type, "tcp")  # Original value

    def test_skip_host_with_existing_host(self):
        """Test --skip-host option with existing host"""
        # Create existing host
        ExecutorHost.objects.create(
            name="test-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )
        
        out = StringIO()
        call_command('create_sample_data', '--skip-host', '--host-name=test-host', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Using existing Docker host: test-host", output)
        self.assertEqual(ExecutorHost.objects.count(), 1)

    def test_skip_host_with_nonexistent_host(self):
        """Test --skip-host option when host doesn't exist"""
        out = StringIO()
        call_command('create_sample_data', '--skip-host', '--host-name=nonexistent', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Docker host "nonexistent" not found', output)
        self.assertIn("Remove --skip-host or create it first", output)

    def test_sample_templates_creation(self):
        """Test that all sample templates are created correctly"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        
        # Check that all expected templates were created
        expected_templates = [
            "alpine-echo-test",
            "python-script-runner", 
            "ubuntu-bash-test"
        ]
        
        for template_name in expected_templates:
            self.assertIn(f"✓ Created template: {template_name}", output)
            template = ContainerTemplate.objects.get(name=template_name)
            self.assertIsNotNone(template.docker_image)
            self.assertIsNotNone(template.command)

    def test_alpine_template_details(self):
        """Test alpine template is created with correct details"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        template = ContainerTemplate.objects.get(name="alpine-echo-test")
        self.assertEqual(template.description, "Simple Alpine Linux echo test")
        self.assertEqual(template.docker_image, "alpine:latest")
        self.assertIn("Hello from Alpine Linux", template.command)
        self.assertEqual(template.timeout_seconds, 60)
        self.assertFalse(template.auto_remove)

    def test_python_template_details(self):
        """Test python template is created with correct details"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        template = ContainerTemplate.objects.get(name="python-script-runner")
        self.assertEqual(template.description, "Python container for running scripts")
        self.assertEqual(template.docker_image, "python:3.11-slim")
        self.assertIn("python -c", template.command)
        self.assertEqual(template.timeout_seconds, 300)
        self.assertEqual(template.memory_limit, 128)
        self.assertEqual(template.cpu_limit, 0.5)

    def test_ubuntu_template_details(self):
        """Test ubuntu template is created with correct details"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        template = ContainerTemplate.objects.get(name="ubuntu-bash-test")
        self.assertEqual(template.description, "Ubuntu container for bash commands")
        self.assertEqual(template.docker_image, "ubuntu:22.04")
        self.assertIn("bash -c", template.command)
        self.assertEqual(template.timeout_seconds, 120)
        self.assertEqual(template.memory_limit, 64)

    def test_existing_templates_not_recreated(self):
        """Test that existing templates are not recreated"""
        # Create existing template
        existing_template = ContainerTemplate.objects.create(
            name="alpine-echo-test",
            description="Existing template",
            docker_image="alpine:3.14",
            command='echo "existing"',
            timeout_seconds=30,
        )
        
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Template already exists: alpine-echo-test", output)
        
        # Verify template wasn't modified
        template = ContainerTemplate.objects.get(name="alpine-echo-test")
        self.assertEqual(template.description, "Existing template")  # Original value
        self.assertEqual(template.docker_image, "alpine:3.14")  # Original value

    def test_sample_job_creation(self):
        """Test that sample job is created correctly"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Sample job Created: Sample Alpine Echo Job", output)
        
        # Verify job was created
        job = ContainerJob.objects.get(name="Sample Alpine Echo Job")
        self.assertEqual(job.template.name, "alpine-echo-test")
        self.assertEqual(job.docker_host.name, "local-docker")

    def test_existing_sample_job_not_recreated(self):
        """Test that existing sample job is not recreated"""
        # First run to create everything
        call_command('create_sample_data')
        
        # Second run should not recreate job
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        self.assertIn("✓ Sample job already exists: Sample Alpine Echo Job", output)
        
        # Verify only one job exists
        self.assertEqual(ContainerJob.objects.count(), 1)

    def test_admin_user_assignment(self):
        """Test that admin user is correctly assigned to created objects"""
        # Create a superuser
        admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass"
        )
        
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        # Check templates have correct created_by
        for template in ContainerTemplate.objects.all():
            self.assertEqual(template.created_by, admin_user)
        
        # Check job has correct created_by
        job = ContainerJob.objects.get(name="Sample Alpine Echo Job")
        self.assertEqual(job.created_by, admin_user)

    def test_no_admin_user_handling(self):
        """Test command works when no admin user exists"""
        # Ensure no superusers exist
        User.objects.filter(is_superuser=True).delete()
        
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        # Command should complete successfully
        output = out.getvalue()
        self.assertIn("Sample data created successfully!", output)
        
        # Check that templates were created with None as created_by
        for template in ContainerTemplate.objects.all():
            self.assertIsNone(template.created_by)

    def test_completion_message_and_instructions(self):
        """Test that completion message and next steps are displayed"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Sample data created successfully!", output)
        self.assertIn("You can now:", output)
        self.assertIn("Visit the Django admin", output)
        self.assertIn("Start the sample job", output)
        self.assertIn("process_container_jobs", output)
        self.assertIn("manage_container_job list", output)

    def test_command_output_formatting(self):
        """Test that command output is properly formatted"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        
        # Check for proper status symbols
        self.assertIn("✓ Created Docker host:", output)
        self.assertIn("✓ Created template:", output)
        self.assertIn("✓ Sample job Created:", output)
        
        # Check for proper formatting
        lines = output.strip().split('\n')
        self.assertTrue(any("Creating sample data..." in line for line in lines))
        self.assertTrue(any("Sample data created successfully!" in line for line in lines))

    def test_get_admin_user_method_edge_cases(self):
        """Test _get_admin_user method handles edge cases"""
        from container_manager.management.commands.create_sample_data import Command
        
        command = Command()
        
        # Test with no users
        User.objects.all().delete()
        result = command._get_admin_user()
        self.assertIsNone(result)
        
        # Test with regular user but no superuser
        regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="pass"
        )
        result = command._get_admin_user()
        self.assertIsNone(result)
        
        # Test with superuser
        admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass"
        )
        result = command._get_admin_user()
        self.assertEqual(result, admin_user)

    def test_get_sample_templates_data_structure(self):
        """Test that sample templates data has correct structure"""
        from container_manager.management.commands.create_sample_data import Command
        
        command = Command()
        templates_data = command._get_sample_templates_data()
        
        self.assertEqual(len(templates_data), 3)
        
        for template_data in templates_data:
            # Required fields
            self.assertIn("name", template_data)
            self.assertIn("description", template_data)
            self.assertIn("docker_image", template_data)
            self.assertIn("command", template_data)
            self.assertIn("timeout_seconds", template_data)
            self.assertIn("auto_remove", template_data)
            self.assertIn("env_vars", template_data)
            
            # Verify types
            self.assertIsInstance(template_data["name"], str)
            self.assertIsInstance(template_data["timeout_seconds"], int)
            self.assertIsInstance(template_data["auto_remove"], bool)
            self.assertIsInstance(template_data["env_vars"], list)

    def test_environment_variables_handling(self):
        """Test that environment variables in templates are handled correctly"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        output = out.getvalue()
        
        # Check that env vars are mentioned in output
        self.assertIn("Added env var: TEST_VAR", output)
        self.assertIn("Added env var: PYTHONUNBUFFERED", output)
        self.assertIn("Added env var: TEST_ENV", output)

    def test_host_creation_failure_handling(self):
        """Test command handles host creation failure gracefully"""
        out = StringIO()
        
        # Test with skip-host but no existing host
        call_command('create_sample_data', '--skip-host', '--host-name=missing', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Docker host "missing" not found', output)
        
        # Verify no templates or jobs were created when host creation fails
        self.assertEqual(ContainerTemplate.objects.count(), 0)
        self.assertEqual(ContainerJob.objects.count(), 0)

    def test_multiple_admin_users_handling(self):
        """Test command correctly picks first admin user when multiple exist"""
        # Create multiple superusers
        admin1 = User.objects.create_superuser(
            username="admin1", email="admin1@test.com", password="pass"
        )
        admin2 = User.objects.create_superuser(
            username="admin2", email="admin2@test.com", password="pass"
        )
        
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        # Should use the first admin user found
        template = ContainerTemplate.objects.first()
        self.assertIn(template.created_by, [admin1, admin2])

    def test_get_or_create_docker_host_logic(self):
        """Test the _get_or_create_docker_host method logic directly"""
        from container_manager.management.commands.create_sample_data import Command
        
        command = Command()
        command.stdout = StringIO()
        
        # Test creation
        options = {"skip_host": False, "host_name": "test-host"}
        host = command._get_or_create_docker_host(options)
        
        self.assertIsNotNone(host)
        self.assertEqual(host.name, "test-host")
        self.assertEqual(ExecutorHost.objects.count(), 1)
        
        # Test existing host reuse
        host2 = command._get_or_create_docker_host(options)
        self.assertEqual(host.id, host2.id)
        self.assertEqual(ExecutorHost.objects.count(), 1)  # No duplicate

    def test_job_creation_with_correct_relationships(self):
        """Test that sample job is created with correct foreign key relationships"""
        out = StringIO()
        call_command('create_sample_data', stdout=out)
        
        job = ContainerJob.objects.get(name="Sample Alpine Echo Job")
        template = ContainerTemplate.objects.get(name="alpine-echo-test")
        host = ExecutorHost.objects.get(name="local-docker")
        
        # Verify relationships
        self.assertEqual(job.template, template)
        self.assertEqual(job.docker_host, host)
        
        # Verify reverse relationships work
        self.assertIn(job, template.jobs.all())
        self.assertIn(job, host.jobs.all())