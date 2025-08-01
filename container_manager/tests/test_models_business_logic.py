"""
Tests for Django models business logic - validation, properties, and lifecycle methods.
"""

import json
import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone as django_timezone

from ..models import (
    ContainerJob,
    EnvironmentVariableTemplate,
    ExecutorHost,
)


class ContainerJobFactory:
    """Simple factory for creating test ContainerJob instances"""

    @staticmethod
    def create(**kwargs):
        defaults = {
            "docker_host": ExecutorHostFactory.create(),
            "docker_image": "alpine:latest",
            "status": "pending",
            "created_by": UserFactory.create(),
        }
        defaults.update(kwargs)
        return ContainerJob.objects.create(**defaults)

    @staticmethod
    def build(**kwargs):
        defaults = {
            "docker_host": ExecutorHostFactory.create(),
            "docker_image": "alpine:latest",
            "status": "pending",
            "created_by": UserFactory.create(),
        }
        defaults.update(kwargs)
        return ContainerJob(**defaults)


class ExecutorHostFactory:
    """Simple factory for creating test ExecutorHost instances"""

    @staticmethod
    def create(**kwargs):
        defaults = {
            "name": f"test-host-{int(time.time() * 1000000) % 1000000}",
            "connection_string": "unix:///var/run/docker.sock",
            "executor_type": "docker",
            "is_active": True,
        }
        defaults.update(kwargs)
        return ExecutorHost.objects.create(**defaults)

    @staticmethod
    def build(**kwargs):
        defaults = {
            "name": f"test-host-{int(time.time() * 1000000) % 1000000}",
            "connection_string": "unix:///var/run/docker.sock",
            "executor_type": "docker",
            "is_active": True,
        }
        defaults.update(kwargs)
        return ExecutorHost(**defaults)


class EnvironmentVariableTemplateFactory:
    """Simple factory for creating test EnvironmentVariableTemplate instances"""

    @staticmethod
    def create(**kwargs):
        defaults = {
            "name": f"test-env-template-{int(time.time() * 1000000) % 1000000}",
            "environment_variables_text": "KEY1=value1\nKEY2=value2",
            "created_by": UserFactory.create(),
        }
        defaults.update(kwargs)
        return EnvironmentVariableTemplate.objects.create(**defaults)

    @staticmethod
    def build(**kwargs):
        defaults = {
            "name": f"test-env-template-{int(time.time() * 1000000) % 1000000}",
            "environment_variables_text": "KEY1=value1\nKEY2=value2",
            "created_by": UserFactory.create(),
        }
        defaults.update(kwargs)
        return EnvironmentVariableTemplate(**defaults)


class UserFactory:
    """Simple factory for creating test User instances"""

    @staticmethod
    def create(**kwargs):
        defaults = {
            "username": f"testuser-{int(time.time() * 1000000) % 1000000}",
            "email": "test@example.com",
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)


class EnvironmentVariableTemplateTest(TestCase):
    """Test EnvironmentVariableTemplate model business logic"""

    def test_get_environment_variables_dict_basic(self):
        """Test parsing basic environment variables"""
        template = EnvironmentVariableTemplateFactory.create(
            environment_variables_text="KEY1=value1\nKEY2=value2\nKEY3=value3"
        )

        env_dict = template.get_environment_variables_dict()
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(env_dict, expected)

    def test_get_environment_variables_dict_empty(self):
        """Test parsing empty environment variables"""
        template = EnvironmentVariableTemplateFactory.create(
            environment_variables_text=""
        )

        env_dict = template.get_environment_variables_dict()
        self.assertEqual(env_dict, {})

    def test_get_environment_variables_dict_with_comments(self):
        """Test parsing environment variables with comments and empty lines"""
        template = EnvironmentVariableTemplateFactory.create(
            environment_variables_text="KEY1=value1\n# This is a comment\n\nKEY2=value2\n# Another comment\nKEY3=value3"
        )

        env_dict = template.get_environment_variables_dict()
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(env_dict, expected)

    def test_get_environment_variables_dict_with_equals_in_value(self):
        """Test parsing environment variables with equals signs in values"""
        template = EnvironmentVariableTemplateFactory.create(
            environment_variables_text="DATABASE_URL=postgresql://user:pass@host:5432/db\nAPI_URL=https://api.example.com/v1?key=abc=123"
        )

        env_dict = template.get_environment_variables_dict()
        expected = {
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",
            "API_URL": "https://api.example.com/v1?key=abc=123",
        }
        self.assertEqual(env_dict, expected)

    def test_get_environment_variables_dict_no_equals(self):
        """Test parsing environment variables with invalid format (no equals)"""
        template = EnvironmentVariableTemplateFactory.create(
            environment_variables_text="KEY1=value1\nINVALID_LINE_NO_EQUALS\nKEY2=value2"
        )

        env_dict = template.get_environment_variables_dict()
        expected = {"KEY1": "value1", "KEY2": "value2"}
        self.assertEqual(env_dict, expected)

    def test_string_representation(self):
        """Test string representation of EnvironmentVariableTemplate"""
        template = EnvironmentVariableTemplateFactory.create(name="test-env-template")
        self.assertEqual(str(template), "test-env-template")


