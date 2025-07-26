"""
Django management command to clean up old containers.

This command removes old Docker containers based on configurable retention periods.
It can be run manually or scheduled via cron/systemd timers.
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from container_manager.docker_service import docker_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clean up old Docker containers based on retention policies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--orphaned-hours",
            type=int,
            default=24,
            help="Hours after which to clean orphaned containers (default: 24)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleaned up without actually removing containers",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force cleanup even if disabled in settings",
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
                total_cleaned = docker_service.cleanup_old_containers(
                    orphaned_hours=orphaned_hours
                )

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
                logger.error(f"Container cleanup error: {e}")
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
        ).exclude(container_id="")

        orphaned_count = orphaned_jobs.count()

        self.stdout.write("\nOrphaned container cleanup preview:")
        self.stdout.write(f"  Orphaned containers to clean: {orphaned_count}")

        if orphaned_count > 0:
            self.stdout.write("\nOrphaned containers that would be removed:")

            for job in orphaned_jobs[:10]:  # Show first 10
                self.stdout.write(
                    f"  - {job.id} ({job.template.name}) - "
                    f"{job.status} {job.completed_at}"
                )

            if orphaned_count > 10:
                self.stdout.write(
                    f"  ... and {orphaned_count - 10} more orphaned containers"
                )

        self.stdout.write("\nTo actually perform cleanup, run without --dry-run")
