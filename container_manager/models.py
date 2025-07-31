import re
import uuid
from functools import cached_property
from typing import ClassVar

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Constants
# (No constants currently defined)


class EnvironmentVariableTemplate(models.Model):
    """Reusable environment variable templates"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    environment_variables_text = models.TextField(
        blank=True,
        help_text="Environment variables, one per line in KEY=value format. Example:\nDEBUG=true\nAPI_KEY=secret123\nTIMEOUT=300",
        verbose_name="Environment Variables",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Environment Variable Template"
        verbose_name_plural = "Environment Variable Templates"
        ordering: ClassVar = ["name"]

    def __str__(self):
        return self.name

    def get_environment_variables_dict(self):
        """
        Parse environment_variables_text into a dictionary.

        Returns:
            dict: Environment variables as key-value pairs
        """
        env_vars = {}
        if not self.environment_variables_text:
            return env_vars

        for line in self.environment_variables_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # Skip empty lines and comments

            if "=" in line:
                key, value = line.split("=", 1)  # Split only on first =
                env_vars[key.strip()] = value.strip()

        return env_vars


class ExecutorHost(models.Model):
    """Host configuration for any executor type (Docker, Cloud Run, etc.)"""

    name = models.CharField(max_length=100, unique=True)
    host_type = models.CharField(
        max_length=10,
        choices=[
            ("tcp", "TCP"),
            ("unix", "Unix Socket"),
        ],
        default="unix",
    )
    connection_string = models.CharField(
        max_length=500,
        help_text="e.g., tcp://192.168.1.100:2376 or unix:///var/run/docker.sock",
    )
    tls_enabled = models.BooleanField(default=False)
    tls_verify = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    auto_pull_images = models.BooleanField(
        default=True,
        help_text="Automatically pull Docker images that don't exist locally",
    )

    # Multi-executor support
    executor_type = models.CharField(
        max_length=50,
        default="docker",
        choices=[
            ("docker", "Docker"),
            ("cloudrun", "Google Cloud Run"),
            ("fargate", "AWS Fargate"),
            ("scaleway", "Scaleway Containers"),
        ],
        help_text="Type of container executor this host represents",
    )

    executor_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Executor-specific configuration for this host. Examples:\n"
            "• Docker: {'base_url': 'tcp://host:2376', 'tls_verify': true}\n"
            "• Cloud Run: {'project': 'my-project', 'region': 'us-central1', 'service_account': 'sa@project.iam'}\n"
            "• AWS Fargate: {'cluster': 'my-cluster', 'subnets': ['subnet-123'], 'security_groups': ['sg-456']}\n"
            "• General: Any JSON config your custom executor implementation needs"
        ),
    )

    # Resource and capacity management
    max_concurrent_jobs = models.PositiveIntegerField(
        default=10, help_text="Maximum number of concurrent jobs for this executor"
    )

    # Weight-based routing
    weight = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Routing weight (higher = more preferred, 1-1000)",
    )

    # Current capacity tracking
    current_job_count = models.PositiveIntegerField(
        default=0, help_text="Current number of running jobs on this host"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Executor Host"
        verbose_name_plural = "Executor Hosts"

    def __str__(self):
        return self.name

    def is_available(self) -> bool:
        """Check if this executor is available for new jobs"""
        return self.is_active

    def get_display_name(self) -> str:
        """
        Get simple display name for the host.

        Note: Executor-specific display formatting has been moved to the service layer
        and individual executor classes to enable true polymorphism.
        Use JobManagementService.get_host_display_info() for detailed display information.
        """
        return f"{self.name} ({self.executor_type.title()})"


class ContainerJob(models.Model):
    """Individual container job instances"""

    STATUS_CHOICES: ClassVar = [
        ("pending", "Pending"),
        ("launching", "Launching"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("timeout", "Timeout"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    docker_host = models.ForeignKey(
        ExecutorHost, related_name="jobs", on_delete=models.CASCADE
    )

    name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Container configuration (merged from ContainerTemplate)
    description = models.TextField(blank=True)
    docker_image = models.CharField(max_length=500, blank=True, default="")
    command = models.TextField(
        blank=True, help_text="Command to run in container (optional)"
    )
    working_directory = models.CharField(max_length=500, blank=True)

    # Resource limits
    memory_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Memory limit in MB"
    )
    cpu_limit = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.1), MaxValueValidator(32.0)],
        help_text="CPU limit (e.g., 1.5 for 1.5 cores)",
    )

    # Timeout settings
    timeout_seconds = models.PositiveIntegerField(
        default=3600, help_text="Maximum execution time in seconds"
    )

    # Environment variable template (reusable base configuration)
    environment_template = models.ForeignKey(
        EnvironmentVariableTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Environment variable template to use as base configuration",
    )

    # Network configuration
    network_configuration = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Network configuration for the container. Examples:\n"
            '[{"network_name": "bridge", "aliases": []}]\n'
            '[{"network_name": "app-network", "aliases": ["api", "backend"]}]\n'
            '[{"network_name": "database-network", "aliases": []}]'
        ),
    )

    # Environment variable overrides (simple key=value format)
    override_environment = models.TextField(
        blank=True,
        default="",
        help_text="Environment variable overrides, one per line in KEY=value format. These override any variables from the template. Example:\nDEBUG=true\nWORKER_COUNT=4",
        verbose_name="Environment Variable Overrides",
    )

    # Execution tracking
    execution_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Unified execution identifier for all executor types",
    )
    exit_code = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    executor_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Executor-specific runtime data and identifiers. Examples:\n"
            "• Docker: {'container_name': 'my-job-123', 'network': 'bridge'}\n"
            "• Cloud Run: {'job_name': 'job-abc123', 'region': 'us-central1', 'project': 'my-project'}\n"
            "• AWS Fargate: {'task_arn': 'arn:aws:ecs:...', 'cluster': 'my-cluster', 'task_definition': 'my-task:1'}\n"
            "• Custom: Any JSON data your executor needs to track or reference the job"
        ),
    )

    # Execution data (merged from ContainerExecution)
    max_memory_usage = models.PositiveIntegerField(
        null=True, blank=True, help_text="Peak memory usage in bytes"
    )
    cpu_usage_percent = models.FloatField(
        null=True, blank=True, help_text="Average CPU usage percentage"
    )

    # Logs (raw with timestamps)
    stdout_log = models.TextField(blank=True)
    stderr_log = models.TextField(blank=True)
    docker_log = models.TextField(blank=True, help_text="Docker daemon logs and events")

    # Processed output for downstream consumption
    clean_output = models.TextField(
        blank=True, help_text="Stdout with timestamps and metadata stripped"
    )

    # Basic metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Container Job"
        verbose_name_plural = "Container Jobs"
        ordering: ClassVar = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"], name="cjob_status_created_idx"
            ),
            models.Index(
                fields=["created_by", "status"], name="cjob_created_by_status_idx"
            ),
            models.Index(fields=["docker_host", "status"], name="cjob_host_status_idx"),
            models.Index(fields=["status"], name="cjob_status_idx"),
        ]

    def __str__(self):
        executor_info = ""
        if self.docker_host and self.docker_host.executor_type != "docker":
            executor_info = f" ({self.docker_host.executor_type})"
        display_name = self.name or "Unnamed Job"
        return f"{display_name} ({self.status}){executor_info}"

    @property
    def duration(self):
        """Calculate job duration if available"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def get_execution_identifier(self) -> str:
        """Get execution identifier - unified interface for all executor types"""
        return self.execution_id or ""

    def set_execution_identifier(self, execution_id: str) -> None:
        """Set execution identifier - unified interface for all executor types"""
        self.execution_id = execution_id

    @cached_property
    def clean_output_processed(self):
        """Get stdout with Docker timestamps and metadata stripped"""
        return self._strip_docker_timestamps(self.stdout_log)

    @cached_property
    def parsed_output(self):
        """Attempt to parse clean_output as JSON, fallback to string"""
        clean = self.clean_output_processed
        if not clean.strip():
            return None

        try:
            import json

            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON, return as string
            return clean

    @staticmethod
    def _strip_docker_timestamps(log_text: str) -> str:
        """Remove Docker timestamps and metadata from log text"""
        if not log_text:
            return ""

        lines = log_text.split("\n")
        clean_lines = []

        # Docker timestamp pattern: 2024-01-26T10:30:45.123456789Z

        timestamp_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*")

        for line in lines:
            # Remove timestamp prefix
            clean_line = timestamp_pattern.sub("", line)
            if clean_line.strip():  # Only add non-empty lines
                clean_lines.append(clean_line)

        return "\n".join(clean_lines)

    def get_override_environment_variables_dict(self):
        """
        Parse override_environment TextField into a dictionary.

        Returns:
            dict: Override environment variables as key-value pairs
        """
        env_vars = {}
        if not self.override_environment:
            return env_vars

        for line in self.override_environment.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # Skip empty lines and comments

            if "=" in line:
                key, value = line.split("=", 1)  # Split only on first =
                env_vars[key.strip()] = value.strip()

        return env_vars

    def get_all_environment_variables(self):
        """
        Get merged environment variables from template and overrides.

        Precedence: Template → Override Environment

        Returns:
            dict: Merged environment variables as key-value pairs
        """
        env_vars = {}

        # Start with template variables (if linked)
        if self.environment_template:
            env_vars.update(self.environment_template.get_environment_variables_dict())

        # Override with job-specific overrides
        env_vars.update(self.get_override_environment_variables_dict())

        return env_vars

    def get_network_names(self) -> list:
        """Get list of network names from network configuration"""
        return [
            network.get("network_name", "")
            for network in (self.network_configuration or [])
            if network.get("network_name")
        ]

    def can_use_executor(self, executor_type: str) -> bool:
        """Check if this job can run on the specified executor type"""
        # All jobs can run on any executor type
        return True

    def clean(self):
        """
        Model validation for ContainerJob.

        Note: Executor-specific validation has been moved to the service layer
        and individual executor classes to enable true polymorphism.
        Use JobManagementService.validate_job_for_execution() for comprehensive validation.
        """
        super().clean()

        # Only core business logic validation remains here
        if self.name and len(self.name) > 200:
            raise ValidationError("Job name cannot exceed 200 characters")

        if self.command and len(self.command) > 2000:
            raise ValidationError("Command cannot exceed 2000 characters")

        # Validate docker_image is provided
        if not self.docker_image:
            raise ValidationError("Docker image is required")
