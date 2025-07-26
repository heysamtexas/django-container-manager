"""
ExecutorFactory for simple weight-based job routing.

This module provides simple routing logic that determines which executor
should handle each job based on configured weights.
"""

import logging
import random
from typing import Dict, Optional

from ..models import ContainerJob, DockerHost
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError

logger = logging.getLogger(__name__)


class ExecutorFactory:
    """Factory for creating and routing to appropriate container executors"""

    def __init__(self):
        self._executor_cache: Dict[str, ContainerExecutor] = {}

    def route_job(self, job: ContainerJob) -> Optional[DockerHost]:
        """
        Determine the best executor host for a job using weight-based routing.

        Args:
            job: ContainerJob to route

        Returns:
            DockerHost instance to use for execution, or None if none available
        """
        available_hosts = DockerHost.objects.filter(is_active=True)

        if not available_hosts.exists():
            logger.warning("No active executors available")
            return None

        # Weight-based selection
        total_weight = sum(host.weight for host in available_hosts)

        if total_weight == 0:
            # If all weights are 0, use random selection
            selected_host = random.choice(list(available_hosts))
        else:
            # Weighted random selection
            target = random.randint(1, total_weight)
            current = 0

            for host in available_hosts:
                current += host.weight
                if current >= target:
                    selected_host = host
                    break
            else:
                # Fallback to first host
                selected_host = available_hosts.first()

        logger.info(
            f"Job {job.id} routed to {selected_host.name} ({selected_host.executor_type}) "
            f"via weight-based routing (weight: {selected_host.weight})",
            extra={
                "job_id": str(job.id),
                "executor_type": selected_host.executor_type,
                "host_name": selected_host.name,
                "weight": selected_host.weight,
            },
        )

        return selected_host

    def get_executor(self, docker_host_or_job) -> ContainerExecutor:
        """
        Get executor instance for a docker host.

        Args:
            docker_host_or_job: DockerHost instance or ContainerJob with docker_host

        Returns:
            ContainerExecutor: Configured executor instance
        """
        # Handle both DockerHost and ContainerJob inputs
        if hasattr(docker_host_or_job, 'docker_host'):
            # It's a ContainerJob
            docker_host = docker_host_or_job.docker_host
            if not docker_host:
                raise ExecutorConfigurationError("Job must have docker_host set")
        else:
            # It's a DockerHost
            docker_host = docker_host_or_job

        executor_type = docker_host.executor_type
        cache_key = f"executor_{executor_type}_{docker_host.id}"

        # Check cache first
        if cache_key in self._executor_cache:
            logger.debug(f"Using cached executor for {executor_type}")
            return self._executor_cache[cache_key]

        # Create new executor instance
        executor = self._create_executor(docker_host)
        self._executor_cache[cache_key] = executor

        logger.debug(f"Created new executor instance for {executor_type}")
        return executor

    def _create_executor(self, docker_host: DockerHost) -> ContainerExecutor:
        """Create executor instance with appropriate configuration"""
        # Create configuration dict for the executor
        config = {
            "docker_host": docker_host,
            "executor_config": docker_host.executor_config,
        }

        if docker_host.executor_type == "docker":
            from .docker import DockerExecutor
            return DockerExecutor(config)

        elif docker_host.executor_type == "cloudrun":
            from .cloudrun import CloudRunExecutor
            return CloudRunExecutor(config)

        elif docker_host.executor_type == "mock":
            from .mock import MockExecutor
            return MockExecutor(config)

        else:
            raise ExecutorConfigurationError(
                f"Unknown executor type: {docker_host.executor_type}"
            )
