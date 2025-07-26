"""
Django management command to process container jobs.

This command polls the database for pending container jobs and executes them
using the Docker service. It runs continuously until stopped.
"""

import logging
import signal
import time
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from container_manager.docker_service import DockerConnectionError, docker_service
from container_manager.models import ContainerJob, DockerHost

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process pending container jobs continuously"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = False
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

    def handle(self, *args, **options):
        """Main command handler"""
        poll_interval = options["poll_interval"]
        max_jobs = options["max_jobs"]
        host_filter = options["host"]
        single_run = options["single_run"]
        cleanup = options["cleanup"]
        cleanup_hours = options["cleanup_hours"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting container job processor "
                f"(poll_interval={poll_interval}s, max_jobs={max_jobs})"
            )
        )

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
                    jobs_launched = self.process_pending_jobs(host_filter, max_jobs)

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
                    logger.error(f"Error in processing cycle: {e}")
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
        self, host_filter: Optional[str] = None, max_jobs: int = 10
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
                success = self.launch_single_job(job)
                if success:
                    launched += 1

            except Exception as e:
                logger.error(f"Failed to launch job {job.id}: {e}")
                self.mark_job_failed(job, str(e))

        return launched

    def launch_single_job(self, job: ContainerJob) -> bool:
        """Launch a single container job (non-blocking)"""

        # Verify Docker host is accessible
        try:
            docker_service.get_client(job.docker_host)
        except DockerConnectionError as e:
            logger.error(f"Cannot connect to Docker host {job.docker_host.name}: {e}")
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
            logger.error(f"Job launch error for {job.id}: {e}")
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

                # Check container status
                status = docker_service.check_container_status(job)

                if status == "exited":
                    # Container finished, harvest results
                    success = docker_service.harvest_completed_job(job)
                    if success:
                        harvested += 1
                        self.stdout.write(self.style.SUCCESS(f"Harvested job {job.id}"))
                elif status == "not-found":
                    # Container disappeared, mark as failed
                    self.mark_job_failed(job, "Container not found")
                    harvested += 1
                elif status == "error":
                    # Error checking status, mark as failed
                    self.mark_job_failed(job, "Error checking container status")
                    harvested += 1
                # For 'running' status, continue monitoring

            except Exception as e:
                logger.error(f"Error monitoring job {job.id}: {e}")
                self.mark_job_failed(job, str(e))
                harvested += 1

        return harvested

    def handle_job_timeout(self, job: ContainerJob):
        """Handle a job that has timed out"""
        from django.utils import timezone

        self.stdout.write(
            self.style.WARNING(
                f"Job {job.id} timed out after {job.template.timeout_seconds} seconds"
            )
        )

        try:
            # Stop the container
            docker_service.stop_container(job)

            # Mark as timed out
            job.status = "timeout"
            job.completed_at = timezone.now()
            job.save()

            # Try to collect any logs before cleanup
            try:
                docker_service._collect_execution_data(job)
            except Exception:
                pass  # Don't fail if log collection fails

        except Exception as e:
            logger.error(f"Error handling timeout for job {job.id}: {e}")

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
            logger.error(f"Failed to mark job {job.id} as failed: {e}")
