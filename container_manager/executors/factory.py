"""
ExecutorFactory for intelligent job routing and executor management.

This module provides centralized routing logic that determines which executor
should handle each job based on configuration rules, resource requirements,
and availability.
"""

import logging
from typing import Dict, List

from django.conf import settings
from django.core.cache import cache

from ..models import ContainerJob, DockerHost
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError, ExecutorResourceError

logger = logging.getLogger(__name__)


class ExecutorFactory:
    """Factory for creating and routing to appropriate container executors"""

    def __init__(self):
        self._executor_cache: Dict[str, ContainerExecutor] = {}
        self._routing_rules = self._load_routing_rules()
        self._executor_configs = self._load_executor_configs()

    def route_job(self, job: ContainerJob) -> str:
        """
        Determine the best executor type for a job.

        Args:
            job: ContainerJob to route

        Returns:
            str: Executor type ('docker', 'cloudrun', etc.)

        Raises:
            ExecutorResourceError: If no suitable executor available
        """
        # Check preferred executor first
        if job.preferred_executor:
            if self._is_executor_available(job.preferred_executor):
                logger.info(
                    f"Using preferred executor {job.preferred_executor} "
                    f"for job {job.id}"
                )
                job.routing_reason = f"Preferred executor: {job.preferred_executor}"
                return job.preferred_executor

            logger.warning(
                f"Preferred executor {job.preferred_executor} "
                f"not available for job {job.id}"
            )

        # Apply routing rules in order
        for rule in self._routing_rules:
            if self._evaluate_rule(rule, job):
                executor_type = rule['executor']
                if self._is_executor_available(executor_type):
                    reason = rule.get('reason', f'Matched rule: {rule["condition"]}')
                    job.routing_reason = reason
                    logger.info(
                        f"Routed job {job.id} to {executor_type}: {reason}"
                    )
                    return executor_type

                logger.debug(
                    f"Rule matched for job {job.id} but executor {executor_type} "
                    "not available"
                )

        # Default fallback to docker
        if self._is_executor_available('docker'):
            job.routing_reason = 'Default fallback to docker'
            logger.info(f"Using default docker executor for job {job.id}")
            return 'docker'

        # No executors available
        available_executors = self.get_available_executors()
        error_msg = (
            f"No suitable executors available for job {job.id}. "
            f"Available: {available_executors}"
        )
        logger.error(error_msg)
        raise ExecutorResourceError(error_msg)

    def get_executor(self, job: ContainerJob) -> ContainerExecutor:
        """
        Get executor instance for a job.

        Args:
            job: ContainerJob with executor_type set

        Returns:
            ContainerExecutor: Configured executor instance
        """
        executor_type = job.executor_type
        if not executor_type:
            raise ExecutorConfigurationError("Job must have executor_type set")

        # Check cache first
        cache_key = self._build_cache_key(executor_type, job)

        if cache_key in self._executor_cache:
            logger.debug(f"Using cached executor for {executor_type}")
            return self._executor_cache[cache_key]

        # Create new executor instance
        executor = self._create_executor(executor_type, job)
        self._executor_cache[cache_key] = executor

        logger.debug(f"Created new executor instance for {executor_type}")
        return executor

    def get_available_executors(self) -> List[str]:
        """Get list of currently available executor types"""
        available = []

        for executor_type in self._executor_configs.keys():
            if self._is_executor_available(executor_type):
                available.append(executor_type)

        return available

    def get_executor_capacity(self, executor_type: str) -> Dict[str, int]:
        """Get capacity information for executor type"""
        if executor_type == 'docker':
            hosts = DockerHost.objects.filter(
                executor_type='docker',
                is_active=True
            )

            total_capacity = sum(host.max_concurrent_jobs for host in hosts)
            current_usage = sum(host.current_job_count for host in hosts)

            return {
                'total_capacity': total_capacity,
                'current_usage': current_usage,
                'available_slots': total_capacity - current_usage,
            }

        # For cloud executors, capacity is typically unlimited or very high
        return {
            'total_capacity': 1000,  # Cloud services have high limits
            'current_usage': 0,      # We don't track cloud usage yet
            'available_slots': 1000,
        }

    def clear_cache(self) -> None:
        """Clear executor cache - useful for testing or config changes"""
        self._executor_cache.clear()
        logger.info("Cleared executor cache")

    def _build_cache_key(self, executor_type: str, job: ContainerJob) -> str:
        """Build cache key for executor instance"""
        if job.docker_host:
            return f"executor_{executor_type}_{job.docker_host.id}"
        return f"executor_{executor_type}_default"

    def _create_executor(
        self, executor_type: str, job: ContainerJob
    ) -> ContainerExecutor:
        """Create executor instance with appropriate configuration"""
        if executor_type not in self._executor_configs:
            raise ExecutorConfigurationError(f"Unknown executor type: {executor_type}")

        config = self._executor_configs[executor_type].copy()

        # Add job-specific configuration
        if job.docker_host:
            config['docker_host'] = job.docker_host

        # Import and instantiate executor
        if executor_type == 'docker':
            from .docker import DockerExecutor
            return DockerExecutor(config)

        if executor_type == 'cloudrun':
            # TODO: Implement CloudRunExecutor in future task
            raise ExecutorConfigurationError(
                "CloudRunExecutor not implemented yet"
            )

        if executor_type == 'fargate':
            # TODO: Implement FargateExecutor in future task
            raise ExecutorConfigurationError(
                "FargateExecutor not implemented yet"
            )

        if executor_type == 'mock':
            from .mock import MockExecutor
            return MockExecutor(config)

        raise ExecutorConfigurationError(
            f"Executor type {executor_type} not implemented"
        )

    def _is_executor_available(self, executor_type: str) -> bool:
        """Check if executor type is available for new jobs"""
        if executor_type not in self._executor_configs:
            return False

        config = self._executor_configs[executor_type]
        if not config.get('enabled', True):
            return False

        if executor_type == 'docker':
            # Check Docker host availability
            available_hosts = DockerHost.objects.filter(
                executor_type='docker',
                is_active=True
            )

            for host in available_hosts:
                if host.is_available():
                    return True
            return False

        # For cloud executors, check configuration and credentials
        return self._check_cloud_executor_health(executor_type)

    def _check_cloud_executor_health(self, executor_type: str) -> bool:
        """Check if cloud executor is healthy and accessible"""
        # Use cache to avoid frequent health checks
        cache_key = f"executor_health_{executor_type}"
        health_status = cache.get(cache_key)

        if health_status is not None:
            return health_status

        # For now, assume cloud executors are healthy if enabled
        # TODO: Add actual health check method to executor interface
        config = self._executor_configs.get(executor_type, {})
        health_status = config.get('enabled', False)

        # Cache result for 5 minutes
        cache.set(cache_key, health_status, 300)
        logger.debug(f"Health check for {executor_type}: {health_status}")
        return health_status

    def _evaluate_rule(self, rule: Dict, job: ContainerJob) -> bool:
        """Evaluate if a routing rule matches a job"""
        condition = rule.get('condition', '')
        if not condition:
            return False

        try:
            # Create evaluation context
            context = {
                'job': job,
                'template': job.template,
                'user': job.created_by,
                'memory_mb': job.template.memory_limit or 0,
                'cpu_cores': job.template.cpu_limit or 0,
                'timeout_seconds': job.template.timeout_seconds,
            }

            # Evaluate condition safely
            # Using eval with restricted globals for simplicity
            # TODO: Consider using a safer expression evaluator in production
            result = eval(condition, {"__builtins__": {}}, context)

            if result:
                logger.debug(f"Rule '{condition}' matched for job {job.id}")

            return bool(result)

        except Exception as e:
            logger.warning(f"Failed to evaluate routing rule '{condition}': {e}")
            return False

    def _load_routing_rules(self) -> List[Dict]:
        """Load routing rules from Django settings"""
        default_rules = [
            {
                'condition': 'memory_mb > 8192',
                'executor': 'fargate',
                'reason': 'High memory requirement (>8GB)',
                'priority': 1,
            },
            {
                'condition': 'cpu_cores > 4.0',
                'executor': 'fargate',
                'reason': 'High CPU requirement (>4 cores)',
                'priority': 2,
            },
            {
                'condition': 'timeout_seconds > 3600',
                'executor': 'cloudrun',
                'reason': 'Long-running job (>1 hour)',
                'priority': 3,
            },
            {
                'condition': 'template.name.startswith("batch-")',
                'executor': 'cloudrun',
                'reason': 'Batch processing template',
                'priority': 4,
            },
            {
                'condition': 'user and user.groups.filter(name="premium").exists()',
                'executor': 'cloudrun',
                'reason': 'Premium user priority',
                'priority': 5,
            },
            {
                'condition': 'template.name.startswith("test-")',
                'executor': 'mock',
                'reason': 'Test template',
                'priority': 6,
            }
        ]

        rules = getattr(settings, 'EXECUTOR_ROUTING_RULES', default_rules)

        # Sort rules by priority (lower number = higher priority)
        sorted_rules = sorted(rules, key=lambda r: r.get('priority', 999))

        logger.info(f"Loaded {len(sorted_rules)} routing rules")
        return sorted_rules

    def _load_executor_configs(self) -> Dict[str, Dict]:
        """Load executor configurations from Django settings"""
        default_configs = {
            'docker': {
                'enabled': True,
                'default': True,
            },
            'cloudrun': {
                'enabled': False,
                'project': 'my-project',
                'region': 'us-central1',
            },
            'fargate': {
                'enabled': False,
                'cluster': 'default',
            },
            'mock': {
                'enabled': True,
            }
        }

        configs = getattr(settings, 'CONTAINER_EXECUTORS', default_configs)
        logger.info(f"Loaded executor configs: {list(configs.keys())}")
        return configs


# Global factory instance
executor_factory = ExecutorFactory()

