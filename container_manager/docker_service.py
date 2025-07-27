"""
Docker integration service for managing container lifecycle across multiple hosts.

BACKWARD COMPATIBILITY LAYER - This module maintains the original DockerService
interface while delegating to the new DockerExecutor implementation.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, Generator, Optional

import docker
from django.utils import timezone as django_timezone
from docker.errors import NotFound

from .executors.docker import DockerExecutor
from .executors.exceptions import ExecutorConnectionError, ExecutorError
from .models import ContainerJob, DockerHost

logger = logging.getLogger(__name__)


# Maintain backward compatibility with existing exception names
class DockerConnectionError(ExecutorConnectionError):
    """Raised when unable to connect to Docker host - legacy alias"""

    pass


class ContainerExecutionError(ExecutorError):
    """Raised when container execution fails - legacy alias"""

    pass


class DockerService:
    """
    Backward compatibility wrapper around DockerExecutor.

    This service maintains the original interface while delegating
    to the new executor-based architecture.
    """

    def __init__(self):
        self._executors: Dict[str, DockerExecutor] = {}

    def _get_executor(self, docker_host: DockerHost) -> DockerExecutor:
        """Get or create DockerExecutor for host"""
        host_key = f"{docker_host.id}"

        if host_key not in self._executors:
            config = {"docker_host": docker_host}
            self._executors[host_key] = DockerExecutor(config)

        return self._executors[host_key]

    def _should_auto_pull_images(self, docker_host: DockerHost) -> bool:
        """Determine if images should be auto-pulled for this host"""
        executor = self._get_executor(docker_host)
        return executor._should_pull_image(docker_host)

    def _build_container_labels(self, job: ContainerJob) -> dict:
        """Build comprehensive labels for container discovery and management"""
        executor = self._get_executor(job.docker_host)
        return executor._build_labels(job)

    def get_client(self, docker_host: DockerHost) -> docker.DockerClient:
        """Get Docker client for host - delegates to executor"""
        try:
            executor = self._get_executor(docker_host)
            return executor._get_client(docker_host)
        except ExecutorConnectionError as e:
            raise DockerConnectionError(str(e))

    def create_container(
        self, job: ContainerJob, environment: Optional[Dict] = None
    ) -> str:
        """Create a container for the given job - legacy interface"""
        try:
            executor = self._get_executor(job.docker_host)
            return executor._create_container(job)
        except ExecutorError as e:
            raise ContainerExecutionError(str(e))

    def start_container(self, job: ContainerJob) -> bool:
        """Start a container for the given job - legacy interface"""
        if not job.container_id:
            raise ContainerExecutionError("No container ID found for job")

        try:
            executor = self._get_executor(job.docker_host)
            return executor._start_container(job, job.container_id)
        except ExecutorError as e:
            logger.exception(f"Failed to start container for job {job.id}: {e}")
            job.status = "failed"
            job.save()
            return False

    def stop_container(self, job: ContainerJob, timeout: int = 10) -> bool:
        """Stop a running container"""
        if not job.container_id:
            return False

        try:
            client = self.get_client(job.docker_host)
            container = client.containers.get(job.container_id)
            container.stop(timeout=timeout)

            logger.info(f"Stopped container {job.container_id} for job {job.id}")
            return True

        except NotFound:
            logger.warning(f"Container {job.container_id} not found")
            return False
        except Exception as e:
            logger.exception(f"Failed to stop container for job {job.id}: {e}")
            return False

    def remove_container(self, job: ContainerJob, force: bool = False) -> bool:
        """Remove a container"""
        if not job.container_id:
            return False

        try:
            executor = self._get_executor(job.docker_host)
            return executor.cleanup(job.container_id)
        except Exception as e:
            logger.exception(f"Failed to remove container for job {job.id}: {e}")
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
            logger.exception(f"Failed to get logs for job {job.id}: {e}")
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
            logger.exception(f"Failed to get stats for job {job.id}: {e}")
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
            logger.exception(f"Failed to wait for container {job.id}: {e}")
            return None

    def _collect_execution_data(self, job: ContainerJob):
        """Collect execution logs and statistics - delegates to executor"""
        try:
            executor = self._get_executor(job.docker_host)
            executor._collect_data(job)
        except Exception as e:
            logger.exception(f"Failed to collect execution data for job {job.id}: {e}")

    def _cleanup_container_after_execution(self, job: ContainerJob):
        """Remove container immediately after execution data is collected"""
        try:
            executor = self._get_executor(job.docker_host)
            executor._immediate_cleanup(job)
        except Exception as e:
            logger.exception(f"Failed to cleanup container for job {job.id}: {e}")

    def launch_job(self, job: ContainerJob) -> bool:
        """Launch a job container in the background (non-blocking)"""
        try:
            executor = self._get_executor(job.docker_host)
            success, execution_id = executor.launch_job(job)

            if success:
                # The executor already updated the job with container_id
                logger.info(f"Launched job {job.id} as container {execution_id}")
                return True
            else:
                logger.error(f"Failed to launch job {job.id}: {execution_id}")
                return False

        except Exception as e:
            logger.exception(f"Failed to launch job {job.id}: {e}")
            job.status = "failed"
            job.completed_at = django_timezone.now()
            job.save()
            return False

    def discover_running_containers(self, docker_host: DockerHost) -> list:
        """Discover all running containers managed by this system"""
        try:
            client = self.get_client(docker_host)
            containers = client.containers.list(
                filters={"label": "django.container_manager.job_id"}
            )
            return containers

        except Exception as e:
            logger.exception(f"Failed to discover containers on {docker_host.name}: {e}")
            return []

    def check_container_status(self, job: ContainerJob) -> str:
        """Check the current status of a job's container"""
        if not job.container_id:
            return "no-container"

        try:
            executor = self._get_executor(job.docker_host)
            status = executor.check_status(job.container_id)

            # Map executor statuses to legacy statuses for compatibility
            if status == "not-found":
                return "not-found"
            elif status == "failed":
                return "error"
            else:
                return status

        except Exception as e:
            logger.exception(f"Failed to check container status for job {job.id}: {e}")
            return "error"

    def harvest_completed_job(self, job: ContainerJob) -> bool:
        """Harvest results from a completed job"""
        try:
            executor = self._get_executor(job.docker_host)
            return executor.harvest_job(job)
        except Exception as e:
            logger.exception(f"Failed to harvest job {job.id}: {e}")
            return False

    def cleanup_old_containers(self, orphaned_hours: int = 24) -> int:
        """Cleanup old containers based on age"""
        total_cleaned = 0

        # Get cutoff time
        cutoff_time = django_timezone.now() - timedelta(hours=orphaned_hours)

        # Find orphaned containers
        orphaned_jobs = ContainerJob.objects.filter(
            completed_at__lt=cutoff_time,
            status__in=["completed", "failed", "timeout", "cancelled"],
        ).exclude(container_id="")

        logger.info(f"Found {orphaned_jobs.count()} orphaned containers to clean")

        for job in orphaned_jobs:
            if job.container_id:
                try:
                    executor = self._get_executor(job.docker_host)
                    if executor.cleanup(job.container_id):
                        # Clear container_id to mark as cleaned
                        job.container_id = ""
                        job.save(update_fields=["container_id"])
                        total_cleaned += 1
                        logger.debug(f"Cleaned up container for job {job.id}")

                except Exception as e:
                    logger.exception(f"Failed to cleanup container for job {job.id}: {e}")

        logger.info(f"Cleaned up {total_cleaned} orphaned containers")
        return total_cleaned


# Global instance for backward compatibility
docker_service = DockerService()
