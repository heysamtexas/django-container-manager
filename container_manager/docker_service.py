"""
Docker integration service for managing container lifecycle across multiple hosts.
"""

import logging
import time
from datetime import timedelta
from typing import Any, Dict, Generator, Optional

import docker
from django.conf import settings
from django.utils import timezone as django_timezone
from docker.errors import NotFound

from .models import ContainerExecution, ContainerJob, DockerHost

logger = logging.getLogger(__name__)


class DockerConnectionError(Exception):
    """Raised when unable to connect to Docker host"""

    pass


class ContainerExecutionError(Exception):
    """Raised when container execution fails"""

    pass


class DockerService:
    """Service for managing Docker containers across multiple hosts"""

    def __init__(self):
        self._clients: Dict[str, docker.DockerClient] = {}

    def _should_auto_pull_images(self, docker_host: DockerHost) -> bool:
        """Determine if images should be auto-pulled for this host"""
        # Check host-specific setting first
        if hasattr(docker_host, "auto_pull_images"):
            return docker_host.auto_pull_images

        # Fall back to global setting
        container_settings = getattr(settings, "CONTAINER_MANAGER", {})
        return container_settings.get("AUTO_PULL_IMAGES", True)

    def _build_container_labels(self, job: ContainerJob) -> dict:
        """Build comprehensive labels for container discovery and management"""
        template = job.template

        labels = {
            # Core identification
            "django-container-manager.job-id": str(job.id),
            "django-container-manager.template": template.name,
            "django-container-manager.image": template.docker_image,
            # Status and lifecycle
            "django-container-manager.status": "running",
            "django-container-manager.created-at": job.created_at.isoformat(),
            # Resource and timeout info
            "django-container-manager.timeout": str(template.timeout_seconds),
            "django-container-manager.host": job.docker_host.name,
        }

        # Add memory limit if set
        if template.memory_limit:
            labels["django-container-manager.memory-limit"] = (
                f"{template.memory_limit}m"
            )

        # Add CPU limit if set
        if template.cpu_limit:
            labels["django-container-manager.cpu-limit"] = str(template.cpu_limit)

        # Add user info if available
        if job.created_by:
            labels["django-container-manager.user"] = job.created_by.username

        # Add job name if set
        if job.name:
            labels["django-container-manager.job-name"] = job.name

        return labels

    def get_client(self, docker_host: DockerHost) -> docker.DockerClient:
        """Get or create a Docker client for the given host"""
        cache_key = f"{docker_host.id}_{docker_host.updated_at.isoformat()}"

        if cache_key in self._clients:
            return self._clients[cache_key]

        try:
            if docker_host.host_type == "tcp":
                client = docker.DockerClient(
                    base_url=docker_host.connection_string,
                    tls=docker_host.tls_enabled,
                    use_ssh_client=False,
                )
            else:  # unix socket
                client = docker.DockerClient(base_url=docker_host.connection_string)

            # Test connection
            client.ping()

            # Cache the client
            self._clients[cache_key] = client
            logger.info(f"Connected to Docker host: {docker_host.name}")

            return client

        except Exception as e:
            logger.error(f"Failed to connect to Docker host {docker_host.name}: {e}")
            raise DockerConnectionError(f"Cannot connect to {docker_host.name}: {e}")

    def create_container(
        self, job: ContainerJob, environment: Optional[Dict[str, str]] = None
    ) -> str:
        """Create a container for the given job"""
        client = self.get_client(job.docker_host)
        template = job.template

        # Build environment variables
        env_vars = {}

        # Add template environment variables
        for env_var in template.environment_variables.all():
            env_vars[env_var.key] = env_var.value

        # Add job override environment variables
        if job.override_environment:
            env_vars.update(job.override_environment)

        # Add any additional environment variables
        if environment:
            env_vars.update(environment)

        # Determine command to run
        command = job.override_command or template.command or None

        # Build comprehensive labels for container discovery and management
        labels = self._build_container_labels(job)

        # Build container configuration
        container_config = {
            "image": template.docker_image,
            "name": f"job_{job.id}_{int(time.time())}",
            "environment": env_vars,
            "detach": True,
            "auto_remove": False,  # Never auto-remove, use cleanup process instead
            "labels": labels,
        }

        # Add command if specified
        if command:
            container_config["command"] = command

        # Add working directory if specified
        if template.working_directory:
            container_config["working_dir"] = template.working_directory

        # Add resource limits (using high-level client parameters)
        if template.memory_limit:
            container_config["mem_limit"] = f"{template.memory_limit}m"

        if template.cpu_limit:
            # For high-level client, use nano_cpus (1 CPU = 1e9 nano CPUs)
            container_config["nano_cpus"] = int(template.cpu_limit * 1e9)

        # Add network configuration
        networks = []
        for network_assignment in template.network_assignments.all():
            networks.append(network_assignment.network_name)

        if networks:
            container_config["network"] = networks[0]  # Primary network

        try:
            # Check if we should auto-pull images
            should_auto_pull = self._should_auto_pull_images(job.docker_host)

            # Check if image exists locally
            try:
                client.images.get(template.docker_image)
                logger.debug(f"Image {template.docker_image} already exists locally")
            except NotFound:
                if should_auto_pull:
                    logger.info(f"Pulling image {template.docker_image}...")
                    client.images.pull(template.docker_image)
                    logger.info(f"Successfully pulled image {template.docker_image}")
                else:
                    raise ContainerExecutionError(
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
            raise ContainerExecutionError(f"Container creation failed: {e}")

    def start_container(self, job: ContainerJob) -> bool:
        """Start a container for the given job"""
        if not job.container_id:
            raise ContainerExecutionError("No container ID found for job")

        client = self.get_client(job.docker_host)

        try:
            container = client.containers.get(job.container_id)
            container.start()

            # Update job status
            job.status = "running"
            job.started_at = django_timezone.now()
            job.save()

            # Create execution record
            ContainerExecution.objects.get_or_create(job=job)

            logger.info(f"Started container {job.container_id} for job {job.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start container for job {job.id}: {e}")
            job.status = "failed"
            job.save()
            raise ContainerExecutionError(f"Container start failed: {e}")

    def stop_container(self, job: ContainerJob, timeout: int = 10) -> bool:
        """Stop a running container"""
        if not job.container_id:
            return False

        client = self.get_client(job.docker_host)

        try:
            container = client.containers.get(job.container_id)
            container.stop(timeout=timeout)

            logger.info(f"Stopped container {job.container_id} for job {job.id}")
            return True

        except NotFound:
            logger.warning(f"Container {job.container_id} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to stop container for job {job.id}: {e}")
            return False

    def remove_container(self, job: ContainerJob, force: bool = False) -> bool:
        """Remove a container"""
        if not job.container_id:
            return False

        client = self.get_client(job.docker_host)

        try:
            container = client.containers.get(job.container_id)
            container.remove(force=force)

            logger.info(f"Removed container {job.container_id} for job {job.id}")
            return True

        except NotFound:
            logger.warning(f"Container {job.container_id} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to remove container for job {job.id}: {e}")
            return False

    def get_container_logs(
        self, job: ContainerJob, follow: bool = False, tail: str = "all"
    ) -> Generator[str, None, None]:
        """Get container logs, optionally following them"""
        if not job.container_id:
            return

        client = self.get_client(job.docker_host)

        try:
            container = client.containers.get(job.container_id)

            logs = container.logs(
                stream=follow, follow=follow, tail=tail, timestamps=True
            )

            # Handle different return types from logs()
            if follow:
                # Streaming mode returns a generator of bytes
                for log_line in logs:
                    if isinstance(log_line, bytes):
                        yield log_line.decode("utf-8", errors="replace")
                    else:
                        yield str(log_line)
            else:
                # Non-streaming mode returns bytes directly
                if isinstance(logs, bytes):
                    yield logs.decode("utf-8", errors="replace")
                else:
                    yield str(logs)

        except NotFound:
            logger.warning(f"Container {job.container_id} not found")
            return
        except Exception as e:
            logger.error(f"Failed to get logs for job {job.id}: {e}")
            return

    def get_container_stats(self, job: ContainerJob) -> Optional[Dict[str, Any]]:
        """Get container resource usage statistics"""
        if not job.container_id:
            return None

        client = self.get_client(job.docker_host)

        try:
            container = client.containers.get(job.container_id)
            stats = container.stats(stream=False)
            return stats

        except NotFound:
            logger.warning(f"Container {job.container_id} not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get stats for job {job.id}: {e}")
            return None

    def wait_for_container(self, job: ContainerJob) -> Optional[int]:
        """Wait for container to complete and return exit code"""
        if not job.container_id:
            return None

        client = self.get_client(job.docker_host)

        try:
            container = client.containers.get(job.container_id)
            result = container.wait()

            exit_code = result["StatusCode"]

            # Update job
            job.exit_code = exit_code
            job.completed_at = django_timezone.now()
            job.status = "completed" if exit_code == 0 else "failed"
            job.save()

            # Collect final logs and stats
            self._collect_execution_data(job)

            logger.info(
                f"Container {job.container_id} completed with exit code {exit_code}"
            )
            return exit_code

        except NotFound:
            logger.warning(f"Container {job.container_id} not found")
            return None
        except Exception as e:
            logger.error(f"Failed to wait for container {job.id}: {e}")
            return None

    def _collect_execution_data(self, job: ContainerJob):
        """Collect execution logs and statistics"""
        try:
            execution, created = ContainerExecution.objects.get_or_create(job=job)

            # Collect logs
            stdout_logs = []
            stderr_logs = []

            for log_line in self.get_container_logs(job):
                if log_line.strip():
                    # Simple heuristic: assume stderr contains
                    # "error", "warning", "exception"
                    if any(
                        keyword in log_line.lower()
                        for keyword in ["error", "warning", "exception"]
                    ):
                        stderr_logs.append(log_line)
                    else:
                        stdout_logs.append(log_line)

            execution.stdout_log = "".join(stdout_logs)
            execution.stderr_log = "".join(stderr_logs)

            # Collect resource stats
            stats = self.get_container_stats(job)
            if stats:
                memory_stats = stats.get("memory_stats", {})
                cpu_stats = stats.get("cpu_stats", {})

                if "max_usage" in memory_stats:
                    execution.max_memory_usage = memory_stats["max_usage"]

                # Calculate CPU usage percentage (simplified)
                if "cpu_usage" in cpu_stats and "system_cpu_usage" in cpu_stats:
                    cpu_usage = cpu_stats["cpu_usage"].get("total_usage", 0)
                    system_usage = cpu_stats.get("system_cpu_usage", 0)
                    if system_usage > 0:
                        execution.cpu_usage_percent = (cpu_usage / system_usage) * 100

            execution.save()

            # Immediately remove container after collecting data
            self._cleanup_container_after_execution(job)

        except Exception as e:
            logger.error(f"Failed to collect execution data for job {job.id}: {e}")

    def _cleanup_container_after_execution(self, job: ContainerJob):
        """Remove container immediately after execution data is collected"""
        container_settings = getattr(settings, "CONTAINER_MANAGER", {})
        immediate_cleanup = container_settings.get("IMMEDIATE_CLEANUP", True)

        if not immediate_cleanup:
            logger.debug(f"Immediate cleanup disabled for job {job.id}")
            return

        if not job.container_id:
            return

        try:
            removed = self.remove_container(job, force=True)
            if removed:
                # Clear container_id to mark as cleaned
                job.container_id = ""
                job.save(update_fields=["container_id"])
                logger.info(
                    f"Immediately cleaned up container for completed job {job.id}"
                )
            else:
                logger.warning(f"Failed to remove container for job {job.id}")

        except Exception as e:
            logger.error(f"Failed to cleanup container for job {job.id}: {e}")

    def launch_job(self, job: ContainerJob) -> bool:
        """Launch a job container in the background (non-blocking)"""
        if job.status != "pending":
            logger.warning(f"Cannot launch job {job.id} in status {job.status}")
            return False

        try:
            # Create container
            container_id = self.create_container(job)
            if not container_id:
                return False

            job.container_id = container_id
            job.save()

            # Start container (non-blocking)
            success = self.start_container(job)
            if not success:
                return False

            logger.info(f"Launched job {job.id} as container {container_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to launch job {job.id}: {e}")
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False

    def discover_running_containers(self, docker_host: DockerHost) -> list:
        """Discover all running containers managed by this system"""
        try:
            client = self.get_client(docker_host)
            containers = client.containers.list(
                filters={"label": "django-container-manager.job-id"}
            )
            return containers

        except Exception as e:
            logger.error(f"Failed to discover containers on {docker_host.name}: {e}")
            return []

    def check_container_status(self, job: ContainerJob) -> str:
        """Check the current status of a job's container"""
        if not job.container_id:
            return "no-container"

        try:
            client = self.get_client(job.docker_host)
            container = client.containers.get(job.container_id)
            return container.status

        except NotFound:
            return "not-found"
        except Exception as e:
            logger.error(f"Failed to check container status for job {job.id}: {e}")
            return "error"

    def harvest_completed_job(self, job: ContainerJob) -> bool:
        """Collect logs and data from a completed container"""
        try:
            # Get final exit code
            exit_code = self.wait_for_container(job)

            # Update job status based on exit code
            if exit_code == 0:
                job.status = "completed"
            else:
                job.status = "failed"

            job.exit_code = exit_code
            job.completed_at = django_timezone.now()
            job.save()

            # Collect execution data and cleanup
            self._collect_execution_data(job)

            logger.info(f"Harvested job {job.id} with exit code {exit_code}")
            return True

        except Exception as e:
            logger.error(f"Failed to harvest job {job.id}: {e}")
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False

    def cleanup_old_containers(self, orphaned_hours: int = 24):
        """Clean up orphaned containers that weren't cleaned up immediately"""
        container_settings = getattr(settings, "CONTAINER_MANAGER", {})

        cleanup_enabled = container_settings.get("CLEANUP_ENABLED", True)
        if not cleanup_enabled:
            logger.info("Orphaned container cleanup is disabled in settings")
            return 0

        # Find jobs with containers that should have been cleaned but weren't
        # These are containers older than orphaned_hours that still have container_id
        cutoff_time = django_timezone.now() - timedelta(hours=orphaned_hours)

        orphaned_jobs = ContainerJob.objects.filter(
            completed_at__lt=cutoff_time,
            status__in=["completed", "failed", "timeout", "cancelled"],
        ).exclude(container_id="")

        cleaned_count = 0
        for job in orphaned_jobs:
            if job.container_id:
                try:
                    removed = self.remove_container(job, force=True)
                    if removed:
                        job.container_id = ""
                        job.save(update_fields=["container_id"])
                        cleaned_count += 1
                        logger.debug(f"Cleaned up orphaned container for job {job.id}")

                except Exception as e:
                    logger.warning(
                        f"Failed to cleanup orphaned container for job {job.id}: {e}"
                    )

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} orphaned containers")

        return cleaned_count


# Global instance
docker_service = DockerService()
