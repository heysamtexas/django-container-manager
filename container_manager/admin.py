from django.contrib import admin, messages
from django.shortcuts import get_object_or_404
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .docker_service import DockerConnectionError, docker_service
from .models import (
    ContainerExecution,
    ContainerJob,
    ContainerTemplate,
    DockerHost,
    EnvironmentVariable,
    NetworkAssignment,
)


class EnvironmentVariableInline(admin.TabularInline):
    model = EnvironmentVariable
    extra = 1
    fields = ("key", "value", "is_secret")


class NetworkAssignmentInline(admin.TabularInline):
    model = NetworkAssignment
    extra = 1
    fields = ("network_name", "aliases")


@admin.register(DockerHost)
class DockerHostAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "executor_type",
        "host_type",
        "connection_string",
        "capacity_display",
        "is_active",
        "connection_status",
        "created_at",
    )
    list_filter = ("executor_type", "host_type", "is_active", "tls_enabled")
    search_fields = ("name", "connection_string")
    readonly_fields = ("created_at", "updated_at", "capacity_display")

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
                )
            },
        ),
        (
            "Executor Configuration",
            {"fields": ("executor_config", "max_concurrent_jobs", "current_job_count")},
        ),
        ("Docker Configuration", {"fields": ("auto_pull_images",)}),
        (
            "Cost and Performance",
            {
                "fields": (
                    "cost_per_hour",
                    "cost_per_job",
                    "average_startup_time",
                    "last_health_check",
                    "health_check_failures",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "TLS Configuration",
            {"fields": ("tls_enabled", "tls_verify"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["test_connection"]

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

    def capacity_display(self, obj):
        """Show current capacity utilization"""
        info = obj.get_capacity_info()
        return (
            f"{info['current_jobs']}/{info['max_jobs']} "
            f"({info['utilization_percent']:.1f}%)"
        )

    capacity_display.short_description = "Capacity"

    def test_connection(self, request, queryset):
        """Test connection to selected Docker hosts"""
        for host in queryset:
            try:
                docker_service.get_client(host)
                messages.success(request, f"Connection to {host.name} successful")
            except DockerConnectionError as e:
                messages.error(request, f"Connection to {host.name} failed: {e}")

    test_connection.short_description = "Test connection to selected hosts"


@admin.register(ContainerTemplate)
class ContainerTemplateAdmin(admin.ModelAdmin):
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

    inlines = [EnvironmentVariableInline, NetworkAssignmentInline]

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
    search_fields = ("id", "name", "template__name", "docker_host__name")
    readonly_fields = (
        "id",
        "container_id",
        "exit_code",
        "started_at",
        "completed_at",
        "created_at",
        "duration_display",
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
                    "preferred_executor",
                    "routing_reason",
                    "external_execution_id",
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
                    "exit_code",
                    "started_at",
                    "completed_at",
                    "duration_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Cost Tracking",
            {"fields": ("estimated_cost", "actual_cost"), "classes": ("collapse",)},
        ),
        (
            "Metadata",
            {"fields": ("created_by", "created_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["create_job", "start_job", "stop_job", "restart_job", "cancel_job"]

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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/logs/",
                self.admin_site.admin_view(self.view_logs),
                name="container_manager_containerjob_logs",
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

    def start_job(self, request, queryset):
        """Start selected jobs"""
        started_count = 0
        for job in queryset:
            if job.status == "pending":
                try:
                    container_id = docker_service.create_container(job)
                    job.container_id = container_id
                    job.save()

                    docker_service.start_container(job)
                    started_count += 1
                    messages.success(request, f"Started job {job.id}")
                except Exception as e:
                    messages.error(request, f"Failed to start job {job.id}: {e}")
            else:
                messages.warning(request, f"Job {job.id} is not in pending status")

        if started_count:
            messages.success(request, f"Started {started_count} jobs")

    start_job.short_description = "Start selected jobs"

    def stop_job(self, request, queryset):
        """Stop selected jobs"""
        stopped_count = 0
        for job in queryset:
            if job.status == "running":
                try:
                    docker_service.stop_container(job)
                    job.status = "cancelled"
                    job.completed_at = timezone.now()
                    job.save()
                    stopped_count += 1
                    messages.success(request, f"Stopped job {job.id}")
                except Exception as e:
                    messages.error(request, f"Failed to stop job {job.id}: {e}")
            else:
                messages.warning(request, f"Job {job.id} is not running")

        if stopped_count:
            messages.success(request, f"Stopped {stopped_count} jobs")

    stop_job.short_description = "Stop selected jobs"

    def restart_job(self, request, queryset):
        """Restart selected jobs"""
        restarted_count = 0
        for job in queryset:
            if job.status in ["running", "completed", "failed"]:
                try:
                    # Stop existing container
                    if job.container_id:
                        docker_service.stop_container(job)
                        docker_service.remove_container(job, force=True)

                    # Reset job status
                    job.status = "pending"
                    job.container_id = ""
                    job.exit_code = None
                    job.started_at = None
                    job.completed_at = None
                    job.save()

                    # Start new container
                    container_id = docker_service.create_container(job)
                    job.container_id = container_id
                    job.save()

                    docker_service.start_container(job)
                    restarted_count += 1
                    messages.success(request, f"Restarted job {job.id}")
                except Exception as e:
                    messages.error(request, f"Failed to restart job {job.id}: {e}")
            else:
                messages.warning(
                    request, f"Cannot restart job {job.id} in status {job.status}"
                )

        if restarted_count:
            messages.success(request, f"Restarted {restarted_count} jobs")

    restart_job.short_description = "Restart selected jobs"

    def cancel_job(self, request, queryset):
        """Cancel selected jobs"""
        cancelled_count = 0
        for job in queryset:
            if job.status in ["pending", "running"]:
                try:
                    if job.container_id:
                        docker_service.stop_container(job)
                        docker_service.remove_container(job, force=True)

                    job.status = "cancelled"
                    job.completed_at = timezone.now()
                    job.save()
                    cancelled_count += 1
                    messages.success(request, f"Cancelled job {job.id}")
                except Exception as e:
                    messages.error(request, f"Failed to cancel job {job.id}: {e}")
            else:
                messages.warning(
                    request, f"Cannot cancel job {job.id} in status {job.status}"
                )

        if cancelled_count:
            messages.success(request, f"Cancelled {cancelled_count} jobs")

    cancel_job.short_description = "Cancel selected jobs"

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
