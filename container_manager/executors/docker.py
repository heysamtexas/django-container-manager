"""
Docker-based container executor implementation.

Implements the ContainerExecutor interface for Docker containers,
providing multi-host Docker support with comprehensive lifecycle management.
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple

import docker
from django.conf import settings
from django.utils import timezone as django_timezone
from docker.errors import NotFound

from ..models import ContainerExecution, ContainerJob, DockerHost
from .base import ContainerExecutor
from .exceptions import (
    ExecutorConnectionError,
    ExecutorError,
)

logger = logging.getLogger(__name__)


class DockerExecutor(ContainerExecutor):
    """Docker-based container executor"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self._clients: Dict[str, docker.DockerClient] = {}
        self.docker_host = config.get("docker_host")

    def launch_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """Launch a container job in the background"""
        try:
            # Validate job can be executed
            self._validate_job(job)

            # Create container
            container_id = self._create_container(job)
            if not container_id:
                return False, "Failed to create container"

            # Start container
            success = self._start_container(job, container_id)
            if not success:
                return False, "Failed to start container"

            return True, container_id

        except ExecutorError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error launching job {job.id}: {e}")
            return False, f"Unexpected error: {e}"

    def check_status(self, execution_id: str) -> str:
        """Check the status of a running execution"""
        if not execution_id:
            return "not-found"

        try:
            # Find the job associated with this execution_id (container_id)
            job = ContainerJob.objects.filter(container_id=execution_id).first()
            if not job:
                return "not-found"

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
            return "not-found"
        except Exception as e:
            logger.error(f"Error checking container status {execution_id}: {e}")
            return "failed"

    def get_logs(self, execution_id: str) -> Tuple[str, str]:
        """Retrieve logs from completed or running execution"""
        if not execution_id:
            return "", ""

        try:
            # Find the job associated with this execution_id
            job = ContainerJob.objects.filter(container_id=execution_id).first()
            if not job:
                return "", ""

            client = self._get_client(job.docker_host)
            container = client.containers.get(execution_id)

            # Get logs
            logs = container.logs(timestamps=True, stderr=True)
            if isinstance(logs, bytes):
                logs_str = logs.decode("utf-8", errors="replace")
            else:
                logs_str = str(logs)

            # For Docker, we get combined stdout/stderr, so split based on timestamps
            stdout_lines = []
            stderr_lines = []

            for line in logs_str.split("\n"):
                if line.strip():
                    # Simple heuristic to separate stderr from stdout
                    keywords = ["error", "warning", "exception", "traceback"]
                    if any(keyword in line.lower() for keyword in keywords):
                        stderr_lines.append(line)
                    else:
                        stdout_lines.append(line)

            stdout = "\n".join(stdout_lines) if stdout_lines else ""
            stderr = "\n".join(stderr_lines) if stderr_lines else ""

            return stdout, stderr

        except NotFound:
            return "", ""
        except Exception as e:
            logger.error(f"Error getting logs for {execution_id}: {e}")
            return "", ""

    def harvest_job(self, job: ContainerJob) -> bool:
        """Collect final results and update job status"""
        if not job.container_id:
            return False

        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(job.container_id)

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

            logger.info(f"Harvested job {job.id} with exit code {exit_code}")
            return True

        except NotFound:
            logger.warning(f"Container {job.container_id} not found during harvest")
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False
        except Exception as e:
            logger.error(f"Error harvesting job {job.id}: {e}")
            return False

    def cleanup(self, execution_id: str) -> bool:
        """Force cleanup of execution resources"""
        if not execution_id:
            return True

        try:
            # Find the job to get docker_host
            job = ContainerJob.objects.filter(container_id=execution_id).first()
            if not job:
                # Try to cleanup anyway with default client
                client = docker.from_env()
            else:
                client = self._get_client(job.docker_host)

            container = client.containers.get(execution_id)
            container.remove(force=True)

            logger.info(f"Cleaned up container {execution_id}")
            return True

        except NotFound:
            # Already cleaned up
            return True
        except Exception as e:
            logger.error(f"Error cleaning up container {execution_id}: {e}")
            return False

    def get_capabilities(self) -> Dict[str, bool]:
        """Return Docker executor capabilities"""
        return {
            "supports_resource_limits": True,
            "supports_networking": True,
            "supports_persistent_storage": True,
            "supports_secrets": False,
            "supports_gpu": True,
            "supports_scaling": False,
        }

    def validate_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """Validate that a job can be executed by Docker"""
        try:
            self._validate_job(job)
            return True, ""
        except ExecutorError as e:
            return False, str(e)

    def estimate_cost(self, job: ContainerJob) -> Optional[float]:
        """Docker doesn't have direct cost estimation"""
        return None

    def get_health_status(self) -> Dict[str, Any]:
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

    # Private helper methods

    def _validate_job(self, job: ContainerJob) -> None:
        """Validate job can be executed"""
        if not job:
            raise ExecutorError("Job cannot be None")

        if job.status != "pending":
            raise ExecutorError(f"Job must be pending, got {job.status}")

        if not job.template:
            raise ExecutorError("Job must have a template")

        if not job.docker_host:
            raise ExecutorError("Job must have a docker_host")

    def _get_client(self, docker_host: DockerHost) -> docker.DockerClient:
        """Get or create Docker client for host"""
        host_key = f"{docker_host.id}"

        if host_key in self._clients:
            try:
                # Test connection only if not in testing mode
                if not getattr(self, "_skip_ping_for_tests", False):
                    self._clients[host_key].ping()
                return self._clients[host_key]
            except Exception:
                # Remove stale client
                del self._clients[host_key]

        try:
            # Create new client based on host type
            if docker_host.host_type == "unix":
                client = docker.DockerClient(base_url=docker_host.connection_string)
            elif docker_host.host_type == "tcp":
                client_kwargs = {
                    "base_url": docker_host.connection_string,
                    "use_ssh_client": False,
                }

                if docker_host.tls_enabled:
                    client_kwargs["tls"] = True

                client = docker.DockerClient(**client_kwargs)
            else:
                raise ExecutorConnectionError(
                    f"Unsupported host type: {docker_host.host_type}"
                )

            # Test connection only if not in testing mode
            if not getattr(self, "_skip_ping_for_tests", False):
                client.ping()

            # Cache client
            self._clients[host_key] = client
            return client

        except Exception as e:
            raise ExecutorConnectionError(
                f"Cannot connect to Docker host {docker_host.name}: {e}"
            )

    def _create_container(self, job: ContainerJob) -> str:
        """Create Docker container for job"""
        client = self._get_client(job.docker_host)
        template = job.template

        # Build environment variables
        environment = {}

        # Add template environment variables
        for env_var in template.environment_variables.all():
            environment[env_var.key] = env_var.value

        # Add job override environment variables
        if job.override_environment:
            environment.update(job.override_environment)

        # Build container configuration
        container_config = {
            "image": template.docker_image,
            "command": job.override_command or template.command,
            "environment": environment,
            "labels": self._build_labels(job),
            "detach": True,
            "remove": False,  # We handle cleanup manually
        }

        # Add resource limits if specified
        if template.memory_limit:
            container_config["mem_limit"] = f"{template.memory_limit}m"

        if template.cpu_limit:
            container_config["cpu_quota"] = int(template.cpu_limit * 100000)
            container_config["cpu_period"] = 100000

        # Handle networking
        networks = []
        for network_assignment in template.network_assignments.all():
            networks.append(network_assignment.network_name)

        if networks:
            container_config["network"] = networks[0]

        try:
            # Check if image exists locally
            try:
                client.images.get(template.docker_image)
                logger.debug(f"Image {template.docker_image} already exists locally")
            except NotFound:
                if self._should_pull_image(job.docker_host):
                    logger.info(f"Pulling image {template.docker_image}...")
                    client.images.pull(template.docker_image)
                    logger.info(f"Successfully pulled image {template.docker_image}")
                else:
                    raise ExecutorError(
                        f"Image {template.docker_image} not found locally and "
                        "auto-pull is disabled"
                    )

            container = client.containers.create(**container_config)

            # Connect to additional networks
            if len(networks) > 1:
                for network_name in networks[1:]:
                    try:
                        network = client.networks.get(network_name)
                        network.connect(container)
                    except NotFound:
                        logger.warning(
                            f"Network {network_name} not found on "
                            f"{job.docker_host.name}"
                        )

            logger.info(f"Created container {container.id} for job {job.id}")
            return container.id

        except Exception as e:
            logger.error(f"Failed to create container for job {job.id}: {e}")
            raise ExecutorError(f"Container creation failed: {e}")

    def _start_container(self, job: ContainerJob, container_id: str) -> bool:
        """Start the created container"""
        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(container_id)
            container.start()

            # Update job status
            job.container_id = container_id
            job.status = "running"
            job.started_at = django_timezone.now()
            job.save()

            # Create execution record
            ContainerExecution.objects.get_or_create(job=job)

            logger.info(f"Started container {container_id} for job {job.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start container {container_id}: {e}")
            job.status = "failed"
            job.save()
            return False

    def _build_labels(self, job: ContainerJob) -> Dict[str, str]:
        """Build comprehensive labels for container discovery and management"""
        template = job.template

        labels = {
            # Django container management labels
            "django.container_manager.job_id": str(job.id),
            "django.container_manager.template_id": str(template.id),
            "django.container_manager.template_name": template.name,
            "django.container_manager.host_id": str(job.docker_host.id),
            "django.container_manager.host_name": job.docker_host.name,
            "django.container_manager.created_at": job.created_at.isoformat(),
            # Standard container labels
            "com.docker.compose.project": "django-container-manager",
            "com.docker.compose.service": template.name,
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

    def _should_pull_image(self, docker_host: DockerHost) -> bool:
        """Determine if images should be auto-pulled for this host"""
        # Check host-specific setting first
        if hasattr(docker_host, "auto_pull_images"):
            return docker_host.auto_pull_images

        # Fall back to global setting
        container_settings = getattr(settings, "CONTAINER_MANAGER", {})
        return container_settings.get("AUTO_PULL_IMAGES", True)

    def _collect_data(self, job: ContainerJob) -> None:
        """Collect execution logs and statistics"""
        if not job.container_id:
            return

        try:
            client = self._get_client(job.docker_host)
            container = client.containers.get(job.container_id)

            # Get or create execution record
            execution, created = ContainerExecution.objects.get_or_create(job=job)

            # Collect logs
            stdout, stderr = self.get_logs(job.container_id)
            execution.stdout_log = stdout
            execution.stderr_log = stderr

            # Clean output for downstream processing
            execution.clean_output = self._strip_docker_timestamps(stdout)

            # Collect resource statistics
            try:
                stats = container.stats(stream=False)
                if stats:
                    memory_usage = stats.get("memory_usage", {})
                    if memory_usage:
                        execution.max_memory_usage = memory_usage.get("max_usage", 0)

                    cpu_stats = stats.get("cpu_stats", {})
                    if cpu_stats:
                        execution.cpu_usage_percent = self._calculate_cpu_percent(stats)
            except Exception as e:
                logger.warning(f"Failed to collect stats for job {job.id}: {e}")

            execution.save()

        except Exception as e:
            logger.error(f"Failed to collect execution data for job {job.id}: {e}")

    def _immediate_cleanup(self, job: ContainerJob) -> None:
        """Immediately cleanup container if configured"""
        container_settings = getattr(settings, "CONTAINER_MANAGER", {})
        immediate_cleanup = container_settings.get("IMMEDIATE_CLEANUP", True)

        if immediate_cleanup and job.container_id:
            self.cleanup(job.container_id)

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

    def _calculate_cpu_percent(self, stats: Dict[str, Any]) -> float:
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
