import json
import re
import uuid
from functools import cached_property

from django.contrib.auth.models import User
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Docker Host"
        verbose_name_plural = "Docker Hosts"

    def __str__(self):
        return f"{self.name} ({self.connection_string})"


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

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Container Job"
        verbose_name_plural = "Container Jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or self.template.name} ({self.status})"

    @property
    def duration(self):
        """Calculate job duration if available"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


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
