import json
import re
import uuid
from functools import cached_property
from typing import Any, Dict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DockerHost(models.Model):
    """Represents a Docker daemon endpoint (TCP or Unix socket)"""

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
        default='docker',
        choices=[
            ('docker', 'Docker'),
            ('cloudrun', 'Google Cloud Run'),
            ('fargate', 'AWS Fargate'),
            ('scaleway', 'Scaleway Containers'),
        ],
        help_text="Type of container executor this host represents"
    )

    executor_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Executor-specific configuration (credentials, regions, etc.)"
    )

    # Resource and capacity management
    max_concurrent_jobs = models.PositiveIntegerField(
        default=10,
        help_text="Maximum number of concurrent jobs for this executor"
    )

    current_job_count = models.PositiveIntegerField(
        default=0,
        help_text="Currently running job count (updated by worker process)"
    )

    # Cost tracking
    cost_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated cost per hour for this executor"
    )

    cost_per_job = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated cost per job execution"
    )

    # Health and performance
    average_startup_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Average container startup time in seconds"
    )

    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful health check timestamp"
    )

    health_check_failures = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive health check failures"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Docker Host"
        verbose_name_plural = "Docker Hosts"

    def __str__(self):
        executor_info = (
            f" ({self.executor_type})" if self.executor_type != 'docker' else ""
        )
        return f"{self.name}{executor_info} ({self.connection_string})"

    def is_available(self) -> bool:
        """Check if this executor is available for new jobs"""
        if not self.is_active:
            return False

        if self.current_job_count >= self.max_concurrent_jobs:
            return False

        # Check health status
        if self.health_check_failures >= 3:
            return False

        return True

    def get_capacity_info(self) -> Dict[str, Any]:
        """Get current capacity information"""
        return {
            'current_jobs': self.current_job_count,
            'max_jobs': self.max_concurrent_jobs,
            'available_slots': max(
                0, self.max_concurrent_jobs - self.current_job_count
            ),
            'utilization_percent': (
                self.current_job_count / self.max_concurrent_jobs
            ) * 100,
        }

    def increment_job_count(self) -> None:
        """Thread-safe increment of current job count"""
        from django.db import transaction

        with transaction.atomic():
            self.refresh_from_db()
            if self.current_job_count < self.max_concurrent_jobs:
                self.current_job_count += 1
                self.save(update_fields=['current_job_count'])

    def decrement_job_count(self) -> None:
        """Thread-safe decrement of current job count"""
        from django.db import transaction

        with transaction.atomic():
            self.refresh_from_db()
            if self.current_job_count > 0:
                self.current_job_count -= 1
                self.save(update_fields=['current_job_count'])


