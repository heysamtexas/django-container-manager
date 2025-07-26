"""
Abstract base class for container executors.

Defines the interface that all container execution backends must implement,
enabling a pluggable architecture for different execution environments.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple


class ContainerExecutor(ABC):
    """Abstract interface for container execution backends"""

    def __init__(self, config: Dict):
        """
        Initialize executor with configuration.

        Args:
            config: Dictionary containing executor-specific configuration
        """
        self.config = config
        self.name = self.__class__.__name__.replace("Executor", "").lower()

    @abstractmethod
    def launch_job(self, job) -> Tuple[bool, str]:
        """
        Launch a container job in the background.

        Args:
            job: ContainerJob instance to execute

        Returns:
            Tuple of (success: bool, execution_id_or_error: str)
            - If success=True, second value is the execution_id
            - If success=False, second value is the error message

        Example:
            success, execution_id = executor.launch_job(job)
            if success:
                job.external_execution_id = execution_id
                job.save()
            else:
                logger.error(f"Launch failed: {execution_id}")
        """
        pass

    @abstractmethod
    def check_status(self, execution_id: str) -> str:
        """
        Check the status of a running execution.

        Args:
            execution_id: Provider-specific execution identifier

        Returns:
            Status string: 'running', 'exited', 'failed', 'not-found'

        Example:
            status = executor.check_status(execution_id)
            if status == 'exited':
                # Job completed, harvest results
                executor.harvest_job(job)
        """
        pass

    @abstractmethod
    def get_logs(self, execution_id: str) -> Tuple[str, str]:
        """
        Retrieve logs from completed or running execution.

        Args:
            execution_id: Provider-specific execution identifier

        Returns:
            Tuple of (stdout: str, stderr: str)

        Example:
            stdout, stderr = executor.get_logs(execution_id)
            execution.stdout_log = stdout
            execution.stderr_log = stderr
        """
        pass

    @abstractmethod
    def harvest_job(self, job) -> bool:
        """
        Collect final results and update job status.

        This method should:
        1. Get final exit code
        2. Collect logs and resource usage
        3. Update job status (completed/failed)
        4. Clean up execution resources

        Args:
            job: ContainerJob instance to harvest

        Returns:
            bool: True if harvesting successful

        Example:
            if executor.harvest_job(job):
                logger.info(f"Job {job.id} harvested successfully")
            else:
                logger.error(f"Failed to harvest job {job.id}")
        """
        pass

    @abstractmethod
    def cleanup(self, execution_id: str) -> bool:
        """
        Force cleanup of execution resources.

        This method should remove any resources associated with the execution,
        such as containers, temporary storage, or cloud resources.

        Args:
            execution_id: Provider-specific execution identifier

        Returns:
            bool: True if cleanup successful

        Example:
            if not executor.cleanup(execution_id):
                logger.warning(f"Failed to cleanup {execution_id}")
        """
        pass

    def get_capabilities(self) -> Dict[str, bool]:
        """
        Return executor capabilities and features.

        Returns:
            Dict with capability flags indicating what features this executor supports

        Example:
            caps = executor.get_capabilities()
            if caps['supports_resource_limits']:
                # Can set memory/CPU limits
                pass
        """
        return {
            "supports_resource_limits": False,
            "supports_networking": False,
            "supports_persistent_storage": False,
            "supports_secrets": False,
            "supports_gpu": False,
            "supports_scaling": False,
        }

    def validate_job(self, job) -> Tuple[bool, str]:
        """
        Validate that a job can be executed by this executor.

        Args:
            job: ContainerJob instance to validate

        Returns:
            Tuple of (valid: bool, error_message: str)

        Example:
            valid, error = executor.validate_job(job)
            if not valid:
                logger.error(f"Job validation failed: {error}")
        """
        if not job:
            return False, "Job cannot be None"

        if not hasattr(job, "template") or not job.template:
            return False, "Job must have a template"

        if not hasattr(job, "docker_host") or not job.docker_host:
            return False, "Job must have a docker_host"

        return True, ""

    def estimate_cost(self, job) -> Optional[float]:
        """
        Estimate the cost of executing a job.

        Args:
            job: ContainerJob instance

        Returns:
            Estimated cost in USD, or None if not available

        Example:
            cost = executor.estimate_cost(job)
            if cost:
                job.estimated_cost = cost
        """
        return None

    def get_health_status(self) -> Dict[str, any]:
        """
        Get health status of the executor backend.

        Returns:
            Dict containing health information

        Example:
            health = executor.get_health_status()
            if not health['healthy']:
                logger.warning(f"Executor unhealthy: {health['error']}")
        """
        return {
            "healthy": True,
            "error": None,
            "last_check": None,
            "response_time": None,
        }

    def __str__(self) -> str:
        """String representation of executor"""
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        """Developer representation of executor"""
        return f"{self.__class__.__name__}(name='{self.name}', config={self.config})"
