"""
Bulk operations for container job management.

This module provides efficient bulk operations for managing large numbers
of container jobs across multiple executors and hosts.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .executors.factory import ExecutorFactory
from .models import ContainerJob, ContainerTemplate, DockerHost

logger = logging.getLogger(__name__)


class BulkJobManager:
    """
    Manager for bulk job operations including creation, migration, and status
    management.
    """

    def __init__(self):
        self.executor_factory = ExecutorFactory()

    def create_jobs_bulk(
        self,
        template: ContainerTemplate,
        count: int,
        user: User,
        host: Optional[DockerHost] = None,
        name_pattern: str = None,
        environment_overrides: Optional[List[Dict[str, Any]]] = None,
        command_overrides: Optional[List[str]] = None,
        batch_size: int = 100,
    ) -> Tuple[List[ContainerJob], List[str]]:
        """
        Create multiple jobs in bulk.

        Args:
            template: Container template to use
            count: Number of jobs to create
            user: User creating the jobs
            host: Specific host to use (optional, will auto-route if None)
            name_pattern: Pattern for job names (e.g., "batch-job-{index}")
            environment_overrides: List of environment override dicts
            command_overrides: List of command overrides
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

        if count > 10000:
            errors.append("Maximum bulk creation limit is 10,000 jobs")
            return created_jobs, errors

        # Prepare environment and command overrides
        env_overrides = environment_overrides or []
        cmd_overrides = command_overrides or []

        # Pad lists to match count
        while len(env_overrides) < count:
            env_overrides.append({})
        while len(cmd_overrides) < count:
            cmd_overrides.append("")

        logger.info(f"Creating {count} jobs in bulk for template {template.name}")

        # Process in batches to avoid memory issues
        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_jobs, batch_errors = self._create_job_batch(
                template=template,
                start_index=batch_start,
                end_index=batch_end,
                user=user,
                host=host,
                name_pattern=name_pattern,
                env_overrides=env_overrides,
                cmd_overrides=cmd_overrides,
            )
            created_jobs.extend(batch_jobs)
            errors.extend(batch_errors)

        logger.info(f"Bulk creation completed: {len(created_jobs)} jobs created")
        return created_jobs, errors

    def _create_job_batch(
        self,
        template: ContainerTemplate,
        start_index: int,
        end_index: int,
        user: User,
        host: Optional[DockerHost],
        name_pattern: Optional[str],
        env_overrides: List[Dict[str, Any]],
        cmd_overrides: List[str],
    ) -> Tuple[List[ContainerJob], List[str]]:
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
                            job_name = f"{template.name}-{i}"

                        # Select host if not specified
                        job_host = host
                        if not job_host:
                            # Auto-route based on template requirements
                            try:
                                executor_type = self.executor_factory.route_job_dry_run(
                                    template
                                )
                                job_host = DockerHost.objects.filter(
                                    executor_type=executor_type, is_active=True
                                ).first()
                            except Exception as e:
                                logger.warning(f"Auto-routing failed for job {i}: {e}")
                                job_host = DockerHost.objects.filter(
                                    is_active=True
                                ).first()

                        if not job_host:
                            errors.append(f"No available host for job {i}")
                            continue

                        # Create job
                        job = ContainerJob.objects.create(
                            template=template,
                            docker_host=job_host,
                            name=job_name,
                            executor_type=job_host.executor_type,  # Match host type
                            override_command=cmd_overrides[i] or "",
                            override_environment=env_overrides[i] or {},
                            created_by=user,
                            status="pending",
                        )
                        jobs.append(job)

                    except Exception as e:
                        error_msg = f"Failed to create job {i}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)

        except Exception as e:
            error_msg = f"Batch creation failed: {e}"
            errors.append(error_msg)
            logger.error(error_msg)

        return jobs, errors

    def migrate_jobs_cross_executor(
        self,
        jobs: List[ContainerJob],
        target_executor_type: str,
        dry_run: bool = False,
        force_migration: bool = False,
    ) -> Tuple[List[ContainerJob], List[str]]:
        """
        Migrate jobs to a different executor type.

        Args:
            jobs: List of jobs to migrate
            target_executor_type: Target executor type (docker, cloudrun, etc.)
            dry_run: If True, don't actually migrate, just validate
            force_migration: If True, migrate even running jobs

        Returns:
            Tuple of (migrated_jobs, error_messages)
        """
        migrated_jobs = []
        errors = []

        # Get target hosts
        target_hosts = list(
            DockerHost.objects.filter(
                executor_type=target_executor_type, is_active=True
            )
        )

        if not target_hosts:
            errors.append(
                f"No available hosts for executor type {target_executor_type}"
            )
            return migrated_jobs, errors

        logger.info(
            f"{'[DRY RUN] ' if dry_run else ''}Migrating {len(jobs)} jobs to "
            f"{target_executor_type}"
        )

        for job in jobs:
            try:
                # Validate migration is possible
                if job.status == "running" and not force_migration:
                    errors.append(
                        f"Job {job.id} is running. Use force_migration=True to "
                        f"migrate running jobs"
                    )
                    continue

                if job.docker_host.executor_type == target_executor_type:
                    errors.append(
                        f"Job {job.id} already on {target_executor_type} executor"
                    )
                    continue

                # Select best target host
                target_host = self._select_best_host(target_hosts, job)

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would migrate job {job.id} to {target_host.name}"
                    )
                    migrated_jobs.append(job)
                    continue

                # Perform migration
                original_host = job.docker_host
                original_status = job.status

                # Stop job if running
                if job.status == "running":
                    try:
                        executor = self.executor_factory.get_executor(original_host)
                        execution_id = job.get_execution_identifier()
                        if execution_id:
                            executor.cleanup(execution_id)
                    except Exception as e:
                        logger.warning(f"Failed to stop job {job.id}: {e}")

                # Update job to new host
                job.docker_host = target_host
                job.executor_type = target_executor_type
                job.routing_reason = (
                    f"Bulk migration from {original_host.executor_type} "
                    f"to {target_executor_type}"
                )

                # Reset execution identifiers
                job.container_id = ""
                job.external_execution_id = ""

                # Set status based on original state
                if original_status == "running":
                    job.status = "pending"  # Will be restarted
                elif original_status in ["completed", "failed", "timeout", "cancelled"]:
                    # Keep final states as-is
                    pass
                else:
                    job.status = "pending"

                job.save()
                migrated_jobs.append(job)

                logger.info(
                    f"Migrated job {job.id} from {original_host.name} to "
                    f"{target_host.name}"
                )

            except Exception as e:
                error_msg = f"Failed to migrate job {job.id}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

        logger.info(
            f"Migration completed: {len(migrated_jobs)} jobs migrated, "
            f"{len(errors)} errors"
        )
        return migrated_jobs, errors

    def _select_best_host(
        self, hosts: List[DockerHost], job: ContainerJob
    ) -> DockerHost:
        """Select the best host for a job based on capacity and requirements."""
        # Simple load balancing - select host with lowest current job count
        best_host = min(hosts, key=lambda h: h.current_job_count or 0)
        return best_host

    def bulk_start_jobs(
        self, jobs: List[ContainerJob], batch_size: int = 50
    ) -> Tuple[List[ContainerJob], List[str]]:
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
                    logger.error(error_msg)

        logger.info(
            f"Bulk start completed: {len(started_jobs)} jobs started, "
            f"{len(errors)} errors"
        )
        return started_jobs, errors

    def bulk_stop_jobs(
        self, jobs: List[ContainerJob], batch_size: int = 50
    ) -> Tuple[List[ContainerJob], List[str]]:
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
                    logger.error(error_msg)

        logger.info(
            f"Bulk stop completed: {len(stopped_jobs)} jobs stopped, "
            f"{len(errors)} errors"
        )
        return stopped_jobs, errors

    def bulk_cancel_jobs(
        self, jobs: List[ContainerJob]
    ) -> Tuple[List[ContainerJob], List[str]]:
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
                logger.error(error_msg)

        logger.info(
            f"Bulk cancel completed: {len(cancelled_jobs)} jobs cancelled, "
            f"{len(errors)} errors"
        )
        return cancelled_jobs, errors

    def bulk_restart_jobs(
        self, jobs: List[ContainerJob], batch_size: int = 50
    ) -> Tuple[List[ContainerJob], List[str]]:
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
                    job.container_id = ""
                    job.external_execution_id = ""
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
                    logger.error(error_msg)

        logger.info(
            f"Bulk restart completed: {len(restarted_jobs)} jobs restarted, "
            f"{len(errors)} errors"
        )
        return restarted_jobs, errors

    def get_bulk_status(self, jobs: List[ContainerJob]) -> Dict[str, Any]:
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
