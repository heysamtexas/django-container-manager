"""
Docker-based container executor implementation.

Implements the ContainerExecutor interface for Docker containers,
providing multi-host Docker support with comprehensive lifecycle management.
"""

import logging
import time
from typing import Any

import docker
from django.db import transaction
from django.utils import timezone as django_timezone
from docker.errors import (
    APIError,
    DockerException,
    NotFound,
)

from ..models import ContainerJob, ExecutorHost
from .base import ContainerExecutor
from .exceptions import (
    ExecutorConnectionError,
    ExecutorError,
)

logger = logging.getLogger(__name__)


class DockerExecutor(ContainerExecutor):
    """Docker-based container executor"""

    def __init__(self, config: dict):
        super().__init__(config)
        self._clients: dict[str, docker.DockerClient] = {}
        self.docker_host = config.get("docker_host")

    @transaction.atomic
    def launch_job(self, job: ContainerJob) -> tuple[bool, str]:
        """Launch a container job in the background with transaction safety and cleanup"""
        # Mark job as launching (two-phase commit pattern)
        job.status = "launching"
        job.save()

        container_id = None
        try:
            # Validate job can be executed
            self._validate_job(job)

            # Create container
            container_id = self._create_container(job)
            if not container_id:
                job.status = "failed"
                job.save()
                return False, "Failed to create container"

            # Start container
            success = self._start_container(job, container_id)
            if not success:
                # Container was created but failed to start - clean it up
                self._safe_container_cleanup(container_id)
                job.status = "failed"
                job.save()
                return False, "Failed to start container"

        except ExecutorError as e:
            logger.error(f"Executor error launching job {job.id}: {e}")
            # Clean up any partially created container
            if container_id:
                self._safe_container_cleanup(container_id)
            job.status = "failed"
            job.save()
            return False, str(e)
        except Exception as e:
            logger.exception(f"Unexpected error launching job {job.id}: {e}")
            # Clean up any partially created container
            if container_id:
                self._safe_container_cleanup(container_id)
            job.status = "failed"
            job.save()
            return False, f"Unexpected error: {e}"
        else:
            return True, container_id

    def check_status(self, execution_id: str) -> str:
        """Check the status of a running execution"""
        if not execution_id:
            return "not-found"

        # Find the job
        job = ContainerJob.objects.filter(execution_id=execution_id).first()
        if not job:
            return "not-found"

        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(execution_id)

            container_status = container.status.lower()

            # Map Docker statuses to our standard statuses
            if container_status == "running":
                return "running"
            elif container_status in ["exited", "stopped"]:
                return "exited"
            elif container_status in ["paused", "restarting"]:
                return "running"  # Consider these as still running
            else:
                return "failed"

        except NotFound:
            logger.debug(f"Container {execution_id} not found")
            return "not-found"
        except APIError as e:
            logger.error(f"Docker API error checking status for {execution_id}: {e}")
            return "failed"
        except DockerException as e:
            logger.error(f"Docker error checking status for {execution_id}: {e}")
            return "failed"
        except Exception as e:
            logger.exception(
                f"Unexpected error checking container status {execution_id}: {e}"
            )
            return "failed"

    def get_logs(self, execution_id: str) -> tuple[str, str]:
        """Retrieve logs from completed or running execution"""
        if not execution_id:
            return "", ""

        try:
            # Find the job associated with this execution_id
            job = ContainerJob.objects.filter(execution_id=execution_id).first()
            if not job:
                return "", ""

            client = self._get_client(job.docker_host)
            container = client.containers.get(execution_id)

            # Get logs (timeout parameter not supported in docker-py 7.x)
            logs = container.logs(timestamps=True, stderr=True)
            logs_str = (
                logs.decode("utf-8", errors="replace")
                if isinstance(logs, bytes)
                else str(logs)
            )

            # Split logs into stdout/stderr
            stdout, stderr = self._split_docker_logs(logs_str)
        except NotFound:
            logger.debug(f"Container {execution_id} not found for log retrieval")
            return "", ""
        except APIError as e:
            logger.error(f"Docker API error getting logs for {execution_id}: {e}")
            return "", ""
        except DockerException as e:
            logger.error(f"Docker error getting logs for {execution_id}: {e}")
            return "", ""
        except Exception as e:
            logger.exception(f"Unexpected error getting logs for {execution_id}: {e}")
            return "", ""
        else:
            return stdout, stderr

    def _split_docker_logs(self, logs_str: str) -> tuple[str, str]:
        """Split combined Docker logs into stdout and stderr based on content heuristics"""
        stdout_lines = []
        stderr_lines = []
        error_keywords = ["error", "warning", "exception", "traceback"]

        for line in logs_str.split("\n"):
            if line.strip():
                if any(keyword in line.lower() for keyword in error_keywords):
                    stderr_lines.append(line)
                else:
                    stdout_lines.append(line)

        return (
            "\n".join(stdout_lines) if stdout_lines else "",
            "\n".join(stderr_lines) if stderr_lines else "",
        )

    def harvest_job(self, job: ContainerJob) -> bool:
        """Collect final results and update job status"""
        execution_id = job.get_execution_identifier()
        if not execution_id:
            return False

        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(execution_id)

            # Get exit code
            container.reload()
            exit_code = container.attrs.get("State", {}).get("ExitCode", -1)

            # Update job status
            job.exit_code = exit_code
            job.completed_at = django_timezone.now()
            job.status = "completed" if exit_code == 0 else "failed"
            job.save()

            # Collect execution data
            self._collect_data(job)

            # Immediate cleanup if configured
            self._immediate_cleanup(job)
        except NotFound:
            logger.warning(
                f"Container {execution_id} not found during harvest - job {job.id}"
            )
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False
        except APIError as e:
            logger.error(f"Docker API error harvesting job {job.id}: {e}")
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False
        except DockerException as e:
            logger.error(f"Docker error harvesting job {job.id}: {e}")
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False
        except Exception as e:
            logger.exception(f"Unexpected error harvesting job {job.id}: {e}")
            return False
        else:
            logger.info(f"Harvested job {job.id} with exit code {exit_code}")
            return True

    def cleanup(self, execution_id: str) -> bool:
        """Force cleanup of execution resources"""
        if not execution_id:
            return True

        try:
            # Find the job to get docker_host
            job = ContainerJob.objects.filter(execution_id=execution_id).first()
            client = docker.from_env() if not job else self._get_client(job.docker_host)

            container = client.containers.get(execution_id)
            container.remove(force=True)
        except NotFound:
            logger.debug(f"Container {execution_id} already cleaned up")
            return True
        except APIError as e:
            logger.error(f"Docker API error cleaning up container {execution_id}: {e}")
            return False
        except DockerException as e:
            logger.error(f"Docker error cleaning up container {execution_id}: {e}")
            return False
        except Exception as e:
            logger.exception(
                f"Unexpected error cleaning up container {execution_id}: {e}"
            )
            return False
        else:
            logger.info(f"Cleaned up container {execution_id}")
            return True

    def get_capabilities(self) -> dict[str, bool]:
        """Return Docker executor capabilities"""
        return {
            "supports_resource_limits": True,
            "supports_networking": True,
            "supports_persistent_storage": True,
            "supports_secrets": False,
            "supports_gpu": True,
            "supports_scaling": False,
        }

    def validate_job(self, job: ContainerJob) -> tuple[bool, str]:
        """Validate that a job can be executed by Docker"""
        try:
            self._validate_job(job)
        except ExecutorError as e:
            return False, str(e)
        else:
            return True, ""

    # estimate_cost method removed - deprecated cost tracking functionality

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of Docker daemon"""
        try:
            if self.docker_host:
                client = self._get_client(self.docker_host)
            else:
                client = docker.from_env()

            start_time = time.time()
            client.ping()
            response_time = time.time() - start_time

            return {
                "healthy": True,
                "error": None,
                "last_check": django_timezone.now(),
                "response_time": response_time,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "last_check": django_timezone.now(),
                "response_time": None,
            }

    def _batch_check_statuses(self, jobs, command_handler) -> int:
        """
        Batch status checking to avoid N+1 Docker API calls.

        Instead of calling check_status() for each job individually,
        this method makes a single containers.list() call and creates
        a lookup table for O(1) status checking.

        Args:
            jobs: List of ContainerJob instances to check
            command_handler: Management command instance for job handling

        Returns:
            int: Number of jobs harvested/completed
        """
        if not jobs:
            return 0

        try:
            # Single Docker API call to get all containers
            client = self._get_client(jobs[0].docker_host)  # All jobs have same host
            all_containers = {c.id: c for c in client.containers.list(all=True)}

            harvested = 0
            for job in jobs:
                if command_handler.should_stop:
                    break

                execution_id = job.get_execution_identifier()
                if not execution_id:
                    harvested += command_handler._handle_job_status(job, "not-found")
                    continue

                # O(1) lookup instead of Docker API call
                container = all_containers.get(execution_id)
                if container:
                    # Map Docker status to our standard status
                    status = self._map_container_status(container.status)
                    harvested += command_handler._handle_job_status(job, status)
                else:
                    # Container disappeared
                    harvested += command_handler._handle_job_status(job, "not-found")

            return harvested

        except Exception as e:
            logger.exception(f"Error in batch status checking: {e}")
            # Fallback to individual checking
            return command_handler._monitor_jobs_individually(jobs)

    def _map_container_status(self, docker_status: str) -> str:
        """Map Docker container status to our standard status"""
        docker_status = docker_status.lower()

        if docker_status == "running":
            return "running"
        elif docker_status in ["exited", "stopped"]:
            return "exited"
        elif docker_status in ["paused", "restarting"]:
            return "running"  # Consider these as still running
        else:
            return "failed"

    def _safe_container_cleanup(self, container_id: str) -> None:
        """
        Safely clean up a container without raising exceptions.
        Used for cleanup during error conditions.
        """
        if not container_id:
            return

        try:
            # Try to find the job to get the proper Docker host
            job = ContainerJob.objects.filter(execution_id=container_id).first()
            if job and job.docker_host:
                client = self._get_client(job.docker_host)
            else:
                # Fallback to default client if we can't determine the host
                client = docker.from_env()

            try:
                container = client.containers.get(container_id)
                # Stop the container if it's running
                if container.status.lower() in ["running", "restarting"]:
                    container.stop(timeout=10)
                # Remove the container
                container.remove(force=True)
                logger.info(f"Cleaned up orphaned container {container_id}")
            except NotFound:
                # Container already gone - that's fine
                logger.debug(f"Container {container_id} already removed")
            except Exception as cleanup_error:
                # Log but don't raise - we're in cleanup mode
                logger.warning(
                    f"Failed to cleanup container {container_id}: {cleanup_error}"
                )

        except Exception as outer_error:
            # Even client creation failed - log but don't raise
            logger.warning(
                f"Failed to initialize cleanup for container {container_id}: {outer_error}"
            )

    def _validate_executor_specific(self, job) -> list[str]:
        """Docker-specific validation logic"""
        errors = []

        # Docker-specific validation: execution_id required for running jobs
        if job.status == "running" and not job.get_execution_identifier():
            errors.append("Execution ID required for running Docker jobs")

        # Docker-specific validation: image is required
        if not job.docker_image:
            errors.append("Docker image is required for Docker executor")

        return errors

    def get_execution_display(self, job) -> dict[str, str]:
        """Docker-specific execution display information"""
        execution_id = job.get_execution_identifier()

        return {
            "type_name": "Docker Container",
            "id_label": "Container ID",
            "id_value": execution_id or "Not started",
            "status_detail": self._get_docker_status_detail(job),
        }

    def _get_docker_status_detail(self, job) -> str:
        """Get Docker-specific status details"""
        status = job.status.title()

        if job.exit_code is not None:
            if job.exit_code == 0:
                status += " (Success)"
            else:
                status += f" (Exit Code: {job.exit_code})"

        return status

    # Private helper methods

    def _validate_job(self, job: ContainerJob) -> None:
        """Validate job can be executed"""
        if not job:
            raise ExecutorError("Job is None")

        if job.status not in ["pending", "launching"]:
            raise ExecutorError(f"Invalid status: {job.status}")

        if not job.docker_image:
            raise ExecutorError("No docker image specified")

        if not job.docker_host:
            raise ExecutorError("No docker_host")

    def _get_client(self, docker_host: ExecutorHost) -> docker.DockerClient:
        """Get or create Docker client for host"""
        host_key = f"{docker_host.id}"

        # Try to use cached client
        cached_client = self._get_cached_client(host_key)
        if cached_client:
            return cached_client

        # Create new client
        try:
            client = self._create_docker_client(docker_host)

            # Test connection only if not in testing mode
            if not getattr(self, "_skip_ping_for_tests", False):
                client.ping()

            # Cache client
            self._clients[host_key] = client
            return client

        except Exception as e:
            raise ExecutorConnectionError(
                f"Cannot connect to Docker host {docker_host.name}: {e}"
            ) from e

    def _get_cached_client(self, host_key: str) -> docker.DockerClient | None:
        """Get cached client if available and working"""
        if host_key not in self._clients:
            return None

        try:
            # Test connection only if not in testing mode
            if not getattr(self, "_skip_ping_for_tests", False):
                self._clients[host_key].ping()
            return self._clients[host_key]
        except Exception:
            # Remove stale client
            del self._clients[host_key]
            return None

    def _create_docker_client(self, docker_host: ExecutorHost) -> docker.DockerClient:
        """Create new Docker client based on host configuration"""
        from ..defaults import get_container_manager_setting

        # Get timeout for Docker client operations
        docker_timeout = get_container_manager_setting("DOCKER_TIMEOUT", 30)

        if docker_host.host_type == "unix":
            return docker.DockerClient(
                base_url=docker_host.connection_string, timeout=docker_timeout
            )
        elif docker_host.host_type == "tcp":
            client_kwargs = {
                "base_url": docker_host.connection_string,
                "use_ssh_client": False,
                "timeout": docker_timeout,
            }
            if docker_host.tls_enabled:
                client_kwargs["tls"] = True
            return docker.DockerClient(**client_kwargs)
        else:
            raise ExecutorConnectionError(
                f"Unsupported host type: {docker_host.host_type}"
            ) from None

    def _create_container(self, job: ContainerJob) -> str:
        """Create Docker container for job with proper cleanup on failure"""

        client = self._get_client(job.docker_host)
        container = None

        try:
            self._ensure_image_available(client, job)
            container_config = self._build_container_config(job)

            # Use Docker client's native timeout support
            container = client.containers.create(**container_config)

            # Setup additional networks - if this fails, we need to cleanup the container
            self._setup_additional_networks(client, job, container)

            logger.info(f"Created container {container.id} for job {job.id}")
            return container.id

        except Exception as e:
            logger.exception(f"Failed to create container for job {job.id}")
            # Clean up the container if it was created but setup failed
            if container:
                try:
                    container.remove(force=True)
                    logger.info(f"Cleaned up failed container {container.id}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to cleanup container after creation failure: {cleanup_error}"
                    )

            raise ExecutorError(f"Container creation failed: {e}") from e

    def _build_container_environment(self, job: ContainerJob) -> dict:
        """Build environment variables for container"""
        environment = {}

        # Add job environment variables (includes template and overrides)
        environment.update(job.get_all_environment_variables())

        return environment

    def _build_container_config(self, job: ContainerJob) -> dict:
        """Build complete container configuration"""
        container_config = {
            "image": job.docker_image,
            "command": job.command,
            "environment": self._build_container_environment(job),
            "labels": self._build_labels(job),
            "detach": True,
        }

        # Add resource limits
        self._add_resource_limits(container_config, job)

        # Add primary network
        self._add_primary_network(container_config, job)

        return container_config

    def _add_resource_limits(self, container_config: dict, job) -> None:
        """Add CPU and memory limits to container configuration"""
        if job.memory_limit:
            container_config["mem_limit"] = f"{job.memory_limit}m"

        if job.cpu_limit:
            container_config["cpu_quota"] = int(job.cpu_limit * 100000)
            container_config["cpu_period"] = 100000

    def _add_primary_network(self, container_config: dict, job) -> None:
        """Add primary network to container configuration"""
        networks = job.get_network_names()
        if networks:
            container_config["network"] = networks[0]

    def _get_network_names(self, job) -> list:
        """Get list of network names from job configuration"""
        return job.get_network_names()

    def _ensure_image_available(self, client, job: ContainerJob) -> None:
        """Ensure Docker image is available locally"""
        try:
            client.images.get(job.docker_image)
            logger.debug(f"Image {job.docker_image} already exists locally")
        except NotFound:
            if self._should_pull_image(job.docker_host):
                logger.info(f"Pulling image {job.docker_image}...")
                client.images.pull(job.docker_image)
                logger.info(f"Successfully pulled image {job.docker_image}")
            else:
                raise ExecutorError(
                    f"Image {job.docker_image} not found locally and "
                    "auto-pull is disabled"
                ) from None

    def _setup_additional_networks(self, client, job: ContainerJob, container) -> None:
        """Connect container to additional networks beyond the primary"""
        networks = job.get_network_names()

        # Connect to additional networks (skip first one as it's already set as primary)
        for network_name in networks[1:]:
            try:
                network = client.networks.get(network_name)
                network.connect(container)
            except NotFound:
                logger.warning(
                    f"Network {network_name} not found on {job.docker_host.name}"
                )

    def _start_container(self, job: ContainerJob, container_id: str) -> bool:
        """Start the created container"""
        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(container_id)

            # Docker client start() doesn't support timeout parameter directly
            # The timeout is handled at the client level
            container.start()

            # Update job status
            job.set_execution_identifier(container_id)
            job.status = "running"
            job.started_at = django_timezone.now()
            job.save()

            logger.info(f"Started container {container_id} for job {job.id}")
            return True

        except Exception:
            logger.exception(f"Failed to start container {container_id}")
            job.status = "failed"
            job.save()
            return False

    def _build_labels(self, job: ContainerJob) -> dict[str, str]:
        """Build comprehensive labels for container discovery and management"""
        labels = {
            # Django container management labels
            "django.container_manager.job_id": str(job.id),
            "django.container_manager.job_name": job.name or "unnamed",
            "django.container_manager.host_id": str(job.docker_host.id),
            "django.container_manager.host_name": job.docker_host.name,
            "django.container_manager.created_at": job.created_at.isoformat(),
            # Standard container labels
            "com.docker.compose.project": "django-container-manager",
            "com.docker.compose.service": job.name or "job",
            # Metadata labels
            "version": "1.0",
            "managed_by": "django-container-manager",
        }

        # Add job name if specified
        if job.name:
            labels["django.container_manager.job_name"] = job.name

        # Add user information if available
        if job.created_by:
            labels["django.container_manager.created_by"] = job.created_by.username

        return labels

    def _should_pull_image(self, docker_host: ExecutorHost) -> bool:
        """Determine if images should be auto-pulled for this host"""
        # Check host-specific setting first
        if hasattr(docker_host, "auto_pull_images"):
            return docker_host.auto_pull_images

        # Fall back to global setting
        from ..defaults import get_container_manager_setting

        return get_container_manager_setting("AUTO_PULL_IMAGES", True)

    def _collect_data(self, job: ContainerJob) -> None:
        """Collect execution logs and statistics"""
        execution_id = job.get_execution_identifier()
        if not execution_id:
            return

        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(execution_id)

            # Collect logs directly on job
            stdout, stderr = self.get_logs(execution_id)
            job.stdout_log = stdout
            job.stderr_log = stderr

            # Clean output for downstream processing
            job.clean_output = self._strip_docker_timestamps(stdout)

            # Collect resource statistics
            try:
                stats = container.stats(stream=False)
                if stats:
                    memory_usage = stats.get("memory_usage", {})
                    if memory_usage:
                        job.max_memory_usage = memory_usage.get("max_usage", 0)

                    cpu_stats = stats.get("cpu_stats", {})
                    if cpu_stats:
                        job.cpu_usage_percent = self._calculate_cpu_percent(stats)
            except Exception as e:
                logger.warning(f"Failed to collect stats for job {job.id}: {e}")

            job.save()

        except Exception:
            logger.exception(f"Failed to collect execution data for job {job.id}")

    def _immediate_cleanup(self, job: ContainerJob) -> None:
        """Immediately cleanup container if configured"""
        from ..defaults import get_container_manager_setting

        immediate_cleanup = get_container_manager_setting("IMMEDIATE_CLEANUP", True)

        execution_id = job.get_execution_identifier()
        if immediate_cleanup and execution_id:
            self.cleanup(execution_id)

    def _strip_docker_timestamps(self, log_text: str) -> str:
        """Remove Docker timestamps from log text"""
        if not log_text:
            return ""

        lines = log_text.split("\n")
        clean_lines = []

        # Docker timestamp pattern: 2024-01-26T10:30:45.123456789Z
        import re

        timestamp_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*")

        for line in lines:
            # Remove timestamp prefix
            clean_line = timestamp_pattern.sub("", line)
            if clean_line.strip():  # Only add non-empty lines
                clean_lines.append(clean_line)

        return "\n".join(clean_lines)

    def _calculate_cpu_percent(self, stats: dict[str, Any]) -> float:
        """Calculate CPU usage percentage from Docker stats"""
        try:
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})

            cpu_usage = cpu_stats.get("cpu_usage", {})
            precpu_usage = precpu_stats.get("cpu_usage", {})

            cpu_delta = cpu_usage.get("total_usage", 0) - precpu_usage.get(
                "total_usage", 0
            )
            system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get(
                "system_cpu_usage", 0
            )

            if system_delta > 0 and cpu_delta > 0:
                cpu_count = cpu_stats.get("online_cpus", 1)
                return (cpu_delta / system_delta) * cpu_count * 100.0

            return 0.0
        except Exception:
            return 0.0
