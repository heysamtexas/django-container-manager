"""
ExecutorFactory for simple weight-based job routing.

This module provides simple routing logic that determines which executor
should handle each job based on configured weights.
"""

import logging
import random

from ..models import ContainerJob, ExecutorHost
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError, ExecutorResourceError

logger = logging.getLogger(__name__)


class ExecutorFactory:
    """Factory for creating and routing to appropriate container executors"""

    def __init__(self):
        self._executor_cache: dict[str, ContainerExecutor] = {}

    def route_job_to_executor_type(self, job: ContainerJob) -> str:
        """
        Route job to best executor type and update job with routing details.

        Args:
            job: ContainerJob to route

        Returns:
            str: Executor type to use
        """
        # Check for preferred executor first
        if job.preferred_executor and self._is_executor_available(
            job.preferred_executor
        ):
            job.routing_reason = f"Preferred executor: {job.preferred_executor}"
            job.save(update_fields=["routing_reason"])
            return job.preferred_executor

        # Use weight-based routing to get a host
        selected_host = self.route_job_to_host(job)
        if not selected_host:
            raise ExecutorResourceError("No available executors for job")

        # Update job with routing info
        job.docker_host = selected_host
        job.executor_type = selected_host.executor_type
        job.routing_reason = (
            "Default fallback to docker"
            if selected_host.executor_type == "docker"
            else f"Routed to {selected_host.executor_type}"
        )
        job.save(update_fields=["docker_host", "executor_type", "routing_reason"])

        return selected_host.executor_type

    def route_job(self, job: ContainerJob) -> ExecutorHost | None:
        """
        Route job to best host using weight-based routing.

        Args:
            job: ContainerJob to route

        Returns:
            ExecutorHost instance to use for execution, or None if none available
        """
        return self.route_job_to_host(job)

    def route_job_to_host(self, job: ContainerJob) -> ExecutorHost | None:
        """
        Original weight-based routing method that returns a ExecutorHost.
        """
        available_hosts = ExecutorHost.objects.filter(is_active=True)

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

        return selected_host

    def get_executor(self, docker_host_or_job) -> ContainerExecutor:
        """
        Get executor instance for a docker host.

        Args:
            docker_host_or_job: ExecutorHost instance or ContainerJob with docker_host

        Returns:
            ContainerExecutor: Configured executor instance
        """
        # Handle both DockerHost and ContainerJob inputs
        if hasattr(docker_host_or_job, "docker_host"):
            # It's a ContainerJob - use job's executor_type
            job = docker_host_or_job
            docker_host = job.docker_host
            if not docker_host:
                raise ExecutorConfigurationError("Job must have docker_host set")
            # Job must have its own executor_type set (not empty string)
            if not job.executor_type:
                raise ExecutorConfigurationError("Job must have executor_type set")
            executor_type = job.executor_type
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

    def route_job_dry_run(self, job: ContainerJob) -> str:
        """
        Perform dry run routing without saving job changes.

        Args:
            job: ContainerJob to route

        Returns:
            str: Executor type that would be selected
        """
        # Check for preferred executor first
        if job.preferred_executor and self._is_executor_available(
            job.preferred_executor
        ):
            return job.preferred_executor

        # Use weight-based routing to get a host
        selected_host = self.route_job_to_host(job)
        if not selected_host:
            raise ExecutorResourceError("No available executors for job")

        return selected_host.executor_type

    def get_available_executors(self) -> list[str]:
        """
        Get list of available executor types.

        Returns:
            List of executor type strings
        """
        executor_types = (
            ExecutorHost.objects.filter(is_active=True)
            .values_list("executor_type", flat=True)
            .distinct()
        )
        return list(executor_types)

    def get_executor_capacity(self, executor_type: str) -> dict:
        """
        Get capacity information for an executor type.

        Args:
            executor_type: Type of executor

        Returns:
            Dict with capacity information
        """
        hosts = ExecutorHost.objects.filter(executor_type=executor_type, is_active=True)

        if not hosts.exists():
            return {"total_capacity": 0, "current_usage": 0, "available_slots": 0}

        # For cloud executors, use large default capacity
        if executor_type in ["cloudrun", "fargate"]:
            return {"total_capacity": 1000, "current_usage": 0, "available_slots": 1000}

        # For Docker hosts, sum up the capacity
        total_capacity = sum(host.max_concurrent_jobs for host in hosts)
        current_usage = sum(host.current_job_count for host in hosts)

        return {
            "total_capacity": total_capacity,
            "current_usage": current_usage,
            "available_slots": max(0, total_capacity - current_usage),
        }

    def _is_executor_available(self, executor_type: str) -> bool:
        """
        Check if an executor type is available.

        Args:
            executor_type: Type of executor to check

        Returns:
            True if executor is available
        """
        hosts = ExecutorHost.objects.filter(executor_type=executor_type, is_active=True)

        return any(host.current_job_count < host.max_concurrent_jobs for host in hosts)

    def clear_cache(self):
        """Clear the executor cache."""
        self._executor_cache.clear()
