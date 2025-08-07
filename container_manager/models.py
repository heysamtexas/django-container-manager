import re
import uuid
from functools import cached_property
from typing import ClassVar

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# Constants
# Priority constants for queue management
PRIORITY_HIGH = 80
PRIORITY_NORMAL = 50
PRIORITY_LOW = 20


class EnvironmentVariableTemplate(models.Model):
    """
        Template for reusable environment variable configurations across jobs.

        Provides a way to define and reuse common environment variable sets,
        promoting consistency and reducing duplication in job configurations.
        Supports standard KEY=VALUE format with validation and parsing.

        Format Requirements:
        - One variable per line: KEY=VALUE
        - No spaces around equals sign: KEY=VALUE (not KEY = VALUE)
        - Quotes for values with spaces: KEY="value with spaces"
        - Comments not supported in variable text
        - Empty lines are ignored

        Variable Resolution:
            Templates are resolved at job execution time, allowing for
            dynamic value injection and validation.

        Example Usage:
            # Create environment template
            env_template = EnvironmentVariableTemplate.objects.create(
                name='python-production',
                description='Production Python application environment',
                environment_variables_text='''
    PYTHONPATH=/app
    ENV=production
    DEBUG=False
    LOG_LEVEL=INFO
    DATABASE_URL=postgresql://user:pass@db:5432/app
    REDIS_URL=redis://redis:6379/0
                '''.strip()
            )

            # Use in job
            job = ContainerJob.objects.create(
                docker_image='myapp:latest',
                command='python manage.py runserver',
                docker_host=docker_host,
                environment_template=env_template
            )

            # Verify parsed variables
            env_dict = env_template.get_environment_variables_dict()
            assert env_dict['ENV'] == 'production'
            assert env_dict['DEBUG'] == 'False'

        Security Considerations:
            - Avoid storing secrets directly in templates
            - Use external secret management for sensitive values
            - Template content is stored in plaintext in database
    """

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

        Processes the environment_variables_text field into a structured
        dictionary format for use in job execution. Handles empty lines,
        comments, and various value formats.

        Returns:
            dict: Environment variables as key-value pairs

        Raises:
            No exceptions - malformed lines are silently skipped

        Example:
            template = EnvironmentVariableTemplate.objects.get(name='web-config')
            env_vars = template.get_environment_variables_dict()
            # Returns: {'DEBUG': 'true', 'PORT': '8000', 'DB_HOST': 'localhost'}

            # Use in container execution
            for key, value in env_vars.items():
                print(f"Setting {key}={value}")
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
    """
    Represents an execution environment for containerized jobs.

    ExecutorHost defines where and how jobs are executed. It abstracts different
    execution backends (Docker daemons, Cloud Run, etc.) behind a unified interface
    while maintaining specific configuration for each executor type.

    Supported Executor Types:
    - 'docker': Local or remote Docker daemon execution
    - 'cloudrun': Google Cloud Run serverless execution
    - 'fargate': AWS Fargate serverless execution
    - 'scaleway': Scaleway Container instances

    Connection String Formats:
        Docker:
        - unix:///var/run/docker.sock (local Unix socket)
        - tcp://docker.example.com:2376 (remote TCP)
        - tcp://docker.example.com:2376 (secure TCP with TLS)

        Cloud Run:
        - projects/PROJECT_ID/locations/REGION (GCP project and region)

        AWS Fargate:
        - cluster/CLUSTER_NAME (ECS cluster name)

        Custom:
        - Any format your custom executor implementation expects

    Health Monitoring:
        Hosts are automatically health-checked to ensure availability.
        Inactive hosts are excluded from job scheduling.

    Example Usage:
        # Create Docker host
        docker_host = ExecutorHost.objects.create(
            name='production-docker',
            executor_type='docker',
            connection_string='unix:///var/run/docker.sock',
            is_active=True,
            max_concurrent_jobs=5
        )

        # Create Cloud Run host
        cloudrun_host = ExecutorHost.objects.create(
            name='gcp-cloudrun',
            executor_type='cloudrun',
            connection_string='projects/my-project/locations/us-central1',
            executor_config={
                'project': 'my-project',
                'region': 'us-central1',
                'service_account': 'jobs@my-project.iam.gserviceaccount.com'
            },
            is_active=True
        )

        # Use in job creation
        job = ContainerJob.objects.create(
            docker_image='nginx:latest',
            command='nginx -g "daemon off;"',
            docker_host=docker_host
        )

    Resource Management:
        - max_concurrent_jobs: Limits simultaneous job execution
        - weight: Influences job routing preferences (1-1000)
        - current_job_count: Tracks active job load
    """

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
        """
        Check if this executor is available for new jobs.

        Determines availability based on active status and current capacity.
        Does not perform network connectivity checks - use health checks
        for detailed availability testing.

        Returns:
            bool: True if executor can accept new jobs

        Example:
            host = ExecutorHost.objects.get(name='production')
            if host.is_available():
                # Safe to assign jobs to this host
                job.docker_host = host
                job.save()
        """
        return self.is_active

    def get_display_name(self) -> str:
        """
        Get simple display name for the host.

        Note: Executor-specific display formatting has been moved to the service layer
        and individual executor classes to enable true polymorphism.
        Use JobManagementService.get_host_display_info() for detailed display information.
        """
        return f"{self.name} ({self.executor_type.title()})"


