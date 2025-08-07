"""
Service layer for job management operations using executor polymorphism.

This module provides a clean service layer that uses executor polymorphism
instead of conditional logic based on executor types. This eliminates the
need for executor-specific logic scattered throughout models and views.
"""

import logging
from typing import TYPE_CHECKING

from .executors.factory import ExecutorFactory

if TYPE_CHECKING:
    from .models import ContainerJob, ExecutorHost

logger = logging.getLogger(__name__)


class JobManagementService:
    """
    Service layer for job operations using executor polymorphism.

    This service replaces executor-specific conditional logic throughout
    the codebase with clean polymorphic calls to executor instances.
    """

    def __init__(self, executor_factory: ExecutorFactory | None = None):
        """
        Initialize service with executor factory.

        Args:
            executor_factory: Factory for creating executor instances.
                             If None, creates a new default factory.
        """
        self.executor_factory = executor_factory or ExecutorFactory()

    def validate_job_for_execution(self, job: "ContainerJob") -> list[str]:
        """
        Validate job can be executed using executor polymorphism.

        This replaces the conditional validation logic that was previously
        scattered in the ContainerJob.clean() method.

        Args:
            job: ContainerJob instance to validate

        Returns:
            List of validation error messages (empty if valid)

        Example:
            errors = job_service.validate_job_for_execution(job)
            if errors:
                raise ValidationError(errors)
        """
        try:
            # Use polymorphic validation instead of conditionals
            executor = self.executor_factory.get_executor(job.docker_host)
            return executor.validate_job_for_execution(job)
        except Exception as e:
            logger.exception(f"Failed to validate job {job.id}")
            return [f"Validation failed: {e}"]

    def get_job_execution_details(self, job: "ContainerJob") -> dict[str, str]:
        """
        Get job execution details using executor polymorphism.

        This replaces the conditional display logic that was previously
        scattered in model display methods.

        Args:
            job: ContainerJob instance

        Returns:
            Dict with display information:
            - type_name: Human-readable executor type name
            - id_label: Label for the execution identifier
            - id_value: Current execution identifier value
            - status_detail: Executor-specific status information

        Example:
            details = job_service.get_job_execution_details(job)
            print(f"{details['type_name']}: {details['id_value']}")
        """
        try:
            # Use polymorphic display instead of conditionals
            executor = self.executor_factory.get_executor(job.docker_host)
            return executor.get_execution_display(job)
        except Exception as e:
            logger.exception(f"Failed to get execution details for job {job.id}")
            return {
                "type_name": "Unknown Executor",
                "id_label": "Execution ID",
                "id_value": job.get_execution_identifier() or "Not assigned",
                "status_detail": f"Error: {e}",
            }

    def prepare_job_for_launch(self, job: "ContainerJob") -> tuple[bool, list[str]]:
        """
        Prepare job for launch using executor polymorphism.

        This performs comprehensive validation and any executor-specific
        preparation needed before launching a job.

        Args:
            job: ContainerJob instance to prepare

        Returns:
            Tuple of (success: bool, errors: list[str])

        Example:
            success, errors = job_service.prepare_job_for_launch(job)
            if not success:
                for error in errors:
                    logger.error(f"Job preparation failed: {error}")
        """
        try:
            # Use executor-specific validation
            errors = self.validate_job_for_execution(job)
            if errors:
                return False, errors

            # Additional preparation can be added here
            return True, []

        except Exception as e:
            logger.exception(f"Failed to prepare job {job.id} for launch")
            return False, [f"Preparation failed: {e}"]

    def launch_job(self, job: "ContainerJob") -> dict[str, any]:
        """
        Launch a job using the appropriate executor.

        This is the unified interface for job launching that replaces
        mock methods in the queue system.

        Args:
            job: ContainerJob instance to launch

        Returns:
            dict: {
                'success': bool,
                'execution_id': str (if successful),
                'error': str (if failed)
            }

        Example:
            result = job_service.launch_job(job)
            if result['success']:
                job.set_execution_identifier(result['execution_id'])
                job.mark_as_running()
            else:
                logger.error(f"Launch failed: {result['error']}")
        """
        try:
            # Prepare job for launch (validation, etc.)
            success, errors = self.prepare_job_for_launch(job)
            if not success:
                return {
                    "success": False,
                    "error": f"Job preparation failed: {'; '.join(errors)}",
                }

            # Get appropriate executor
            executor = self.executor_factory.get_executor(job.docker_host)

            # Launch job using executor
            success, result = executor.launch_job(job)

            if success:
                # result is execution_id
                logger.info(
                    f"Successfully launched job {job.id} with execution_id: {result}"
                )
                return {"success": True, "execution_id": result}
            else:
                # result is error message
                logger.error(f"Failed to launch job {job.id}: {result}")
                return {"success": False, "error": result}

        except Exception as e:
            error_msg = f"Unexpected error launching job {job.id}: {e!s}"
            logger.exception(error_msg)
            return {"success": False, "error": error_msg}

    def check_job_status(self, job: "ContainerJob") -> dict[str, any]:
        """
        Check the status of a running job.

        Args:
            job: ContainerJob instance to check

        Returns:
            dict: {
                'status': str,  # 'running', 'exited', 'failed', 'not-found'
                'execution_id': str,
                'error': str (if applicable)
            }

        Example:
            result = job_service.check_job_status(job)
            if result['status'] == 'exited':
                # Job completed, harvest results
                harvest_result = job_service.harvest_job_results(job)
        """
        try:
            if not job.get_execution_identifier():
                return {
                    "status": "not-found",
                    "execution_id": None,
                    "error": "No execution identifier found",
                }

            # Get appropriate executor
            executor = self.executor_factory.get_executor(job.docker_host)

            # Check status using executor
            status = executor.check_status(job.get_execution_identifier())

            return {
                "status": status,
                "execution_id": job.get_execution_identifier(),
                "error": None,
            }

        except Exception as e:
            error_msg = f"Error checking status for job {job.id}: {e!s}"
            logger.exception(error_msg)
            return {
                "status": "not-found",
                "execution_id": job.get_execution_identifier(),
                "error": error_msg,
            }

    def harvest_job_results(self, job: "ContainerJob") -> dict[str, any]:
        """
        Harvest results from a completed job.

        Args:
            job: ContainerJob instance to harvest

        Returns:
            dict: {
                'success': bool,
                'status': str,  # Final job status
                'logs_collected': bool,
                'error': str (if applicable)
            }

        Example:
            result = job_service.harvest_job_results(job)
            if result['success']:
                logger.info(f"Job {job.id} harvested successfully")
        """
        try:
            if not job.get_execution_identifier():
                return {
                    "success": False,
                    "status": "unknown",
                    "logs_collected": False,
                    "error": "No execution identifier found",
                }

            # Get appropriate executor
            executor = self.executor_factory.get_executor(job.docker_host)

            # Harvest job results using executor
            success = executor.harvest_job(job)

            if success:
                logger.info(f"Successfully harvested results for job {job.id}")
                return {
                    "success": True,
                    "status": job.status,
                    "logs_collected": True,
                    "error": None,
                }
            else:
                logger.warning(f"Failed to harvest results for job {job.id}")
                return {
                    "success": False,
                    "status": job.status,
                    "logs_collected": False,
                    "error": "Harvesting failed",
                }

        except Exception as e:
            error_msg = f"Error harvesting results for job {job.id}: {e!s}"
            logger.exception(error_msg)
            return {
                "success": False,
                "status": "unknown",
                "logs_collected": False,
                "error": error_msg,
            }

    def cleanup_job_execution(self, job: "ContainerJob") -> dict[str, any]:
        """
        Clean up execution resources for a job.

        Args:
            job: ContainerJob instance to cleanup

        Returns:
            dict: {
                'success': bool,
                'error': str (if applicable)
            }

        Example:
            result = job_service.cleanup_job_execution(job)
            if not result['success']:
                logger.warning(f"Cleanup failed: {result['error']}")
        """
        try:
            if not job.get_execution_identifier():
                return {
                    "success": True,  # Nothing to cleanup
                    "error": None,
                }

            # Get appropriate executor
            executor = self.executor_factory.get_executor(job.docker_host)

            # Cleanup using executor
            success = executor.cleanup(job.get_execution_identifier())

            if success:
                logger.debug(
                    f"Successfully cleaned up execution resources for job {job.id}"
                )
                return {"success": True, "error": None}
            else:
                logger.warning(
                    f"Failed to cleanup execution resources for job {job.id}"
                )
                return {"success": False, "error": "Cleanup failed"}

        except Exception as e:
            error_msg = f"Error cleaning up job {job.id}: {e!s}"
            logger.exception(error_msg)
            return {"success": False, "error": error_msg}

    def get_host_display_info(self, host: "ExecutorHost") -> dict[str, str]:
        """
        Get host display information using executor polymorphism.

        This replaces the conditional display logic in ExecutorHost.get_display_name().

        Args:
            host: ExecutorHost instance

        Returns:
            Dict with host display information:
            - name: Host name
            - type_name: Human-readable executor type name
            - connection_info: Connection details appropriate for the executor type

        Example:
            info = job_service.get_host_display_info(host)
            display_name = f"{info['name']} ({info['type_name']})"
        """
        try:
            # Check if executor can be created (validates host configuration)
            self.executor_factory.get_executor(host)

            # Get executor-specific display name
            if host.executor_type == "docker":
                type_name = "Docker"
                connection_info = host.connection_string
            elif host.executor_type == "cloudrun":
                type_name = "Cloud Run"
                config = host.executor_config or {}
                region = config.get("region", "unknown")
                connection_info = f"Region: {region}"
            else:
                type_name = host.executor_type.title()
                connection_info = host.connection_string

            return {
                "name": host.name,
                "type_name": type_name,
                "connection_info": connection_info,
            }

        except Exception as e:
            logger.exception(f"Failed to get display info for host {host.id}")
            return {
                "name": host.name,
                "type_name": "Unknown",
                "connection_info": f"Error: {e}",
            }


