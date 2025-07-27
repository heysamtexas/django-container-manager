"""
Google Cloud Run executor for serverless container execution.

This executor uses Google Cloud Run Jobs API to execute container jobs
with automatic scaling, pay-per-use pricing, and managed infrastructure.
"""

import logging
import time
from typing import Dict, Optional, Tuple

from django.utils import timezone

from ..models import ContainerExecution, ContainerJob
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError

logger = logging.getLogger(__name__)


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

    def __init__(self, config: Dict):
        super().__init__(config)

        # Required configuration - try executor_config first, then parse connection_string
        self.project_id = config.get("project_id")
        if not self.project_id and "executor_config" in config:
            self.project_id = config["executor_config"].get("project_id")
        
        # If still no project_id, try parsing from connection_string
        if not self.project_id and "docker_host" in config:
            connection_string = config["docker_host"].connection_string
            if connection_string.startswith("cloudrun://"):
                # Parse cloudrun://project-id/region format
                parts = connection_string[11:].split("/")
                if len(parts) >= 1:
                    self.project_id = parts[0]
        
        if not self.project_id:
            raise ExecutorConfigurationError(
                "CloudRun executor requires 'project_id' configuration"
            )

        # Cloud Run settings - parse region from connection string if available
        self.region = config.get("region")
        if not self.region and "executor_config" in config:
            self.region = config["executor_config"].get("region")
        
        # Parse region from connection_string if still not set
        if not self.region and "docker_host" in config:
            connection_string = config["docker_host"].connection_string
            if connection_string.startswith("cloudrun://"):
                parts = connection_string[11:].split("/")
                if len(parts) >= 2:
                    self.region = parts[1]
        
        # Default region if still not set
        if not self.region:
            self.region = "us-central1"
            
        self.service_account = config.get("service_account")
        self.vpc_connector = config.get("vpc_connector")

        # Resource settings
        self.memory_limit = config.get("memory_limit", 512)  # MB
        self.cpu_limit = config.get("cpu_limit", 1.0)  # cores
        self.timeout_seconds = config.get("timeout_seconds", 600)  # seconds

        # Job settings
        self.max_retries = config.get("max_retries", 3)
        self.parallelism = config.get("parallelism", 1)
        self.task_count = config.get("task_count", 1)

        # Additional settings
        self.env_vars = config.get("env_vars", {})
        self.labels = config.get("labels", {})

        # GCP client (will be initialized when needed)
        self._run_client = None
        self._logging_client = None

        # Job tracking
        self._active_jobs = {}  # job_name -> job_info

    def _get_run_client(self):
        """Get or create Cloud Run client."""
        if self._run_client is None:
            try:
                from google.cloud import run_v2

                self._run_client = run_v2.JobsClient()
            except ImportError:
                raise ExecutorConfigurationError(
                    "Google Cloud Run client not available. "
                    "Install with: pip install google-cloud-run"
                )
            except Exception as e:
                raise ExecutorConfigurationError(
                    f"Failed to initialize Cloud Run client: {e}"
                )

        return self._run_client

    def _get_logging_client(self):
        """Get or create Cloud Logging client."""
        if self._logging_client is None:
            try:
                from google.cloud import logging

                self._logging_client = logging.Client(project=self.project_id)
            except ImportError:
                raise ExecutorConfigurationError(
                    "Google Cloud Logging client not available. Install with: pip install google-cloud-logging"
                )
            except Exception as e:
                raise ExecutorConfigurationError(
                    f"Failed to initialize Cloud Logging client: {e}"
                )

        return self._logging_client

    def launch_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """
        Launch a job using Cloud Run Jobs API.

        Args:
            job: ContainerJob to launch

        Returns:
            Tuple of (success, job_name or error_message)
        """
        try:
            logger.info(
                f"CloudRun executor launching job {job.id} (template: {job.template.name})"
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

                # Create execution record
                execution = ContainerExecution.objects.create(
                    job=job,
                    stdout_log=f"Cloud Run job {job_name} created and started\n",
                    stderr_log="",
                    docker_log=f"Cloud Run job: {job_resource.name}\n"
                    f"Execution: {execution_name}\n"
                    f"Region: {self.region}\n"
                    f"Project: {self.project_id}\n",
                )

                logger.info(
                    f"CloudRun job {job.id} launched successfully as {job_name}"
                )
                return True, job_name

            except Exception as e:
                logger.error(f"Failed to create/run Cloud Run job: {e}")
                return False, f"Cloud Run API error: {e}"

        except Exception as e:
            logger.error(f"CloudRun executor failed to launch job {job.id}: {e}")
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
            job_info = self._active_jobs.get(execution_id)
            if not job_info:
                return "not-found"

            # Check cached status first
            if job_info["status"] != "running":
                return job_info["status"]

            client = self._get_run_client()

            try:
                # Get the latest execution status
                executions = client.list_executions(
                    parent=job_info["job_resource_name"]
                )

                # Find the most recent execution
                latest_execution = None
                for execution in executions:
                    if (
                        latest_execution is None
                        or execution.create_time > latest_execution.create_time
                    ):
                        latest_execution = execution

                if not latest_execution:
                    job_info["status"] = "failed"
                    return "failed"

                # Map Cloud Run status to our status
                conditions = latest_execution.status.conditions
                for condition in conditions:
                    if condition.type_ == "Completed":
                        if condition.state.name == "CONDITION_SUCCEEDED":
                            job_info["status"] = "completed"
                            return "completed"
                        elif condition.state.name == "CONDITION_FAILED":
                            job_info["status"] = "failed"
                            return "failed"

                # Check if still running or pending
                if latest_execution.status.phase.name in [
                    "PHASE_PENDING",
                    "PHASE_RUNNING",
                ]:
                    return "running"

                # Default to failed for unknown states
                job_info["status"] = "failed"
                return "failed"

            except Exception as e:
                logger.error(f"Error checking Cloud Run job status: {e}")
                return "running"  # Assume still running on API errors

        except Exception as e:
            logger.error(f"Error checking status for execution {execution_id}: {e}")
            return "not-found"

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
                logger.warning(f"No job info found for {job.id}, using minimal data")
                # Mark as completed with minimal data
                job.status = "completed"
                job.exit_code = 0
                job.completed_at = timezone.now()
                job.save()
                return True

            try:
                # Get execution details
                client = self._get_run_client()

                executions = client.list_executions(
                    parent=job_info["job_resource_name"]
                )

                latest_execution = None
                for execution in executions:
                    if (
                        latest_execution is None
                        or execution.create_time > latest_execution.create_time
                    ):
                        latest_execution = execution

                if latest_execution:
                    # Determine exit code and status
                    exit_code = 0
                    status = "completed"

                    conditions = latest_execution.status.conditions
                    for condition in conditions:
                        if condition.type_ == "Completed":
                            if condition.state.name == "CONDITION_FAILED":
                                exit_code = 1
                                status = "failed"
                                break

                    # Update job
                    job.exit_code = exit_code
                    job.status = status
                    job.completed_at = timezone.now()
                    job.save()

                    # Collect logs
                    logs = self._collect_logs(job_info)

                    # Update execution record
                    try:
                        execution = job.execution
                        execution.stdout_log += logs.get(
                            "stdout", "No stdout logs available\n"
                        )
                        execution.stderr_log = logs.get("stderr", "")
                        execution.docker_log += (
                            f"Job completed with exit code {exit_code}\n"
                        )
                        execution.docker_log += logs.get("cloud_run", "")

                        # Estimate resource usage (Cloud Run doesn't provide detailed metrics)
                        execution.max_memory_usage = (
                            self.memory_limit * 1024 * 1024
                        )  # Convert MB to bytes
                        execution.cpu_usage_percent = min(
                            self.cpu_limit * 100, 100
                        )  # Estimate CPU usage
                        execution.save()

                    except ContainerExecution.DoesNotExist:
                        ContainerExecution.objects.create(
                            job=job,
                            stdout_log=logs.get("stdout", "No stdout logs available\n"),
                            stderr_log=logs.get("stderr", ""),
                            docker_log=f"Job completed with exit code {exit_code}\n"
                            + logs.get("cloud_run", ""),
                            max_memory_usage=self.memory_limit * 1024 * 1024,
                            cpu_usage_percent=min(self.cpu_limit * 100, 100),
                        )

            except Exception as e:
                logger.error(f"Error harvesting Cloud Run job details: {e}")
                # Still mark as completed but with minimal data
                job.status = "completed"
                job.exit_code = 0
                job.completed_at = timezone.now()
                job.save()

            # Clean up tracking
            if execution_id in self._active_jobs:
                del self._active_jobs[execution_id]

            logger.info(f"Successfully harvested CloudRun job {job.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to harvest CloudRun job {job.id}: {e}")
            return False

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

            return True

        except Exception as e:
            logger.error(f"Error cleaning up execution {execution_id}: {e}")
            return False

    def get_logs(self, execution_id: str) -> Optional[str]:
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

    def get_resource_usage(self, execution_id: str) -> Optional[Dict]:
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

    def _create_job_spec(self, job: ContainerJob, job_name: str) -> "run_v2.Job":
        """Create Cloud Run job specification."""
        from google.cloud import run_v2

        # Build environment variables
        env_vars = []

        # Add template environment variables
        for key, value in job.template.get_all_environment_variables().items():
            env_vars.append(run_v2.EnvVar(name=key, value=value))

        # Add override environment variables
        if job.override_environment:
            for key, value in job.override_environment.items():
                env_vars.append(run_v2.EnvVar(name=key, value=value))

        # Add additional configured environment variables
        for key, value in self.env_vars.items():
            env_vars.append(run_v2.EnvVar(name=key, value=value))

        # Determine command
        command = None
        args = None
        if job.override_command:
            command_parts = job.override_command.split()
            if command_parts:
                command = [command_parts[0]]
                args = command_parts[1:]
        elif job.template.command:
            command_parts = job.template.command.split()
            if command_parts:
                command = [command_parts[0]]
                args = command_parts[1:]

        # Build resource requirements
        memory_mb = min(job.template.memory_limit, 32768)  # Cloud Run max
        cpu_cores = min(job.template.cpu_limit, 8.0)  # Cloud Run max
        timeout = min(job.template.timeout_seconds, 3600)  # Cloud Run max

        # Create container spec
        container = run_v2.Container(
            image=job.template.docker_image,
            env=env_vars,
            resources=run_v2.ResourceRequirements(
                limits={"memory": f"{memory_mb}Mi", "cpu": str(cpu_cores)}
            ),
        )

        if command:
            container.command = command
        if args:
            container.args = args

        # Create task template
        task_template = run_v2.TaskTemplate(
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

        # Build labels
        labels = {
            "managed-by": "django-docker-manager",
            "job-id": str(job.id),
            "template": job.template.name.replace("_", "-").lower(),
        }
        labels.update(self.labels)

        # Create job spec
        job_spec = run_v2.Job(
            spec=run_v2.JobSpec(template=task_template), labels=labels
        )

        return job_spec

    def _collect_logs(self, job_info: Dict) -> Dict[str, str]:
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

            end_time = datetime.datetime.now(datetime.timezone.utc)
            start_time = end_time - datetime.timedelta(hours=1)

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
            logger.error(f"Failed to collect logs: {e}")
            return {
                "stdout": f"Failed to collect logs: {e}\n",
                "stderr": "",
                "cloud_run": f"Log collection error: {e}\n",
            }

    def get_cost_estimate(self, job: ContainerJob) -> Dict[str, float]:
        """
        Estimate the cost of running this job on Cloud Run.

        Returns:
            Dictionary with cost breakdown
        """
        # Cloud Run pricing (as of 2024, may vary by region)
        # CPU: $0.00002400 per vCPU-second
        # Memory: $0.00000250 per GiB-second
        # Requests: $0.40 per million requests

        cpu_cores = min(job.template.cpu_limit, 8.0)
        memory_gb = min(job.template.memory_limit / 1024, 32)  # Convert MB to GB
        duration_seconds = job.template.timeout_seconds

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