class JobManager(models.Manager):
    """
    Custom manager for ContainerJob with common query patterns.

    Provides convenient methods for filtering jobs by status, timing,
    and execution characteristics. All methods return QuerySets that
    can be further filtered or chained.

    Manager Methods:
        - create_job(): Convenient job creation with environment handling
        - Standard Django manager methods (filter, exclude, etc.)

    Usage Patterns:
        # Use custom creation method
        job = ContainerJob.objects.create_job(
            image='python:3.9',
            command='python script.py',
            environment_vars={'DEBUG': 'true'}
        )

        # Standard QuerySet operations
        pending_jobs = ContainerJob.objects.filter(status='pending')
        recent_jobs = ContainerJob.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        )
    """

    def create_job(
        self,
        image: str,
        command: str = "",
        name: str = "",
        environment_template=None,
        environment_vars: dict[str, str] | None = None,
        **kwargs,
    ):
        """
        Create a ContainerJob with convenient environment variable handling.

        Args:
            image: Docker image to use
            command: Command to run in the container (optional)
            name: Job name (optional)
            environment_template: Template name (str) or instance (optional)
            environment_vars: Environment variables as dict (optional)
            **kwargs: Additional ContainerJob fields

        Returns:
            ContainerJob: Created job instance

        Example:
            job = ContainerJob.objects.create_job(
                image="python:3.11",
                command="python app.py",
                environment_vars={"DEBUG": "true", "WORKERS": "4"}
            )
        """
        # Handle environment template lookup if string provided
        template_instance = None
        if environment_template:
            if isinstance(environment_template, str):
                try:
                    template_instance = EnvironmentVariableTemplate.objects.get(
                        name=environment_template
                    )
                except EnvironmentVariableTemplate.DoesNotExist:
                    raise ValueError(
                        f"Environment template '{environment_template}' not found"
                    ) from None
            else:
                template_instance = environment_template

        # Merge environment variables
        final_env_dict = {}

        # Start with template variables if provided
        if template_instance:
            final_env_dict.update(template_instance.get_environment_variables_dict())

        # Override with provided environment_vars
        if environment_vars:
            final_env_dict.update(environment_vars)

        # Convert dict to text format for override_environment field
        override_env_text = ""
        if final_env_dict:
            override_env_text = "\n".join(
                f"{key}={value}" for key, value in final_env_dict.items()
            )

        # Create the job with processed environment variables
        return self.create(
            docker_image=image,
            command=command,
            name=name,
            environment_template=template_instance,
            override_environment=override_env_text,
            **kwargs,
        )