class JobValidationService:
    """
    Specialized service for job validation operations.

    This service can be used when you only need validation functionality
    without the full job management service.
    """

    def __init__(self, executor_factory: ExecutorFactory | None = None):
        """Initialize validation service with executor factory."""
        self.job_service = JobManagementService(executor_factory)

    def validate_job(self, job: "ContainerJob") -> list[str]:
        """
        Validate job using executor polymorphism.

        Args:
            job: ContainerJob instance to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        return self.job_service.validate_job_for_execution(job)

    def is_job_valid(self, job: "ContainerJob") -> bool:
        """
        Check if job is valid for execution.

        Args:
            job: ContainerJob instance to check

        Returns:
            True if job is valid, False otherwise
        """
        errors = self.validate_job(job)
        return len(errors) == 0


# Convenient module-level instances for simple usage
_default_factory = ExecutorFactory()
job_service = JobManagementService(_default_factory)
job_validator = JobValidationService(_default_factory)


# Module-level convenience functions for easy import
def launch_job(job: "ContainerJob") -> dict[str, any]:
    """
    Module-level convenience function for launching jobs.

    This provides a simple import path for the queue manager and other
    components that need to launch jobs.

    Args:
        job: ContainerJob instance to launch

    Returns:
        dict: Launch result with 'success', 'execution_id', and 'error' keys

    Example:
        from container_manager.services import launch_job

        result = launch_job(job)
        if result['success']:
            job.set_execution_identifier(result['execution_id'])
            job.mark_as_running()
        else:
            logger.error(f"Launch failed: {result['error']}")
    """
    return job_service.launch_job(job)


def check_job_status(job: "ContainerJob") -> dict[str, any]:
    """
    Module-level convenience function for checking job status.

    Args:
        job: ContainerJob instance to check

    Returns:
        dict: Status result with 'status', 'execution_id', and 'error' keys
    """
    return job_service.check_job_status(job)


def harvest_job_results(job: "ContainerJob") -> dict[str, any]:
    """
    Module-level convenience function for harvesting job results.

    Args:
        job: ContainerJob instance to harvest

    Returns:
        dict: Harvest result with 'success', 'status', 'logs_collected', and 'error' keys
    """
    return job_service.harvest_job_results(job)


def cleanup_job_execution(job: "ContainerJob") -> dict[str, any]:
    """
    Module-level convenience function for cleaning up job execution resources.

    Args:
        job: ContainerJob instance to cleanup

    Returns:
        dict: Cleanup result with 'success' and 'error' keys
    """
    return job_service.cleanup_job_execution(job)
