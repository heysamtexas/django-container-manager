"""
Django management command to process container jobs.

This command polls the database for pending container jobs and executes them
using the Docker service. It runs continuously until stopped.
"""

import logging
import signal
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from container_manager.executors.exceptions import (
    ExecutorResourceError,
)
from container_manager.executors.factory import ExecutorFactory
from container_manager.models import ContainerJob, ExecutorHost

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Process pending container jobs and manage their execution lifecycle.

    This command handles the core job processing workflow:
    - Discovers pending jobs in the database
    - Launches jobs on available executor hosts
    - Monitors running jobs for completion
    - Harvests logs and results from completed jobs
    - Updates job status throughout the lifecycle

    Usage Examples:
        # Process all pending jobs once
        python manage.py process_container_jobs --single-run

        # Run in continuous mode (daemon-like)
        python manage.py process_container_jobs

        # Process only jobs for specific host
        python manage.py process_container_jobs --host production-docker

        # Limit concurrent jobs and poll faster
        python manage.py process_container_jobs --max-jobs 5 --poll-interval 10

        # Force specific executor type
        python manage.py process_container_jobs --executor-type cloudrun

        # Run cleanup before processing
        python manage.py process_container_jobs --cleanup --cleanup-hours 48

    Job Processing Flow:
        1. Query database for pending jobs
        2. Check executor host availability and capacity
        3. Launch jobs within resource limits
        4. Monitor running jobs for status changes
        5. Harvest completed jobs for logs and exit codes
        6. Update database with final results

    Monitoring and Logging:
        - Progress logged to console and Django logging system
        - Job execution details logged for debugging
        - Resource usage tracked and reported
        - Errors logged with context for troubleshooting

    Signal Handling:
        - SIGTERM: Graceful shutdown, finish current operations
        - SIGINT (Ctrl+C): Immediate shutdown with cleanup

    Exit Codes:
        0: Success, all jobs processed normally
        1: General error (configuration, database, etc.)
        2: Executor error (Docker daemon unavailable, etc.)
        3: Job processing error (job failures, resource limits)

    IMPORTANT: This command should run continuously in production to ensure
    jobs are processed promptly. Use process managers like systemd, supervisor,
    or Docker for reliable operation.
    """

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
            help=(
                "Polling interval in seconds (default: 5). "
                "Lower values increase responsiveness but CPU usage. "
                "Recommended: 5-30 seconds for production."
            ),
        )
        parser.add_argument(
            "--max-jobs",
            type=int,
            default=10,
            help=(
                "Maximum number of concurrent jobs to process (default: 10). "
                "Consider host resources when setting this value. "
                "Higher values may overwhelm the system."
            ),
        )
        parser.add_argument(
            "--host",
            type=str,
            help=(
                "Only process jobs for the specified executor host. "
                "Use host name as configured in ExecutorHost model. "
                "Useful for dedicated processing nodes."
            ),
        )
        parser.add_argument(
            "--single-run",
            action="store_true",
            help=(
                "Process jobs once and exit (don't run continuously). "
                "Useful for testing, debugging, or scheduled execution via cron."
            ),
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help=(
                "Run cleanup of old containers before processing jobs. "
                "WARNING: Currently disabled due to service refactoring. "
                "Use cleanup_containers command separately."
            ),
        )
        parser.add_argument(
            "--cleanup-hours",
            type=int,
            default=24,
            help=(
                "Hours after which to cleanup old containers (default: 24). "
                "Only used with --cleanup flag. Currently non-functional."
            ),
        )
        parser.add_argument(
            "--use-factory",
            action="store_true",
            help=(
                "Use ExecutorFactory for intelligent job routing. "
                "Default: auto-detect from settings. "
                "Enable for multi-executor environments."
            ),
        )
        parser.add_argument(
            "--executor-type",
            type=str,
            help=(
                "Force specific executor type (docker, cloudrun, fargate, mock). "
                "Jobs will only run on hosts matching this type. "
                "Useful for testing specific executors."
            ),
        )

    def handle(self, *args, **options):
        """Main command handler"""
        config = self._parse_and_validate_options(options)

        self._display_startup_info(config)
        self._run_cleanup_if_requested(config)
        self._validate_host_filter(config.get("host_filter"))

        # Run main processing loop
        processed_count, error_count = self._run_processing_loop(config)

        self._display_completion_summary(processed_count, error_count)

    def _parse_and_validate_options(self, options):
        """Parse and validate command options"""
        from ...defaults import get_use_executor_factory

        config = {
            "poll_interval": options["poll_interval"],
            "max_jobs": options["max_jobs"],
            "host_filter": options["host"],
            "single_run": options["single_run"],
            "cleanup": options["cleanup"],
            "cleanup_hours": options["cleanup_hours"],
            "use_factory": options["use_factory"],
            "executor_type": options["executor_type"],
        }

        # Determine if we should use the executor factory
        config["factory_enabled"] = (
            config["use_factory"]
            or get_use_executor_factory()
            or config["executor_type"] is not None
        )

        return config

    def _display_startup_info(self, config):
        """Display startup information and configuration"""
        routing_mode = (
            "ExecutorFactory" if config["factory_enabled"] else "Direct Docker"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting container job processor "
                f"(poll_interval={config['poll_interval']}s, "
                f"max_jobs={config['max_jobs']}, routing={routing_mode})"
            )
        )

        if config["factory_enabled"]:
            self._display_executor_info(config["executor_type"])

    def _display_executor_info(self, executor_type):
        """Display available executor information"""
        available_hosts = ExecutorHost.objects.filter(is_active=True)
        available_executors = list(
            available_hosts.values_list("executor_type", flat=True).distinct()
        )
        self.stdout.write(f"Available executors: {', '.join(available_executors)}")

        if executor_type:
            self.stdout.write(f"Forcing executor type: {executor_type}")

    def _run_cleanup_if_requested(self, config):
        """Run container cleanup if requested"""
        if config["cleanup"]:
            self.stdout.write("Running container cleanup...")
            try:
                # TODO: Implement cleanup via ExecutorProvider
                # For now, skip cleanup as docker_service is deprecated
                self.stdout.write(
                    self.style.WARNING(
                        "Container cleanup temporarily disabled - docker_service deprecated"
                    )
                )
                self.stdout.write(self.style.SUCCESS("Cleanup completed"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Cleanup failed: {e}"))

    def _validate_host_filter(self, host_filter):
        """Validate host filter if provided"""
        if host_filter:
            try:
                docker_host = ExecutorHost.objects.get(name=host_filter, is_active=True)
                self.stdout.write(f"Processing jobs only for host: {docker_host.name}")
            except ExecutorHost.DoesNotExist:
                raise CommandError(
                    f'Docker host "{host_filter}" not found or inactive'
                ) from None

    def _run_processing_loop(self, config):
        """Run the main job processing loop"""
        processed_count = 0
        error_count = 0

        try:
            while not self.should_stop:
                try:
                    cycle_launched, cycle_harvested = self._process_single_cycle(config)
                    processed_count += cycle_launched + cycle_harvested

                    self._report_cycle_results(
                        cycle_launched, cycle_harvested, processed_count, error_count
                    )

                    if config["single_run"]:
                        break

                    time.sleep(config["poll_interval"])

                except Exception as e:
                    error_count += 1
                    logger.exception("Error in processing cycle")
                    self.stdout.write(self.style.ERROR(f"Processing error: {e}"))
                    time.sleep(config["poll_interval"] * 2)  # Sleep longer after errors

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted by user"))

        return processed_count, error_count

    def _process_single_cycle(self, config):
        """Process a single cycle of job launching and monitoring"""
        # Launch phase: Start pending jobs (non-blocking)
        jobs_launched = self.process_pending_jobs(
            config["host_filter"],
            config["max_jobs"],
            config["factory_enabled"],
            config["executor_type"],
        )

        # Monitor phase: Check running jobs and harvest completed ones
        jobs_harvested = self.monitor_running_jobs(config["host_filter"])

        return jobs_launched, jobs_harvested

    def _report_cycle_results(self, launched, harvested, total_processed, total_errors):
        """Report results of a processing cycle"""
        if launched > 0 or harvested > 0:
            self.stdout.write(
                f"Launched {launched} jobs, "
                f"harvested {harvested} jobs "
                f"(total processed: {total_processed}, "
                f"errors: {total_errors})"
            )

    def _display_completion_summary(self, processed_count, error_count):
        """Display final completion summary"""
        self.stdout.write(
            self.style.SUCCESS(
                f"Job processor stopped. "
                f"Processed {processed_count} jobs with {error_count} errors."
            )
        )

    def process_pending_jobs(
        self,
        host_filter: str | None = None,
        max_jobs: int = 10,
        use_factory: bool = False,
        force_executor_type: str | None = None,
    ) -> int:
        """Launch pending jobs and return the number launched"""

        # Get pending jobs
        queryset = (
            ContainerJob.objects.filter(status="pending")
            .select_related("docker_host")
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
                logger.exception(f"Failed to launch job {job.id}")
                self.mark_job_failed(job, str(e))

        return launched

    def launch_single_job(
        self,
        job: ContainerJob,
        use_factory: bool = False,
        force_executor_type: str | None = None,
    ) -> bool:
        """Launch a single container job (non-blocking)"""

        if use_factory:
            return self.launch_job_with_factory(job, force_executor_type)
        else:
            return self.launch_job_with_executor_provider(job)

    def launch_job_with_factory(
        self, job: ContainerJob, force_executor_type: str | None = None
    ) -> bool:
        """Launch job using ExecutorFactory"""
        try:
            # Verify job has docker_host assigned
            if not job.docker_host:
                self.mark_job_failed(job, "Job must have docker_host assigned")
                return False

            # Handle force executor type by finding appropriate host
            if force_executor_type:
                suitable_host = ExecutorHost.objects.filter(
                    executor_type=force_executor_type, is_active=True
                ).first()
                if suitable_host:
                    job.docker_host = suitable_host
                    job.routing_reason = (
                        f"Forced to {force_executor_type} via command line"
                    )
                    job.save()
                else:
                    self.mark_job_failed(
                        job, f"No available {force_executor_type} hosts"
                    )
                    return False

            # Display launch information
            executor_type = job.docker_host.executor_type
            self.stdout.write(
                f"Launching job {job.id} ({job.name or 'unnamed'}) "
                f"using {executor_type} executor on {job.docker_host.name}"
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
            logger.exception(f"No available executors for job {job.id}")
            self.mark_job_failed(job, f"No available executors: {e}")
            return False
        except Exception as e:
            logger.exception(f"Job launch error for {job.id}")
            self.mark_job_failed(job, str(e))
            return False

    def launch_job_with_executor_provider(self, job: ContainerJob) -> bool:
        """Launch job using ExecutorProvider (docker_service removed)"""
        try:
            # Get executor instance and launch job
            executor = self.executor_factory.get_executor(job.docker_host)

            self.stdout.write(
                f"Launching job {job.id} ({job.name or 'unnamed'}) on {job.docker_host.name}"
            )

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

        except Exception as e:
            logger.exception(f"Job launch error for {job.id}")
            self.mark_job_failed(job, str(e))
            return False

    def monitor_running_jobs(self, host_filter: str | None = None) -> int:
        """Monitor running jobs and harvest completed ones using batch status checking"""
        running_jobs = self._get_running_jobs(host_filter)

        if not running_jobs:
            return 0

        # Use batch status checking for better performance
        return self._monitor_jobs_batch(running_jobs)

    def _monitor_jobs_batch(self, running_jobs) -> int:
        """Monitor jobs using batch status checking to avoid N+1 Docker API calls"""
        from collections import defaultdict

        from django.utils import timezone

        # Group jobs by Docker host for batch processing
        jobs_by_host = defaultdict(list)
        for job in running_jobs:
            jobs_by_host[job.docker_host].append(job)

        harvested = 0
        now = timezone.now()

        for host, jobs in jobs_by_host.items():
            if self.should_stop:
                break

            try:
                # Check timeouts first (no Docker API calls needed)
                active_jobs = []
                for job in jobs:
                    if self._job_has_timed_out(job, now):
                        self.handle_job_timeout(job)
                        harvested += 1
                    else:
                        active_jobs.append(job)

                if not active_jobs:
                    continue

                # Batch status check for remaining jobs
                harvested += self._batch_status_check_for_host(host, active_jobs)

            except Exception as e:
                logger.exception(f"Error monitoring jobs for host {host.name}")
                # Mark all jobs as failed for this host
                for job in jobs:
                    if not self._job_has_timed_out(job, now):
                        self.mark_job_failed(job, f"Host monitoring error: {e}")
                        harvested += 1

        return harvested

    def _batch_status_check_for_host(self, host, jobs) -> int:
        """Perform batch status checking for jobs on a single host"""
        try:
            executor = self.executor_factory.get_executor(host)

            # Only do batch checking for Docker executors
            if hasattr(executor, "_get_client") and hasattr(
                executor, "_batch_check_statuses"
            ):
                return executor._batch_check_statuses(jobs, self)
            else:
                # Fallback to individual checks for non-Docker executors
                return self._monitor_jobs_individually(jobs)

        except Exception as e:
            logger.exception(f"Error getting executor for host {host.name}")
            # Mark all jobs as failed
            harvested = 0
            for job in jobs:
                self.mark_job_failed(job, f"Executor error: {e}")
                harvested += 1
            return harvested

    def _monitor_jobs_individually(self, jobs) -> int:
        """Fallback to individual job monitoring (original N+1 approach)"""
        harvested = 0
        for job in jobs:
            if self.should_stop:
                break
            try:
                job_harvested = self._monitor_single_job(job)
                harvested += job_harvested
            except Exception as e:
                logger.exception(f"Error monitoring job {job.id}")
                self.mark_job_failed(job, str(e))
                harvested += 1
        return harvested

    def _get_running_jobs(self, host_filter: str | None = None):
        """Get list of running jobs, optionally filtered by host"""
        queryset = ContainerJob.objects.filter(status="running").select_related(
            "environment_template", "docker_host"
        )

        if host_filter:
            queryset = queryset.filter(docker_host__name=host_filter)

        return list(queryset)

    def _monitor_single_job(self, job: ContainerJob) -> int:
        """Monitor a single job and return 1 if harvested, 0 if still running"""
        from django.utils import timezone

        # Check for timeout first
        if self._job_has_timed_out(job, timezone.now()):
            self.handle_job_timeout(job)
            return 1

        # Check execution status
        status = self.check_job_status(job)
        return self._handle_job_status(job, status)

    def _job_has_timed_out(self, job: ContainerJob, now) -> bool:
        """Check if job has exceeded its timeout"""
        if not job.started_at:
            return False

        running_time = (now - job.started_at).total_seconds()
        return running_time > job.timeout_seconds

    def _handle_job_status(self, job: ContainerJob, status: str) -> int:
        """Handle job based on its current status, return 1 if harvested"""
        if status in ["completed", "exited"]:
            return self._harvest_successful_job(job)
        elif status == "failed":
            self.mark_job_failed(job, "Job execution failed")
            return 1
        elif status == "not-found":
            self.mark_job_failed(job, "Execution not found")
            return 1
        # For 'running' status, continue monitoring
        return 0

    def _harvest_successful_job(self, job: ContainerJob) -> int:
        """Harvest a successfully completed job"""
        success = self.harvest_completed_job(job)
        if success:
            self.stdout.write(self.style.SUCCESS(f"Harvested job {job.id}"))
            return 1
        return 0

    def check_job_status(self, job: ContainerJob) -> str:
        """Check job status using ExecutorProvider"""
        if not job.docker_host:
            return "error"

        try:
            executor = self.executor_factory.get_executor(job.docker_host)
            execution_id = job.get_execution_identifier()
            if not execution_id:
                return "not-found"
            return executor.check_status(execution_id)
        except Exception:
            logger.exception(f"Error checking status for job {job.id}")
            return "error"

    def harvest_completed_job(self, job: ContainerJob) -> bool:
        """Harvest completed job using ExecutorProvider"""
        if not job.docker_host:
            return False

        try:
            executor = self.executor_factory.get_executor(job.docker_host)
            return executor.harvest_job(job)
        except Exception:
            logger.exception(f"Error harvesting job {job.id}")
            return False

    def handle_job_timeout(self, job: ContainerJob):
        """Handle a job that has timed out"""
        from django.utils import timezone

        self.stdout.write(
            self.style.WARNING(
                f"Job {job.id} timed out after {job.timeout_seconds} seconds"
            )
        )

        try:
            # Stop the execution using appropriate method
            if not job.docker_host:
                logger.error(f"Job {job.id} has no docker_host assigned")
                return

            # Use ExecutorProvider for all executor types
            try:
                executor = self.executor_factory.get_executor(job.docker_host)
                execution_id = job.get_execution_identifier()
                if execution_id:
                    executor.cleanup(execution_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup timed out job {job.id}: {e}")

            # Mark as timed out
            job.status = "timeout"
            job.completed_at = timezone.now()
            job.save()

        except Exception:
            logger.exception(f"Error handling timeout for job {job.id}")

    def mark_job_failed(self, job: ContainerJob, error_message: str):
        """Mark a job as failed with error message"""
        try:
            with transaction.atomic():
                job.status = "failed"
                job.completed_at = timezone.now()
                job.save()

                # Set error message on job directly
                if job.docker_log:
                    job.docker_log += f"\nERROR: {error_message}"
                else:
                    job.docker_log = f"ERROR: {error_message}"
                job.save()

        except Exception:
            logger.exception(f"Failed to mark job {job.id} as failed")
