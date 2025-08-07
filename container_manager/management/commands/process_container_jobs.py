"""
Django management command to process container jobs.

This command supports two modes:
1. Queue Mode: Processes jobs from the queue system (new)
2. Legacy Mode: Direct job processing (existing behavior)

The command can run continuously or process once and exit.
"""

import logging
import signal
import threading
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from container_manager.executors.exceptions import (
    ExecutorResourceError,
)
from container_manager.executors.factory import ExecutorFactory
from container_manager.models import ContainerJob, ExecutorHost
from container_manager.queue import queue_manager

logger = logging.getLogger(__name__)


EXAMPLES = """
Examples:

Queue Mode (default - recommended):
  %(prog)s                                          # Continuous queue processing (NEW DEFAULT)
  %(prog)s --once                                   # Process queue once and exit
  %(prog)s --max-concurrent=10 --poll-interval=5   # Custom concurrency and polling
  %(prog)s --dry-run                                # See what would be processed
  %(prog)s --graceful-shutdown                      # Enhanced shutdown handling

Legacy Mode (deprecated):
  %(prog)s --legacy-mode                            # ⚠️  DEPRECATED: Use legacy processing
  %(prog)s --legacy-mode --single-run               # ⚠️  DEPRECATED: Process pending jobs once
  %(prog)s --legacy-mode --host=docker-host         # ⚠️  DEPRECATED: Process specific host

Operational:
  kill -USR1 <pid>                                  # Get queue status (queue mode)
  kill -TERM <pid>                                  # Graceful shutdown
"""