class ExecutorHostTest(TestCase):
    """Test ExecutorHost model business logic"""

    def test_is_available_active_host(self):
        """Test is_available for active host"""
        host = ExecutorHostFactory.create(is_active=True)
        self.assertTrue(host.is_available())

    def test_is_available_inactive_host(self):
        """Test is_available for inactive host"""
        host = ExecutorHostFactory.create(is_active=False)
        self.assertFalse(host.is_available())

    def test_get_display_name_docker(self):
        """Test get_display_name for Docker host"""
        host = ExecutorHostFactory.create(
            name="production-docker", executor_type="docker"
        )

        display_name = host.get_display_name()
        self.assertEqual(display_name, "production-docker (Docker)")

    def test_get_display_name_cloudrun(self):
        """Test get_display_name for Cloud Run host"""
        host = ExecutorHostFactory.create(name="gcp-cloudrun", executor_type="cloudrun")

        display_name = host.get_display_name()
        self.assertEqual(display_name, "gcp-cloudrun (Cloudrun)")

    def test_string_representation(self):
        """Test string representation of ExecutorHost"""
        host = ExecutorHostFactory.create(name="test-host")
        self.assertEqual(str(host), "test-host")


class ContainerJobTest(TestCase):
    """Test ContainerJob model business logic"""

    def test_duration_property_completed(self):
        """Test duration property for completed job"""
        start_time = django_timezone.now() - timedelta(minutes=30)
        end_time = django_timezone.now()

        job = ContainerJobFactory.create(started_at=start_time, completed_at=end_time)

        duration = job.duration
        self.assertIsNotNone(duration)
        self.assertAlmostEqual(duration.total_seconds(), 1800, delta=10)  # ~30 minutes

    def test_duration_property_not_completed(self):
        """Test duration property for job without completion time"""
        job = ContainerJobFactory.create(
            started_at=django_timezone.now(), completed_at=None
        )

        duration = job.duration
        self.assertIsNone(duration)

    def test_duration_property_not_started(self):
        """Test duration property for job without start time"""
        job = ContainerJobFactory.create(
            started_at=None, completed_at=django_timezone.now()
        )

        duration = job.duration
        self.assertIsNone(duration)

    def test_get_execution_identifier_unified(self):
        """Test get_execution_identifier with unified execution_id"""
        job = ContainerJobFactory.create(execution_id="unified-exec-123")
        self.assertEqual(job.get_execution_identifier(), "unified-exec-123")

    def test_get_execution_identifier_with_value(self):
        """Test get_execution_identifier returns set value"""
        job = ContainerJobFactory.create(execution_id="test-execution-123")
        self.assertEqual(job.get_execution_identifier(), "test-execution-123")

    def test_get_execution_identifier_empty_default(self):
        """Test get_execution_identifier returns empty string when not set"""
        job = ContainerJobFactory.create(execution_id="")
        self.assertEqual(job.get_execution_identifier(), "")

    def test_set_execution_identifier_unified(self):
        """Test set_execution_identifier sets unified field"""
        job = ContainerJobFactory.create()
        job.set_execution_identifier("new-exec-456")

        self.assertEqual(job.execution_id, "new-exec-456")

    def test_set_execution_identifier_docker(self):
        """Test set_execution_identifier for Docker executor"""
        docker_host = ExecutorHostFactory.create(executor_type="docker")
        job = ContainerJobFactory.create(docker_host=docker_host)
        job.set_execution_identifier("docker-container-456")

        self.assertEqual(job.execution_id, "docker-container-456")

    def test_set_execution_identifier_cloudrun(self):
        """Test set_execution_identifier for Cloud Run executor"""
        cloudrun_host = ExecutorHostFactory.create(executor_type="cloudrun")
        job = ContainerJobFactory.create(docker_host=cloudrun_host)
        job.set_execution_identifier("cloudrun-job-456")

        self.assertEqual(job.execution_id, "cloudrun-job-456")

    def test_clean_output_processed_property(self):
        """Test clean_output_processed property strips Docker timestamps"""
        job = ContainerJobFactory.create(
            stdout_log="2024-01-26T10:30:45.123456789Z Application started\n2024-01-26T10:30:46.123456789Z Processing data"
        )

        clean_output = job.clean_output_processed
        expected = "Application started\nProcessing data"
        self.assertEqual(clean_output, expected)

    def test_parsed_output_json(self):
        """Test parsed_output property with valid JSON"""
        json_output = json.dumps({"status": "success", "result": 42})
        job = ContainerJobFactory.create(stdout_log=json_output)

        parsed = job.parsed_output
        expected = {"status": "success", "result": 42}
        self.assertEqual(parsed, expected)

    def test_parsed_output_string(self):
        """Test parsed_output property with non-JSON string"""
        job = ContainerJobFactory.create(stdout_log="Simple text output")

        parsed = job.parsed_output
        self.assertEqual(parsed, "Simple text output")

    def test_parsed_output_empty(self):
        """Test parsed_output property with empty output"""
        job = ContainerJobFactory.create(stdout_log="")

        parsed = job.parsed_output
        self.assertIsNone(parsed)

    def test_strip_docker_timestamps_static_method(self):
        """Test _strip_docker_timestamps static method"""
        log_text = "2024-01-26T10:30:45.123456789Z First line\n2024-01-26T10:30:46.123456789Z Second line\n\n2024-01-26T10:30:47.123456789Z Third line"

        clean_text = ContainerJob._strip_docker_timestamps(log_text)
        expected = "First line\nSecond line\nThird line"
        self.assertEqual(clean_text, expected)

    def test_strip_docker_timestamps_empty(self):
        """Test _strip_docker_timestamps with empty string"""
        result = ContainerJob._strip_docker_timestamps("")
        self.assertEqual(result, "")

    def test_strip_docker_timestamps_none(self):
        """Test _strip_docker_timestamps with None"""
        result = ContainerJob._strip_docker_timestamps(None)
        self.assertEqual(result, "")

    def test_get_all_environment_variables_template_and_override(self):
        """Test get_all_environment_variables merges template and override"""
        env_template = EnvironmentVariableTemplateFactory.create(
            environment_variables_text="BASE_VAR=base_value\nSHARED_VAR=base_shared"
        )

        job = ContainerJobFactory.create(
            environment_template=env_template,
            override_environment="OVERRIDE_VAR=override_value\nSHARED_VAR=override_shared",
        )

        all_vars = job.get_all_environment_variables()
        expected = {
            "BASE_VAR": "base_value",
            "SHARED_VAR": "override_shared",  # Override takes precedence
            "OVERRIDE_VAR": "override_value",
        }
        self.assertEqual(all_vars, expected)

    def test_get_all_environment_variables_no_template(self):
        """Test get_all_environment_variables with only override variables"""
        job = ContainerJobFactory.create(
            environment_template=None,
            override_environment="JOB_VAR=job_value\nJOB_OVERRIDE=job_override",
        )

        all_vars = job.get_all_environment_variables()
        expected = {
            "JOB_VAR": "job_value",
            "JOB_OVERRIDE": "job_override",
        }
        self.assertEqual(all_vars, expected)

    def test_get_override_environment_variables_dict_basic(self):
        """Test parsing override environment variables from TextField"""
        job = ContainerJobFactory.create(
            override_environment="OVERRIDE1=value1\nOVERRIDE2=value2\nOVERRIDE3=value3"
        )

        env_dict = job.get_override_environment_variables_dict()
        expected = {"OVERRIDE1": "value1", "OVERRIDE2": "value2", "OVERRIDE3": "value3"}
        self.assertEqual(env_dict, expected)

    def test_get_override_environment_variables_dict_empty(self):
        """Test parsing empty override environment variables"""
        job = ContainerJobFactory.create(override_environment="")

        env_dict = job.get_override_environment_variables_dict()
        self.assertEqual(env_dict, {})

    def test_get_override_environment_variables_dict_with_comments(self):
        """Test parsing override environment variables with comments"""
        job = ContainerJobFactory.create(
            override_environment="KEY1=value1\n# This is a comment\n\nKEY2=value2\n# Another comment\nKEY3=value3"
        )

        env_dict = job.get_override_environment_variables_dict()
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(env_dict, expected)

    def test_get_network_names(self):
        """Test get_network_names extracts network names from configuration"""
        job = ContainerJobFactory.create(
            network_configuration=[
                {"network_name": "bridge", "aliases": []},
                {"network_name": "app-network", "aliases": ["api", "backend"]},
                {"network_name": "database-network", "aliases": []},
            ]
        )

        network_names = job.get_network_names()
        expected = ["bridge", "app-network", "database-network"]
        self.assertEqual(network_names, expected)

    def test_get_network_names_empty(self):
        """Test get_network_names with empty configuration"""
        job = ContainerJobFactory.create(network_configuration=[])

        network_names = job.get_network_names()
        self.assertEqual(network_names, [])

    def test_can_use_executor(self):
        """Test can_use_executor returns True for all executor types"""
        job = ContainerJobFactory.create()

        self.assertTrue(job.can_use_executor("docker"))
        self.assertTrue(job.can_use_executor("cloudrun"))
        self.assertTrue(job.can_use_executor("fargate"))
        self.assertTrue(job.can_use_executor("mock"))

    def test_clean_validation_success(self):
        """Test clean method with valid job"""
        job = ContainerJobFactory.build(
            name="valid-job-name", command='echo "test"', docker_image="nginx:latest"
        )

        # Should not raise ValidationError
        try:
            job.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly")

    def test_clean_validation_long_name(self):
        """Test clean method with name too long"""
        long_name = "a" * 201  # Exceeds 200 character limit
        job = ContainerJobFactory.build(name=long_name, docker_image="nginx:latest")

        with self.assertRaises(ValidationError) as context:
            job.clean()

        self.assertIn("Job name cannot exceed 200 characters", str(context.exception))

    def test_clean_validation_long_command(self):
        """Test clean method with command too long"""
        long_command = 'echo "' + "a" * 2000 + '"'  # Exceeds 2000 character limit
        job = ContainerJobFactory.build(
            command=long_command, docker_image="nginx:latest"
        )

        with self.assertRaises(ValidationError) as context:
            job.clean()

        self.assertIn("Command cannot exceed 2000 characters", str(context.exception))

    def test_clean_validation_missing_image(self):
        """Test clean method with missing image"""
        job = ContainerJobFactory.build(docker_image="")

        with self.assertRaises(ValidationError) as context:
            job.clean()

        self.assertIn("Docker image is required", str(context.exception))

    def test_string_representation_with_name(self):
        """Test string representation with job name"""
        docker_host = ExecutorHostFactory.create(executor_type="docker")
        job = ContainerJobFactory.create(
            name="test-job", status="running", docker_host=docker_host
        )

        self.assertEqual(str(job), "test-job (running)")

    def test_string_representation_unnamed_job(self):
        """Test string representation for unnamed job"""
        docker_host = ExecutorHostFactory.create(executor_type="docker")
        job = ContainerJobFactory.create(
            name="", status="completed", docker_host=docker_host
        )

        self.assertEqual(str(job), "Unnamed Job (completed)")

    def test_string_representation_non_docker_executor(self):
        """Test string representation shows executor type for non-Docker"""
        cloudrun_host = ExecutorHostFactory.create(executor_type="cloudrun")
        job = ContainerJobFactory.create(
            name="cloudrun-job", status="running", docker_host=cloudrun_host
        )

        self.assertEqual(str(job), "cloudrun-job (running) (cloudrun)")