class ContainerTemplate(models.Model):
    """Reusable container definitions with configuration"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    docker_image = models.CharField(max_length=500)
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

    # Auto cleanup (deprecated - use cleanup process instead)
    auto_remove = models.BooleanField(
        default=False,
        help_text="[DEPRECATED] Use cleanup process instead of auto-remove",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Container Template"
        verbose_name_plural = "Container Templates"

    def __str__(self):
        return f"{self.name} ({self.docker_image})"


class EnvironmentVariable(models.Model):
    """Environment variables for container templates"""

    template = models.ForeignKey(
        ContainerTemplate,
        related_name="environment_variables",
        on_delete=models.CASCADE,
    )
    key = models.CharField(max_length=200)
    value = models.TextField()
    is_secret = models.BooleanField(
        default=False, help_text="Mark as secret to hide value in logs"
    )

    class Meta:
        verbose_name = "Environment Variable"
        verbose_name_plural = "Environment Variables"
        unique_together = ["template", "key"]

    def __str__(self):
        if self.is_secret:
            return f"{self.key}=***"
        return f"{self.key}={self.value[:50]}..."


class NetworkAssignment(models.Model):
    """Docker network assignments for container templates"""

    template = models.ForeignKey(
        ContainerTemplate, related_name="network_assignments", on_delete=models.CASCADE
    )
    network_name = models.CharField(max_length=200)
    aliases = models.JSONField(
        default=list, blank=True, help_text="Network aliases for the container"
    )

    class Meta:
        verbose_name = "Network Assignment"
        verbose_name_plural = "Network Assignments"
        unique_together = ["template", "network_name"]

    def __str__(self):
        return f"{self.template.name} -> {self.network_name}"


class ContainerJob(models.Model):
    """Individual container job instances"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("timeout", "Timeout"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ContainerTemplate, related_name="jobs", on_delete=models.CASCADE
    )
    docker_host = models.ForeignKey(
        DockerHost, related_name="jobs", on_delete=models.CASCADE
    )

    name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Override template settings if needed
    override_command = models.TextField(blank=True)
    override_environment = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional or override environment variables",
    )

    # Execution tracking
    container_id = models.CharField(max_length=100, blank=True, default="")
    exit_code = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Multi-executor support
    executor_type = models.CharField(
        max_length=50,
        default='docker',
        choices=[
            ('docker', 'Docker'),
            ('cloudrun', 'Google Cloud Run'),
            ('fargate', 'AWS Fargate'),
            ('scaleway', 'Scaleway Containers'),
            ('mock', 'Mock (Testing)'),
        ],
        help_text="Container execution backend to use for this job"
    )

    external_execution_id = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text=(
            "Cloud provider's execution/job ID "
            "(e.g., Cloud Run job name, Fargate task ARN)"
        )
    )

    executor_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific data like regions, URLs, resource identifiers"
    )

    # Routing and preferences
    preferred_executor = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Preferred executor type for this job (overrides routing rules)"
    )

    routing_reason = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Reason why this executor was chosen (for debugging/analytics)"
    )

    # Cost and resource tracking
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated execution cost in USD"
    )

    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Actual execution cost in USD (if available)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Container Job"
        verbose_name_plural = "Container Jobs"
        ordering = ["-created_at"]

    def __str__(self):
        executor_info = (
            f" ({self.executor_type})" if self.executor_type != 'docker' else ""
        )
        return f"{self.name or self.template.name} ({self.status}){executor_info}"

    @property
    def duration(self):
        """Calculate job duration if available"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def get_execution_identifier(self) -> str:
        """Get the appropriate execution ID for this job's executor"""
        if self.executor_type == 'docker':
            return self.container_id

        return self.external_execution_id or ''

    def set_execution_identifier(self, execution_id: str) -> None:
        """Set the execution ID for this job's executor"""
        if self.executor_type == 'docker':
            self.container_id = execution_id
        else:
            self.external_execution_id = execution_id

    def can_use_executor(self, executor_type: str) -> bool:
        """Check if this job can run on the specified executor type"""
        if self.preferred_executor:
            return self.preferred_executor == executor_type

        # Check template compatibility
        if hasattr(self.template, 'supported_executors'):
            return executor_type in self.template.supported_executors

        return True  # Default: all jobs can run anywhere

    def estimate_resources(self) -> Dict[str, Any]:
        """Estimate resource requirements for routing decisions"""
        return {
            'memory_mb': self.template.memory_limit or 512,
            'cpu_cores': self.template.cpu_limit or 1.0,
            'timeout_seconds': self.template.timeout_seconds,
            'storage_required': bool(self.template.working_directory),
        }

    def clean(self):
        """Model validation for ContainerJob"""
        super().clean()

        # Validate executor type matches docker_host
        if self.docker_host and self.executor_type != self.docker_host.executor_type:
            raise ValidationError(
                f"Job executor type '{self.executor_type}' doesn't match "
                f"host executor type '{self.docker_host.executor_type}'"
            )

        # Validate external_execution_id for non-docker executors
        if (self.executor_type != 'docker' and
            self.status == 'running' and
            not self.external_execution_id):
            raise ValidationError(
                f"external_execution_id required for {self.executor_type} executor"
            )


class ContainerExecution(models.Model):
    """Execution history and logs for container jobs"""

    job = models.OneToOneField(
        ContainerJob, related_name="execution", on_delete=models.CASCADE
    )

    # Resource usage
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Container Execution"
        verbose_name_plural = "Container Executions"

    def __str__(self):
        return f"Execution for {self.job}"

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
