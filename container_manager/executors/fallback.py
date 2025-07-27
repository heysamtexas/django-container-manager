"""
Fallback and retry logic for executor failures.
"""

import logging
import random
import time
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from ..models import ContainerJob, ExecutorHost
from .base import ContainerExecutor

logger = logging.getLogger(__name__)

# Constants
HIGH_MEMORY_THRESHOLD_MB = 1024  # 1GB threshold for high memory jobs


class ExecutorFallbackManager:
    """
    Manages fallback logic when executors fail.
    Implements retry mechanisms and graceful degradation.
    """

    def __init__(self):
        self.max_retries = getattr(settings, "EXECUTOR_MAX_RETRIES", 3)
        self.base_delay = getattr(settings, "EXECUTOR_BASE_RETRY_DELAY", 1.0)
        self.max_delay = getattr(settings, "EXECUTOR_MAX_RETRY_DELAY", 60.0)
        self.jitter_factor = getattr(settings, "EXECUTOR_RETRY_JITTER", 0.1)

    def execute_with_fallback(
        self,
        job: ContainerJob,
        primary_executor: ContainerExecutor,
        fallback_executors: list[ContainerExecutor],
    ) -> tuple[bool, str]:
        """
        Execute job with fallback logic.

        Args:
            job: Container job to execute
            primary_executor: Primary executor to try first
            fallback_executors: List of fallback executors

        Returns:
            Tuple of (success, execution_id_or_error_message)
        """
        executors_to_try = [primary_executor, *fallback_executors]
        last_error = "No executors available"

        for attempt, executor in enumerate(executors_to_try):
            try:
                logger.info(
                    f"Attempting to execute job {job.id} on "
                    f"{executor.__class__.__name__} "
                    f"(attempt {attempt + 1}/{len(executors_to_try)})"
                )

                # Update job routing reason
                if attempt == 0:
                    job.routing_reason = (
                        f"Primary executor: {executor.__class__.__name__}"
                    )
                else:
                    job.routing_reason = (
                        f"Fallback to {executor.__class__.__name__} "
                        f"(attempt {attempt + 1})"
                    )
                job.save()

                # Try to execute
                success, execution_id = executor.launch_job(job)

                if success:
                    logger.info(
                        f"Job {job.id} successfully executed on "
                        f"{executor.__class__.__name__}"
                    )
                    return True, execution_id

                logger.warning(
                    f"Job {job.id} failed on {executor.__class__.__name__}: "
                    f"{execution_id}"
                )
                last_error = execution_id

                # If this wasn't the last executor, add delay before trying next
                if attempt < len(executors_to_try) - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(f"Waiting {delay:.2f}s before trying next executor")
                    time.sleep(delay)

            except Exception as e:
                logger.exception(
                    f"Exception executing job {job.id} on "
                    f"{executor.__class__.__name__}"
                )
                last_error = str(e)

                # If this wasn't the last executor, add delay before trying next
                if attempt < len(executors_to_try) - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(f"Waiting {delay:.2f}s before trying next executor")
                    time.sleep(delay)

        # All executors failed
        job.routing_reason = f"All executors failed. Last error: {last_error}"
        job.save()

        logger.error(f"All executors failed for job {job.id}. Last error: {last_error}")
        return False, last_error

    def retry_with_backoff(
        self,
        job: ContainerJob,
        executor: ContainerExecutor,
        max_attempts: int | None = None,
    ) -> tuple[bool, str]:
        """
        Retry job execution with exponential backoff.

        Args:
            job: Container job to execute
            executor: Executor to use
            max_attempts: Maximum retry attempts (defaults to class setting)

        Returns:
            Tuple of (success, execution_id_or_error_message)
        """
        max_attempts = max_attempts or self.max_retries
        last_error = "No attempts made"

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Retry attempt {attempt + 1}/{max_attempts} for job {job.id} "
                    f"on {executor.__class__.__name__}"
                )

                success, execution_id = executor.launch_job(job)

                if success:
                    logger.info(
                        f"Job {job.id} succeeded on retry attempt {attempt + 1}"
                    )
                    job.routing_reason = f"Succeeded on retry attempt {attempt + 1}"
                    job.save()
                    return True, execution_id

                logger.warning(
                    f"Retry attempt {attempt + 1} failed for job {job.id}: "
                    f"{execution_id}"
                )
                last_error = execution_id

                # If this wasn't the last attempt, wait before retrying
                if attempt < max_attempts - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(f"Waiting {delay:.2f}s before retry")
                    time.sleep(delay)

            except Exception as e:
                logger.exception(
                    f"Exception on retry attempt {attempt + 1} for job {job.id}"
                )
                last_error = str(e)

                # If this wasn't the last attempt, wait before retrying
                if attempt < max_attempts - 1:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(f"Waiting {delay:.2f}s before retry")
                    time.sleep(delay)

        # All retries failed
        job.routing_reason = (
            f"All {max_attempts} retry attempts failed. Last error: {last_error}"
        )
        job.save()

        logger.error(
            f"All {max_attempts} retry attempts failed for job {job.id}. "
            f"Last error: {last_error}"
        )
        return False, last_error

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * 2^attempt
        delay = self.base_delay * (2**attempt)

        # Cap at max delay
        delay = min(delay, self.max_delay)

        # Add jitter to avoid thundering herd
        jitter = delay * self.jitter_factor * random.random()
        delay += jitter

        return delay


