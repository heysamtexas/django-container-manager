from typing import ClassVar

from django.contrib import admin, messages
from django.db import models
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .docker_service import DockerConnectionError, docker_service
from .models import (
    ContainerExecution,
    ContainerJob,
    ContainerTemplate,
    EnvironmentVariableTemplate,
    ExecutorHost,
    NetworkAssignment,
)


class NetworkAssignmentInline(admin.TabularInline):
    model = NetworkAssignment
    extra = 1
    fields = ("network_name", "aliases")


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
            docker_service.get_client(obj)
            return format_html('<span style="color: green;">●</span> Connected')
        except DockerConnectionError:
            return format_html('<span style="color: red;">●</span> Connection Failed')

    connection_status.short_description = "Status"

    def test_connection(self, request, queryset):
        """Test connection to selected Docker hosts"""
        for host in queryset:
            try:
                docker_service.get_client(host)
                messages.success(request, f"Connection to {host.name} successful")
            except DockerConnectionError as e:
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


@admin.register(ContainerTemplate)
class ContainerTemplateAdmin(admin.ModelAdmin):
    formfield_overrides: ClassVar = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(attrs={"rows": 8, "cols": 80})
        },
    }
    list_display = (
        "name",
        "docker_image",
        "memory_limit",
        "cpu_limit",
        "timeout_seconds",
        "auto_remove",
        "created_at",
    )
    list_filter = ("auto_remove", "created_at", "created_by")
    search_fields = ("name", "docker_image", "description")
    readonly_fields = ("created_at", "updated_at")

    inlines: ClassVar = [NetworkAssignmentInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "description",
                    "docker_image",
                    "command",
                    "working_directory",
                )
            },
        ),
        (
            "Resource Limits",
            {
                "fields": ("memory_limit", "cpu_limit", "timeout_seconds"),
                "classes": ("collapse",),
            },
        ),
        (
            "Environment Variables",
            {
                "fields": (
                    "environment_template",
                    "override_environment_variables_text",
                ),
                "description": "Choose a base environment template and add overrides as needed. Overrides take precedence over template variables.",
            },
        ),
        ("Execution Settings", {"fields": ("auto_remove",)}),
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


