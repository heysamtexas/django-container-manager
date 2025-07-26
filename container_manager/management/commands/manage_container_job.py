"""
Django management command for managing individual container jobs.

This command provides utilities for creating, running, and managing
individual container jobs for testing and debugging purposes.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from container_manager.docker_service import docker_service
from container_manager.models import (
    ContainerExecution,
    ContainerJob,
    ContainerTemplate,
    DockerHost,
)


class Command(BaseCommand):
    help = "Manage individual container jobs"

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

    def handle_create(self, options):
        """Create a new container job"""
        template_name = options["template_name"]
        host_name = options["host_name"]
        job_name = options.get("name", "")
        override_command = options.get("command", "")
        env_vars = options.get("env", [])

        try:
            template = ContainerTemplate.objects.get(name=template_name)
        except ContainerTemplate.DoesNotExist:
            raise CommandError(f'Template "{template_name}" not found')

        try:
            docker_host = DockerHost.objects.get(name=host_name, is_active=True)
        except DockerHost.DoesNotExist:
            raise CommandError(f'Docker host "{host_name}" not found or inactive')

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
        job_id = options["job_id"]

        try:
            job = ContainerJob.objects.get(id=job_id)
        except (ContainerJob.DoesNotExist, ValueError):
            raise CommandError(f'Job "{job_id}" not found')

        if job.status != "pending":
            raise CommandError(
                f"Job {job_id} is not in pending status (current: {job.status})"
            )

        self.stdout.write(f"Running job {job.id}...")

        try:
            success = docker_service.execute_job(job)

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"Job {job.id} completed successfully")
                )
            else:
                self.stdout.write(self.style.ERROR(f"Job {job.id} failed or timed out"))

            # Refresh and show updated job
            job.refresh_from_db()
            self.show_job_summary(job)

        except Exception as e:
            raise CommandError(f"Failed to run job: {e}")

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
        self.stdout.write("-" * 100)
        self.stdout.write(
            f"{'ID':<36} {'Name':<20} {'Status':<10} {'Host':<15} {'Created':<20}"
        )
        self.stdout.write("-" * 100)

        # Display jobs
        for job in jobs:
            name = job.name or job.template.name
            if len(name) > 19:
                name = name[:16] + "..."

            self.stdout.write(
                f"{str(job.id):<36} {name:<20} {job.status:<10} "
                f"{job.docker_host.name:<15} "
                f"{job.created_at.strftime('%Y-%m-%d %H:%M'):<20}"
            )

        self.stdout.write("-" * 100)
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
            raise CommandError(f'Job "{job_id}" not found')

        self.show_job_details(job, show_logs)

    def handle_cancel(self, options):
        """Cancel a running job"""
        job_id = options["job_id"]

        try:
            job = ContainerJob.objects.get(id=job_id)
        except (ContainerJob.DoesNotExist, ValueError):
            raise CommandError(f'Job "{job_id}" not found')

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
            raise CommandError(f"Failed to cancel job: {e}")

    def handle_cleanup(self, options):
        """Cleanup old containers"""
        hours = options.get("hours", 24)

        self.stdout.write(f"Cleaning up containers older than {hours} hours...")

        try:
            docker_service.cleanup_old_containers(orphaned_hours=hours)
            self.stdout.write(self.style.SUCCESS("Cleanup completed"))
        except Exception as e:
            raise CommandError(f"Cleanup failed: {e}")

    def show_job_summary(self, job):
        """Show a brief job summary"""
        self.stdout.write(f"  ID: {job.id}")
        self.stdout.write(f"  Name: {job.name or job.template.name}")
        self.stdout.write(f"  Template: {job.template.name}")
        self.stdout.write(f"  Host: {job.docker_host.name}")
        self.stdout.write(f"  Status: {job.status}")
        if job.duration:
            self.stdout.write(f"  Duration: {job.duration}")

    def show_job_details(self, job, show_logs=False):
        """Show detailed job information"""
        self.stdout.write(f"\nJob Details: {job.id}")
        self.stdout.write("=" * 50)

        # Basic info
        self.stdout.write(f"Name: {job.name or job.template.name}")
        self.stdout.write(
            f"Template: {job.template.name} ({job.template.docker_image})"
        )
        self.stdout.write(f"Docker Host: {job.docker_host.name}")
        self.stdout.write(f"Status: {job.status}")
        self.stdout.write(f"Container ID: {job.container_id or 'N/A'}")
        self.stdout.write(
            f"Exit Code: {job.exit_code if job.exit_code is not None else 'N/A'}"
        )

        # Timestamps
        self.stdout.write(f"Created: {job.created_at}")
        if job.started_at:
            self.stdout.write(f"Started: {job.started_at}")
        if job.completed_at:
            self.stdout.write(f"Completed: {job.completed_at}")
        if job.duration:
            self.stdout.write(f"Duration: {job.duration}")

        # Command and environment
        command = job.override_command or job.template.command
        if command:
            self.stdout.write(f"Command: {command}")

        if job.override_environment:
            self.stdout.write("Override Environment:")
            for key, value in job.override_environment.items():
                self.stdout.write(f"  {key}={value}")

        # Execution details
        try:
            execution = job.execution
            self.stdout.write("\nExecution Details:")
            self.stdout.write("-" * 20)

            if execution.max_memory_usage:
                memory_mb = execution.max_memory_usage / (1024 * 1024)
                self.stdout.write(f"Max Memory: {memory_mb:.2f} MB")

            if execution.cpu_usage_percent:
                self.stdout.write(f"CPU Usage: {execution.cpu_usage_percent:.2f}%")

            # Show logs if requested
            if show_logs:
                if execution.stdout_log:
                    self.stdout.write("\nStdout Logs:")
                    self.stdout.write("-" * 15)
                    self.stdout.write(execution.stdout_log)

                # Show clean output for downstream processing
                clean_output = execution.clean_output
                if clean_output:
                    self.stdout.write("\nClean Output (timestamps stripped):")
                    self.stdout.write("-" * 40)
                    self.stdout.write(clean_output)

                    # Try to show parsed JSON in a nice format
                    parsed = execution.parsed_output
                    if parsed is not None and parsed != clean_output:
                        self.stdout.write("\nParsed Output (JSON):")
                        self.stdout.write("-" * 25)
                        if isinstance(parsed, (dict, list)):
                            import json

                            self.stdout.write(json.dumps(parsed, indent=2))
                        else:
                            self.stdout.write(str(parsed))

                if execution.stderr_log:
                    self.stdout.write("\nStderr Logs:")
                    self.stdout.write("-" * 15)
                    self.stdout.write(execution.stderr_log)

                if execution.docker_log:
                    self.stdout.write("\nDocker Logs:")
                    self.stdout.write("-" * 15)
                    self.stdout.write(execution.docker_log)

        except ContainerExecution.DoesNotExist:
            self.stdout.write("\nNo execution details available")

    def get_default_user(self):
        """Get a default user for job creation"""
        try:
            return User.objects.filter(is_superuser=True).first()
        except Exception:
            return None