class Command(BaseCommand):
    help = """
    Process container jobs using the intelligent queue system (default) or legacy processing.

    QUEUE MODE (Default):
        Uses the queue management system for intelligent job processing with
        priority handling, retry logic, and efficient resource utilization.

        Features:
        - Priority-based job selection
        - Automatic retry with exponential backoff
        - Concurrency control and resource management
        - Graceful shutdown handling
        - Real-time metrics and monitoring

    LEGACY MODE (⚠️  Deprecated):
        Traditional direct job processing maintained for backward compatibility only.
        This mode will be removed in a future version. Please migrate to queue mode.

    Queue Mode Workflow:
        1. Fetch ready jobs from queue (priority ordered)
        2. Launch jobs within concurrency limits
        3. Monitor job completion and handle retries
        4. Update queue state and metrics
        5. Repeat until shutdown or --once mode

    Legacy Mode Workflow:
        1. Query database for pending/running jobs
        2. Check executor host availability
        3. Launch jobs within resource limits
        4. Monitor and harvest completed jobs
        5. Update job status and logs

    Signal Handling:
        - SIGTERM: Graceful shutdown, finish current operations
        - SIGINT (Ctrl+C): Immediate shutdown with cleanup
        - SIGUSR1: Status report (queue mode only)

    Exit Codes:
        0: Success, jobs processed normally
        1: Configuration or validation error
        2: Execution or processing error
    """

    def create_parser(self, prog_name, subcommand, **kwargs):
        """Add usage examples to help output"""
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.epilog = EXAMPLES % {"prog": f"{prog_name} {subcommand}"}
        return parser

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = False
        self.executor_factory = ExecutorFactory()
        self.shutdown_event = threading.Event()
        self.queue_mode = False

    def add_arguments(self, parser):
        # Processing Mode (Queue mode is now default)
        parser.add_argument(
            "--legacy-mode",
            action="store_true",
            help=(
                "⚠️  DEPRECATED: Run in legacy processing mode. "
                "This mode is deprecated and will be removed in a future version. "
                "Use queue mode (default) instead for better performance and reliability."
            ),
        )
        parser.add_argument(
            "--queue-mode",
            action="store_true",
            help=(
                "Run in queue processing mode (now the default). "
                "Uses intelligent queue management with priority handling, "
                "retry logic, and efficient resource utilization. "
                "This flag is now optional since queue mode is the default."
            ),
        )

        parser.add_argument(
            "--max-concurrent",
            type=int,
            default=5,
            help=(
                "Maximum concurrent jobs when in queue mode (default: 5). "
                "Controls resource utilization and system load."
            ),
        )

        parser.add_argument(
            "--once",
            action="store_true",
            help=(
                "Process queue once and exit (don't run continuously). "
                "Useful for testing, debugging, or scheduled execution."
            ),
        )

        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help=(
                "Timeout in seconds for job acquisition (default: 30). "
                "How long to wait for database locks in queue mode."
            ),
        )

        parser.add_argument(
            "--shutdown-timeout",
            type=int,
            default=30,
            help=(
                "Timeout in seconds for graceful shutdown (default: 30). "
                "How long to wait for running jobs to complete during shutdown."
            ),
        )

        parser.add_argument(
            "--graceful-shutdown",
            action="store_true",
            help=(
                "Use enhanced graceful shutdown with job completion tracking. "
                "Recommended for production deployments with long-running jobs."
            ),
        )

        # Shared Arguments
        parser.add_argument(
            "--poll-interval",
            type=int,
            default=10,
            help=(
                "Polling interval in seconds (default: 10). "
                "How often to check for new jobs."
            ),
        )

        # Legacy Mode Arguments (DEPRECATED - backward compatibility only)
        parser.add_argument(
            "--max-jobs",
            type=int,
            default=10,
            help=(
                "⚠️  DEPRECATED: Maximum concurrent jobs in legacy mode (default: 10). "
                "Use --max-concurrent instead (works in both modes)."
            ),
        )
        parser.add_argument(
            "--host",
            type=str,
            help=(
                "⚠️  DEPRECATED: Only process jobs for specific executor host (legacy mode only). "
                "This option will be removed. Queue mode processes all hosts intelligently."
            ),
        )
        parser.add_argument(
            "--single-run",
            action="store_true",
            help=(
                "⚠️  DEPRECATED: Process jobs once and exit in legacy mode. "
                "Use --once instead (works in both modes)."
            ),
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help=(
                "⚠️  DEPRECATED: Run cleanup of old containers (legacy mode only). "
                "WARNING: Currently disabled. Use cleanup_containers command separately."
            ),
        )
        parser.add_argument(
            "--cleanup-hours",
            type=int,
            default=24,
            help=(
                "⚠️  DEPRECATED: Hours for cleanup threshold (default: 24). "
                "Only used with deprecated --cleanup flag."
            ),
        )
        parser.add_argument(
            "--use-factory",
            action="store_true",
            help=(
                "⚠️  DEPRECATED: Use ExecutorFactory for job routing (legacy mode only). "
                "Queue mode always uses intelligent routing."
            ),
        )
        parser.add_argument(
            "--executor-type",
            type=str,
            help=(
                "⚠️  DEPRECATED: Force specific executor type (legacy mode only). "
                "Queue mode processes all executor types intelligently."
            ),
        )

        # Common Arguments
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show what would be processed without actually doing it. "
                "Works in both queue mode and legacy mode."
            ),
        )

        parser.add_argument(
            "--verbose",
            action="store_true",
            help=(
                "Enable verbose output and debug logging. "
                "Useful for troubleshooting and monitoring."
            ),
        )

    def handle(self, *args, **options):
        """Main command handler"""
        # Set up logging level
        if options["verbose"]:
            logging.getLogger("container_manager").setLevel(logging.DEBUG)

        # Validate arguments
        self._validate_arguments(options)

        # Set mode flag for signal handlers
        # Determine processing mode (queue mode is now default)
        use_legacy = options["legacy_mode"]
        use_queue = not use_legacy  # Queue mode unless explicitly requested legacy

        self.queue_mode = use_queue

        # Show deprecation warnings
        if use_legacy:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  DEPRECATED: Legacy mode is deprecated and will be removed in a future version. "
                    "Please migrate to queue mode (default) for better performance and reliability."
                )
            )

        # Warn about deprecated arguments
        deprecated_args = {
            "host": "--host",
            "single_run": "--single-run",
            "cleanup": "--cleanup",
            "cleanup_hours": "--cleanup-hours",
            "use_factory": "--use-factory",
            "executor_type": "--executor-type",
            "max_jobs": "--max-jobs",
        }

        for arg, flag in deprecated_args.items():
            if options.get(arg):
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  DEPRECATED: {flag} is deprecated and may not work correctly."
                    )
                )

        try:
            if use_queue:
                self._setup_queue_signal_handlers()
                self._handle_queue_mode(options)
            else:
                self._setup_legacy_signal_handlers()
                self._handle_legacy_mode(options)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted by user"))
        except Exception as e:
            logger.exception(f"Command failed: {e}")
            raise CommandError(f"Command failed: {e}") from e

    def _validate_arguments(self, options):
        """Validate command arguments"""
        # Check for conflicting mode arguments
        if options["legacy_mode"] and options["queue_mode"]:
            raise CommandError("Cannot specify both --legacy-mode and --queue-mode")

        # Validate legacy mode conflicts (now using queue mode as default)
        use_legacy = options["legacy_mode"]
        if not use_legacy:  # Queue mode (default)
            conflicting_args = [
                "host",
                "single_run",
                "cleanup",
                "use_factory",
                "executor_type",
            ]
            for arg in conflicting_args:
                if options.get(arg):
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  Warning: {arg.replace('_', '-')} is a legacy-mode argument but queue mode is active. "
                            f"This argument will be ignored. Use --legacy-mode if you need legacy features."
                        )
                    )
                    options[arg] = None  # Disable the conflicting argument

        # Validate ranges
        if options["max_concurrent"] < 1:
            raise CommandError("--max-concurrent must be at least 1")

        if options["max_jobs"] < 1:
            raise CommandError("--max-jobs must be at least 1")

        if options["poll_interval"] < 1:
            raise CommandError("--poll-interval must be at least 1")

        if options["timeout"] < 1:
            raise CommandError("--timeout must be at least 1")

        if options["shutdown_timeout"] < 1:
            raise CommandError("--shutdown-timeout must be at least 1")

    def _setup_queue_signal_handlers(self):
        """Set up signal handlers for queue mode"""

        def shutdown_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.stdout.write(
                self.style.WARNING(
                    f"Received {signal_name}, shutting down gracefully..."
                )
            )
            self.shutdown_event.set()

        def status_handler(signum, frame):
            """Handle SIGUSR1 for status reporting"""
            try:
                metrics = queue_manager.get_worker_metrics()
                self.stdout.write(f"Queue Status: {metrics}")
            except Exception as e:
                self.stdout.write(f"Error getting queue status: {e}")

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        # Only set up SIGUSR1 on Unix systems
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, status_handler)

    def _setup_legacy_signal_handlers(self):
        """Set up signal handlers for legacy mode (original behavior)"""

        def signal_handler(signum, frame):
            self.stdout.write(
                self.style.WARNING(
                    f"Received signal {signum}, shutting down gracefully..."
                )
            )
            self.should_stop = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _handle_queue_mode(self, options):
        """Handle queue processing mode"""
        max_concurrent = options["max_concurrent"]
        poll_interval = options["poll_interval"]
        once = options["once"]
        dry_run = options["dry_run"]
        timeout = options["timeout"]
        shutdown_timeout = options["shutdown_timeout"]
        graceful_shutdown = options["graceful_shutdown"]

        mode_type = "graceful" if graceful_shutdown else "basic"
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting queue processor ({mode_type} shutdown, max_concurrent={max_concurrent}, "
                f"poll_interval={poll_interval}s, once={once})"
            )
        )

        if dry_run:
            self._dry_run_queue_mode(options)
            return

        if once:
            # Single queue processing run
            result = queue_manager.launch_next_batch(
                max_concurrent=max_concurrent, timeout=timeout
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed queue: launched {result['launched']} jobs"
                )
            )

            if result["errors"]:
                self.stdout.write(
                    self.style.WARNING(f"Encountered {len(result['errors'])} errors:")
                )
                for error in result["errors"]:
                    self.stdout.write(f"  - {error}")

            return
        else:
            # Continuous queue processing - choose method based on graceful shutdown option
            try:
                if graceful_shutdown:
                    # Use enhanced graceful shutdown with job completion tracking
                    stats = queue_manager.process_queue_with_graceful_shutdown(
                        max_concurrent=max_concurrent,
                        poll_interval=poll_interval,
                        shutdown_timeout=shutdown_timeout,
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Graceful queue processor finished. "
                            f"Processed {stats['iterations']} iterations, "
                            f"launched {stats['jobs_launched']} jobs"
                        )
                    )

                    if stats["clean_shutdown"]:
                        self.stdout.write(
                            self.style.SUCCESS("Clean shutdown completed")
                        )
                    elif stats.get("jobs_interrupted", 0) > 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Forced shutdown with {stats['jobs_interrupted']} jobs interrupted"
                            )
                        )
                else:
                    # Use basic continuous processing
                    stats = queue_manager.process_queue_continuous(
                        max_concurrent=max_concurrent,
                        poll_interval=poll_interval,
                        shutdown_event=self.shutdown_event,
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Queue processor finished. "
                            f"Processed {stats['iterations']} iterations, "
                            f"launched {stats['jobs_launched']} jobs"
                        )
                    )

                # Report errors for both modes
                if stats["errors"]:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Encountered {len(stats['errors'])} errors during processing"
                        )
                    )

            except Exception as e:
                logger.exception("Error in continuous queue processing")
                raise CommandError(f"Queue processing failed: {e}") from e

    def _handle_legacy_mode(self, options):
        """Handle legacy job processing mode (original behavior)"""
        config = self._parse_and_validate_options(options)

        self._display_startup_info(config)
        self._run_cleanup_if_requested(config)
        self._validate_host_filter(config.get("host_filter"))

        if options["dry_run"]:
            self._dry_run_legacy_mode(config)
            return

        # Run main processing loop
        processed_count, error_count = self._run_processing_loop(config)

        self._display_completion_summary(processed_count, error_count)

    def _dry_run_queue_mode(self, options):
        """Show what would be processed in queue mode without actually doing it"""
        metrics = queue_manager.get_worker_metrics()

        self.stdout.write("Queue Status (dry run):")
        self.stdout.write(f"  Ready to launch now: {metrics['ready_now']}")
        self.stdout.write(f"  Scheduled for future: {metrics['scheduled_future']}")
        self.stdout.write(f"  Currently running: {metrics['running']}")
        self.stdout.write(f"  Launch failed: {metrics['launch_failed']}")

        # Show next jobs that would be processed
        ready_jobs = queue_manager.get_ready_jobs(limit=options["max_concurrent"])

        if ready_jobs:
            self.stdout.write(
                f"\nNext {len(ready_jobs)} job(s) that would be launched:"
            )
            for job in ready_jobs:
                scheduled_str = ""
                if job.scheduled_for:
                    scheduled_str = (
                        f", scheduled={job.scheduled_for.strftime('%H:%M:%S')}"
                    )
                self.stdout.write(
                    f"  - Job {job.id}: {job.name or 'unnamed'} "
                    f"(priority={job.priority}, "
                    f"queued={job.queued_at.strftime('%H:%M:%S')}{scheduled_str})"
                )
        else:
            self.stdout.write("\nNo jobs ready for launch")

    def _dry_run_legacy_mode(self, config):
        """Show what would be processed in legacy mode"""
        # Get pending jobs using legacy logic
        queryset = (
            ContainerJob.objects.filter(status="pending")
            .select_related("docker_host")
            .order_by("created_at")
        )

        if config.get("host_filter"):
            queryset = queryset.filter(docker_host__name=config["host_filter"])

        queryset = queryset.filter(docker_host__is_active=True)
        pending_jobs = list(queryset[: config.get("max_jobs", 10)])

        self.stdout.write(
            f"Legacy Mode - Would process {len(pending_jobs)} pending jobs:"
        )
        for job in pending_jobs:
            self.stdout.write(
                f"  - Job {job.id}: {job.name or 'unnamed'} on {job.docker_host.name}"
            )

        # Also show running jobs that would be monitored
        running_jobs = ContainerJob.objects.filter(status="running")
        if config.get("host_filter"):
            running_jobs = running_jobs.filter(docker_host__name=config["host_filter"])

        running_count = running_jobs.count()
        self.stdout.write(f"\nWould monitor {running_count} running jobs")

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

            # Mark as timed out using proper state transitions
            if job.status == "running":
                job.transition_to("timeout", save=True)
            else:
                # If not running, transition through running first
                job.transition_to("running", save=True)
                job.transition_to("timeout", save=True)

            # Update completion time
            job.completed_at = timezone.now()
            job.save(update_fields=["completed_at"])

        except Exception:
            logger.exception(f"Error handling timeout for job {job.id}")

    def mark_job_failed(self, job: ContainerJob, error_message: str):
        """Mark a job as failed with error message using proper state transitions"""
        try:
            with transaction.atomic():
                # Use proper state transitions based on current status
                original_status = job.status

                if job.status == "pending":
                    # pending -> running -> failed (required transition path)
                    job.transition_to("running", save=True)  # Save intermediate step
                    job.transition_to("failed", save=True)  # Save final state
                elif job.status in ["queued", "launching", "running", "retrying"]:
                    # These can transition directly to failed
                    job.transition_to("failed", save=True)
                elif job.status == "failed":
                    # Already failed, nothing to do for status
                    pass
                else:
                    # For other statuses, log warning but don't change status
                    self.stdout.write(
                        self.style.WARNING(
                            f"Cannot mark job {job.id} as failed from status '{job.status}'"
                        )
                    )
                    return

                # Update completion time if we changed status to failed
                if original_status != "failed" and job.status == "failed":
                    job.completed_at = timezone.now()
                    job.save(update_fields=["completed_at"])

                # Set error message on job directly
                if job.docker_log:
                    job.docker_log += f"\nERROR: {error_message}"
                else:
                    job.docker_log = f"ERROR: {error_message}"
                job.save(update_fields=["docker_log"])

        except Exception:
            logger.exception(f"Failed to mark job {job.id} as failed")
