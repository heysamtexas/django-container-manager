"""
Container executors package for multi-cloud container execution.

This package provides an abstraction layer over different container execution backends
including Docker, Google Cloud Run, AWS Fargate, and others.
"""

from .base import ContainerExecutor
from .exceptions import (
    ExecutorAuthenticationError,
    ExecutorConfigurationError,
    ExecutorConnectionError,
    ExecutorError,
    ExecutorResourceError,
    ExecutorTimeoutError,
)

__all__ = [
    "ContainerExecutor",
    "ExecutorAuthenticationError",
    "ExecutorConfigurationError",
    "ExecutorConnectionError",
    "ExecutorError",
    "ExecutorResourceError",
    "ExecutorTimeoutError",
    "get_executor",
]


def get_executor(executor_type: str, config: dict | None = None) -> ContainerExecutor:
    """
    Factory function to create executor instances.

    Args:
        executor_type: Type of executor ('docker', 'cloudrun', 'fargate', etc.)
        config: Optional configuration override

    Returns:
        ContainerExecutor instance

    Raises:
        ExecutorConfigurationError: If executor type unknown or config invalid

    Example:
        >>> executor = get_executor('docker', {'host': 'local'})
        >>> success, execution_id = executor.launch_job(job)
    """
    if not executor_type:
        raise ExecutorConfigurationError("executor_type cannot be empty")

    config = config or {}

    # Import executors locally to avoid circular imports
    if executor_type == "docker":
        from .docker import DockerExecutor

        return DockerExecutor(config)

    if executor_type == "cloudrun":
        from .cloudrun import CloudRunExecutor

        return CloudRunExecutor(config)

    if executor_type == "mock":
        from .mock import MockExecutor

        return MockExecutor(config)

    raise ExecutorConfigurationError(f"Unknown executor type: {executor_type}")
