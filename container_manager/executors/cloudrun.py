"""
Google Cloud Run executor for serverless container execution.

This executor uses Google Cloud Run Jobs API to execute container jobs
with automatic scaling, pay-per-use pricing, and managed infrastructure.
"""

import logging
import time

from django.utils import timezone

from ..models import ContainerJob
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError

logger = logging.getLogger(__name__)

# Constants
MIN_CONNECTION_STRING_PARTS = (
    2  # Minimum parts required in cloudrun:// connection string
)


class CloudRunExecutor(ContainerExecutor):
    """
    Cloud Run executor that executes jobs using Google Cloud Run Jobs API.

    Configuration options:
    - project_id: GCP project ID (required)
    - region: Cloud Run region (default: us-central1)
    - service_account: Service account email for job execution
    - vpc_connector: VPC connector for network access
    - memory_limit: Memory limit in MB (128-32768)
    - cpu_limit: CPU limit in cores (0.08-8.0)
    - timeout_seconds: Job timeout in seconds (max 3600)
    - max_retries: Maximum job retries (default: 3)
    - parallelism: Number of parallel job executions (default: 1)
    - task_count: Number of tasks per job (default: 1)
    - env_vars: Additional environment variables
    - labels: GCP resource labels
    """

    def __init__(self, config: dict):
        super().__init__(config)

        # Parse required configuration
        self.project_id = self._parse_project_id(config)
        self.region = self._parse_region(config)

        # Parse optional settings
        self._parse_service_settings(config)
        self._parse_resource_settings(config)
        self._parse_job_settings(config)
        self._parse_additional_settings(config)

        # Initialize client tracking
        self._run_client = None
        self._logging_client = None
        self._active_jobs = {}  # job_name -> job_info

    def _parse_project_id(self, config: dict) -> str:
        """Parse and validate project_id from configuration"""
        # Try direct config first
        project_id = config.get("project_id")
        if project_id:
            return project_id

        # Try executor_config
        if "executor_config" in config:
            project_id = config["executor_config"].get("project_id")
            if project_id:
                return project_id

        # Try parsing from connection_string
        project_id = self._parse_project_from_connection_string(config)
        if project_id:
            return project_id

        raise ExecutorConfigurationError("project_id required")

    def _parse_project_from_connection_string(self, config: dict) -> str | None:
        """Extract project_id from cloudrun:// connection string"""
        if "docker_host" not in config:
            return None

        connection_string = config["docker_host"].connection_string
        if not connection_string.startswith("cloudrun://"):
            return None

        parts = connection_string[11:].split("/")
        return parts[0] if parts else None

    def _parse_region(self, config: dict) -> str:
        """Parse region with fallbacks to default"""
        # Try direct config first
        region = config.get("region")
        if region:
            return region

        # Try executor_config
        if "executor_config" in config:
            region = config["executor_config"].get("region")
            if region:
                return region

        # Try parsing from connection_string
        region = self._parse_region_from_connection_string(config)
        if region:
            return region

        # Default region
        return "us-central1"

    def _parse_region_from_connection_string(self, config: dict) -> str | None:
        """Extract region from cloudrun:// connection string"""
        if "docker_host" not in config:
            return None

        connection_string = config["docker_host"].connection_string
        if not connection_string.startswith("cloudrun://"):
            return None

        parts = connection_string[11:].split("/")
        return parts[1] if len(parts) >= MIN_CONNECTION_STRING_PARTS else None

    def _parse_service_settings(self, config: dict) -> None:
        """Parse service account and VPC settings"""
        self.service_account = config.get("service_account")
        self.vpc_connector = config.get("vpc_connector")

    def _parse_resource_settings(self, config: dict) -> None:
        """Parse resource limit settings"""
        self.memory_limit = config.get("memory_limit", 512)  # MB
        self.cpu_limit = config.get("cpu_limit", 1.0)  # cores
        self.timeout_seconds = config.get("timeout_seconds", 600)  # seconds

    def _parse_job_settings(self, config: dict) -> None:
        """Parse job execution settings"""
        self.max_retries = config.get("max_retries", 3)
        self.parallelism = config.get("parallelism", 1)
        self.task_count = config.get("task_count", 1)

    def _parse_additional_settings(self, config: dict) -> None:
        """Parse environment variables and labels"""
        self.env_vars = config.get("env_vars", {})
        self.labels = config.get("labels", {})

    def _get_run_client(self):
        """Get or create Cloud Run client."""
        if self._run_client is None:
            try:
                from google.cloud import run_v2

                self._run_client = run_v2.JobsClient()
            except ImportError as e:
                raise ExecutorConfigurationError(
                    "google-cloud-run not installed"
                ) from e
            except Exception as e:
                raise ExecutorConfigurationError(
                    f"Failed to initialize Cloud Run client: {e}"
                ) from e

        return self._run_client

    def _get_logging_client(self):
        """Get or create Cloud Logging client."""
        if self._logging_client is None:
            try:
                from google.cloud import logging

                self._logging_client = logging.Client(project=self.project_id)
            except ImportError as e:
                raise ExecutorConfigurationError(
                    "google-cloud-logging not installed"
                ) from e
            except Exception as e:
                raise ExecutorConfigurationError(
                    f"Failed to initialize Cloud Logging client: {e}"
                ) from e

        return self._logging_client

    def launch_job(self, job: ContainerJob) -> tuple[bool, str]:
        """
        Launch a job using Cloud Run Jobs API.

        Args:
            job: ContainerJob to launch

        Returns:
            Tuple of (success, job_name or error_message)
        """
        try:
            logger.info(
                f"CloudRun executor launching job {job.id} (name: {job.name or 'unnamed'})"
            )

            # Generate unique job name
            job_name = f"job-{job.id.hex[:8]}-{int(time.time())}"

            # Create job specification
            job_spec = self._create_job_spec(job, job_name)

            # Get Cloud Run client
            client = self._get_run_client()

            # Create the job
            parent = f"projects/{self.project_id}/locations/{self.region}"

            try:
                from google.cloud import run_v2

                request = run_v2.CreateJobRequest(
                    parent=parent, job=job_spec, job_id=job_name
                )

                operation = client.create_job(request=request)

                # Wait for job creation to complete
                job_resource = operation.result(timeout=60)

                logger.info(f"Cloud Run job created: {job_resource.name}")

                # Start the job execution
                execution_request = run_v2.RunJobRequest(name=job_resource.name)
                execution_operation = client.run_job(request=execution_request)

                # Don't wait for execution to complete, just get the execution name
                execution_name = execution_operation.name

                # Store job info for tracking
                job_info = {
                    "job_id": str(job.id),
                    "job_name": job_name,
                    "job_resource_name": job_resource.name,
                    "execution_name": execution_name,
                    "start_time": timezone.now(),
                    "status": "running",
                }
                self._active_jobs[job_name] = job_info

                # Update job status
                job.status = "running"
                job.started_at = timezone.now()
                job.save()

                # Set execution data directly on job
                job.stdout_log = f"Cloud Run job {job_name} created and started\n"
                job.stderr_log = ""
                job.docker_log = (
                    f"Cloud Run job: {job_resource.name}\n"
                    f"Execution: {execution_name}\n"
                    f"Region: {self.region}\n"
                    f"Project: {self.project_id}\n"
                )
            except Exception as e:
                logger.exception("Failed to create/run Cloud Run job")
                return False, f"Cloud Run API error: {e}"
            else:
                logger.info(
                    f"CloudRun job {job.id} launched successfully as {job_name}"
                )
                return True, job_name

        except Exception as e:
            logger.exception(f"CloudRun executor failed to launch job {job.id}")
            return False, str(e)

    def check_status(self, execution_id: str) -> str:
        """
        Check status of a Cloud Run job execution.

        Args:
            execution_id: Cloud Run job name

        Returns:
            Status string ('running', 'completed', 'failed', 'not-found')
        """
        try:
            job_info = self._get_job_info_with_validation(execution_id)
            if not job_info:
                return "not-found"

            # Return cached status if not running
            if job_info["status"] != "running":
                return job_info["status"]

            # Get fresh status from Cloud Run
            return self._get_fresh_status_from_cloudrun(job_info)

        except Exception:
            logger.exception(f"Error checking status for execution {execution_id}")
            return "not-found"

    def _get_job_info_with_validation(self, execution_id: str):
        """Get job info and validate it exists"""
        return self._active_jobs.get(execution_id)

    def _get_fresh_status_from_cloudrun(self, job_info: dict) -> str:
        """Get current status from Cloud Run API"""
        try:
            client = self._get_run_client()
            latest_execution = self._get_latest_execution_from_api(client, job_info)

            if not latest_execution:
                return self._update_job_status_and_return(job_info, "failed")

            return self._map_execution_status(job_info, latest_execution)

        except Exception:
            logger.exception("Error checking Cloud Run job status")
            return "running"  # Assume still running on API errors

    def _get_latest_execution_from_api(self, client, job_info: dict):
        """Get the most recent execution from Cloud Run API"""
        executions = client.list_executions(parent=job_info["job_resource_name"])

        latest_execution = None
        for execution in executions:
            if (
                latest_execution is None
                or execution.create_time > latest_execution.create_time
            ):
                latest_execution = execution

        return latest_execution

    def _map_execution_status(self, job_info: dict, execution) -> str:
        """Map Cloud Run execution status to our standard status"""
        # Check completion conditions first
        completion_status = self._check_completion_conditions(execution)
        if completion_status:
            return self._update_job_status_and_return(job_info, completion_status)

        # Check if still running or pending
        if self._is_execution_active(execution):
            return "running"

        # Default to failed for unknown states
        return self._update_job_status_and_return(job_info, "failed")

    def _check_completion_conditions(self, execution):
        """Check Cloud Run completion conditions"""
        conditions = execution.status.conditions
        for condition in conditions:
            if condition.type_ == "Completed":
                if condition.state.name == "CONDITION_SUCCEEDED":
                    return "completed"
                elif condition.state.name == "CONDITION_FAILED":
                    return "failed"
        return None

    def _is_execution_active(self, execution) -> bool:
        """Check if execution is still active (running or pending)"""
        return execution.status.phase.name in ["PHASE_PENDING", "PHASE_RUNNING"]

    def _update_job_status_and_return(self, job_info: dict, status: str) -> str:
        """Update cached job status and return it"""
        job_info["status"] = status
        return status

    def harvest_job(self, job: ContainerJob) -> bool:
        """
        Harvest results from a completed Cloud Run job.

        Args:
            job: ContainerJob to harvest

        Returns:
            True if harvest was successful
        """
        try:
            logger.info(f"Harvesting CloudRun job {job.id}")

            execution_id = job.get_execution_identifier()
            job_info = self._active_jobs.get(execution_id)

            if not job_info:
                self._handle_missing_job_info(job)
                return True

            try:
                self._harvest_job_with_details(job, job_info)
            except Exception:
                logger.exception("Error harvesting Cloud Run job details")
                # Mark job as completed with minimal data when detailed harvest fails
                job.status = "completed"
                job.exit_code = 0
                job.completed_at = timezone.now()
                job.save()

            self._cleanup_job_tracking(execution_id)
        except Exception:
            logger.exception(f"Failed to harvest CloudRun job {job.id}")
            return False
        else:
            logger.info(f"Successfully harvested CloudRun job {job.id}")
            return True

    def _handle_missing_job_info(self, job: ContainerJob) -> None:
        """Handle job harvest when no job info is found"""
        logger.warning(f"No job info found for {job.id}, using minimal data")
        job.status = "completed"
        job.exit_code = 0
        job.completed_at = timezone.now()
        job.save()

    def _harvest_job_with_details(self, job: ContainerJob, job_info: dict) -> None:
        """Harvest job with full Cloud Run execution details"""
        latest_execution = self._get_latest_execution(job_info)

        if latest_execution:
            exit_code, status = self._determine_job_outcome(latest_execution)
            self._update_job_status(job, exit_code, status)

            logs = self._collect_logs(job_info)
            self._update_execution_record(job, logs, exit_code)

    def _get_latest_execution(self, job_info: dict):
        """Get the latest execution from Cloud Run"""
        client = self._get_run_client()
        executions = client.list_executions(parent=job_info["job_resource_name"])

        latest_execution = None
        for execution in executions:
            if (
                latest_execution is None
                or execution.create_time > latest_execution.create_time
            ):
                latest_execution = execution

        return latest_execution

    def _determine_job_outcome(self, execution) -> tuple:
        """Determine exit code and status from Cloud Run execution"""
        exit_code = 0
        status = "completed"

        conditions = execution.status.conditions
        for condition in conditions:
            if (
                condition.type_ == "Completed"
                and condition.state.name == "CONDITION_FAILED"
            ):
                exit_code = 1
                status = "failed"
                break

        return exit_code, status

    def _update_job_status(
        self, job: ContainerJob, exit_code: int, status: str
    ) -> None:
        """Update job with final status and exit code"""
        job.exit_code = exit_code
        job.status = status
        job.completed_at = timezone.now()
        job.save()

    def _update_execution_record(
        self, job: ContainerJob, logs: dict, exit_code: int
    ) -> None:
        """Update job with execution record with logs and resource usage"""
        # Update logs directly on job
        if job.stdout_log:
            job.stdout_log += logs.get("stdout", "No stdout logs available\n")
        else:
            job.stdout_log = logs.get("stdout", "No stdout logs available\n")

        job.stderr_log = logs.get("stderr", "")

        if job.docker_log:
            job.docker_log += f"Job completed with exit code {exit_code}\n"
            job.docker_log += logs.get("cloud_run", "")
        else:
            job.docker_log = f"Job completed with exit code {exit_code}\n" + logs.get(
                "cloud_run", ""
            )

        # Estimate resource usage (Cloud Run doesn't provide detailed metrics)
        job.max_memory_usage = self.memory_limit * 1024 * 1024  # Convert MB to bytes
        job.cpu_usage_percent = min(self.cpu_limit * 100, 100)  # Estimate CPU usage
        job.save()

    def _cleanup_job_tracking(self, execution_id: str) -> None:
        """Clean up job tracking data"""
        if execution_id in self._active_jobs:
            del self._active_jobs[execution_id]

    def cleanup(self, execution_id: str) -> bool:
        """
        Clean up Cloud Run job resources.

        Args:
            execution_id: Cloud Run job name

        Returns:
            True if cleanup was successful
        """
        try:
            logger.debug(f"Cleaning up CloudRun job {execution_id}")

            job_info = self._active_jobs.get(execution_id)
            if job_info:
                try:
                    client = self._get_run_client()

                    # Delete the Cloud Run job
                    from google.cloud import run_v2

                    delete_request = run_v2.DeleteJobRequest(
                        name=job_info["job_resource_name"]
                    )

                    operation = client.delete_job(request=delete_request)
                    operation.result(timeout=60)  # Wait for deletion

                    logger.info(
                        f"Cloud Run job {job_info['job_resource_name']} deleted"
                    )

                except Exception as e:
                    logger.warning(f"Failed to delete Cloud Run job: {e}")
                    # Don't fail cleanup if we can't delete the job

                # Remove from tracking
                del self._active_jobs[execution_id]
        except Exception:
            logger.exception(f"Error cleaning up execution {execution_id}")
            return False
        else:
            return True

    def get_logs(self, execution_id: str) -> str | None:
        """
        Get logs from Cloud Run job execution.

        Args:
            execution_id: Cloud Run job name

        Returns:
            Log string or None if not found
        """
        job_info = self._active_jobs.get(execution_id)
        if not job_info:
            return f"CloudRun logs for execution {execution_id}\nExecution not found in tracking\n"

        logs = self._collect_logs(job_info)

        return (
            f"=== STDOUT ===\n{logs.get('stdout', 'No stdout logs')}\n"
            f"=== STDERR ===\n{logs.get('stderr', 'No stderr logs')}\n"
            f"=== CLOUD RUN ===\n{logs.get('cloud_run', 'No Cloud Run logs')}\n"
        )

    def get_resource_usage(self, execution_id: str) -> dict | None:
        """
        Get resource usage stats for Cloud Run execution.

        Args:
            execution_id: Cloud Run job name

        Returns:
            Resource usage dictionary or None if not found
        """
        # Cloud Run doesn't provide detailed resource metrics
        # Return estimates based on configuration
        return {
            "memory_usage_bytes": self.memory_limit * 1024 * 1024,  # Estimate
            "cpu_usage_percent": min(self.cpu_limit * 100, 100),  # Estimate
            "execution_time_seconds": 0,  # Would need to calculate from start/end times
        }

    def _create_job_spec(self, job: ContainerJob, job_name: str):
        """Create Cloud Run job specification."""
        from google.cloud import run_v2

        env_vars = self._build_environment_variables(job)
        command, args = self._parse_command(job)
        container = self._create_container_spec(job, env_vars, command, args)
        task_template = self._create_task_template(container, job)
        labels = self._build_job_labels(job)

        return run_v2.Job(spec=run_v2.JobSpec(template=task_template), labels=labels)

    def _build_environment_variables(self, job: ContainerJob) -> list:
        """Build complete list of environment variables"""
        from google.cloud import run_v2

        env_vars = []

        # Add job environment variables (includes template and overrides)
        for key, value in job.get_all_environment_variables().items():
            env_vars.append(run_v2.EnvVar(name=key, value=value))

        # Add additional configured environment variables
        for key, value in self.env_vars.items():
            env_vars.append(run_v2.EnvVar(name=key, value=value))

        return env_vars

    def _parse_command(self, job: ContainerJob) -> tuple:
        """Parse command and arguments from job configuration"""
        command_string = job.command
        if not command_string:
            return None, None

        command_parts = command_string.split()
        if not command_parts:
            return None, None

        return [command_parts[0]], command_parts[1:]

    def _create_container_spec(
        self, job: ContainerJob, env_vars: list, command: list, args: list
    ):
        """Create Cloud Run container specification"""
        from google.cloud import run_v2

        memory_mb = min(job.memory_limit or 512, 32768)  # Cloud Run max
        cpu_cores = min(job.cpu_limit or 1.0, 8.0)  # Cloud Run max

        container = run_v2.Container(
            image=job.docker_image,
            env=env_vars,
            resources=run_v2.ResourceRequirements(
                limits={"memory": f"{memory_mb}Mi", "cpu": str(cpu_cores)}
            ),
        )

        if command:
            container.command = command
        if args:
            container.args = args

        return container

    def _create_task_template(self, container, job: ContainerJob):
        """Create Cloud Run task template"""
        from google.cloud import run_v2

        timeout = min(job.timeout_seconds or 3600, 3600)  # Cloud Run max

        return run_v2.TaskTemplate(
            template=run_v2.ExecutionTemplate(
                template=run_v2.TaskTemplate(
                    template=run_v2.ContainerTemplate(
                        containers=[container],
                        timeout=f"{timeout}s",
                        service_account=self.service_account,
                        vpc_access=run_v2.VpcAccess(connector=self.vpc_connector)
                        if self.vpc_connector
                        else None,
                    )
                ),
                parallelism=self.parallelism,
                task_count=self.task_count,
                task_timeout=f"{timeout}s",
            )
        )

    def _build_job_labels(self, job: ContainerJob) -> dict:
        """Build labels for Cloud Run job"""
        labels = {
            "managed-by": "django-docker-manager",
            "job-id": str(job.id),
            "job-name": (job.name or "unnamed").replace("_", "-").lower(),
        }
        labels.update(self.labels)
        return labels

    def _collect_logs(self, job_info: dict) -> dict[str, str]:
        """Collect logs from Cloud Logging."""
        try:
            logging_client = self._get_logging_client()

            # Build log filter
            job_name = job_info["job_name"]
            filter_str = (
                f'resource.type="cloud_run_job" '
                f'resource.labels.job_name="{job_name}" '
                f"severity>=DEFAULT"
            )

            # Get logs from the last hour
            import datetime

            datetime.datetime.now(datetime.timezone.utc)
            # We'll get all entries from the last hour, but don't need start_time

            entries = logging_client.list_entries(
                filter_=filter_str, page_size=1000, max_results=1000
            )

            stdout_logs = []
            stderr_logs = []
            cloud_run_logs = []

            for entry in entries:
                timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                severity = entry.severity.name if entry.severity else "INFO"
                message = (
                    entry.payload
                    if isinstance(entry.payload, str)
                    else str(entry.payload)
                )

                log_line = f"[{timestamp}] {severity}: {message}"

                # Categorize logs based on severity and content
                if severity in ["ERROR", "CRITICAL"]:
                    stderr_logs.append(log_line)
                elif "cloud run" in message.lower():
                    cloud_run_logs.append(log_line)
                else:
                    stdout_logs.append(log_line)

            return {
                "stdout": "\n".join(stdout_logs) + "\n" if stdout_logs else "",
                "stderr": "\n".join(stderr_logs) + "\n" if stderr_logs else "",
                "cloud_run": "\n".join(cloud_run_logs) + "\n" if cloud_run_logs else "",
            }

        except Exception as e:
            logger.exception("Failed to collect logs")
            return {
                "stdout": f"Failed to collect logs: {e}\n",
                "stderr": "",
                "cloud_run": f"Log collection error: {e}\n",
            }

    def get_cost_estimate(self, job: ContainerJob) -> dict[str, float]:
        """
        Estimate the cost of running this job on Cloud Run.

        Returns:
            Dictionary with cost breakdown
        """
        # Cloud Run pricing (as of 2024, may vary by region)
        # CPU: $0.00002400 per vCPU-second
        # Memory: $0.00000250 per GiB-second
        # Requests: $0.40 per million requests

        cpu_cores = min(job.cpu_limit or 1.0, 8.0)
        memory_gb = min((job.memory_limit or 512) / 1024, 32)  # Convert MB to GB
        duration_seconds = job.timeout_seconds or 3600

        cpu_cost = cpu_cores * duration_seconds * 0.00002400
        memory_cost = memory_gb * duration_seconds * 0.00000250
        request_cost = 0.40 / 1000000  # Cost per request

        total_cost = cpu_cost + memory_cost + request_cost

        return {
            "cpu_cost": cpu_cost,
            "memory_cost": memory_cost,
            "request_cost": request_cost,
            "total_cost": total_cost,
            "currency": "USD",
        }

    def _validate_executor_specific(self, job) -> list[str]:
        """CloudRun-specific validation logic"""
        errors = []

        # CloudRun-specific validation: execution_id required for running jobs
        if job.status == "running" and not job.get_execution_identifier():
            errors.append("Execution ID required for running Cloud Run jobs")

        # CloudRun-specific validation: project_id is required
        config = job.docker_host.executor_config or {}
        if not config.get("project_id"):
            errors.append("project_id is required for Cloud Run executor")

        # CloudRun-specific validation: resource limits
        if job.memory_limit and job.memory_limit > 32768:
            errors.append("Cloud Run memory limit cannot exceed 32768 MB")
        if job.cpu_limit and job.cpu_limit > 8.0:
            errors.append("Cloud Run CPU limit cannot exceed 8.0 cores")

        return errors

    def get_execution_display(self, job) -> dict[str, str]:
        """CloudRun-specific execution display information"""
        execution_id = job.get_execution_identifier()
        config = job.docker_host.executor_config or {}
        region = config.get("region", "unknown")

        return {
            "type_name": f"Cloud Run Job ({region})",
            "id_label": "Execution ID",
            "id_value": execution_id or "Not started",
            "status_detail": self._get_cloudrun_status_detail(job),
        }

    def _get_cloudrun_status_detail(self, job) -> str:
        """Get CloudRun-specific status details"""
        status = job.status.title()

        if job.exit_code is not None:
            if job.exit_code == 0:
                status += " (Success)"
            else:
                status += f" (Exit Code: {job.exit_code})"

        # Add Cloud Run specific details if available
        config = job.docker_host.executor_config or {}
        if config.get("project_id"):
            status += f" [Project: {config['project_id']}]"

        return status