class ContainerJob(models.Model):
    """
    Represents a containerized job execution request with full lifecycle tracking.

    This is the core model for managing Docker container jobs. It handles the complete
    lifecycle from job creation through execution to completion, including resource
    monitoring, log collection, and status tracking.

    Key Features:
    - Multi-executor support (Docker, Cloud Run, Fargate, custom)
    - Resource limit enforcement (memory, CPU)
    - Environment variable template integration
    - Automatic log harvesting and storage
    - Comprehensive status tracking and transitions
    - Network configuration support
    - Execution metadata tracking for different executor types

    Status Lifecycle:
        pending -> launching -> running -> completed/failed/timeout/cancelled

    Typical Usage:
        # Create and execute a simple job
        job = ContainerJob.objects.create_job(
            image='python:3.9',
            command='python -c "print(\'Hello World\')"',
            environment_vars={'ENV': 'production'}
        )

        # Assign to executor host
        job.docker_host = ExecutorHost.objects.get(name='production')
        job.save()

        # Monitor execution (handled by process_container_jobs command)
        while job.status not in ['completed', 'failed', 'timeout', 'cancelled']:
            time.sleep(5)
            job.refresh_from_db()

        # Retrieve results
        logs = job.stdout_log
        exit_code = job.exit_code
        duration = job.duration

    Environment Variable Handling:
        Jobs support layered environment variable configuration:
        1. Template variables (from environment_template)
        2. Override variables (from override_environment)

        Combined variables available via get_all_environment_variables()

    Related Models:
        - ExecutorHost: Defines where the job executes
        - EnvironmentVariableTemplate: Provides base environment configuration

    Resource Management:
        - memory_limit: Container memory limit in MB
        - cpu_limit: Container CPU limit in cores (e.g., 1.5)
        - timeout_seconds: Maximum execution time before forced termination

    Execution Tracking:
        - execution_id: Unified identifier across all executor types
        - executor_metadata: Executor-specific runtime data
        - stdout_log/stderr_log: Captured container output
        - max_memory_usage: Peak memory consumption
        - cpu_usage_percent: Average CPU utilization
    """

    STATUS_CHOICES: ClassVar = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("launching", "Launching"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("timeout", "Timeout"),
        ("cancelled", "Cancelled"),
        ("retrying", "Retrying"),
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

    # Queue State Fields (Queue Management System)
    queued_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When job was added to queue for execution",
    )

    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When job should be launched (for scheduled execution)",
    )

    launched_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When job container was actually launched",
    )

    retry_count = models.IntegerField(
        default=0, help_text="Number of launch attempts made"
    )

    max_retries = models.IntegerField(
        default=3, help_text="Maximum launch attempts before giving up"
    )

    priority = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Job priority (0-100, higher numbers = higher priority)",
    )

    # Retry information fields
    last_error = models.TextField(
        blank=True, null=True, help_text="Last error message from failed launch attempt"
    )

    last_error_at = models.DateTimeField(
        blank=True, null=True, help_text="When the last error occurred"
    )

    retry_strategy = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("default", "Default"),
            ("aggressive", "Aggressive"),
            ("conservative", "Conservative"),
            ("high_priority", "High Priority"),
        ],
        help_text="Retry strategy to use for this job",
    )

    # Basic metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Custom manager with convenience methods
    objects = JobManager()

    class Meta:
        verbose_name = "Container Job"
        verbose_name_plural = "Container Jobs"
        ordering: ClassVar = ["-created_at"]
        indexes: ClassVar = [
            # Existing indexes
            models.Index(
                fields=["status", "created_at"], name="cjob_status_created_idx"
            ),
            models.Index(
                fields=["created_by", "status"], name="cjob_created_by_status_idx"
            ),
            models.Index(fields=["docker_host", "status"], name="cjob_host_status_idx"),
            models.Index(fields=["status"], name="cjob_status_idx"),
            # Queue management indexes
            models.Index(
                fields=["queued_at", "launched_at"], name="cjob_queue_launched_idx"
            ),
            models.Index(
                fields=["scheduled_for", "queued_at"], name="cjob_scheduled_queue_idx"
            ),
            models.Index(
                fields=["queued_at", "retry_count"], name="cjob_queue_retry_idx"
            ),
            models.Index(
                fields=["priority", "queued_at"], name="cjob_priority_queue_idx"
            ),
            models.Index(fields=["status", "queued_at"], name="cjob_status_queue_idx"),
        ]

    def __str__(self):
        executor_info = ""
        if self.docker_host and self.docker_host.executor_type != "docker":
            executor_info = f" ({self.docker_host.executor_type})"
        display_name = self.name or "Unnamed Job"
        return f"{display_name} ({self.status}){executor_info}"

    @property
    def duration(self):
        """
        Calculate job execution duration.

        For completed jobs, returns the time between started_at and completed_at.
        For active jobs, returns None since completion time is unknown.
        For jobs that never started, returns None.

        Returns:
            timedelta or None: Job execution duration, or None if not calculable

        Example:
            job = ContainerJob.objects.get(id=job_id)

            if job.duration:
                duration = job.duration
                print(f"Job ran for {duration.total_seconds()} seconds")

                # Format for display
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                print(f"Duration: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
            else:
                print("Job duration not available (not started or not completed)")
        """
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @property
    def is_queued(self):
        """Job is queued for execution but not yet launched"""
        return self.queued_at is not None and self.launched_at is None

    @property
    def is_ready_to_launch(self):
        """Job is ready to launch (queued and scheduled time has passed)"""
        if not self.is_queued:
            return False
        if self.scheduled_for and self.scheduled_for > timezone.now():
            return False
        return not self.retry_count >= self.max_retries

    @property
    def queue_status(self):
        """Human-readable queue status"""
        if not self.queued_at:
            return "not_queued"
        elif not self.launched_at:
            if self.scheduled_for and self.scheduled_for > timezone.now():
                return "scheduled"
            elif self.retry_count >= self.max_retries:
                return "launch_failed"
            else:
                return "queued"
        else:
            return "launched"

    # State Machine Validation
    from typing import ClassVar

    VALID_TRANSITIONS: ClassVar[dict[str, list[str]]] = {
        "pending": ["queued", "launching", "running", "cancelled"],
        "queued": ["launching", "running", "failed", "retrying", "cancelled"],
        "launching": ["running", "failed", "cancelled"],
        "running": ["completed", "failed", "timeout", "cancelled"],
        "failed": ["retrying", "cancelled"],
        "retrying": ["queued", "failed", "cancelled"],
        "completed": [],  # Terminal state
        "timeout": [],  # Terminal state
        "cancelled": [],  # Terminal state
    }

    def can_transition_to(self, new_status):
        """Check if transition to new status is valid"""
        valid_transitions = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in valid_transitions

    def transition_to(self, new_status, save=True):
        """Safely transition to new status with validation"""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition from {self.status} to {new_status}. "
                f"Valid transitions: {self.VALID_TRANSITIONS.get(self.status, [])}"
            )

        self.status = new_status

        # Update timestamps based on status
        if new_status == "running" and not self.launched_at:
            self.launched_at = timezone.now()
        elif new_status == "completed" and not self.completed_at:
            self.completed_at = timezone.now()

        if save:
            update_fields = ["status"]
            # Add timestamp fields if they were updated
            if new_status == "running" and not self.launched_at:
                update_fields.append("launched_at")
            elif new_status == "completed" and not self.completed_at:
                update_fields.append("completed_at")

            self.save(update_fields=update_fields)

        return True

    # Helper methods for common state transitions
    def mark_as_queued(self, scheduled_for=None):
        """Mark job as queued with proper state transition"""
        self.transition_to("queued", save=False)
        self.queued_at = timezone.now()
        if scheduled_for:
            self.scheduled_for = scheduled_for
        self.save(update_fields=["status", "queued_at", "scheduled_for"])

    def mark_as_running(self):
        """Mark job as running with proper state transition"""
        self.transition_to("running", save=False)
        if not self.launched_at:
            self.launched_at = timezone.now()
        self.save(update_fields=["status", "launched_at"])

    def mark_as_completed(self):
        """Mark job as completed with proper state transition"""
        self.transition_to("completed", save=False)
        if not self.completed_at:
            self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    def mark_as_failed(self, should_retry=False):
        """Mark job as failed, optionally setting up retry"""
        if should_retry and self.retry_count < self.max_retries:
            self.transition_to("retrying", save=False)
            self.retry_count += 1
            self.save(update_fields=["status", "retry_count"])
        else:
            self.transition_to("failed")

    def get_execution_identifier(self) -> str:
        """
        Get execution identifier - unified interface for all executor types.

        Returns the execution identifier used to track this job across
        different executor implementations. The format varies by executor:
        - Docker: container ID (e.g., 'a1b2c3d4e5f6')
        - Cloud Run: job name (e.g., 'job-abc123-def456')
        - Fargate: task ARN or task ID

        Returns:
            str: Execution identifier, or empty string if not set

        Example:
            job = ContainerJob.objects.get(id=job_id)
            exec_id = job.get_execution_identifier()
            if exec_id:
                print(f"Job {job.id} is running as {exec_id}")
            else:
                print("Job has not been launched yet")
        """
        return self.execution_id or ""

    def set_execution_identifier(self, execution_id: str) -> None:
        """
        Set execution identifier - unified interface for all executor types.

        Records the execution identifier returned by the executor when
        the job is launched. This identifier is used for status monitoring,
        log collection, and cleanup operations.

        Args:
            execution_id: Identifier from the executor system

        Example:
            # Called by executor during job launch
            success, container_id = executor.launch_job(job)
            if success:
                job.set_execution_identifier(container_id)
                job.save()
        """
        self.execution_id = execution_id

    @cached_property
    def clean_output_processed(self):
        """
        Get stdout with Docker timestamps and metadata stripped.

        Processes the raw stdout_log to remove Docker-specific timestamps
        and formatting, leaving only the actual application output. Useful
        for parsing application results or displaying clean output to users.

        Returns:
            str: Cleaned stdout content without timestamps

        Example:
            job = ContainerJob.objects.get(id=job_id)
            clean_output = job.clean_output_processed
            # Original: "2024-01-26T10:30:45.123456789Z Hello World"
            # Cleaned:  "Hello World"
        """
        return self._strip_docker_timestamps(self.stdout_log)

    @cached_property
    def parsed_output(self):
        """
        Attempt to parse clean_output as JSON, fallback to string.

        Tries to parse the cleaned output as JSON for structured data
        processing. If parsing fails, returns the output as a string.
        Useful for jobs that output JSON results.

        Returns:
            dict/list/str/None: Parsed JSON object, or string if not JSON, or None if empty

        Example:
            job = ContainerJob.objects.get(id=job_id)
            result = job.parsed_output

            if isinstance(result, dict):
                # Job output was JSON object
                print(f"Status: {result.get('status')}")
            elif isinstance(result, str):
                # Job output was plain text
                print(f"Output: {result}")
            else:
                # No output or empty
                print("No output available")
        """
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

        Combines environment variables from the linked template with
        job-specific overrides. Override variables take precedence
        over template variables with the same key.

        Precedence: Template → Override Environment

        Returns:
            dict: Merged environment variables as key-value pairs

        Example:
            # Template has: DEBUG=False, LOG_LEVEL=INFO
            # Override has: DEBUG=True, CUSTOM_VAR=value
            job = ContainerJob.objects.get(id=job_id)
            env_vars = job.get_all_environment_variables()
            # Result: {'DEBUG': 'True', 'LOG_LEVEL': 'INFO', 'CUSTOM_VAR': 'value'}

            # Use in container execution
            for key, value in env_vars.items():
                print(f"Setting environment: {key}={value}")
        """
        env_vars = {}

        # Start with template variables (if linked)
        if self.environment_template:
            env_vars.update(self.environment_template.get_environment_variables_dict())

        # Override with job-specific overrides
        env_vars.update(self.get_override_environment_variables_dict())

        return env_vars

    def get_network_names(self) -> list:
        """
        Get list of network names from network configuration.

        Extracts network names from the network_configuration JSON field
        for use in container networking setup. Filters out empty or
        invalid network configurations.

        Returns:
            list: List of network names configured for this job

        Example:
            job = ContainerJob.objects.get(id=job_id)
            networks = job.get_network_names()
            # Returns: ['app-network', 'database-network']

            # Use in container setup
            for network in networks:
                print(f"Job will connect to network: {network}")
        """
        return [
            network.get("network_name", "")
            for network in (self.network_configuration or [])
            if network.get("network_name")
        ]

    def can_use_executor(self, executor_type: str) -> bool:
        """
        Check if this job can run on the specified executor type.

        Validates whether this job's configuration is compatible with
        the specified executor type. Currently all jobs are compatible
        with all executor types, but this method provides a hook for
        future executor-specific validation.

        Args:
            executor_type: Type of executor to check ('docker', 'cloudrun', etc.)

        Returns:
            bool: True if job can run on this executor type

        Example:
            job = ContainerJob.objects.get(id=job_id)

            if job.can_use_executor('cloudrun'):
                # Safe to assign to Cloud Run host
                cloudrun_host = ExecutorHost.objects.filter(
                    executor_type='cloudrun', is_active=True
                ).first()
                job.docker_host = cloudrun_host
                job.save()
        """
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

    def save(self, *args, **kwargs):
        """Override save to validate state transitions"""
        if self.pk:  # Existing object - check for status changes
            try:
                old_obj = ContainerJob.objects.get(pk=self.pk)
                if old_obj.status != self.status and not old_obj.can_transition_to(
                    self.status
                ):
                    # Validate transition
                    raise ValueError(
                        f"Invalid status transition: {old_obj.status} -> {self.status}"
                    )
            except ContainerJob.DoesNotExist:
                pass  # New object, no validation needed

        super().save(*args, **kwargs)
