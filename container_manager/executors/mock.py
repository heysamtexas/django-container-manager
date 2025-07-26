"""
Mock executor for testing and development purposes.

This executor simulates container execution without actually running containers,
making it useful for testing routing logic and development workflows.
"""

import logging
import time
import uuid
from typing import Dict, Optional, Tuple

from django.utils import timezone

from ..models import ContainerExecution, ContainerJob
from .base import ContainerExecutor

logger = logging.getLogger(__name__)


class MockExecutor(ContainerExecutor):
    """Mock executor that simulates container execution for testing"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.simulate_failures = config.get('simulate_failures', False)
        self.failure_rate = config.get('failure_rate', 0.1)  # 10% failure rate
        self.execution_delay = config.get('execution_delay', 1.0)  # seconds

    def launch_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """
        Simulate launching a job.
        
        Args:
            job: ContainerJob to launch
            
        Returns:
            Tuple of (success, execution_id or error_message)
        """
        try:
            logger.info(f"Mock executor launching job {job.id}")

            # Simulate some processing time
            time.sleep(min(self.execution_delay, 0.1))  # Cap at 100ms for tests

            # Generate mock execution ID
            execution_id = f"mock-{uuid.uuid4().hex[:8]}"

            # Update job status
            job.status = 'running'
            job.started_at = timezone.now()
            job.save()

            # Create execution record
            execution = ContainerExecution.objects.create(
                job=job,
                stdout_log=f"Mock execution started for job {job.id}\n",
                stderr_log="",
                docker_log=f"Mock container {execution_id} created\n"
            )

            logger.info(f"Mock job {job.id} launched with ID {execution_id}")
            return True, execution_id

        except Exception as e:
            logger.error(f"Mock executor failed to launch job {job.id}: {e}")
            return False, str(e)

    def check_status(self, execution_id: str) -> str:
        """
        Check status of a mock execution.
        
        Args:
            execution_id: Mock execution identifier
            
        Returns:
            Status string ('running', 'completed', 'failed', 'not-found')
        """
        # For mock executor, simulate quick completion
        return 'completed'

    def harvest_job(self, job: ContainerJob) -> bool:
        """
        Harvest results from a completed mock job.
        
        Args:
            job: ContainerJob to harvest
            
        Returns:
            True if harvest was successful
        """
        try:
            logger.info(f"Harvesting mock job {job.id}")

            # Simulate execution completion
            job.status = 'completed'
            job.exit_code = 0
            job.completed_at = timezone.now()
            job.save()

            # Update execution record with mock results
            try:
                execution = job.execution
                execution.stdout_log += f"Mock job {job.id} completed successfully\n"
                execution.docker_log += "Mock container finished with exit code 0\n"
                execution.max_memory_usage = 1024 * 1024 * 64  # 64MB
                execution.cpu_usage_percent = 25.5
                execution.save()
            except ContainerExecution.DoesNotExist:
                # Create execution record if it doesn't exist
                ContainerExecution.objects.create(
                    job=job,
                    stdout_log=f"Mock job {job.id} completed successfully\n",
                    stderr_log="",
                    docker_log="Mock container finished with exit code 0\n",
                    max_memory_usage=1024 * 1024 * 64,
                    cpu_usage_percent=25.5
                )

            logger.info(f"Successfully harvested mock job {job.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to harvest mock job {job.id}: {e}")
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
        # Nothing to clean up for mock executor
        return True

    def get_logs(self, execution_id: str) -> Optional[str]:
        """
        Get logs from mock execution.
        
        Args:
            execution_id: Mock execution identifier
            
        Returns:
            Log string or None if not found
        """
        return f"Mock logs for execution {execution_id}\nMock job completed successfully\n"

    def get_resource_usage(self, execution_id: str) -> Optional[Dict]:
        """
        Get resource usage stats for mock execution.
        
        Args:
            execution_id: Mock execution identifier
            
        Returns:
            Resource usage dictionary or None if not found
        """
        return {
            'memory_usage_bytes': 1024 * 1024 * 64,  # 64MB
            'cpu_usage_percent': 25.5,
            'execution_time_seconds': 5.0,
        }

