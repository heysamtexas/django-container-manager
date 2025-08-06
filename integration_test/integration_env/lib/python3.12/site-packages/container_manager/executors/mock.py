"""
Mock executor for testing and development purposes.

This executor simulates container execution without actually running containers,
making it useful for testing routing logic and development workflows.
Supports configurable behaviors including failure simulation, execution delays,
resource usage patterns, and performance benchmarking.
"""

import json
import logging
import random
import time
import uuid

from django.utils import timezone

from ..models import ContainerJob
from .base import ContainerExecutor

# Constants
IMMEDIATE_EXECUTION_THRESHOLD = 0.5  # Seconds threshold for immediate test completion
HIGH_MEMORY_THRESHOLD_MB = 8192  # 8GB threshold for high memory jobs
HIGH_CPU_THRESHOLD = 4.0  # CPU cores threshold for high CPU jobs

logger = logging.getLogger(__name__)


class MockExecutor(ContainerExecutor):
    """
    Mock executor that simulates container execution for testing.

    Configuration options:
    - simulate_failures: Enable random failures (default: False)
    - failure_rate: Probability of failure 0.0-1.0 (default: 0.1)
    - execution_delay: Base execution time in seconds (default: 1.0)
    - memory_usage_pattern: 'low', 'medium', 'high', or custom MB value
    - cpu_usage_pattern: 'low', 'medium', 'high', or custom percentage
    - exit_code_distribution: Dict of exit_code -> probability
    - simulate_timeout: Enable timeout simulation (default: False)
    - timeout_rate: Probability of timeout 0.0-1.0 (default: 0.05)
    - log_patterns: List of log patterns to simulate
    - resource_fluctuation: Enable resource usage fluctuation (default: False)
    """

    def __init__(self, config: dict):
        super().__init__(config)

        # Failure simulation
        self.simulate_failures = config.get("simulate_failures", False)
        self.failure_rate = config.get("failure_rate", 0.1)

        # Execution timing
        self.execution_delay = config.get("execution_delay", 1.0)
        self.simulate_timeout = config.get("simulate_timeout", False)
        self.timeout_rate = config.get("timeout_rate", 0.05)

        # Resource patterns
        self.memory_usage_pattern = config.get("memory_usage_pattern", "medium")
        self.cpu_usage_pattern = config.get("cpu_usage_pattern", "medium")
        self.resource_fluctuation = config.get("resource_fluctuation", False)

        # Exit code distribution
        self.exit_code_distribution = config.get(
            "exit_code_distribution",
            {
                0: 0.85,  # 85% success
                1: 0.10,  # 10% general error
                2: 0.03,  # 3% invalid usage
                130: 0.02,  # 2% interrupted
            },
        )

        # Log patterns
        self.log_patterns = config.get(
            "log_patterns",
            [
                "Starting application...",
                "Loading configuration...",
                "Processing data...",
                "Operation completed successfully",
            ],
        )

        # Performance tracking
        self._execution_times = []
        self._memory_peaks = []
        self._cpu_averages = []

        # In-memory execution tracking
        self._running_executions = {}  # execution_id -> execution_info

    def launch_job(self, job: ContainerJob) -> tuple[bool, str]:
        """
        Simulate launching a job with configurable behaviors.

        Args:
            job: ContainerJob to launch

        Returns:
            Tuple of (success, execution_id or error_message)
        """
        try:
            logger.info(
                f"Mock executor launching job {job.id} (name: {job.name or 'unnamed'})"
            )

            # Simulate launch failures if configured
            if self.simulate_failures and random.random() < self.failure_rate:
                error_msg = f"Mock launch failure for job {job.id}"
                logger.warning(error_msg)
                return False, error_msg

            # Generate mock execution ID
            execution_id = f"mock-{uuid.uuid4().hex[:8]}"

            # Determine execution parameters
            execution_time = self._calculate_execution_time(job)
            memory_usage = self._calculate_memory_usage(job)
            cpu_usage = self._calculate_cpu_usage(job)
            will_timeout = self._should_timeout(job)
            exit_code = self._determine_exit_code()

            # Store execution info for status checking
            execution_info = {
                "job_id": str(job.id),
                "start_time": timezone.now(),
                "execution_time": execution_time,
                "memory_usage": memory_usage,
                "cpu_usage": cpu_usage,
                "will_timeout": will_timeout,
                "exit_code": exit_code,
                "logs": self._generate_logs(job),
                "status": "running",
            }
            self._running_executions[execution_id] = execution_info

            # Simulate some launch processing time
            launch_delay = min(
                self.execution_delay * 0.1, 0.1
            )  # Cap at 100ms for tests
            time.sleep(launch_delay)

            # Update job status and set execution identifier
            job.status = "running"
            job.started_at = timezone.now()
            job.set_execution_identifier(execution_id)

            # Set initial execution data on job
            job.stdout_log = (
                "Mock execution started for job "
                + str(job.id)
                + "\n"
                + execution_info["logs"]["stdout"][:200]
            )
            job.stderr_log = ""
            job.docker_log = (
                f"Mock container {execution_id} created\n"
                + f"Container configuration: {json.dumps(self._get_container_config(job))}\n"
            )

            job.save()

            logger.info(
                f"Mock job {job.id} launched with ID {execution_id} "
                f"(estimated runtime: {execution_time:.1f}s)"
            )
            return True, execution_id

        except Exception as e:
            logger.exception(f"Mock executor failed to launch job {job.id}")
            return False, str(e)

    def check_status(self, execution_id: str) -> str:
        """
        Check status of a mock execution with realistic timing.

        Args:
            execution_id: Mock execution identifier

        Returns:
            Status string ('running', 'completed', 'failed', 'not-found')
        """
        if execution_id not in self._running_executions:
            return "not-found"

        execution_info = self._running_executions[execution_id]

        # Check if already completed
        if execution_info["status"] != "running":
            return execution_info["status"]

        # Calculate elapsed time
        elapsed = (timezone.now() - execution_info["start_time"]).total_seconds()

        # Check for timeout
        if (
            execution_info["will_timeout"]
            and elapsed >= execution_info["execution_time"] * 0.8
        ):
            execution_info["status"] = "timeout"
            return "timeout"

        # Check if execution should be completed
        # For tests, if execution_delay is very small, complete immediately
        if (
            execution_info["execution_time"] < IMMEDIATE_EXECUTION_THRESHOLD
            or elapsed >= execution_info["execution_time"]
        ):
            # Determine final status based on exit code
            if execution_info["exit_code"] == 0:
                execution_info["status"] = "completed"
            else:
                execution_info["status"] = "failed"

            return execution_info["status"]

        # Still running
        return "running"

    def harvest_job(self, job: ContainerJob) -> bool:
        """
        Harvest results from a completed mock job with realistic data.

        Args:
            job: ContainerJob to harvest

        Returns:
            True if harvest was successful
        """
        try:
            logger.info(f"Harvesting mock job {job.id}")

            # Get execution identifier and info
            execution_id = job.get_execution_identifier()
            execution_info = self._running_executions.get(execution_id)

            if not execution_info:
                logger.warning(
                    f"No execution info found for job {job.id}, using defaults"
                )
                # Use default values if execution info is missing
                exit_code = 0
                memory_usage = 1024 * 1024 * 64  # 64MB
                cpu_usage = 25.5
                logs = {
                    "stdout": f"Mock job {job.id} completed\n",
                    "stderr": "",
                    "docker": "Mock container finished\n",
                }
                will_timeout = False
            else:
                exit_code = execution_info["exit_code"]
                memory_usage = execution_info["memory_usage"]
                cpu_usage = execution_info["cpu_usage"]
                logs = execution_info["logs"]
                will_timeout = execution_info.get("will_timeout", False)

            # Update job with results
            job.exit_code = exit_code
            job.completed_at = timezone.now()

            # Set job status based on execution state
            if will_timeout:
                job.status = "timeout"
            elif exit_code == 0:
                job.status = "completed"
            else:
                job.status = "failed"

            job.save()

            # Update job with complete execution results
            job.stdout_log = logs["stdout"]
            job.stderr_log = logs["stderr"]
            if job.docker_log:
                job.docker_log += logs["docker"]
            else:
                job.docker_log = logs["docker"]
            job.max_memory_usage = memory_usage
            job.cpu_usage_percent = cpu_usage
            job.save()

            # Track performance metrics
            if execution_info and "execution_time" in execution_info:
                self._execution_times.append(execution_info["execution_time"])
                self._memory_peaks.append(memory_usage)
                self._cpu_averages.append(cpu_usage)

            # Clean up execution tracking
            if execution_id and execution_id in self._running_executions:
                del self._running_executions[execution_id]

            logger.info(
                f"Successfully harvested mock job {job.id} "
                f"(status: {job.status}, exit_code: {job.exit_code})"
            )
            return True

        except Exception:
            logger.exception(f"Failed to harvest mock job {job.id}")
            return False

    def cleanup(self, execution_id: str) -> bool:
        """
        Clean up mock execution resources.

        Args:
            execution_id: Mock execution identifier

        Returns:
            True if cleanup was successful
        """
        logger.debug(f"Cleaning up mock execution {execution_id}")

        # Remove from tracking if still present
        if execution_id in self._running_executions:
            del self._running_executions[execution_id]

        return True

    def get_logs(self, execution_id: str) -> str | None:
        """
        Get logs from mock execution.

        Args:
            execution_id: Mock execution identifier

        Returns:
            Log string or None if not found
        """
        execution_info = self._running_executions.get(execution_id)
        if execution_info:
            logs = execution_info["logs"]
            return (
                f"=== STDOUT ===\n{logs['stdout']}\n=== STDERR ===\n{logs['stderr']}\n"
                f"=== DOCKER ===\n{logs['docker']}"
            )

        return (
            f"Mock logs for execution {execution_id}\nExecution not found in tracking\n"
        )

    def get_resource_usage(self, execution_id: str) -> dict | None:
        """
        Get resource usage stats for mock execution.

        Args:
            execution_id: Mock execution identifier

        Returns:
            Resource usage dictionary or None if not found
        """
        execution_info = self._running_executions.get(execution_id)
        if execution_info:
            return {
                "memory_usage_bytes": execution_info["memory_usage"],
                "cpu_usage_percent": execution_info["cpu_usage"],
                "execution_time_seconds": execution_info["execution_time"],
            }

        # Default values if not tracked
        return {
            "memory_usage_bytes": 1024 * 1024 * 64,  # 64MB
            "cpu_usage_percent": 25.5,
            "execution_time_seconds": 5.0,
        }

    # Performance and benchmarking methods

    def get_performance_stats(self) -> dict:
        """
        Get performance statistics for benchmarking.

        Returns:
            Dictionary with performance metrics
        """
        if not self._execution_times:
            return {
                "total_executions": 0,
                "avg_execution_time": 0,
                "avg_memory_peak": 0,
                "avg_cpu_usage": 0,
            }

        return {
            "total_executions": len(self._execution_times),
            "avg_execution_time": sum(self._execution_times)
            / len(self._execution_times),
            "min_execution_time": min(self._execution_times),
            "max_execution_time": max(self._execution_times),
            "avg_memory_peak": sum(self._memory_peaks) / len(self._memory_peaks),
            "min_memory_peak": min(self._memory_peaks),
            "max_memory_peak": max(self._memory_peaks),
            "avg_cpu_usage": sum(self._cpu_averages) / len(self._cpu_averages),
            "min_cpu_usage": min(self._cpu_averages),
            "max_cpu_usage": max(self._cpu_averages),
        }

    def reset_performance_stats(self):
        """Reset performance tracking statistics."""
        self._execution_times.clear()
        self._memory_peaks.clear()
        self._cpu_averages.clear()

    def get_active_executions(self) -> list[dict]:
        """
        Get list of currently active executions.

        Returns:
            List of execution info dictionaries
        """
        return [
            {
                "execution_id": exec_id,
                "job_id": info["job_id"],
                "start_time": info["start_time"],
                "estimated_completion": info["start_time"]
                + timezone.timedelta(seconds=info["execution_time"]),
                "status": info["status"],
            }
            for exec_id, info in self._running_executions.items()
        ]

    # Helper methods for simulation configuration

    def _calculate_execution_time(self, job: ContainerJob) -> float:
        """Calculate execution time based on job template and configuration."""
        base_time = self.execution_delay

        # Adjust based on template properties
        if (
            job.memory_limit or 0
        ) > HIGH_MEMORY_THRESHOLD_MB:  # High memory jobs take longer
            base_time *= 1.5
        if (job.cpu_limit or 0) > HIGH_CPU_THRESHOLD:  # High CPU jobs take longer
            base_time *= 1.2

        # Add some randomness
        return base_time * random.uniform(0.8, 1.5)

    def _calculate_memory_usage(self, job: ContainerJob) -> int:
        """Calculate memory usage in bytes based on pattern and job."""
        if isinstance(self.memory_usage_pattern, int | float):
            base_mb = self.memory_usage_pattern
        else:
            patterns = {"low": 32, "medium": 128, "high": 512}
            base_mb = patterns.get(self.memory_usage_pattern, 128)

        # For testing custom values, honor them exactly when specified
        if isinstance(self.memory_usage_pattern, int | float):
            actual_mb = base_mb
        else:
            # Use template memory limit as upper bound for pattern-based calculation
            max_mb = min(job.memory_limit or 512, base_mb * 2)
            actual_mb = random.uniform(base_mb * 0.7, max_mb)

        return int(actual_mb * 1024 * 1024)  # Convert to bytes

    def _calculate_cpu_usage(self, job: ContainerJob) -> float:
        """Calculate CPU usage percentage based on pattern and job."""
        if isinstance(self.cpu_usage_pattern, int | float):
            base_percent = self.cpu_usage_pattern
        else:
            patterns = {"low": 15.0, "medium": 45.0, "high": 85.0}
            base_percent = patterns.get(self.cpu_usage_pattern, 45.0)

        # Add fluctuation if enabled
        if self.resource_fluctuation:
            return random.uniform(base_percent * 0.5, min(100.0, base_percent * 1.5))

        return base_percent

    def _should_timeout(self, job: ContainerJob) -> bool:
        """Determine if this execution should timeout."""
        return self.simulate_timeout and random.random() < self.timeout_rate

    def _determine_exit_code(self) -> int:
        """Determine exit code based on configured distribution."""
        rand = random.random()
        cumulative = 0.0

        for exit_code, probability in self.exit_code_distribution.items():
            cumulative += probability
            if rand <= cumulative:
                return int(exit_code)

        # Fallback to success
        return 0

    def _generate_logs(self, job: ContainerJob) -> dict[str, str]:
        """Generate realistic log patterns for the job."""
        job_name = job.name or "unnamed"
        job_id = str(job.id)

        # Generate stdout logs
        stdout_lines = []
        for pattern in self.log_patterns:
            stdout_lines.append(
                f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] {pattern}"
            )

        # Add job-specific information
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        stdout_lines.extend(
            [
                f"[{timestamp}] Processing job: {job_name}",
                f"[{timestamp}] Job ID: {job_id}",
                f"[{timestamp}] Memory limit: {job.memory_limit or 'unlimited'}MB",
                f"[{timestamp}] CPU limit: {job.cpu_limit or 'unlimited'} cores",
            ]
        )

        # Add environment variables if present
        all_env_vars = job.get_all_environment_variables()
        if all_env_vars:
            env_count = len(all_env_vars)
            stdout_lines.append(
                f"[{timestamp}] Environment variables: {env_count} total"
            )

        stdout_lines.append(
            f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Execution completed"
        )

        # Generate stderr logs (usually empty for successful runs)
        stderr_lines = []

        # Generate docker logs
        docker_lines = [
            f"Container created for job {job_id}",
            f"Using image: {job.docker_image}",
            f"Resource limits applied: {job.memory_limit or 'unlimited'}MB memory, "
            f"{job.cpu_limit or 'unlimited'} CPU cores",
            "Container started successfully",
            "Container execution completed",
        ]

        return {
            "stdout": "\n".join(stdout_lines) + "\n",
            "stderr": "\n".join(stderr_lines) + ("\n" if stderr_lines else ""),
            "docker": "\n".join(docker_lines) + "\n",
        }

    def _get_container_config(self, job: ContainerJob) -> dict:
        """Generate container configuration for logging."""
        return {
            "image": job.docker_image,
            "memory_limit": f"{job.memory_limit or 'unlimited'}MB",
            "cpu_limit": job.cpu_limit or "unlimited",
            "timeout_seconds": job.timeout_seconds or 3600,
            "environment_vars": len(job.get_all_environment_variables()),
            "command_override": bool(job.command),
        }

    def _validate_executor_specific(self, job) -> list[str]:
        """Mock-specific validation logic"""
        errors = []

        # Mock-specific validation: can be configured to fail validation
        config = self.config.get("mock_behaviors", {})
        if config.get("fail_validation"):
            errors.append("Mock executor configured to fail validation")

        # Mock executor is very permissive, most validation passes
        return errors

    def get_execution_display(self, job) -> dict[str, str]:
        """Mock-specific execution display information"""
        execution_id = job.get_execution_identifier()

        # Add mock-specific details
        config = self.config.get("mock_behaviors", {})
        behavior = "Default"
        if config.get("fail_launch"):
            behavior = "Fail Launch"
        elif config.get("always_succeed"):
            behavior = "Always Succeed"
        elif config.get("random_failure"):
            behavior = "Random Failure"

        return {
            "type_name": f"Mock Executor ({behavior})",
            "id_label": "Mock Execution ID",
            "id_value": execution_id or "Not started",
            "status_detail": self._get_mock_status_detail(job),
        }

    def _get_mock_status_detail(self, job) -> str:
        """Get Mock-specific status details"""
        status = job.status.title()

        if job.exit_code is not None:
            if job.exit_code == 0:
                status += " (Mock Success)"
            else:
                status += f" (Mock Exit Code: {job.exit_code})"

        # Add mock behavior info
        config = self.config.get("mock_behaviors", {})
        if config:
            behaviors = []
            if config.get("fail_launch"):
                behaviors.append("Fail Launch")
            if config.get("always_succeed"):
                behaviors.append("Always Succeed")
            if config.get("random_failure"):
                behaviors.append("Random Failure")
            if behaviors:
                status += f" [Behaviors: {', '.join(behaviors)}]"

        return status
