import logging
from typing import ClassVar

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Avg, Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .executors.exceptions import ExecutorConnectionError
from .executors.factory import ExecutorProvider
from .models import (
    ContainerJob,
    EnvironmentVariableTemplate,
    ExecutorHost,
)
from .queue import queue_manager

logger = logging.getLogger(__name__)


@admin.register(ExecutorHost)
class ExecutorHostAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "executor_type",
        "host_type",
        "connection_string",
        "weight",
        "is_active",
        "connection_status",
        "created_at",
    )
    list_filter = ("executor_type", "host_type", "is_active", "tls_enabled")
    search_fields = ("name", "connection_string")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "executor_type",
                    "host_type",
                    "connection_string",
                    "is_active",
                    "weight",
                )
            },
        ),
        (
            "Executor Configuration",
            {"fields": ("executor_config", "max_concurrent_jobs")},
        ),
        ("Docker Configuration", {"fields": ("auto_pull_images",)}),
        (
            "TLS Configuration",
            {"fields": ("tls_enabled", "tls_verify"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions: ClassVar = ["test_connection"]

    def connection_status(self, obj):
        """Show connection status with colored indicator"""
        if not obj.is_active:
            return format_html('<span style="color: gray;">●</span> Inactive')

        try:
            provider = ExecutorProvider()
            executor = provider.get_executor(obj)  # Check if executor can be created

            # Actually test the connection by checking health status
            health = executor.get_health_status()
            if health.get("healthy", False):
                return format_html('<span style="color: green;">●</span> Connected')
            else:
                error_msg = health.get("error", "Unknown error")[
                    :50
                ]  # Truncate long errors
                return format_html(
                    '<span style="color: red;">●</span> Failed: {}', error_msg
                )

        except ExecutorConnectionError:
            return format_html('<span style="color: red;">●</span> Connection Failed')
        except Exception as e:
            return format_html(
                '<span style="color: red;">●</span> Error: {}', str(e)[:50]
            )

    connection_status.short_description = "Status"

    def test_connection(self, request, queryset):
        """Test connection to selected executor hosts"""
        provider = ExecutorProvider()
        for host in queryset:
            try:
                executor = provider.get_executor(
                    host
                )  # Check if executor can be created

                # Actually test the connection
                health = executor.get_health_status()
                if health.get("healthy", False):
                    response_time = health.get("response_time", 0)
                    messages.success(
                        request,
                        f"Connection to {host.name} successful (response: {response_time:.3f}s)",
                    )
                else:
                    error_msg = health.get("error", "Unknown error")
                    messages.error(
                        request, f"Connection to {host.name} failed: {error_msg}"
                    )

            except ExecutorConnectionError as e:
                messages.error(request, f"Connection to {host.name} failed: {e}")
            except Exception as e:
                messages.error(request, f"Connection to {host.name} failed: {e}")

    test_connection.short_description = "Test connection to selected hosts"


@admin.register(EnvironmentVariableTemplate)
class EnvironmentVariableTemplateAdmin(admin.ModelAdmin):
    formfield_overrides: ClassVar = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(attrs={"rows": 10, "cols": 80})
        },
    }

    list_display = (
        "name",
        "description",
        "created_by",
        "created_at",
        "updated_at",
    )
    list_filter = ("created_at", "created_by")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description")},
        ),
        (
            "Environment Variables",
            {
                "fields": ("environment_variables_text",),
                "description": "Enter environment variables one per line in KEY=value format. Comments starting with # are ignored.",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ContainerTemplateAdmin removed - templates merged into ContainerJob
# @admin.register(ContainerTemplate)
# class ContainerTemplateAdmin(admin.ModelAdmin):
#     formfield_overrides: ClassVar = {
#         models.TextField: {
#             "widget": admin.widgets.AdminTextareaWidget(attrs={"rows": 8, "cols": 80})
#         },
#     }
#     list_display = (
#         "name",
#         "docker_image",
#         "memory_limit",
#         "cpu_limit",
#         "timeout_seconds",
#         "auto_remove",
#         "created_at",
#     )
#     list_filter = ("auto_remove", "created_at", "created_by")
#     search_fields = ("name", "docker_image", "description")
#     readonly_fields = ("created_at", "updated_at")

# ContainerTemplateAdmin fieldsets and methods removed


class QueueStatusFilter(admin.SimpleListFilter):
    """Custom filter for queue status"""

    title = "Queue Status"
    parameter_name = "queue_status"

    def lookups(self, request, model_admin):
        return [
            ("not_queued", "Not Queued"),
            ("queued", "Queued (Ready)"),
            ("scheduled", "Scheduled (Future)"),
            ("launched", "Launched"),
            ("launch_failed", "Launch Failed"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "not_queued":
            return queryset.filter(queued_at__isnull=True)
        elif self.value() == "queued":
            return queryset.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=models.F("max_retries"),
            ).filter(
                models.Q(scheduled_for__isnull=True)
                | models.Q(scheduled_for__lte=timezone.now())
            )
        elif self.value() == "scheduled":
            return queryset.filter(
                scheduled_for__isnull=False,
                scheduled_for__gt=timezone.now(),
                launched_at__isnull=True,
            )
        elif self.value() == "launched":
            return queryset.filter(launched_at__isnull=False)
        elif self.value() == "launch_failed":
            return queryset.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__gte=models.F("max_retries"),
            )
        return queryset


@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_name",
        "queue_status_display",
        "execution_status_display",
        "priority_display",
        "docker_image",
        "docker_host",
        "created_at_short",
        "queued_at_short",
        "launched_at_short",
        "retry_count",
        "duration_display",
    )
    list_filter = (
        "status",
        "priority",
        QueueStatusFilter,
        "docker_host",
        "created_at",
        "queued_at",
        "launched_at",
        "retry_count",
    )
    search_fields = (
        "id",
        "name",
        "docker_image",
        "docker_host__name",
        "command",
    )
    readonly_fields = (
        "id",
        "execution_id",
        "exit_code",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
        "launched_at",
        "queued_at",
        "last_error_at",
        "queue_status_detail",
        "duration_display",
        "executor_metadata_display",
        "max_memory_usage",
        "cpu_usage_percent",
        "stdout_log",
        "stderr_log",
        "docker_log",
        "clean_output",
    )

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("id", "name", "docker_image", "docker_host", "priority")},
        ),
        (
            "Queue Information",
            {
                "fields": (
                    "queue_status_detail",
                    "queued_at",
                    "scheduled_for",
                    "launched_at",
                    "retry_count",
                    "max_retries",
                    "retry_strategy",
                    "last_error",
                    "last_error_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Execution Status",
            {
                "fields": (
                    "status",
                    "exit_code",
                    "started_at",
                    "completed_at",
                    "duration_display",
                ),
            },
        ),
        (
            "Container Configuration",
            {
                "fields": ("command", "environment_template", "network_configuration"),
                "classes": ("collapse",),
            },
        ),
        (
            "Execution Overrides",
            {
                "fields": ("override_environment",),
                "classes": ("collapse",),
            },
        ),
        (
            "Executor Configuration",
            {
                "fields": ("executor_metadata",),
                "classes": ("collapse",),
            },
        ),
        (
            "Resource Usage",
            {
                "fields": ("max_memory_usage", "cpu_usage_percent"),
                "classes": ("collapse",),
            },
        ),
        (
            "Logs",
            {
                "fields": ("stdout_log", "stderr_log", "docker_log", "clean_output"),
                "classes": ("collapse",),
            },
        ),
        (
            "Multi-Executor Data",
            {
                "fields": ("executor_metadata_display",),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions: ClassVar = [
        "create_job",
        "start_job_multi",
        "stop_job_multi",
        "restart_job_multi",
        "cancel_job_multi",
        "export_job_data",
        # New queue management actions
        "queue_selected_jobs",
        "dequeue_selected_jobs",
        "retry_failed_jobs",
        "set_high_priority",
        "set_normal_priority",
        "set_low_priority",
    ]

    def job_name(self, obj):
        return obj.name or "Unnamed Job"

    job_name.short_description = "Name"

    def duration_display(self, obj):
        duration = obj.duration
        if duration:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "-"

    duration_display.short_description = "Duration"

    def get_executor_type(self, obj):
        """Display executor type from docker_host"""
        if obj.docker_host:
            return obj.docker_host.executor_type
        return "No Host"

    get_executor_type.short_description = "Executor Type"

    def queue_status_display(self, obj):
        """Display queue status with color coding"""
        status = obj.queue_status

        # Define colors and icons for different statuses
        status_config = {
            "not_queued": {"color": "#6c757d", "icon": "○", "label": "Not Queued"},
            "queued": {"color": "#007bff", "icon": "⏳", "label": "Queued"},
            "scheduled": {"color": "#fd7e14", "icon": "📅", "label": "Scheduled"},
            "launched": {"color": "#28a745", "icon": "🚀", "label": "Launched"},
            "launch_failed": {
                "color": "#dc3545",
                "icon": "❌",
                "label": "Launch Failed",
            },
        }

        config = status_config.get(
            status, {"color": "#6c757d", "icon": "?", "label": status.title()}
        )

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            config["color"],
            config["icon"],
            config["label"],
        )

    queue_status_display.short_description = "Queue Status"
    queue_status_display.admin_order_field = "queued_at"

    def execution_status_display(self, obj):
        """Display container execution status"""
        status = obj.status or "not_started"

        status_config = {
            "pending": {"color": "#6c757d", "icon": "⏸"},
            "queued": {"color": "#007bff", "icon": "📋"},
            "retrying": {"color": "#fd7e14", "icon": "🔄"},
            "running": {"color": "#17a2b8", "icon": "▶️"},
            "completed": {"color": "#28a745", "icon": "✅"},
            "failed": {"color": "#dc3545", "icon": "💥"},
            "cancelled": {"color": "#6f42c1", "icon": "⏹"},
            "timeout": {"color": "#dc3545", "icon": "⏰"},
            "not_started": {"color": "#6c757d", "icon": "○"},
        }

        config = status_config.get(status, {"color": "#6c757d", "icon": "?"})

        return format_html(
            '<span style="color: {};">{} {}</span>',
            config["color"],
            config["icon"],
            status.replace("_", " ").title(),
        )

    execution_status_display.short_description = "Execution Status"
    execution_status_display.admin_order_field = "status"

    def priority_display(self, obj):
        """Display priority with visual indicator"""
        priority = obj.priority

        if priority >= 80:
            color = "#dc3545"  # High priority - red
            indicator = "🔥"
        elif priority >= 60:
            color = "#fd7e14"  # Medium-high priority - orange
            indicator = "⬆️"
        elif priority >= 40:
            color = "#28a745"  # Normal priority - green
            indicator = "➡️"
        else:
            color = "#6c757d"  # Low priority - gray
            indicator = "⬇️"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            indicator,
            priority,
        )

    priority_display.short_description = "Priority"
    priority_display.admin_order_field = "priority"

    def created_at_short(self, obj):
        """Short format for created timestamp"""
        if obj.created_at:
            if timezone.now().date() == obj.created_at.date():
                return obj.created_at.strftime("%H:%M:%S")
            else:
                return obj.created_at.strftime("%m/%d %H:%M")
        return "-"

    created_at_short.short_description = "Created"
    created_at_short.admin_order_field = "created_at"

    def queued_at_short(self, obj):
        """Short format for queued timestamp"""
        if obj.queued_at:
            if timezone.now().date() == obj.queued_at.date():
                return obj.queued_at.strftime("%H:%M:%S")
            else:
                return obj.queued_at.strftime("%m/%d %H:%M")
        return "-"

    queued_at_short.short_description = "Queued"
    queued_at_short.admin_order_field = "queued_at"

    def launched_at_short(self, obj):
        """Short format for launched timestamp"""
        if obj.launched_at:
            if timezone.now().date() == obj.launched_at.date():
                return obj.launched_at.strftime("%H:%M:%S")
            else:
                return obj.launched_at.strftime("%m/%d %H:%M")
        return "-"

    launched_at_short.short_description = "Launched"
    launched_at_short.admin_order_field = "launched_at"

    def queue_status_detail(self, obj):
        """Detailed queue status information"""
        if not obj.queued_at:
            return format_html('<em style="color: #6c757d;">Job is not queued</em>')

        details = []

        # Basic queue info
        details.append(
            f"<strong>Status:</strong> {obj.queue_status.replace('_', ' ').title()}"
        )
        details.append(f"<strong>Priority:</strong> {obj.priority}")

        # Timing information
        if obj.queued_at:
            details.append(
                f"<strong>Queued:</strong> {obj.queued_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        if obj.scheduled_for:
            if obj.scheduled_for > timezone.now():
                time_diff = obj.scheduled_for - timezone.now()
                details.append(
                    f"<strong>Scheduled for:</strong> {obj.scheduled_for.strftime('%Y-%m-%d %H:%M:%S')} (in {time_diff})"
                )
            else:
                details.append(
                    f"<strong>Was scheduled for:</strong> {obj.scheduled_for.strftime('%Y-%m-%d %H:%M:%S')} (overdue)"
                )

        if obj.launched_at:
            details.append(
                f"<strong>Launched:</strong> {obj.launched_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Retry information
        if obj.retry_count > 0:
            details.append(
                f"<strong>Retry attempts:</strong> {obj.retry_count}/{obj.max_retries}"
            )

        if obj.last_error and obj.last_error_at:
            details.append(
                f"<strong>Last error:</strong> {obj.last_error_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            details.append(
                f"<strong>Error message:</strong> {obj.last_error[:100]}{'...' if len(obj.last_error) > 100 else ''}"
            )

        return format_html("<br>".join(details))

    queue_status_detail.short_description = "Queue Details"

    def get_queryset(self, request):
        """Optimize queryset for admin list view"""
        return (
            super()
            .get_queryset(request)
            .select_related("docker_host", "environment_template")
        )

    def executor_metadata_display(self, obj):
        """Display executor metadata in readable format"""
        if obj.executor_metadata:
            import json

            formatted_json = json.dumps(obj.executor_metadata, indent=2)
            return format_html("<pre>{}</pre>", formatted_json)
        return "None"

    executor_metadata_display.short_description = "Executor Metadata"

    def get_urls(self):
        """Add custom URLs for AJAX actions and queue management"""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/logs/",
                self.admin_site.admin_view(self.view_logs),
                name="container_manager_containerjob_logs",
            ),
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="container_manager_containerjob_dashboard",
            ),
            # Queue management AJAX endpoints
            path(
                "<int:job_id>/dequeue/",
                self.admin_site.admin_view(self.dequeue_job_view),
                name="container_manager_containerjob_dequeue",
            ),
            path(
                "<int:job_id>/requeue/",
                self.admin_site.admin_view(self.requeue_job_view),
                name="container_manager_containerjob_requeue",
            ),
            path(
                "<int:job_id>/cancel/",
                self.admin_site.admin_view(self.cancel_job_view),
                name="container_manager_containerjob_cancel",
            ),
            path(
                "queue-stats/",
                self.admin_site.admin_view(self.queue_stats_view),
                name="container_manager_containerjob_queue_stats",
            ),
        ]
        return custom_urls + urls

    def view_logs(self, request, object_id):
        """View job logs"""
        job = get_object_or_404(ContainerJob, pk=object_id)

        if not request.user.has_perm("container_manager.view_containerjob"):
            raise PermissionDenied

        logs = {
            "stdout": job.stdout_log,
            "stderr": job.stderr_log,
            "docker": job.docker_log,
        }

        context = {
            "job": job,
            "logs": logs,
            "title": f"Logs for Job {job.id}",
        }

        return render(request, "admin/container_manager/job_logs.html", context)

    def dashboard_view(self, request):
        """Multi-executor dashboard view"""
        # Get executor statistics
        executor_stats = (
            ContainerJob.objects.values("docker_host__executor_type")
            .annotate(
                total_jobs=Count("id"),
                running_jobs=Count("id", filter=models.Q(status="running")),
                completed_jobs=Count("id", filter=models.Q(status="completed")),
                failed_jobs=Count("id", filter=models.Q(status="failed")),
                avg_duration=Avg("duration"),
            )
            .order_by("docker_host__executor_type")
        )

        # Get host information
        hosts = ExecutorHost.objects.filter(is_active=True)
        host_capacity = []
        for host in hosts:
            host_capacity.append(
                {
                    "host": host,
                    "health": "Active",
                }
            )

        # Simplified dashboard - no complex routing decisions or cost tracking

        context = {
            "title": "Multi-Executor Dashboard",
            "executor_stats": executor_stats,
            "host_capacity": host_capacity,
            "opts": self.model._meta,
        }

        return render(request, "admin/multi_executor_dashboard.html", context)

    def queue_selected_jobs(self, request, queryset):
        """Queue selected jobs for execution"""
        if not request.user.has_perm("container_manager.change_containerjob"):
            raise PermissionDenied

        queued_count = 0
        error_count = 0
        errors = []

        for job in queryset:
            try:
                if job.is_queued:
                    continue  # Skip already queued jobs

                if job.status in ["completed", "cancelled"]:
                    errors.append(
                        f"Job {job.id} ({job.name or 'Unnamed'}): Cannot queue {job.status} job"
                    )
                    error_count += 1
                    continue

                queue_manager.queue_job(job)
                queued_count += 1

                logger.info(f"Admin user {request.user.username} queued job {job.id}")

            except Exception as e:
                errors.append(f"Job {job.id} ({job.name or 'Unnamed'}): {e!s}")
                error_count += 1
                logger.error(f"Error queuing job {job.id}: {e}")

        # Provide user feedback
        if queued_count > 0:
            messages.success(request, f"Successfully queued {queued_count} job(s)")

        if error_count > 0:
            messages.warning(request, f"{error_count} job(s) could not be queued")
            for error in errors[:5]:  # Show max 5 errors
                messages.error(request, error)
            if len(errors) > 5:
                messages.error(request, f"... and {len(errors) - 5} more errors")

    queue_selected_jobs.short_description = "📤 Queue selected jobs for execution"

    def dequeue_selected_jobs(self, request, queryset):
        """Remove selected jobs from queue"""
        if not request.user.has_perm("container_manager.change_containerjob"):
            raise PermissionDenied

        dequeued_count = 0
        error_count = 0
        errors = []

        for job in queryset.filter(queued_at__isnull=False, launched_at__isnull=True):
            try:
                queue_manager.dequeue_job(job)
                dequeued_count += 1

                logger.info(f"Admin user {request.user.username} dequeued job {job.id}")

            except Exception as e:
                errors.append(f"Job {job.id} ({job.name or 'Unnamed'}): {e!s}")
                error_count += 1
                logger.error(f"Error dequeuing job {job.id}: {e}")

        if dequeued_count > 0:
            messages.success(
                request, f"Successfully removed {dequeued_count} job(s) from queue"
            )
        else:
            messages.info(request, "No queued jobs found in selection")

        if error_count > 0:
            messages.warning(request, f"{error_count} job(s) could not be dequeued")
            for error in errors[:3]:
                messages.error(request, error)

    dequeue_selected_jobs.short_description = "📥 Remove selected jobs from queue"

    def retry_failed_jobs(self, request, queryset):
        """Retry selected failed jobs"""
        if not request.user.has_perm("container_manager.change_containerjob"):
            raise PermissionDenied

        retried_count = 0
        error_count = 0

        for job in queryset.filter(status__in=["failed", "retrying"]):
            try:
                queue_manager.retry_failed_job(job, reset_count=True)
                retried_count += 1

                logger.info(f"Admin user {request.user.username} retried job {job.id}")

            except Exception as e:
                error_count += 1
                logger.error(f"Error retrying job {job.id}: {e}")
                messages.error(request, f"Job {job.id}: {e!s}")

        if retried_count > 0:
            messages.success(
                request, f"Successfully queued {retried_count} job(s) for retry"
            )
        else:
            messages.info(request, "No failed jobs found in selection")

        if error_count > 0:
            messages.warning(request, f"{error_count} job(s) could not be retried")

    retry_failed_jobs.short_description = "🔄 Retry selected failed jobs"

    def set_high_priority(self, request, queryset):
        """Set selected jobs to high priority"""
        if not request.user.has_perm("container_manager.change_containerjob"):
            raise PermissionDenied

        updated = queryset.update(priority=80)
        messages.success(request, f"Set {updated} job(s) to high priority")
        logger.info(
            f"Admin user {request.user.username} set {updated} jobs to high priority"
        )

    set_high_priority.short_description = "🔥 Set high priority (80)"

    def set_normal_priority(self, request, queryset):
        """Set selected jobs to normal priority"""
        if not request.user.has_perm("container_manager.change_containerjob"):
            raise PermissionDenied

        updated = queryset.update(priority=50)
        messages.success(request, f"Set {updated} job(s) to normal priority")
        logger.info(
            f"Admin user {request.user.username} set {updated} jobs to normal priority"
        )

    set_normal_priority.short_description = "➡️ Set normal priority (50)"

    def set_low_priority(self, request, queryset):
        """Set selected jobs to low priority"""
        if not request.user.has_perm("container_manager.change_containerjob"):
            raise PermissionDenied

        updated = queryset.update(priority=20)
        messages.success(request, f"Set {updated} job(s) to low priority")
        logger.info(
            f"Admin user {request.user.username} set {updated} jobs to low priority"
        )

    set_low_priority.short_description = "⬇️ Set low priority (20)"

    def create_job(self, request, queryset):
        """Create new jobs based on selected jobs"""
        created_count = 0
        for job in queryset:
            ContainerJob.objects.create(
                docker_host=job.docker_host,
                name=f"{job.name or 'Unnamed Job'} (Copy)",
                docker_image=job.docker_image,
                command=job.command,
                environment_template=job.environment_template,
                memory_limit=job.memory_limit,
                cpu_limit=job.cpu_limit,
                timeout_seconds=job.timeout_seconds,
                override_environment=job.override_environment,
                created_by=request.user,
            )
            created_count += 1

        messages.success(request, f"Created {created_count} new jobs")

    create_job.short_description = "Create copy of selected jobs"

    def start_job_multi(self, request, queryset):
        """Start selected jobs using appropriate executors"""
        started_count = 0
        for job in queryset:
            if job.status == "pending":
                try:
                    # Use executor factory for multi-executor support
                    from .executors.factory import ExecutorFactory

                    factory = ExecutorFactory()
                    executor = factory.get_executor(job.docker_host)

                    success, execution_id = executor.launch_job(job)
                    if success:
                        job.set_execution_identifier(execution_id)
                        job.status = "running"
                        job.started_at = timezone.now()
                        job.save()
                        started_count += 1
                        messages.success(
                            request,
                            f"Started job {job.id} on {job.docker_host.executor_type if job.docker_host else 'unknown'}",
                        )
                    else:
                        messages.error(
                            request, f"Failed to start job {job.id}: {execution_id}"
                        )
                except Exception as e:
                    messages.error(request, f"Failed to start job {job.id}: {e}")
            else:
                messages.warning(request, f"Job {job.id} is not in pending status")

        if started_count:
            messages.success(
                request, f"Started {started_count} jobs across multiple executors"
            )

    start_job_multi.short_description = "Start selected jobs (multi-executor)"

    def stop_job_multi(self, request, queryset):
        """Stop selected jobs using appropriate executors"""
        stopped_count = 0
        for job in queryset:
            if job.status == "running":
                try:
                    from .executors.factory import ExecutorFactory

                    factory = ExecutorFactory()
                    executor = factory.get_executor(job.docker_host)

                    execution_id = job.get_execution_identifier()
                    if execution_id:
                        executor.cleanup(execution_id)

                    job.status = "cancelled"
                    job.completed_at = timezone.now()
                    job.save()
                    stopped_count += 1
                    messages.success(
                        request,
                        f"Stopped job {job.id} on {job.docker_host.executor_type if job.docker_host else 'unknown'}",
                    )
                except Exception as e:
                    messages.error(request, f"Failed to stop job {job.id}: {e}")
            else:
                messages.warning(request, f"Job {job.id} is not running")

        if stopped_count:
            messages.success(
                request, f"Stopped {stopped_count} jobs across multiple executors"
            )

    stop_job_multi.short_description = "Stop selected jobs (multi-executor)"

    def restart_job_multi(self, request, queryset):
        """Restart selected jobs using appropriate executors"""
        restarted_count = 0
        for job in queryset:
            if job.status in ["running", "completed", "failed"]:
                try:
                    from .executors.factory import ExecutorFactory

                    factory = ExecutorFactory()
                    executor = factory.get_executor(job.docker_host)

                    # Stop existing execution
                    execution_id = job.get_execution_identifier()
                    if execution_id:
                        executor.cleanup(execution_id)

                    # Reset job status
                    job.status = "pending"
                    job.set_execution_identifier("")
                    job.exit_code = None
                    job.started_at = None
                    job.completed_at = None
                    job.save()

                    # Start new execution
                    success, new_execution_id = executor.launch_job(job)
                    if success:
                        job.set_execution_identifier(new_execution_id)
                        job.status = "running"
                        job.started_at = timezone.now()
                        job.save()
                        restarted_count += 1
                        messages.success(
                            request,
                            f"Restarted job {job.id} on {job.docker_host.executor_type if job.docker_host else 'unknown'}",
                        )
                    else:
                        messages.error(
                            request,
                            f"Failed to restart job {job.id}: {new_execution_id}",
                        )
                except Exception as e:
                    messages.error(request, f"Failed to restart job {job.id}: {e}")
            else:
                messages.warning(
                    request, f"Cannot restart job {job.id} in status {job.status}"
                )

        if restarted_count:
            messages.success(
                request, f"Restarted {restarted_count} jobs across multiple executors"
            )

    restart_job_multi.short_description = "Restart selected jobs (multi-executor)"

    def cancel_job_multi(self, request, queryset):
        """Cancel selected jobs using appropriate executors"""
        cancelled_count = 0
        for job in queryset:
            if job.status in ["pending", "running"]:
                try:
                    if job.status == "running":
                        from .executors.factory import ExecutorFactory

                        factory = ExecutorFactory()
                        executor = factory.get_executor(job.docker_host)

                        execution_id = job.get_execution_identifier()
                        if execution_id:
                            executor.cleanup(execution_id)

                    job.status = "cancelled"
                    job.completed_at = timezone.now()
                    job.save()
                    cancelled_count += 1
                    messages.success(
                        request,
                        f"Cancelled job {job.id} on {job.docker_host.executor_type if job.docker_host else 'unknown'}",
                    )
                except Exception as e:
                    messages.error(request, f"Failed to cancel job {job.id}: {e}")
            else:
                messages.warning(
                    request, f"Cannot cancel job {job.id} in status {job.status}"
                )

        if cancelled_count:
            messages.success(
                request, f"Cancelled {cancelled_count} jobs across multiple executors"
            )

    cancel_job_multi.short_description = "Cancel selected jobs (multi-executor)"

    # Route jobs method removed - jobs now have direct docker_host assignment

    # calculate_costs method removed - deprecated cost tracking functionality

    def export_job_data(self, request, queryset):
        """Export job data to CSV"""
        import csv

        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="container_jobs.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Job ID",
                "Name",
                "Docker Image",
                "Executor Type",
                "Status",
                "Duration (seconds)",
                "Created At",
            ]
        )

        for job in queryset:
            duration = job.duration.total_seconds() if job.duration else None

            writer.writerow(
                [
                    str(job.id),
                    job.name or "Unnamed Job",
                    job.docker_image,
                    job.docker_host.executor_type if job.docker_host else "No Host",
                    job.status,
                    duration,
                    job.created_at.isoformat(),
                ]
            )

        messages.success(request, f"Exported {queryset.count()} jobs to CSV")
        return response

    export_job_data.short_description = "Export selected jobs to CSV"

    def bulk_status_report(self, request, queryset):
        """Generate bulk status report for selected jobs"""
        from .bulk_operations import BulkJobManager

        bulk_manager = BulkJobManager()
        status_report = bulk_manager.get_bulk_status(list(queryset))

        # Create summary message
        summary_parts = [
            f"Total: {status_report['total_jobs']}",
            f"Success Rate: {status_report['success_rate']:.1f}%",
            f"Avg Duration: {status_report['avg_duration_seconds']:.1f}s",
        ]

        # Add status breakdown
        status_parts = []
        for status, count in status_report["status_counts"].items():
            status_parts.append(f"{status}: {count}")

        messages.info(
            request,
            f"Bulk Status Report - {', '.join(summary_parts)}. "
            f"Status breakdown: {', '.join(status_parts)}",
        )

        # Add executor breakdown if multiple types
        if len(status_report["executor_counts"]) > 1:
            executor_parts = []
            for executor_type, count in status_report["executor_counts"].items():
                executor_parts.append(f"{executor_type}: {count}")

            messages.info(request, f"Executor breakdown: {', '.join(executor_parts)}")

    bulk_status_report.short_description = "Generate status report for selected jobs"

    @method_decorator(csrf_protect)
    def dequeue_job_view(self, request, job_id):
        """AJAX endpoint to dequeue a single job"""
        if request.method != "POST":
            return JsonResponse(
                {"success": False, "error": "Method not allowed"}, status=405
            )

        try:
            if not request.user.has_perm("container_manager.change_containerjob"):
                return JsonResponse({"success": False, "error": "Permission denied"})

            job = get_object_or_404(ContainerJob, id=job_id)

            if not job.is_queued:
                return JsonResponse({"success": False, "error": "Job is not queued"})

            queue_manager.dequeue_job(job)

            logger.info(
                f"Admin user {request.user.username} dequeued job {job.id} via AJAX"
            )

            return JsonResponse(
                {"success": True, "message": f"Job {job.id} removed from queue"}
            )

        except Exception as e:
            logger.error(f"Error dequeuing job {job_id}: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    @method_decorator(require_POST)
    @method_decorator(csrf_protect)
    def requeue_job_view(self, request, job_id):
        """AJAX endpoint to requeue a single job"""
        try:
            if not request.user.has_perm("container_manager.change_containerjob"):
                return JsonResponse({"success": False, "error": "Permission denied"})

            job = get_object_or_404(ContainerJob, id=job_id)

            if job.is_queued:
                return JsonResponse(
                    {"success": False, "error": "Job is already queued"}
                )

            if job.status in ["completed", "cancelled"]:
                return JsonResponse(
                    {"success": False, "error": f"Cannot queue {job.status} job"}
                )

            queue_manager.queue_job(job)

            logger.info(
                f"Admin user {request.user.username} requeued job {job.id} via AJAX"
            )

            return JsonResponse(
                {"success": True, "message": f"Job {job.id} added to queue"}
            )

        except Exception as e:
            logger.error(f"Error requeuing job {job_id}: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    @method_decorator(require_POST)
    @method_decorator(csrf_protect)
    def cancel_job_view(self, request, job_id):
        """AJAX endpoint to cancel a single job"""
        try:
            if not request.user.has_perm("container_manager.change_containerjob"):
                return JsonResponse({"success": False, "error": "Permission denied"})

            job = get_object_or_404(ContainerJob, id=job_id)

            if job.status != "running":
                return JsonResponse({"success": False, "error": "Job is not running"})

            # For now, we'll mark the job as cancelled
            # In a real implementation, this would integrate with the job execution service
            job.status = "cancelled"
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "completed_at"])

            logger.info(
                f"Admin user {request.user.username} cancelled job {job.id} via AJAX"
            )
            return JsonResponse({"success": True, "message": f"Job {job.id} cancelled"})

        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    def queue_stats_view(self, request):
        """View queue statistics"""
        if not request.user.has_perm("container_manager.view_containerjob"):
            raise PermissionDenied

        try:
            stats = queue_manager.get_worker_metrics()

            # Add additional statistics
            stats.update(
                {
                    "total_jobs": ContainerJob.objects.count(),
                    "completed_today": ContainerJob.objects.filter(
                        status="completed", completed_at__date=timezone.now().date()
                    ).count(),
                    "failed_today": ContainerJob.objects.filter(
                        status="failed", completed_at__date=timezone.now().date()
                    ).count(),
                    "high_priority_queued": ContainerJob.objects.filter(
                        queued_at__isnull=False,
                        launched_at__isnull=True,
                        priority__gte=70,
                    ).count(),
                }
            )

            if request.headers.get("Accept") == "application/json":
                return JsonResponse(stats)

            context = {"stats": stats, "title": "Queue Statistics"}

            return render(request, "admin/container_manager/queue_stats.html", context)

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            if request.headers.get("Accept") == "application/json":
                return JsonResponse({"error": str(e)}, status=500)
            else:
                messages.error(request, f"Error loading queue statistics: {e}")
                return HttpResponseRedirect(
                    reverse("admin:container_manager_containerjob_changelist")
                )

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Note: Complex admin interfaces removed for simplicity