class JobManagerTest(TestCase):
    """Test JobManager convenience methods"""

    def test_create_job_basic(self):
        """Test basic job creation with minimal parameters"""
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="python:3.11", docker_host=docker_host, created_by=user
        )

        self.assertEqual(job.docker_image, "python:3.11")
        self.assertEqual(job.docker_host, docker_host)
        self.assertEqual(job.created_by, user)
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.command, "")
        self.assertEqual(job.name, "")
        self.assertEqual(job.override_environment, "")

    def test_create_job_with_all_parameters(self):
        """Test job creation with all convenience parameters"""
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="node:18",
            command="npm start",
            name="web-server",
            environment_vars={"NODE_ENV": "production", "PORT": "3000"},
            memory_limit=512,
            cpu_limit=1.5,
            timeout_seconds=7200,
            docker_host=docker_host,
            created_by=user,
        )

        self.assertEqual(job.docker_image, "node:18")
        self.assertEqual(job.command, "npm start")
        self.assertEqual(job.name, "web-server")
        self.assertEqual(job.memory_limit, 512)
        self.assertEqual(job.cpu_limit, 1.5)
        self.assertEqual(job.timeout_seconds, 7200)

        # Check environment variables were converted to text format
        expected_env = "NODE_ENV=production\nPORT=3000"
        self.assertEqual(job.override_environment, expected_env)

        # Check parsed environment variables
        env_dict = job.get_override_environment_variables_dict()
        expected_dict = {"NODE_ENV": "production", "PORT": "3000"}
        self.assertEqual(env_dict, expected_dict)

    def test_create_job_with_environment_template_name(self):
        """Test job creation with environment template by name"""
        template = EnvironmentVariableTemplateFactory.create(
            name="web-template", environment_variables_text="DEBUG=false\nWORKERS=4"
        )
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="python:3.11",
            environment_template="web-template",
            docker_host=docker_host,
            created_by=user,
        )

        self.assertEqual(job.environment_template, template)

        # Check template variables were set in override_environment
        expected_env = "DEBUG=false\nWORKERS=4"
        self.assertEqual(job.override_environment, expected_env)

        # Check merged environment variables
        env_dict = job.get_all_environment_variables()
        expected_dict = {"DEBUG": "false", "WORKERS": "4"}
        self.assertEqual(env_dict, expected_dict)

    def test_create_job_with_environment_template_instance(self):
        """Test job creation with environment template instance"""
        template = EnvironmentVariableTemplateFactory.create(
            name="api-template",
            environment_variables_text="API_VERSION=v2\nRATE_LIMIT=1000",
        )
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="api:latest",
            environment_template=template,
            docker_host=docker_host,
            created_by=user,
        )

        self.assertEqual(job.environment_template, template)

        # Check template variables were set
        expected_env = "API_VERSION=v2\nRATE_LIMIT=1000"
        self.assertEqual(job.override_environment, expected_env)

    def test_create_job_template_with_overrides(self):
        """Test job creation with template and override variables"""
        template = EnvironmentVariableTemplateFactory.create(
            name="db-template",
            environment_variables_text="DB_HOST=localhost\nDB_PORT=5432\nDEBUG=true",
        )
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="postgres:15",
            environment_template="db-template",
            environment_vars={"DEBUG": "false", "DB_NAME": "production"},
            docker_host=docker_host,
            created_by=user,
        )

        self.assertEqual(job.environment_template, template)

        # Check merged environment variables (overrides should win)
        env_dict = job.get_all_environment_variables()
        expected_dict = {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DEBUG": "false",  # Override value
            "DB_NAME": "production",  # New variable
        }
        self.assertEqual(env_dict, expected_dict)

    def test_create_job_template_not_found(self):
        """Test job creation with non-existent template name"""
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        with self.assertRaises(ValueError) as context:
            ContainerJob.objects.create_job(
                image="python:3.11",
                environment_template="nonexistent-template",
                docker_host=docker_host,
                created_by=user,
            )

        self.assertIn(
            "Environment template 'nonexistent-template' not found",
            str(context.exception),
        )

    def test_create_job_empty_environment_vars(self):
        """Test job creation with empty environment_vars dict"""
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="alpine:latest",
            environment_vars={},
            docker_host=docker_host,
            created_by=user,
        )

        self.assertEqual(job.override_environment, "")

    def test_create_job_none_environment_vars(self):
        """Test job creation with None environment_vars"""
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        job = ContainerJob.objects.create_job(
            image="alpine:latest",
            environment_vars=None,
            docker_host=docker_host,
            created_by=user,
        )

        self.assertEqual(job.override_environment, "")

    def test_create_job_backwards_compatibility(self):
        """Test that regular create() method still works unchanged"""
        docker_host = ExecutorHostFactory.create()
        user = UserFactory.create()

        # Use the old create() method directly
        job = ContainerJob.objects.create(
            docker_image="ubuntu:22.04",
            docker_host=docker_host,
            created_by=user,
            override_environment="LEGACY=true",
        )

        self.assertEqual(job.docker_image, "ubuntu:22.04")
        self.assertEqual(job.override_environment, "LEGACY=true")
