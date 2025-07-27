"""
Django management command for managing individual container jobs.

This command provides utilities for creating, running, and managing
individual container jobs for testing and debugging purposes.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from container_manager.docker_service import docker_service
from container_manager.executors.factory import ExecutorFactory
from container_manager.models import (
    ContainerExecution,
    ContainerJob,
    ContainerTemplate,
    ExecutorHost,
)

# Constants
MAX_NAME_DISPLAY_LENGTH = 19  # Maximum job name length for display before truncation


class Command(BaseCommand):
    help = "Manage individual container jobs"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor_factory = ExecutorFactory()

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest="action", help="Available actions", required=True
        )

        # Create job subcommand
        create_parser = subparsers.add_parser("create", help="Create a new job")
        create_parser.add_argument("template_name", help="Template name")
        create_parser.add_argument("host_name", help="Docker host name")
        create_parser.add_argument("--name", help="Job name")
        create_parser.add_argument("--command", help="Override command")
        create_parser.add_argument(
            "--env", action="append", help="Environment variables (KEY=VALUE format)"
        )
        create_parser.add_argument(
            "--executor-type", help="Preferred executor type (docker, mock, etc.)"
        )

        # Run job subcommand
        run_parser = subparsers.add_parser("run", help="Run a specific job")
        run_parser.add_argument("job_id", help="Job UUID")

        # List jobs subcommand
        list_parser = subparsers.add_parser("list", help="List jobs")
        list_parser.add_argument("--status", help="Filter by status")
        list_parser.add_argument("--host", help="Filter by host name")
        list_parser.add_argument("--limit", type=int, default=20, help="Limit results")

        # Show job subcommand
        show_parser = subparsers.add_parser("show", help="Show job details")
        show_parser.add_argument("job_id", help="Job UUID")
        show_parser.add_argument("--logs", action="store_true", help="Show logs")

        # Cancel job subcommand
        cancel_parser = subparsers.add_parser("cancel", help="Cancel a running job")
        cancel_parser.add_argument("job_id", help="Job UUID")

        # Cleanup subcommand
        cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old containers")
        cleanup_parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Hours after which to cleanup (default: 24)",
        )

        # Status subcommand
        status_parser = subparsers.add_parser("status", help="Show executor status")
        status_parser.add_argument(
            "--capacity", action="store_true", help="Show capacity information"
        )

    def handle(self, *args, **options):
        """Main command handler"""
        action = options["action"]

        if action == "create":
            self.handle_create(options)
        elif action == "run":
            self.handle_run(options)
        elif action == "list":
            self.handle_list(options)
        elif action == "show":
            self.handle_show(options)
        elif action == "cancel":
            self.handle_cancel(options)
        elif action == "cleanup":
            self.handle_cleanup(options)
        elif action == "status":
            self.handle_status(options)

    def handle_create(self, options):
        """Create a new container job"""
        template_name = options["template_name"]
        host_name = options["host_name"]
        job_name = options.get("name", "")
        override_command = options.get("command", "")
        env_vars = options.get("env", [])
        # executor_type is captured but not used in current implementation

        try:
            template = ContainerTemplate.objects.get(name=template_name)
        except ContainerTemplate.DoesNotExist:
            raise CommandError(f'Template "{template_name}" not found') from None

        try:
            docker_host = ExecutorHost.objects.get(name=host_name, is_active=True)
        except ExecutorHost.DoesNotExist:
            raise CommandError(f'Docker host "{host_name}" not found or inactive') from None

        # Parse environment variables
        override_environment = {}
        for env_var in env_vars or []:
            if "=" not in env_var:
                raise CommandError(f"Invalid environment variable format: {env_var}")
            key, value = env_var.split("=", 1)
            override_environment[key] = value

        # Create the job
        job = ContainerJob.objects.create(
            template=template,
            docker_host=docker_host,
            name=job_name,
            override_command=override_command or "",
            override_environment=override_environment,
            created_by=self.get_default_user(),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created job {job.id} ({job.name or job.template.name})"
            )
        )

        # Show job details
        self.show_job_summary(job)

    def handle_run(self, options):
        """Run a specific job"""
        job = self._validate_job_for_run(options["job_id"])
        self.stdout.write(f"Running job {job.id}...")

        try:
            self._ensure_job_has_host(job)
            executor = self.executor_factory.get_executor(job.docker_host)

            self._display_execution_info(job)
            self._execute_and_wait_for_job(job, executor)

            job.refresh_from_db()
            self.show_job_summary(job)

        except Exception as e:
            raise CommandError(f"Failed to run job: {e}") from e

    def _validate_job_for_run(self, job_id):
        """Validate job exists and is in pending status"""
        try:
            job = ContainerJob.objects.get(id=job_id)
        except (ContainerJob.DoesNotExist, ValueError):
            raise CommandError(f'Job "{job_id}" not found') from None

        if job.status != "pending":
            raise CommandError(
                f"Job {job_id} is not in pending status (current: {job.status})"
            )
        return job

    def _ensure_job_has_host(self, job):
        """Ensure job has a docker host assigned via routing"""
        if not job.docker_host:
            selected_host = self.executor_factory.route_job(job)
            if selected_host:
                job.docker_host = selected_host
                job.executor_type = selected_host.executor_type
                job.save()
            else:
                raise CommandError("No available executor hosts")

    def _display_execution_info(self, job):
        """Display execution information to user"""
        self.stdout.write(f"Using {job.executor_type} executor")
        self.stdout.write(f"Selected host: {job.docker_host.name}")

    def _execute_and_wait_for_job(self, job, executor):
        """Execute job and wait for completion"""
        success, execution_id = executor.launch_job(job)

        if success:
            job.set_execution_identifier(execution_id)
            job.save()

            self.stdout.write(
                f"Job launched as {execution_id}, waiting for completion..."
            )

            self._wait_for_job_completion(job)
            self._harvest_and_report_results(job, executor)
        else:
            self.stdout.write(
                self.style.ERROR(f"Job {job.id} failed to launch: {execution_id}")
            )

    def _wait_for_job_completion(self, job):
        """Wait for job to complete using simple polling"""
        import time

        while job.status == "running":
            time.sleep(1)
            job.refresh_from_db()

    def _harvest_and_report_results(self, job, executor):
        """Harvest results and report final status"""
        harvest_success = executor.harvest_job(job)

        if harvest_success and job.status == "completed":
            self.stdout.write(
                self.style.SUCCESS(f"Job {job.id} completed successfully")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Job {job.id} failed or timed out")
            )

    def handle_list(self, options):
        """List container jobs"""
        queryset = ContainerJob.objects.select_related(
            "template", "docker_host"
        ).order_by("-created_at")

        # Apply filters
        if options.get("status"):
            queryset = queryset.filter(status=options["status"])

        if options.get("host"):
            queryset = queryset.filter(docker_host__name=options["host"])

        # Limit results
        limit = options.get("limit", 20)
        jobs = list(queryset[:limit])

        if not jobs:
            self.stdout.write("No jobs found")
            return

        # Display table header
        self.stdout.write("\nContainer Jobs:")
        self.stdout.write("-" * 120)
        self.stdout.write(
            f"{'ID':<36} {'Name':<20} {'Status':<10} {'Executor':<10} {'Host':<15} {'Created':<20}"
        )
        self.stdout.write("-" * 120)

        # Display jobs
        for job in jobs:
            name = job.name or job.template.name
            if len(name) > MAX_NAME_DISPLAY_LENGTH:
                name = name[:MAX_NAME_DISPLAY_LENGTH - 3] + "..."

            executor_type = job.executor_type or "docker"
            self.stdout.write(
                f"{job.id!s:<36} {name:<20} {job.status:<10} {executor_type:<10} "
                f"{job.docker_host.name:<15} "
                f"{job.created_at.strftime('%Y-%m-%d %H:%M'):<20}"
            )

        self.stdout.write("-" * 120)
        self.stdout.write(f"Total: {len(jobs)} jobs")

    def handle_show(self, options):
        """Show detailed job information"""
        job_id = options["job_id"]
        show_logs = options.get("logs", False)

        try:
            job = ContainerJob.objects.select_related("template", "docker_host").get(
                id=job_id
            )
        except (ContainerJob.DoesNotExist, ValueError):
            raise CommandError(f'Job "{job_id}" not found') from None

        self.show_job_details(job, show_logs)

    def handle_cancel(self, options):
        """Cancel a running job"""
        job_id = options["job_id"]

        try:
            job = ContainerJob.objects.get(id=job_id)
        except (ContainerJob.DoesNotExist, ValueError):
            raise CommandError(f'Job "{job_id}" not found') from None

        if job.status not in ["pending", "running"]:
            raise CommandError(f"Cannot cancel job in status: {job.status}")

        self.stdout.write(f"Cancelling job {job.id}...")

        try:
            if job.container_id:
                docker_service.stop_container(job)
                docker_service.remove_container(job, force=True)

            job.status = "cancelled"
            job.save()

            self.stdout.write(
                self.style.SUCCESS(f"Job {job.id} cancelled successfully")
            )

        except Exception as e:
            raise CommandError(f"Failed to cancel job: {e}") from e

    def handle_cleanup(self, options):
        """Cleanup old containers"""
        hours = options.get("hours", 24)

        self.stdout.write(f"Cleaning up containers older than {hours} hours...")

        try:
            docker_service.cleanup_old_containers(orphaned_hours=hours)
            self.stdout.write(self.style.SUCCESS("Cleanup completed"))
        except Exception as e:
            raise CommandError(f"Cleanup failed: {e}") from e

    def show_job_summary(self, job):
        """Show a brief job summary"""
        self.stdout.write(f"  ID: {job.id}")
        self.stdout.write(f"  Name: {job.name or job.template.name}")
        self.stdout.write(f"  Template: {job.template.name}")
        self.stdout.write(f"  Host: {job.docker_host.name}")
        self.stdout.write(f"  Executor: {job.executor_type or 'docker'}")
        self.stdout.write(f"  Status: {job.status}")
        if job.duration:
            self.stdout.write(f"  Duration: {job.duration}")
        # Routing reason removed in simplified system

    def show_job_details(self, job, show_logs=False):
        """Show detailed job information"""
        self._display_job_header(job)
        self._display_basic_job_info(job)
        self._display_execution_identifier(job)
        self._display_job_timestamps(job)
        self._display_command_info(job)
        self._display_execution_details(job, show_logs)

    def _display_job_header(self, job):
        """Display job header information"""
        self.stdout.write(f"\nJob Details: {job.id}")
        self.stdout.write("=" * 50)

    def _display_basic_job_info(self, job):
        """Display basic job information"""
        self.stdout.write(f"Name: {job.name or job.template.name}")
        self.stdout.write(
            f"Template: {job.template.name} ({job.template.docker_image})"
        )
        self.stdout.write(f"Docker Host: {job.docker_host.name}")
        self.stdout.write(f"Executor Type: {job.executor_type or 'docker'}")
        self.stdout.write(f"Status: {job.status}")

    def _display_execution_identifier(self, job):
        """Display appropriate execution ID based on executor type"""
        execution_id = job.get_execution_identifier()
        if job.executor_type == "docker" or not job.executor_type:
            self.stdout.write(f"Container ID: {execution_id or 'N/A'}")
        else:
            self.stdout.write(f"Execution ID: {execution_id or 'N/A'}")

        self.stdout.write(
            f"Exit Code: {job.exit_code if job.exit_code is not None else 'N/A'}"
        )

    def _display_job_timestamps(self, job):
        """Display job timestamp information"""
        self.stdout.write(f"Created: {job.created_at}")
        if job.started_at:
            self.stdout.write(f"Started: {job.started_at}")
        if job.completed_at:
            self.stdout.write(f"Completed: {job.completed_at}")
        if job.duration:
            self.stdout.write(f"Duration: {job.duration}")

    def _display_command_info(self, job):
        """Display command and environment information"""
        command = job.override_command or job.template.command
        if command:
            self.stdout.write(f"Command: {command}")

        if job.override_environment:
            self.stdout.write("Override Environment:")
            for key, value in job.override_environment.items():
                self.stdout.write(f"  {key}={value}")

    def _display_execution_details(self, job, show_logs):
        """Display execution details and logs if available"""
        try:
            execution = job.execution
            self._display_execution_stats(execution)
            if show_logs:
                self._display_execution_logs(execution)
        except ContainerExecution.DoesNotExist:
            self.stdout.write("\nNo execution details available")

    def _display_execution_stats(self, execution):
        """Display execution statistics"""
        self.stdout.write("\nExecution Details:")
        self.stdout.write("-" * 20)

        if execution.max_memory_usage:
            memory_mb = execution.max_memory_usage / (1024 * 1024)
            self.stdout.write(f"Max Memory: {memory_mb:.2f} MB")

        if execution.cpu_usage_percent:
            self.stdout.write(f"CPU Usage: {execution.cpu_usage_percent:.2f}%")

    def _display_execution_logs(self, execution):
        """Display execution logs in various formats"""
        self._display_stdout_logs(execution)
        self._display_clean_output(execution)
        self._display_stderr_logs(execution)
        self._display_docker_logs(execution)

    def _display_stdout_logs(self, execution):
        """Display stdout logs"""
        if execution.stdout_log:
            self.stdout.write("\nStdout Logs:")
            self.stdout.write("-" * 15)
            self.stdout.write(execution.stdout_log)

    def _display_clean_output(self, execution):
        """Display clean output and parsed JSON"""
        clean_output = execution.clean_output
        if clean_output:
            self.stdout.write("\nClean Output (timestamps stripped):")
            self.stdout.write("-" * 40)
            self.stdout.write(clean_output)

            # Try to show parsed JSON in a nice format
            parsed = execution.parsed_output
            if parsed is not None and parsed != clean_output:
                self._display_parsed_output(parsed)

    def _display_parsed_output(self, parsed):
        """Display parsed JSON output"""
        self.stdout.write("\nParsed Output (JSON):")
        self.stdout.write("-" * 25)
        if isinstance(parsed, dict | list):
            import json
            self.stdout.write(json.dumps(parsed, indent=2))
        else:
            self.stdout.write(str(parsed))

    def _display_stderr_logs(self, execution):
        """Display stderr logs"""
        if execution.stderr_log:
            self.stdout.write("\nStderr Logs:")
            self.stdout.write("-" * 15)
            self.stdout.write(execution.stderr_log)

    def _display_docker_logs(self, execution):
        """Display docker logs"""
        if execution.docker_log:
            self.stdout.write("\nDocker Logs:")
            self.stdout.write("-" * 15)
            self.stdout.write(execution.docker_log)

    def get_default_user(self):
        """Get a default user for job creation"""
        try:
            return User.objects.filter(is_superuser=True).first()
        except Exception:
            return None

    def handle_status(self, options):
        """Show executor status"""
        show_capacity = options.get("capacity", False)

        self.stdout.write("\nExecutor Status:")
        self.stdout.write("=" * 50)

        # Get available executors
        available_hosts = ExecutorHost.objects.filter(is_active=True)
        available_executors = list(available_hosts.values_list('executor_type', flat=True).distinct())

        if not available_executors:
            self.stdout.write(self.style.ERROR("No executors available"))
            return

        self.stdout.write(f"Available executors: {', '.join(available_executors)}")

        if show_capacity:
            self.stdout.write("\nCapacity Information:")
            self.stdout.write("-" * 30)

            for executor_type in available_executors:
                hosts_of_type = available_hosts.filter(executor_type=executor_type)
                capacity = {
                    'total_hosts': hosts_of_type.count(),
                    'active_hosts': hosts_of_type.filter(is_active=True).count()
                }

                self.stdout.write(f"\n{executor_type.upper()} Executor:")
                self.stdout.write(f"  Total Hosts: {capacity['total_hosts']}")
                self.stdout.write(f"  Active Hosts: {capacity['active_hosts']}")

                if capacity["total_hosts"] > 0:
                    utilization = (
                        capacity["active_hosts"] / capacity["total_hosts"]
                    ) * 100
                    self.stdout.write(f"  Utilization: {utilization:.1f}%")

        # Show recent job statistics
        self.stdout.write("\nRecent Job Statistics:")
        self.stdout.write("-" * 25)

        from datetime import timedelta

        from django.utils import timezone

        # Last 24 hours
        since = timezone.now() - timedelta(hours=24)
        recent_jobs = ContainerJob.objects.filter(created_at__gte=since)

        if recent_jobs.exists():
            # Group by executor type
            from django.db.models import Count

            stats = (
                recent_jobs.values("executor_type")
                .annotate(total=Count("id"))
                .order_by("executor_type")
            )

            for stat in stats:
                executor_type = stat["executor_type"] or "docker"
                count = stat["total"]
                self.stdout.write(f"  {executor_type}: {count} jobs")

            # Status breakdown
            self.stdout.write("\nStatus breakdown (last 24h):")
            status_stats = (
                recent_jobs.values("status")
                .annotate(total=Count("id"))
                .order_by("status")
            )

            for stat in status_stats:
                status = stat["status"]
                count = stat["total"]
                self.stdout.write(f"  {status}: {count} jobs")
        else:
            self.stdout.write("  No jobs in the last 24 hours")