@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_name",
        "template",
        "docker_host",
        "executor_type",
        "status",
        "duration_display",
        "created_at",
    )
    list_filter = ("status", "executor_type", "docker_host", "template", "created_at")
    search_fields = (
        "id",
        "name",
        "template__name",
        "docker_host__name",
    )
    readonly_fields = (
        "id",
        "container_id",
        "external_execution_id",
        "exit_code",
        "started_at",
        "completed_at",
        "created_at",
        "duration_display",
        "executor_metadata_display",
    )

    fieldsets = (
        (
            "Job Information",
            {"fields": ("id", "template", "docker_host", "name", "status")},
        ),
        (
            "Executor Configuration",
            {
                "fields": (
                    "executor_type",
                    "executor_metadata",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Execution Overrides",
            {
                "fields": ("override_command", "override_environment"),
                "classes": ("collapse",),
            },
        ),
        (
            "Execution Details",
            {
                "fields": (
                    "container_id",
                    "external_execution_id",
                    "exit_code",
                    "started_at",
                    "completed_at",
                    "duration_display",
                ),
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
        return obj.name or obj.template.name

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

        try:
            execution = job.execution
            logs = {
                "stdout": execution.stdout_log,
                "stderr": execution.stderr_log,
                "docker": execution.docker_log,
            }
        except ContainerExecution.DoesNotExist:
            logs = {"stdout": "", "stderr": "", "docker": ""}

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
            ContainerJob.objects.values("executor_type")
            .annotate(
                total_jobs=Count("id"),
                running_jobs=Count("id", filter=models.Q(status="running")),
                completed_jobs=Count("id", filter=models.Q(status="completed")),
                failed_jobs=Count("id", filter=models.Q(status="failed")),
                avg_duration=Avg("duration"),
            )
            .order_by("executor_type")
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
                template=job.template,
                docker_host=job.docker_host,
                name=f"{job.name or job.template.name} (Copy)",
                override_command=job.override_command,
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
                            request, f"Started job {job.id} on {job.executor_type}"
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
                        request, f"Stopped job {job.id} on {job.executor_type}"
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
                    job.container_id = ""
                    job.external_execution_id = ""
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
                            request, f"Restarted job {job.id} on {job.executor_type}"
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
                        request, f"Cancelled job {job.id} on {job.executor_type}"
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

    def route_jobs(self, request, queryset):
        """Route jobs to optimal executors"""
        routed_count = 0
        for job in queryset:
            if job.status == "pending":
                try:
                    from .executors.factory import ExecutorFactory

                    factory = ExecutorFactory()

                    # Re-route the job
                    executor_type = factory.route_job(job)

                    # Find appropriate host for the selected executor
                    from .models import ExecutorHost

                    suitable_host = ExecutorHost.objects.filter(
                        executor_type=executor_type, is_active=True
                    ).first()

                    if suitable_host:
                        job.docker_host = suitable_host
                        job.executor_type = executor_type
                        job.save()
                        routed_count += 1
                        messages.success(
                            request, f"Routed job {job.id} to {executor_type}"
                        )
                    else:
                        messages.error(
                            request, f"No available host found for {executor_type}"
                        )

                except Exception as e:
                    messages.error(request, f"Failed to route job {job.id}: {e}")
            else:
                messages.warning(request, f"Job {job.id} is not in pending status")

        if routed_count:
            messages.success(request, f"Re-routed {routed_count} jobs")

    route_jobs.short_description = "Re-route selected jobs to optimal executors"

    def calculate_costs(self, request, queryset):
        """Calculate costs for completed jobs"""
        calculated_count = 0
        for job in queryset:
            if job.status in ["completed", "failed"]:
                try:
                    from .cost.tracker import CostTracker

                    tracker = CostTracker()

                    cost_record = tracker.finalize_job_cost(job)
                    if cost_record:
                        calculated_count += 1
                        messages.success(
                            request,
                            f"Calculated cost for job {job.id}: "
                            f"${cost_record.total_cost:.6f} {cost_record.currency}",
                        )
                    else:
                        messages.warning(
                            request, f"No cost profile available for job {job.id}"
                        )

                except ImportError:
                    messages.error(request, "Cost tracking not available")
                    break
                except Exception as e:
                    messages.error(
                        request, f"Failed to calculate cost for job {job.id}: {e}"
                    )
            else:
                messages.warning(request, f"Job {job.id} is not completed")

        if calculated_count:
            messages.success(request, f"Calculated costs for {calculated_count} jobs")

    calculate_costs.short_description = "Calculate costs for completed jobs"

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
                "Template",
                "Executor Type",
                "Status",
                "Duration (seconds)",
                "Cost",
                "Created At",
                "Routing Reason",
            ]
        )

        for job in queryset:
            duration = job.duration.total_seconds() if job.duration else None
            cost = f"${job.actual_cost:.6f}" if job.actual_cost else job.estimated_cost

            writer.writerow(
                [
                    str(job.id),
                    job.name or job.template.name,
                    job.template.name,
                    job.executor_type,
                    job.status,
                    duration,
                    cost,
                    job.created_at.isoformat(),
                    "N/A",  # routing_reason removed
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


@admin.register(ContainerExecution)
class ContainerExecutionAdmin(admin.ModelAdmin):
    list_display = ("job", "max_memory_usage_mb", "cpu_usage_percent", "created_at")
    list_filter = ("created_at", "job__status")
    search_fields = ("job__id", "job__name", "job__template__name")
    readonly_fields = (
        "job",
        "max_memory_usage",
        "cpu_usage_percent",
        "clean_output_processed",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Job Information", {"fields": ("job",)}),
        ("Resource Usage", {"fields": ("max_memory_usage", "cpu_usage_percent")}),
        (
            "Logs",
            {
                "fields": ("stdout_log", "stderr_log", "docker_log"),
                "classes": ("collapse",),
            },
        ),
        (
            "Processed Output",
            {"fields": ("clean_output_processed",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def max_memory_usage_mb(self, obj):
        if obj.max_memory_usage:
            return f"{obj.max_memory_usage / (1024 * 1024):.2f} MB"
        return "-"

    max_memory_usage_mb.short_description = "Max Memory Usage"


# Note: Complex admin interfaces removed for simplicity