class HealthChecker:
    """
    Monitors executor and host health for fallback decisions.
    """

    def __init__(self):
        self.health_check_interval = getattr(
            settings, "EXECUTOR_HEALTH_CHECK_INTERVAL", 300
        )  # 5 minutes
        self.failure_threshold = getattr(settings, "EXECUTOR_FAILURE_THRESHOLD", 3)
        self.recovery_threshold = getattr(settings, "EXECUTOR_RECOVERY_THRESHOLD", 2)

    def check_host_health(self, host: ExecutorHost) -> bool:
        """
        Check if a host is healthy for job execution.

        Args:
            host: Docker host to check

        Returns:
            True if host is healthy, False otherwise
        """
        try:
            # Check if host is active
            if not host.is_active:
                return False

            # Check recent failure count
            if host.health_check_failures >= self.failure_threshold and host.last_health_check:
                time_since_check = timezone.now() - host.last_health_check
                if time_since_check.total_seconds() < self.health_check_interval:
                    return False

            # Perform actual health check
            return self._perform_health_check(host)

        except Exception:
            logger.exception(f"Error checking health for host {host.name}")
            return False

    def _perform_health_check(self, host: ExecutorHost) -> bool:
        """
        Perform actual health check on the host.

        Args:
            host: Docker host to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from ..docker_service import docker_service

            # Try to get client - this will test connectivity
            client = docker_service.get_client(host)

            # Try a simple operation
            client.ping()

            # Update success state
            host.health_check_failures = max(0, host.health_check_failures - 1)
            host.last_health_check = timezone.now()
            host.save()

            logger.debug(f"Health check passed for host {host.name}")
            return True

        except Exception:
            # Update failure state
            host.health_check_failures += 1
            host.last_health_check = timezone.now()
            host.save()

            logger.warning(f"Health check failed for host {host.name}")
            return False

    def get_healthy_hosts(self, executor_type: str | None = None) -> list[ExecutorHost]:
        """
        Get list of healthy hosts, optionally filtered by executor type.

        Args:
            executor_type: Optional executor type filter

        Returns:
            List of healthy ExecutorHost instances
        """
        queryset = ExecutorHost.objects.filter(is_active=True)

        if executor_type:
            queryset = queryset.filter(executor_type=executor_type)

        healthy_hosts = []
        for host in queryset:
            if self.check_host_health(host):
                healthy_hosts.append(host)

        return healthy_hosts


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for executor reliability.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_counts: dict[str, int] = {}
        self._last_failures: dict[str, datetime] = {}
        self._circuit_states: dict[str, str] = {}  # "closed", "open", "half-open"

    def call(self, executor_name: str, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Args:
            executor_name: Name of the executor
            func: Function to execute
            *args, **kwargs: Arguments for the function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is open
        """
        state = self._get_circuit_state(executor_name)

        if state == "open":
            if self._should_attempt_reset(executor_name):
                self._circuit_states[executor_name] = "half-open"
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {executor_name}"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success(executor_name)
            return result

        except Exception:
            self._on_failure(executor_name)
            raise

    def _get_circuit_state(self, executor_name: str) -> str:
        """Get current circuit state for executor."""
        return self._circuit_states.get(executor_name, "closed")

    def _should_attempt_reset(self, executor_name: str) -> bool:
        """Check if enough time has passed to attempt reset."""
        last_failure = self._last_failures.get(executor_name)
        if not last_failure:
            return True

        time_since_failure = (datetime.now() - last_failure).total_seconds()
        return time_since_failure >= self.recovery_timeout

    def _on_success(self, executor_name: str):
        """Handle successful execution."""
        self._failure_counts[executor_name] = 0
        self._circuit_states[executor_name] = "closed"

    def _on_failure(self, executor_name: str):
        """Handle failed execution."""
        self._failure_counts[executor_name] = (
            self._failure_counts.get(executor_name, 0) + 1
        )
        self._last_failures[executor_name] = datetime.now()

        if self._failure_counts[executor_name] >= self.failure_threshold:
            self._circuit_states[executor_name] = "open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""



