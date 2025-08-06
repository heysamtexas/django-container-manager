"""
Django management command to clean up old containers.

This command removes old Docker containers based on configurable retention periods.
It can be run manually or scheduled via cron/systemd timers.
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

# docker_service has been deprecated - cleanup functionality temporarily disabled

logger = logging.getLogger(__name__)

# Constants
ORPHANED_CONTAINERS_DISPLAY_LIMIT = 10  # Limit for displaying orphaned containers list


class Command(BaseCommand):
    help = """
    Clean up old Docker containers based on retention policies.

    This command removes old container artifacts to free up disk space and
    maintain system performance. It identifies containers from completed
    jobs that exceed configured retention periods.

    WARNING: Currently disabled due to service refactoring. This command
    is being updated to work with the new ExecutorFactory system.

    Usage Examples:
        # Preview what would be cleaned (recommended first)
        python manage.py cleanup_containers --dry-run

        # Clean containers older than 48 hours
        python manage.py cleanup_containers --orphaned-hours 48

        # Force cleanup even if disabled in settings
        python manage.py cleanup_containers --force

        # Combine options for careful cleanup
        python manage.py cleanup_containers --dry-run --orphaned-hours 24

    Cleanup Process:
        1. Identify completed jobs older than retention period
        2. Find associated container artifacts
        3. Verify containers are not actively running
        4. Remove containers and associated data
        5. Update database records as needed

    Safety Features:
        - Dry-run mode shows preview without making changes
        - Settings-based enable/disable control
        - Force flag required when cleanup disabled
        - Retention period prevents accidental deletion
        - Active container protection

    Retention Policy:
        - Only processes completed, failed, timeout, or cancelled jobs
        - Respects configured retention periods
        - Preserves recent jobs for debugging
        - Logs all cleanup actions for audit trail

    IMPORTANT: Always test with --dry-run first to verify cleanup scope.
    Consider running this command via cron for automated maintenance.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--orphaned-hours",
            type=int,
            default=24,
            help=(
                "Hours after which to clean orphaned containers (default: 24). "
                "Containers from jobs completed longer than this are eligible. "
                "Minimum recommended: 12 hours for debugging access."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show what would be cleaned up without making changes. "
                "RECOMMENDED: Always run this first to verify cleanup scope. "
                "Safe to run in production for impact assessment."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Force cleanup even if disabled in settings. "
                "WARNING: Use with caution in production environments. "
                "Overrides CLEANUP_ENABLED=False setting."
            ),
        )

    def handle(self, *args, **options):
        """Main command handler"""
        container_settings = getattr(settings, "CONTAINER_MANAGER", {})

        # Check if cleanup is enabled
        cleanup_enabled = container_settings.get("CLEANUP_ENABLED", True)
        if not cleanup_enabled and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Container cleanup is disabled in settings. "
                    "Use --force to override."
                )
            )
            return

        # Get orphaned container cleanup period
        orphaned_hours = options["orphaned_hours"]

        self.stdout.write(
            f"Orphaned container cleanup starting...\n"
            f"Orphaned containers older than: {orphaned_hours} hours\n"
            f"Dry run: {options['dry_run']}"
        )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No containers will be removed")
            )
            # TODO: Implement dry run logic to show what would be cleaned
            self._show_cleanup_preview(orphaned_hours)
        else:
            try:
                # docker_service.cleanup_old_containers was deprecated
                # TODO: Implement cleanup via ExecutorProvider
                self.stdout.write(
                    self.style.WARNING(
                        "Container cleanup temporarily disabled - docker_service has been deprecated"
                    )
                )
                total_cleaned = 0

                if total_cleaned > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully cleaned up {total_cleaned} containers"
                        )
                    )
                else:
                    self.stdout.write("No containers needed cleanup")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Cleanup failed: {e}"))
                logger.exception("Container cleanup error")
                raise

    def _show_cleanup_preview(self, orphaned_hours: int):
        """Show what would be cleaned up in dry run mode"""
        from datetime import timedelta

        from django.utils import timezone

        from container_manager.models import ContainerJob

        cutoff_time = timezone.now() - timedelta(hours=orphaned_hours)

        # Find orphaned containers that would be cleaned
        orphaned_jobs = ContainerJob.objects.filter(
            completed_at__lt=cutoff_time,
            status__in=["completed", "failed", "timeout", "cancelled"],
        ).exclude(execution_id="")

        orphaned_count = orphaned_jobs.count()

        self.stdout.write("\nOrphaned container cleanup preview:")
        self.stdout.write(f"  Orphaned containers to clean: {orphaned_count}")

        if orphaned_count > 0:
            self.stdout.write("\nOrphaned containers that would be removed:")

            for job in orphaned_jobs[:10]:  # Show first 10
                self.stdout.write(
                    f"  - {job.id} ({job.name or 'Unnamed'}) - "
                    f"{job.status} {job.completed_at}"
                )

            if orphaned_count > ORPHANED_CONTAINERS_DISPLAY_LIMIT:
                self.stdout.write(
                    f"  ... and {orphaned_count - ORPHANED_CONTAINERS_DISPLAY_LIMIT} more orphaned containers"
                )

        self.stdout.write("\nTo actually perform cleanup, run without --dry-run")
