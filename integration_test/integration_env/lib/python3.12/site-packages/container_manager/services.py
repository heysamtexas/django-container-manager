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