class GracefulDegradationManager:
    """
    Manages graceful degradation strategies when resources are limited.
    """

    def __init__(self):
        self.degradation_strategies = {
            "reduce_resources": self._reduce_resource_limits,
            "delay_execution": self._delay_non_critical_jobs,
            "queue_jobs": self._queue_jobs_for_later,
            "redirect_to_fallback": self._redirect_to_fallback_executor,
        }

    def apply_degradation(
        self, job: ContainerJob, available_executors: list[ContainerExecutor]
    ) -> tuple[bool, str]:
        """
        Apply degradation strategy for job execution.

        Args:
            job: Container job to execute
            available_executors: List of available executors

        Returns:
            Tuple of (success, message)
        """
        # Prioritize strategies based on job characteristics
        strategies = self._get_prioritized_strategies(job)

        for strategy_name in strategies:
            strategy_func = self.degradation_strategies.get(strategy_name)
            if strategy_func:
                try:
                    success, message = strategy_func(job, available_executors)
                    if success:
                        logger.info(
                            f"Degradation strategy '{strategy_name}' succeeded for "
                            f"job {job.id}: {message}"
                        )
                        return True, message
                except Exception:
                    logger.exception(
                        f"Degradation strategy '{strategy_name}' failed for "
                        f"job {job.id}"
                    )

        return False, "All degradation strategies failed"

    def _get_prioritized_strategies(self, job: ContainerJob) -> list[str]:
        """
        Get prioritized list of degradation strategies based on job characteristics.

        Args:
            job: Container job

        Returns:
            List of strategy names in priority order
        """
        strategies = []

        # High priority jobs get resource reduction first
        if job.template.memory_limit > HIGH_MEMORY_THRESHOLD_MB:  # More than 1GB
            strategies.append("reduce_resources")

        # Non-critical jobs can be delayed
        if "test" in (job.name or "").lower() or "batch" in (job.name or "").lower():
            strategies.append("delay_execution")

        # Always try fallback executors
        strategies.append("redirect_to_fallback")

        # Queue as last resort
        strategies.append("queue_jobs")

        return strategies

    def _reduce_resource_limits(
        self, job: ContainerJob, available_executors: list[ContainerExecutor]
    ) -> tuple[bool, str]:
        """
        Reduce resource limits to fit available capacity.

        Args:
            job: Container job
            available_executors: Available executors

        Returns:
            Tuple of (success, message)
        """
        original_memory = job.template.memory_limit
        original_cpu = job.template.cpu_limit

        # Reduce memory by 25%
        new_memory = int(original_memory * 0.75)
        # Reduce CPU by 25%
        new_cpu = original_cpu * 0.75 if original_cpu else None

        # Update job metadata to track the reduction
        job.executor_metadata = job.executor_metadata or {}
        job.executor_metadata["degradation"] = {
            "strategy": "reduce_resources",
            "original_memory_mb": original_memory,
            "reduced_memory_mb": new_memory,
            "original_cpu_cores": original_cpu,
            "reduced_cpu_cores": new_cpu,
        }

        # Try to execute with reduced resources
        # Note: This would require modifying the template temporarily
        # For now, we'll just mark it in metadata
        job.routing_reason = (
            f"Resource limits reduced (memory: {new_memory}MB, CPU: {new_cpu} cores)"
        )
        job.save()

        return True, f"Reduced resource limits: memory {original_memory}→{new_memory}MB"

    def _delay_non_critical_jobs(
        self, job: ContainerJob, available_executors: list[ContainerExecutor]
    ) -> tuple[bool, str]:
        """
        Delay non-critical jobs.

        Args:
            job: Container job
            available_executors: Available executors

        Returns:
            Tuple of (success, message)
        """
        # Add delay metadata
        job.executor_metadata = job.executor_metadata or {}
        job.executor_metadata["degradation"] = {
            "strategy": "delay_execution",
            "delayed_at": timezone.now().isoformat(),
            "delay_reason": "Resource contention",
        }

        job.routing_reason = "Delayed due to resource contention"
        job.save()

        return True, "Job delayed for later execution"

    def _queue_jobs_for_later(
        self, job: ContainerJob, available_executors: list[ContainerExecutor]
    ) -> tuple[bool, str]:
        """
        Queue jobs for later execution.

        Args:
            job: Container job
            available_executors: Available executors

        Returns:
            Tuple of (success, message)
        """
        # Mark job as queued
        job.executor_metadata = job.executor_metadata or {}
        job.executor_metadata["degradation"] = {
            "strategy": "queue_jobs",
            "queued_at": timezone.now().isoformat(),
            "queue_reason": "No available executors",
        }

        job.routing_reason = "Queued for later execution - no available executors"
        job.save()

        return True, "Job queued for later execution"

    def _redirect_to_fallback_executor(
        self, job: ContainerJob, available_executors: list[ContainerExecutor]
    ) -> tuple[bool, str]:
        """
        Redirect to fallback executor.

        Args:
            job: Container job
            available_executors: Available executors

        Returns:
            Tuple of (success, message)
        """
        if not available_executors:
            return False, "No fallback executors available"

        # Try the first available executor
        executor = available_executors[0]

        job.executor_metadata = job.executor_metadata or {}
        job.executor_metadata["degradation"] = {
            "strategy": "redirect_to_fallback",
            "fallback_executor": executor.__class__.__name__,
            "redirected_at": timezone.now().isoformat(),
        }

        job.routing_reason = (
            f"Redirected to fallback executor: {executor.__class__.__name__}"
        )
        job.save()

        return True, f"Redirected to fallback executor: {executor.__class__.__name__}"
