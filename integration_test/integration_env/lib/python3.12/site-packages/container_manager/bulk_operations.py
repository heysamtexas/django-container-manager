"""
Bulk operations for container job management.

This module provides efficient bulk operations for managing large numbers
of container jobs across multiple executors and hosts.
"""

import logging
from typing import Any
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .executors.factory import ExecutorFactory
from .models import ContainerJob, ExecutorHost

logger = logging.getLogger(__name__)

# Constants
MAX_BULK_CREATION_LIMIT = (
    10000  # Maximum jobs that can be created in a single bulk operation
)


class BulkJobManager:
    """
    Manager for bulk job operations including creation, migration, and status
    management.
    """

    def __init__(self):
        self.executor_factory = ExecutorFactory()

    def create_jobs_bulk(
        self,
        docker_image: str,
        count: int,
        user: User,
        host: ExecutorHost | None = None,
        name_pattern: str | None = None,
        command: str = "",
        environment_variables: dict[str, str] | None = None,
        memory_limit: int | None = None,
        cpu_limit: float | None = None,
        timeout_seconds: int = 3600,
        batch_size: int = 100,
    ) -> tuple[list[ContainerJob], list[str]]:
        """
        Create multiple jobs in bulk.

        Args:
            docker_image: Docker image to use for all jobs
            count: Number of jobs to create
            user: User creating the jobs
            host: Specific host to use (optional, will auto-route if None)
            name_pattern: Pattern for job names (e.g., "batch-job-{index}")
            command: Command to run in containers
            environment_variables: Base environment variables for all jobs
            memory_limit: Memory limit in MB
            cpu_limit: CPU limit in cores
            timeout_seconds: Timeout in seconds
            batch_size: Number of jobs to create per database transaction

        Returns:
            Tuple of (created_jobs, error_messages)
        """
        created_jobs = []
        errors = []

        # Validate inputs
        if count <= 0:
            errors.append("Count must be positive")
            return created_jobs, errors

        if count > MAX_BULK_CREATION_LIMIT:
            errors.append(
                f"Maximum bulk creation limit is {MAX_BULK_CREATION_LIMIT:,} jobs"
            )
            return created_jobs, errors

        # Prepare base environment variables
        base_env = environment_variables or {}

        logger.info(f"Creating {count} jobs in bulk with image {docker_image}")

        # Process in batches to avoid memory issues
        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_jobs, batch_errors = self._create_job_batch(
                docker_image=docker_image,
                start_index=batch_start,
                end_index=batch_end,
                user=user,
                host=host,
                name_pattern=name_pattern,
                command=command,
                environment_variables=base_env,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                timeout_seconds=timeout_seconds,
            )
            created_jobs.extend(batch_jobs)
            errors.extend(batch_errors)

        logger.info(f"Bulk creation completed: {len(created_jobs)} jobs created")
        return created_jobs, errors

    def _create_job_batch(
        self,
        docker_image: str,
        start_index: int,
        end_index: int,
        user: User,
        host: ExecutorHost | None,
        name_pattern: str | None,
        command: str,
        environment_variables: dict[str, str],
        memory_limit: int | None,
        cpu_limit: float | None,
        timeout_seconds: int,
    ) -> tuple[list[ContainerJob], list[str]]:
        """Create a batch of jobs within a single transaction."""
        jobs = []
        errors = []

        try:
            with transaction.atomic():
                for i in range(start_index, end_index):
                    try:
                        # Generate job name
                        if name_pattern:
                            job_name = name_pattern.format(
                                index=i, batch=start_index // 100, uuid=str(uuid4())[:8]
                            )
                        else:
                            job_name = f"job-{i}"

                        # Select host if not specified
                        job_host = host
                        if not job_host:
                            # Use first available host
                            job_host = ExecutorHost.objects.filter(
                                is_active=True
                            ).first()

                        if not job_host:
                            errors.append(f"No available host for job {i}")
                            continue

                        # Convert environment variables dict to text format
                        env_text = ""
                        if environment_variables:
                            env_text = "\n".join(
                                [f"{k}={v}" for k, v in environment_variables.items()]
                            )

                        # Create job
                        job = ContainerJob.objects.create(
                            docker_host=job_host,
                            name=job_name,
                            docker_image=docker_image,
                            command=command,
                            override_environment=env_text,
                            memory_limit=memory_limit,
                            cpu_limit=cpu_limit,
                            timeout_seconds=timeout_seconds,
                            # executor_type removed - comes from docker_host
                            created_by=user,
                            status="pending",
                        )
                        jobs.append(job)

                    except Exception as e:
                        error_msg = f"Failed to create job {i}: {e}"
                        errors.append(error_msg)
                        logger.exception(error_msg)

        except Exception as e:
            error_msg = f"Batch creation failed: {e}"
            errors.append(error_msg)
            logger.exception(error_msg)

        return jobs, errors

    def _select_best_host(
        self, hosts: list[ExecutorHost], job: ContainerJob
    ) -> ExecutorHost:
        """Select the best host for a job based on capacity and requirements."""
        # Simple load balancing - select host with lowest current job count
        best_host = min(hosts, key=lambda h: h.current_job_count or 0)
        return best_host

    def bulk_start_jobs(
        self, jobs: list[ContainerJob], batch_size: int = 50
    ) -> tuple[list[ContainerJob], list[str]]:
        """
        Start multiple jobs in bulk.

        Args:
            jobs: List of jobs to start
            batch_size: Number of jobs to start per batch

        Returns:
            Tuple of (started_jobs, error_messages)
        """
        started_jobs = []
        errors = []

        # Filter to only pending jobs
        pending_jobs = [job for job in jobs if job.status == "pending"]

        logger.info(f"Starting {len(pending_jobs)} jobs in bulk")

        # Process in batches to avoid overwhelming executors
        for batch_start in range(0, len(pending_jobs), batch_size):
            batch_end = min(batch_start + batch_size, len(pending_jobs))
            batch_jobs = pending_jobs[batch_start:batch_end]

            for job in batch_jobs:
                try:
                    executor = self.executor_factory.get_executor(job.docker_host)
                    success, execution_id = executor.launch_job(job)

                    if success:
                        job.set_execution_identifier(execution_id)
                        job.status = "running"
                        job.started_at = timezone.now()
                        job.save()
                        started_jobs.append(job)
                        logger.debug(f"Started job {job.id}")
                    else:
                        error_msg = f"Failed to start job {job.id}: {execution_id}"
                        errors.append(error_msg)
                        logger.error(error_msg)

                except Exception as e:
                    error_msg = f"Exception starting job {job.id}: {e}"
                    errors.append(error_msg)
                    logger.exception(error_msg)

        logger.info(
            f"Bulk start completed: {len(started_jobs)} jobs started, "
            f"{len(errors)} errors"
        )
        return started_jobs, errors

    def bulk_stop_jobs(
        self, jobs: list[ContainerJob], batch_size: int = 50
    ) -> tuple[list[ContainerJob], list[str]]:
        """
        Stop multiple jobs in bulk.

        Args:
            jobs: List of jobs to stop
            batch_size: Number of jobs to stop per batch

        Returns:
            Tuple of (stopped_jobs, error_messages)
        """
        stopped_jobs = []
        errors = []

        # Filter to only running jobs
        running_jobs = [job for job in jobs if job.status == "running"]

        logger.info(f"Stopping {len(running_jobs)} jobs in bulk")

        # Process in batches
        for batch_start in range(0, len(running_jobs), batch_size):
            batch_end = min(batch_start + batch_size, len(running_jobs))
            batch_jobs = running_jobs[batch_start:batch_end]

            for job in batch_jobs:
                try:
                    executor = self.executor_factory.get_executor(job.docker_host)
                    execution_id = job.get_execution_identifier()

                    if execution_id:
                        executor.cleanup(execution_id)

                    job.status = "cancelled"
                    job.completed_at = timezone.now()
                    job.save()
                    stopped_jobs.append(job)
                    logger.debug(f"Stopped job {job.id}")

                except Exception as e:
                    error_msg = f"Exception stopping job {job.id}: {e}"
                    errors.append(error_msg)
                    logger.exception(error_msg)

        logger.info(
            f"Bulk stop completed: {len(stopped_jobs)} jobs stopped, "
            f"{len(errors)} errors"
        )
        return stopped_jobs, errors

    def bulk_cancel_jobs(
        self, jobs: list[ContainerJob]
    ) -> tuple[list[ContainerJob], list[str]]:
        """
        Cancel multiple jobs in bulk.

        Args:
            jobs: List of jobs to cancel

        Returns:
            Tuple of (cancelled_jobs, error_messages)
        """
        cancelled_jobs = []
        errors = []

        # Filter to only active jobs
        active_jobs = [job for job in jobs if job.status in ["pending", "running"]]

        logger.info(f"Cancelling {len(active_jobs)} jobs in bulk")

        for job in active_jobs:
            try:
                if job.status == "running":
                    # Stop running job
                    executor = self.executor_factory.get_executor(job.docker_host)
                    execution_id = job.get_execution_identifier()

                    if execution_id:
                        executor.cleanup(execution_id)

                job.status = "cancelled"
                job.completed_at = timezone.now()
                job.save()
                cancelled_jobs.append(job)
                logger.debug(f"Cancelled job {job.id}")

            except Exception as e:
                error_msg = f"Exception cancelling job {job.id}: {e}"
                errors.append(error_msg)
                logger.exception(error_msg)

        logger.info(
            f"Bulk cancel completed: {len(cancelled_jobs)} jobs cancelled, "
            f"{len(errors)} errors"
        )
        return cancelled_jobs, errors

    def bulk_restart_jobs(
        self, jobs: list[ContainerJob], batch_size: int = 50
    ) -> tuple[list[ContainerJob], list[str]]:
        """
        Restart multiple jobs in bulk.

        Args:
            jobs: List of jobs to restart
            batch_size: Number of jobs to restart per batch

        Returns:
            Tuple of (restarted_jobs, error_messages)
        """
        restarted_jobs = []
        errors = []

        # Filter to restartable jobs
        restartable_jobs = [
            job
            for job in jobs
            if job.status in ["running", "completed", "failed", "timeout", "cancelled"]
        ]

        logger.info(f"Restarting {len(restartable_jobs)} jobs in bulk")

        # Process in batches
        for batch_start in range(0, len(restartable_jobs), batch_size):
            batch_end = min(batch_start + batch_size, len(restartable_jobs))
            batch_jobs = restartable_jobs[batch_start:batch_end]

            for job in batch_jobs:
                try:
                    executor = self.executor_factory.get_executor(job.docker_host)

                    # Stop if running
                    if job.status == "running":
                        execution_id = job.get_execution_identifier()
                        if execution_id:
                            executor.cleanup(execution_id)

                    # Reset job state
                    job.status = "pending"
                    job.set_execution_identifier("")
                    job.exit_code = None
                    job.started_at = None
                    job.completed_at = None
                    job.save()

                    # Start job
                    success, execution_id = executor.launch_job(job)

                    if success:
                        job.set_execution_identifier(execution_id)
                        job.status = "running"
                        job.started_at = timezone.now()
                        job.save()
                        restarted_jobs.append(job)
                        logger.debug(f"Restarted job {job.id}")
                    else:
                        error_msg = f"Failed to restart job {job.id}: {execution_id}"
                        errors.append(error_msg)
                        logger.error(error_msg)

                except Exception as e:
                    error_msg = f"Exception restarting job {job.id}: {e}"
                    errors.append(error_msg)
                    logger.exception(error_msg)

        logger.info(
            f"Bulk restart completed: {len(restarted_jobs)} jobs restarted, "
            f"{len(errors)} errors"
        )
        return restarted_jobs, errors

    def get_bulk_status(self, jobs: list[ContainerJob]) -> dict[str, Any]:
        """
        Get aggregated status information for a list of jobs.

        Args:
            jobs: List of jobs to analyze

        Returns:
            Dictionary with status counts and summary information
        """
        status_counts = {}
        executor_counts = {}
        host_counts = {}
        total_duration = 0
        completed_jobs = 0

        for job in jobs:
            # Count by status
            status_counts[job.status] = status_counts.get(job.status, 0) + 1

            # Count by executor type
            executor_type = job.docker_host.executor_type
            executor_counts[executor_type] = executor_counts.get(executor_type, 0) + 1

            # Count by host
            host_name = job.docker_host.name
            host_counts[host_name] = host_counts.get(host_name, 0) + 1

            # Calculate duration stats
            if job.duration:
                total_duration += job.duration.total_seconds()
                completed_jobs += 1

        avg_duration = total_duration / completed_jobs if completed_jobs > 0 else 0

        return {
            "total_jobs": len(jobs),
            "status_counts": status_counts,
            "executor_counts": executor_counts,
            "host_counts": host_counts,
            "avg_duration_seconds": avg_duration,
            "completed_jobs": completed_jobs,
            "success_rate": (
                status_counts.get("completed", 0) / len(jobs) * 100 if jobs else 0
            ),
        }


# Global instance for convenience
bulk_manager = BulkJobManager()
