"""
Abstract base class for container executors.

Defines the interface that all container execution backends must implement,
enabling a pluggable architecture for different execution environments.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ContainerExecutor(ABC):
    """Abstract interface for container execution backends"""

    def __init__(self, config: dict):
        """
        Initialize executor with configuration.

        Args:
            config: Dictionary containing executor-specific configuration
        """
        self.config = config
        self.name = self.__class__.__name__.replace("Executor", "").lower()

    @abstractmethod
    def launch_job(self, job) -> tuple[bool, str]:
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
                job.set_execution_identifier(execution_id)
                job.save()
            else:
                logger.error(f"Launch failed: {execution_id}")
        """

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

    @abstractmethod
    def get_logs(self, execution_id: str) -> tuple[str, str]:
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

    def get_capabilities(self) -> dict[str, bool]:
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

    def validate_job(self, job) -> tuple[bool, str]:
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
            return False, "Job is None"

        if not hasattr(job, "docker_image") or not job.docker_image:
            return False, "No docker_image"

        if not hasattr(job, "docker_host") or not job.docker_host:
            return False, "No docker_host"

        return True, ""

    def validate_job_for_execution(self, job) -> list[str]:
        """
        Validate job can be executed by this executor.

        This method performs comprehensive validation including executor-specific
        requirements that were previously scattered in model validation.

        Args:
            job: ContainerJob instance to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Common validations all executors need
        if not job:
            errors.append("Job is None")
            return errors

        # Template is optional - jobs can work without one

        if not job.docker_host:
            errors.append("Job must have a docker_host")

        # Check job status - only certain statuses are valid for launch
        valid_launch_statuses = ["pending", "created", "queued", "retrying"]
        if hasattr(job, "status") and job.status not in valid_launch_statuses:
            errors.append(
                f"Job status '{job.status}' is not valid for launch (must be one of: {', '.join(valid_launch_statuses)})"
            )

        # Executor type is now determined by docker_host.executor_type
        # No additional validation needed since docker_host is required and determines executor type

        # Let subclasses add executor-specific validations
        errors.extend(self._validate_executor_specific(job))
        return errors

    def _validate_executor_specific(self, job) -> list[str]:
        """
        Override in subclasses for executor-specific validation.

        Args:
            job: ContainerJob instance to validate

        Returns:
            List of executor-specific validation errors
        """
        return []

    def get_execution_display(self, job) -> dict[str, str]:
        """
        Get execution display information for this executor type.

        This method provides executor-specific display formatting that was
        previously scattered in model display methods.

        Args:
            job: ContainerJob instance

        Returns:
            Dict with display information containing:
            - type_name: Human-readable executor type name
            - id_label: Label for the execution identifier
            - id_value: Current execution identifier value
            - status_detail: Executor-specific status information
        """
        return {
            "type_name": f"{self.name.title()} Executor",
            "id_label": "Execution ID",
            "id_value": job.get_execution_identifier() or "Not assigned",
            "status_detail": self._get_status_detail(job),
        }

    def _get_status_detail(self, job) -> str:
        """
        Override in subclasses for executor-specific status details.

        Args:
            job: ContainerJob instance

        Returns:
            Executor-specific status detail string
        """
        return job.status.title()

    # estimate_cost method removed - deprecated cost tracking functionality

    # start_cost_tracking method removed - deprecated cost tracking functionality

    # update_resource_usage method removed - deprecated cost tracking functionality

    # finalize_cost_tracking method removed - deprecated cost tracking functionality

    def get_health_status(self) -> dict[str, any]:
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
