from typing import ClassVar

from django.contrib import admin, messages
from django.db import models
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .executors.exceptions import ExecutorConnectionError
from .executors.factory import ExecutorProvider
from .models import (
    ContainerJob,
    EnvironmentVariableTemplate,
    ExecutorHost,
)


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
            provider.get_executor(obj)  # Check if executor can be created
            # Try to get executor - if it fails, connection is bad
            return format_html('<span style="color: green;">●</span> Connected')
        except ExecutorConnectionError:
            return format_html('<span style="color: red;">●</span> Connection Failed')
        except Exception:
            return format_html('<span style="color: red;">●</span> Connection Failed')

    connection_status.short_description = "Status"

    def test_connection(self, request, queryset):
        """Test connection to selected executor hosts"""
        provider = ExecutorProvider()
        for host in queryset:
            try:
                provider.get_executor(host)  # Check if executor can be created
                # If we can get executor, connection is good
                messages.success(request, f"Connection to {host.name} successful")
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


@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_name",
        "docker_image",
        "docker_host",
        "get_executor_type",
        "status",
        "duration_display",
        "created_at",
    )
    list_filter = ("status", "docker_host", "created_at")
    search_fields = (
        "id",
        "name",
        "docker_image",
        "docker_host__name",
    )
    readonly_fields = (
        "id",
        "execution_id",
        "exit_code",
        "started_at",
        "completed_at",
        "created_at",
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
            "Job Information",
            {"fields": ("id", "docker_image", "docker_host", "name", "status")},
        ),
        (
            "Executor Configuration",
            {
                "fields": ("executor_metadata",),
                "classes": ("collapse",),
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
            "Execution Details",
            {
                "fields": (
                    "execution_id",
                    "exit_code",
                    "started_at",
                    "completed_at",
                    "duration_display",
                ),
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
            "Metadata",
            {"fields": ("created_by", "created_at"), "classes": ("collapse",)},
        ),
    )

    actions: ClassVar = [
        "create_job",
        "start_job_multi",
        "stop_job_multi",
        "restart_job_multi",
        "cancel_job_multi",
        "export_job_data",
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

    def executor_metadata_display(self, obj):
        """Display executor metadata in readable format"""
        if obj.executor_metadata:
            import json

            formatted_json = json.dumps(obj.executor_metadata, indent=2)
            return format_html("<pre>{}</pre>", formatted_json)
        return "None"

    executor_metadata_display.short_description = "Executor Metadata"

    def get_urls(self):
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
        ]
        return custom_urls + urls

    def view_logs(self, request, object_id):
        """View job logs"""
        job = get_object_or_404(ContainerJob, pk=object_id)

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

        return admin.site.index(request, extra_context=context)

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

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Note: Complex admin interfaces removed for simplicity
