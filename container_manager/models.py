import json
import re
import uuid
from functools import cached_property
from typing import ClassVar

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Constants
MAX_PERCENTAGE = 100  # Maximum percentage value for A/B testing


class EnvironmentVariableTemplate(models.Model):
    """Reusable environment variable templates"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    environment_variables_text = models.TextField(
        blank=True,
        help_text="Environment variables, one per line in KEY=value format. Example:\nDEBUG=true\nAPI_KEY=secret123\nTIMEOUT=300",
        verbose_name="Environment Variables"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Environment Variable Template"
        verbose_name_plural = "Environment Variable Templates"
        ordering: ClassVar = ['name']

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

        for line in self.environment_variables_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Skip empty lines and comments

            if '=' in line:
                key, value = line.split('=', 1)  # Split only on first =
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
        help_text="Routing weight (higher = more preferred, 1-1000)"
    )

    # Current capacity tracking
    current_job_count = models.PositiveIntegerField(
        default=0,
        help_text="Current number of running jobs on this host"
    )

    # Health monitoring
    health_check_failures = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive health check failures"
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last health check"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Executor Host"
        verbose_name_plural = "Executor Hosts"

    def __str__(self):
        executor_info = (
            f" ({self.executor_type})" if self.executor_type != "docker" else ""
        )
        return f"{self.name}{executor_info} ({self.connection_string})"

    def is_available(self) -> bool:
        """Check if this executor is available for new jobs"""
        return self.is_active

    def get_display_name(self) -> str:
        """Get display name for the host"""
        if self.executor_type == "docker":
            return f"{self.name} (Docker)"
        elif self.executor_type == "cloudrun":
            config = self.executor_config
            region = config.get("region", "unknown")
            return f"{self.name} (Cloud Run - {region})"
        else:
            return f"{self.name} ({self.executor_type.title()})"


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

    # Environment variable template (reusable base configuration)
    environment_template = models.ForeignKey(
        EnvironmentVariableTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional environment variable template to use as base configuration"
    )

    # Environment variable overrides (simple key=value format)
    override_environment_variables_text = models.TextField(
        blank=True,
        help_text="Environment variable overrides, one per line in KEY=value format. These override any variables from the template. Example:\nDEBUG=true\nWORKER_COUNT=4",
        verbose_name="Environment Variable Overrides"
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

    def get_override_environment_variables_dict(self):
        """
        Parse override_environment_variables_text into a dictionary.

        Returns:
            dict: Override environment variables as key-value pairs
        """
        env_vars = {}
        if not self.override_environment_variables_text:
            return env_vars

        for line in self.override_environment_variables_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Skip empty lines and comments

            if '=' in line:
                key, value = line.split('=', 1)  # Split only on first =
                env_vars[key.strip()] = value.strip()

        return env_vars

    def get_all_environment_variables(self):
        """
        Get merged environment variables from template and overrides.

        Precedence: Template → Container Overrides → Job Overrides

        Returns:
            dict: Merged environment variables as key-value pairs
        """
        env_vars = {}

        # Start with template variables (if linked)
        if self.environment_template:
            env_vars.update(self.environment_template.get_environment_variables_dict())

        # Override with container-specific variables
        env_vars.update(self.get_override_environment_variables_dict())

        return env_vars




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
        unique_together: ClassVar = ["template", "network_name"]

    def __str__(self):
        return f"{self.template.name} -> {self.network_name}"


class ContainerJob(models.Model):
    """Individual container job instances"""

    STATUS_CHOICES: ClassVar = [
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
        ExecutorHost, related_name="jobs", on_delete=models.CASCADE
    )

    name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Override template settings if needed
    override_command = models.TextField(
        blank=True,
        help_text=(
            "Override the template's default command. Examples:\n"
            "• Single command: python main.py --config=prod\n"
            "• Shell command: bash -c \"echo Starting...; python app.py; echo Done\"\n"
            "• Multi-step: bash -c \"pip install -r requirements.txt && python manage.py migrate && python manage.py runserver\"\n"
            "• Script execution: /bin/sh /scripts/deploy.sh --environment=staging\n"
            "• Data processing: python process_data.py --input=/data/input.csv --output=/data/results.json\n"
            "Leave blank to use the template's default command."
        )
    )
    override_environment = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Additional or override environment variables for this specific job. Examples:\n"
            "• Simple config: {\"DEBUG\": \"true\", \"LOG_LEVEL\": \"info\"}\n"
            "• Database: {\"DB_HOST\": \"prod-db.company.com\", \"DB_NAME\": \"prod_db\"}\n"
            "• API keys: {\"API_KEY\": \"sk-1234567890\", \"WEBHOOK_URL\": \"https://api.company.com/webhook\"}\n"
            "• File paths: {\"INPUT_FILE\": \"/data/batch_2024.csv\", \"OUTPUT_DIR\": \"/results/batch_001\"}\n"
            "• Feature flags: {\"ENABLE_FEATURE_X\": \"true\", \"USE_NEW_ALGORITHM\": \"false\"}\n"
            "These merge with template environment variables, with job values taking precedence."
        ),
    )

    # Execution tracking
    execution_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Unified execution identifier for all executor types"
    )
    container_id = models.CharField(max_length=100, blank=True, default="")  # DEPRECATED: Remove after migration
    exit_code = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Multi-executor support
    executor_type = models.CharField(
        max_length=50,
        default="docker",
        choices=[
            ("docker", "Docker"),
            ("cloudrun", "Google Cloud Run"),
            ("fargate", "AWS Fargate"),
            ("scaleway", "Scaleway Containers"),
            ("mock", "Mock (Testing)"),
        ],
        help_text="Container execution backend to use for this job",
    )

    preferred_executor = models.CharField(
        max_length=50,
        blank=True,
        default="",
        choices=[
            ("docker", "Docker"),
            ("cloudrun", "Google Cloud Run"),
            ("fargate", "AWS Fargate"),
            ("scaleway", "Scaleway Containers"),
            ("mock", "Mock (Testing)"),
        ],
        help_text="Preferred executor type for this job (used by routing logic)",
    )

    routing_reason = models.TextField(
        blank=True,
        default="",
        help_text="Explanation of why this executor was chosen for this job"
    )

    external_execution_id = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=(
            "Cloud provider's execution/job ID "
            "(e.g., Cloud Run job name, Fargate task ARN)"
        ),
    )

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

    # Basic metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Container Job"
        verbose_name_plural = "Container Jobs"
        ordering: ClassVar = ["-created_at"]

    def __str__(self):
        executor_info = (
            f" ({self.executor_type})" if self.executor_type != "docker" else ""
        )
        return f"{self.name or self.template.name} ({self.status}){executor_info}"

    @property
    def duration(self):
        """Calculate job duration if available"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def get_execution_identifier(self) -> str:
        """Get execution identifier - unified interface for all executor types"""
        # NEW: Use unified field first
        if self.execution_id:
            return self.execution_id

        # FALLBACK: Legacy field support during migration
        if self.executor_type == "docker":
            return self.container_id or ""
        return self.external_execution_id or ""

    def set_execution_identifier(self, execution_id: str) -> None:
        """Set execution identifier - unified interface for all executor types"""
        # NEW: Always set unified field
        self.execution_id = execution_id

        # MIGRATION: Also set legacy fields for backward compatibility
        if self.executor_type == "docker":
            self.container_id = execution_id
        else:
            self.external_execution_id = execution_id

    def can_use_executor(self, executor_type: str) -> bool:
        """Check if this job can run on the specified executor type"""
        # All jobs can run on any executor type
        return True

    def clean(self):
        """Model validation for ContainerJob"""
        super().clean()

        # Validate executor type matches docker_host
        if self.docker_host and self.executor_type != self.docker_host.executor_type:
            raise ValidationError(
                f"Job executor type '{self.executor_type}' doesn't match "
                f"host executor type '{self.docker_host.executor_type}'"
            )

        # Validate execution_id for running jobs (all executor types)
        if self.status == "running" and not self.get_execution_identifier():
            raise ValidationError(
                f"execution_id required for running {self.executor_type} jobs"
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


# Routing Rules Models
class RoutingRuleSet(models.Model):
    """
    Collection of routing rules with metadata.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # A/B testing support
    ab_test_enabled = models.BooleanField(default=False)
    ab_test_percentage = models.FloatField(
        default=0.0, help_text="Percentage of jobs to apply this ruleset to (0-100)"
    )

    class Meta:
        ordering: ClassVar = ["name"]
        verbose_name = "Routing Rule Set"
        verbose_name_plural = "Routing Rule Sets"

    def __str__(self):
        return self.name

    def clean(self):
        """Validate the ruleset"""
        from django.core.exceptions import ValidationError

        if self.ab_test_enabled and not (0 <= self.ab_test_percentage <= MAX_PERCENTAGE):
            raise ValidationError(f"A/B test percentage must be between 0 and {MAX_PERCENTAGE}")


class RoutingRule(models.Model):
    """
    Individual routing rule with condition and target executor.
    """

    EXECUTOR_CHOICES: ClassVar = [
        ("docker", "Docker"),
        ("cloudrun", "Cloud Run"),
        ("fargate", "AWS Fargate"),
        ("mock", "Mock (Testing)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ruleset = models.ForeignKey(
        RoutingRuleSet, on_delete=models.CASCADE, related_name="rules"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Rule definition
    condition = models.TextField(
        help_text="Python expression that evaluates to True/False"
    )
    target_executor = models.CharField(max_length=50, choices=EXECUTOR_CHOICES)
    priority = models.IntegerField(
        default=100, help_text="Lower numbers = higher priority"
    )

    # Rule metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Statistics
    execution_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar = ["priority", "created_at"]
        unique_together: ClassVar = ["ruleset", "name"]
        verbose_name = "Routing Rule"
        verbose_name_plural = "Routing Rules"

    def __str__(self):
        return f"{self.ruleset.name}: {self.name}"

    def clean(self):
        """Validate the rule condition"""
        from django.core.exceptions import ValidationError

        if self.condition:
            try:
                from .routing.evaluator import (
                    SafeExpressionError,
                    SafeExpressionEvaluator,
                )

                evaluator = SafeExpressionEvaluator()
                # Test with dummy context
                dummy_context = {
                    "memory_mb": 512,
                    "cpu_cores": 1.0,
                    "timeout_seconds": 600,
                    "job_name": "test-job",
                    "image": "test:latest",
                }
                evaluator.evaluate(self.condition, dummy_context)
            except SafeExpressionError as e:
                raise ValidationError(f"Invalid condition: {e}") from e

    def evaluate(self, job) -> bool:
        """
        Evaluate this rule against a job.

        Args:
            job: ContainerJob to evaluate

        Returns:
            True if rule matches, False otherwise
        """
        if not self.is_active:
            return False

        try:
            from django.utils import timezone as django_timezone

            from .routing.evaluator import (
                SafeExpressionError,
                SafeExpressionEvaluator,
                create_evaluation_context,
            )

            evaluator = SafeExpressionEvaluator()
            context = create_evaluation_context(job)
            result = evaluator.evaluate(self.condition, context)

            # Update statistics
            self.execution_count += 1
            if result:
                self.success_count += 1
            self.last_executed = django_timezone.now()
            self.save(
                update_fields=["execution_count", "success_count", "last_executed"]
            )

            return result

        except SafeExpressionError:
            return False

    @property
    def success_rate(self) -> float:
        """Calculate rule success rate"""
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100


class RoutingDecision(models.Model):
    """
    Log of routing decisions for analysis and debugging.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_id = models.UUIDField()  # Reference to ContainerJob

    # Decision details
    selected_executor = models.CharField(max_length=50)
    rule_used = models.ForeignKey(
        RoutingRule, on_delete=models.SET_NULL, null=True, blank=True
    )
    ruleset_used = models.ForeignKey(
        RoutingRuleSet, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Context at decision time
    decision_reason = models.TextField()
    evaluated_rules = models.JSONField(default=list)  # List of rule IDs evaluated
    job_context = models.JSONField(default=dict)  # Job context at decision time

    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    execution_time_ms = models.FloatField(null=True, blank=True)

    # A/B testing
    is_ab_test = models.BooleanField(default=False)
    ab_test_group = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering: ClassVar = ["-timestamp"]
        verbose_name = "Routing Decision"
        verbose_name_plural = "Routing Decisions"
        indexes: ClassVar = [
            models.Index(fields=["job_id"]),
            models.Index(fields=["selected_executor"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"Decision for job {self.job_id}: {self.selected_executor}"


class RuleValidationResult(models.Model):
    """
    Results of rule validation tests.
    """

    rule = models.ForeignKey(RoutingRule, on_delete=models.CASCADE)
    test_case = models.CharField(max_length=100)
    expected_result = models.BooleanField()
    actual_result = models.BooleanField()
    passed = models.BooleanField()
    error_message = models.TextField(blank=True)
    tested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-tested_at"]
        verbose_name = "Rule Validation Result"
        verbose_name_plural = "Rule Validation Results"

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"{self.rule.name} - {self.test_case}: {status}"
