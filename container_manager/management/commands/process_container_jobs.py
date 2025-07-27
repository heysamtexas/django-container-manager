"""
Django management command to process container jobs.

This command polls the database for pending container jobs and executes them
using the Docker service. It runs continuously until stopped.
"""

import logging
import signal
import time
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from container_manager.docker_service import DockerConnectionError, docker_service
from container_manager.executors.exceptions import ExecutorResourceError
from container_manager.executors.factory import ExecutorFactory
from container_manager.models import ContainerJob, DockerHost

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process pending container jobs continuously"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = False
        self.executor_factory = ExecutorFactory()
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            self.stdout.write(
                self.style.WARNING(
                    f"Received signal {signum}, shutting down gracefully..."
                )
            )
            self.should_stop = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def add_arguments(self, parser):
        parser.add_argument(
            "--poll-interval",
            type=int,
            default=5,
            help="Polling interval in seconds (default: 5)",
        )
        parser.add_argument(
            "--max-jobs",
            type=int,
            default=10,
            help="Maximum number of concurrent jobs to process (default: 10)",
        )
        parser.add_argument(
            "--host", type=str, help="Only process jobs for the specified Docker host"
        )
        parser.add_argument(
            "--single-run",
            action="store_true",
            help="Process jobs once and exit (don't run continuously)",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Run cleanup of old containers before processing jobs",
        )
        parser.add_argument(
            "--cleanup-hours",
            type=int,
            default=24,
            help="Hours after which to cleanup old containers (default: 24)",
        )
        parser.add_argument(
            "--use-factory",
            action="store_true",
            help="Use ExecutorFactory for intelligent job routing (default: auto-detect from settings)",
        )
        parser.add_argument(
            "--executor-type",
            type=str,
            help="Force specific executor type (docker, mock, etc.)",
        )

    def handle(self, *args, **options):
        """Main command handler"""
        poll_interval = options["poll_interval"]
        max_jobs = options["max_jobs"]
        host_filter = options["host"]
        single_run = options["single_run"]
        cleanup = options["cleanup"]
        cleanup_hours = options["cleanup_hours"]
        use_factory = options["use_factory"]
        executor_type = options["executor_type"]

        # Determine if we should use the executor factory
        from ...defaults import get_use_executor_factory
        factory_enabled = (
            use_factory
            or get_use_executor_factory()
            or executor_type is not None
        )

        routing_mode = "ExecutorFactory" if factory_enabled else "Direct Docker"
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting container job processor "
                f"(poll_interval={poll_interval}s, max_jobs={max_jobs}, routing={routing_mode})"
            )
        )

        if factory_enabled:
            available_hosts = DockerHost.objects.filter(is_active=True)
            available_executors = list(available_hosts.values_list('executor_type', flat=True).distinct())
            self.stdout.write(f"Available executors: {', '.join(available_executors)}")

            if executor_type:
                self.stdout.write(f"Forcing executor type: {executor_type}")

        # Run cleanup if requested
        if cleanup:
            self.stdout.write("Running container cleanup...")
            try:
                docker_service.cleanup_old_containers(orphaned_hours=cleanup_hours)
                self.stdout.write(self.style.SUCCESS("Cleanup completed"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Cleanup failed: {e}"))

        # Validate Docker hosts
        if host_filter:
            try:
                docker_host = DockerHost.objects.get(name=host_filter, is_active=True)
                self.stdout.write(f"Processing jobs only for host: {docker_host.name}")
            except DockerHost.DoesNotExist:
                raise CommandError(f'Docker host "{host_filter}" not found or inactive')

        # Main processing loop
        processed_count = 0
        error_count = 0

        try:
            while not self.should_stop:
                try:
                    # Launch phase: Start pending jobs (non-blocking)
                    jobs_launched = self.process_pending_jobs(
                        host_filter, max_jobs, factory_enabled, executor_type
                    )

                    # Monitor phase: Check running jobs and harvest completed ones
                    jobs_harvested = self.monitor_running_jobs(host_filter)

                    processed_count += jobs_launched + jobs_harvested

                    if jobs_launched > 0 or jobs_harvested > 0:
                        self.stdout.write(
                            f"Launched {jobs_launched} jobs, "
                            f"harvested {jobs_harvested} jobs "
                            f"(total processed: {processed_count}, "
                            f"errors: {error_count})"
                        )

                    if single_run:
                        break

                    # Sleep between polling cycles
                    time.sleep(poll_interval)

                except Exception as e:
                    error_count += 1
                    logger.exception(f"Error in processing cycle: {e}")
                    self.stdout.write(self.style.ERROR(f"Processing error: {e}"))

                    # Sleep longer after errors
                    time.sleep(poll_interval * 2)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted by user"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Job processor stopped. "
                f"Processed {processed_count} jobs with {error_count} errors."
            )
        )

    def process_pending_jobs(
        self,
        host_filter: Optional[str] = None,
        max_jobs: int = 10,
        use_factory: bool = False,
        force_executor_type: Optional[str] = None,
    ) -> int:
        """Launch pending jobs and return the number launched"""

        # Get pending jobs
        queryset = (
            ContainerJob.objects.filter(status="pending")
            .select_related("template", "docker_host")
            .order_by("created_at")
        )

        if host_filter:
            queryset = queryset.filter(docker_host__name=host_filter)

        # Only process active hosts
        queryset = queryset.filter(docker_host__is_active=True)

        # Limit to max_jobs
        pending_jobs = list(queryset[:max_jobs])

        if not pending_jobs:
            return 0

        launched = 0
        for job in pending_jobs:
            if self.should_stop:
                break

            try:
                success = self.launch_single_job(job, use_factory, force_executor_type)
                if success:
                    launched += 1

            except Exception as e:
                logger.exception(f"Failed to launch job {job.id}: {e}")
                self.mark_job_failed(job, str(e))

        return launched

    def launch_single_job(
        self,
        job: ContainerJob,
        use_factory: bool = False,
        force_executor_type: Optional[str] = None,
    ) -> bool:
        """Launch a single container job (non-blocking)"""

        if use_factory:
            return self.launch_job_with_factory(job, force_executor_type)
        else:
            return self.launch_job_with_docker_service(job)

    def launch_job_with_factory(
        self, job: ContainerJob, force_executor_type: Optional[str] = None
    ) -> bool:
        """Launch job using ExecutorFactory"""
        try:
            # Route job to appropriate executor
            if force_executor_type:
                job.executor_type = force_executor_type
                job.routing_reason = f"Forced to {force_executor_type} via command line"
            else:
                selected_host = self.executor_factory.route_job(job)
                if selected_host:
                    job.docker_host = selected_host
                    job.executor_type = selected_host.executor_type
                else:
                    # No available hosts
                    self.mark_job_failed(job, "No available executor hosts")
                    return False

            job.save()

            # Display routing information
            self.stdout.write(
                f"Launching job {job.id} ({job.template.name}) "
                f"using {job.executor_type} executor on {job.docker_host.name}"
            )

            # Get executor instance and launch job
            executor = self.executor_factory.get_executor(job.docker_host)
            success, execution_id = executor.launch_job(job)

            if success:
                job.set_execution_identifier(execution_id)
                job.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Job {job.id} launched successfully as {execution_id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Job {job.id} failed to launch: {execution_id}")
                )

            return success

        except ExecutorResourceError as e:
            logger.exception(f"No available executors for job {job.id}: {e}")
            self.mark_job_failed(job, f"No available executors: {e}")
            return False
        except Exception as e:
            logger.exception(f"Job launch error for {job.id}: {e}")
            self.mark_job_failed(job, str(e))
            return False

    def launch_job_with_docker_service(self, job: ContainerJob) -> bool:
        """Launch job using legacy docker_service (backward compatibility)"""
        # Verify Docker host is accessible
        try:
            docker_service.get_client(job.docker_host)
        except DockerConnectionError as e:
            logger.exception(f"Cannot connect to Docker host {job.docker_host.name}: {e}")
            self.mark_job_failed(job, f"Docker host connection failed: {e}")
            return False

        self.stdout.write(
            f"Launching job {job.id} ({job.template.name}) on {job.docker_host.name}"
        )

        try:
            # Launch the job (non-blocking)
            success = docker_service.launch_job(job)

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"Job {job.id} launched successfully")
                )
            else:
                self.stdout.write(self.style.ERROR(f"Job {job.id} failed to launch"))

            return success

        except Exception as e:
            logger.exception(f"Job launch error for {job.id}: {e}")
            self.mark_job_failed(job, str(e))
            return False

    def monitor_running_jobs(self, host_filter: Optional[str] = None) -> int:
        """Monitor running jobs and harvest completed ones"""
        from django.utils import timezone

        # Get running jobs from database
        queryset = ContainerJob.objects.filter(status="running").select_related(
            "template", "docker_host"
        )

        if host_filter:
            queryset = queryset.filter(docker_host__name=host_filter)

        running_jobs = list(queryset)

        if not running_jobs:
            return 0

        harvested = 0
        now = timezone.now()

        for job in running_jobs:
            if self.should_stop:
                break

            try:
                # Check for timeout
                if job.started_at:
                    running_time = (now - job.started_at).total_seconds()
                    if running_time > job.template.timeout_seconds:
                        # Job timed out
                        self.handle_job_timeout(job)
                        harvested += 1
                        continue

                # Check execution status (works for all executor types)
                status = self.check_job_status(job)

                if status in ["completed", "exited"]:
                    # Job finished, harvest results
                    success = self.harvest_completed_job(job)
                    if success:
                        harvested += 1
                        self.stdout.write(self.style.SUCCESS(f"Harvested job {job.id}"))
                elif status == "failed":
                    # Job failed, mark as failed
                    self.mark_job_failed(job, "Job execution failed")
                    harvested += 1
                elif status == "not-found":
                    # Execution disappeared, mark as failed
                    self.mark_job_failed(job, "Execution not found")
                    harvested += 1
                # For 'running' status, continue monitoring

            except Exception as e:
                logger.exception(f"Error monitoring job {job.id}: {e}")
                self.mark_job_failed(job, str(e))
                harvested += 1

        return harvested

    def check_job_status(self, job: ContainerJob) -> str:
        """Check job status using appropriate method based on executor type"""
        if job.executor_type == "docker" or not job.executor_type:
            # Use legacy docker service for backward compatibility
            return docker_service.check_container_status(job)
        else:
            # Use executor factory for non-docker executors
            try:
                executor = self.executor_factory.get_executor(job.docker_host)
                execution_id = job.get_execution_identifier()
                return executor.check_status(execution_id)
            except Exception as e:
                logger.exception(f"Error checking status for job {job.id}: {e}")
                return "error"

    def harvest_completed_job(self, job: ContainerJob) -> bool:
        """Harvest completed job using appropriate method based on executor type"""
        if job.executor_type == "docker" or not job.executor_type:
            # Use legacy docker service for backward compatibility
            return docker_service.harvest_completed_job(job)
        else:
            # Use executor factory for non-docker executors
            try:
                executor = self.executor_factory.get_executor(job.docker_host)
                return executor.harvest_job(job)
            except Exception as e:
                logger.exception(f"Error harvesting job {job.id}: {e}")
                return False

    def handle_job_timeout(self, job: ContainerJob):
        """Handle a job that has timed out"""
        from django.utils import timezone

        self.stdout.write(
            self.style.WARNING(
                f"Job {job.id} timed out after {job.template.timeout_seconds} seconds"
            )
        )

        try:
            # Stop the execution using appropriate method
            if job.executor_type == "docker" or not job.executor_type:
                # Use legacy docker service
                docker_service.stop_container(job)
                # Try to collect any logs before cleanup
                try:
                    docker_service._collect_execution_data(job)
                except Exception:
                    pass  # Don't fail if log collection fails
            else:
                # Use executor factory for non-docker executors
                try:
                    executor = self.executor_factory.get_executor(job.docker_host)
                    execution_id = job.get_execution_identifier()
                    executor.cleanup(execution_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup timed out job {job.id}: {e}")

            # Mark as timed out
            job.status = "timeout"
            job.completed_at = timezone.now()
            job.save()

        except Exception as e:
            logger.exception(f"Error handling timeout for job {job.id}: {e}")

    def mark_job_failed(self, job: ContainerJob, error_message: str):
        """Mark a job as failed with error message"""
        try:
            with transaction.atomic():
                job.status = "failed"
                job.completed_at = timezone.now()
                job.save()

                # Create or update execution record with error
                from container_manager.models import ContainerExecution

                execution, created = ContainerExecution.objects.get_or_create(job=job)
                execution.docker_log = f"ERROR: {error_message}"
                execution.save()

        except Exception as e:
            logger.exception(f"Failed to mark job {job.id} as failed: {e}")
