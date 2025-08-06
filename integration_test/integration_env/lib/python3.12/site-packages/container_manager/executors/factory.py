"""
ExecutorProvider for creating executor instances.

This module provides executor instantiation and caching for different
executor types (Docker, CloudRun, Mock, etc.).
"""

import logging

from ..models import ExecutorHost
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError

logger = logging.getLogger(__name__)


class ExecutorProvider:
    """Provider for creating and caching container executor instances"""

    def __init__(self):
        self._executor_cache: dict[str, ContainerExecutor] = {}

    # Routing methods removed - jobs now have direct docker_host assignment

    def get_executor(self, docker_host_or_job) -> ContainerExecutor:
        """
        Get executor instance for a docker host.

        Args:
            docker_host_or_job: ExecutorHost instance or ContainerJob with docker_host

        Returns:
            ContainerExecutor: Configured executor instance
        """
        # Handle both ExecutorHost and ContainerJob inputs
        if hasattr(docker_host_or_job, "docker_host"):
            # It's a ContainerJob - get executor_type from docker_host
            job = docker_host_or_job
            docker_host = job.docker_host
            if not docker_host:
                raise ExecutorConfigurationError("Job must have docker_host set")
            executor_type = docker_host.executor_type
        else:
            # It's a ExecutorHost
            docker_host = docker_host_or_job
            executor_type = docker_host.executor_type
        cache_key = f"executor_{executor_type}_{docker_host.id}"

        # Check cache first
        if cache_key in self._executor_cache:
            logger.debug(f"Using cached executor for {executor_type}")
            return self._executor_cache[cache_key]

        # Create new executor instance
        executor = self._create_executor(docker_host, executor_type)
        self._executor_cache[cache_key] = executor

        logger.debug(f"Created new executor instance for {executor_type}")
        return executor

    def _create_executor(
        self, docker_host: ExecutorHost, executor_type: str
    ) -> ContainerExecutor:
        """Create executor instance with appropriate configuration"""
        # Create configuration dict for the executor
        config = {
            "docker_host": docker_host,
            "executor_config": docker_host.executor_config,
        }

        if executor_type == "docker":
            from .docker import DockerExecutor

            return DockerExecutor(config)

        elif executor_type == "cloudrun":
            from .cloudrun import CloudRunExecutor

            return CloudRunExecutor(config)

        elif executor_type == "mock":
            from .mock import MockExecutor

            return MockExecutor(config)

        else:
            raise ExecutorConfigurationError(f"Unknown executor type: {executor_type}")

    # Routing utility methods removed - no longer needed with direct host assignment

    def clear_cache(self):
        """Clear the executor cache."""
        self._executor_cache.clear()


# Backward compatibility alias
ExecutorFactory = ExecutorProvider
