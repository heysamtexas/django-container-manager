# Job Lifecycle Management Guide

This guide covers managing container jobs throughout their complete lifecycle in Django Docker Container Manager.

## Job Overview

A container job represents a single execution of a container template on a specific Docker host. Jobs progress through several states from creation to completion, with full logging and monitoring capabilities.

## Job States

### State Diagram
```
pending → running → completed
   ↓         ↓         ↑
   ↓      failed ←-----┘
   ↓         ↓
   → cancelled ←
```

### State Descriptions

- **pending**: Job created but not yet started
- **running**: Container is currently executing
- **completed**: Job finished successfully (exit code 0)
- **failed**: Job finished with error (non-zero exit code)
- **cancelled**: Job was manually cancelled before completion

## Creating Jobs

### Via Django Admin

1. Navigate to **Container Manager** → **Container Jobs**
2. Click **Add Container Job**
3. Select:
   - **Template**: Container template to use
   - **Docker Host**: Host to run the container on
   - **Priority**: Job execution priority (1-5)
4. Optionally override:
   - **Command**: Override template command
   - **Memory Limit**: Override template memory limit
   - **CPU Limit**: Override template CPU limit
   - **Timeout**: Override template timeout

### Via Management Command

```bash
# Create job from template
uv run python manage.py manage_container_job create template-name docker-host-name

# Create with command override
uv run python manage.py manage_container_job create template-name docker-host-name --command="echo 'Custom command'"

# Create with resource overrides
uv run python manage.py manage_container_job create template-name docker-host-name \
    --memory=1024 \
    --cpu=2.0 \
    --timeout=7200

# Create and run immediately
uv run python manage.py manage_container_job run template-name docker-host-name
```

### Via Python API

```python
from container_manager.models import ContainerJob, ContainerTemplate, DockerHost

# Basic job creation
template = ContainerTemplate.objects.get(name="my-template")
host = DockerHost.objects.get(name="local-docker")

job = ContainerJob.objects.create(
    template=template,
    docker_host=host,
    priority=3
)

# Job with overrides
job = ContainerJob.objects.create(
    template=template,
    docker_host=host,
    command_override="python custom_script.py",
    memory_limit_override=2048,
    cpu_limit_override=2.0,
    timeout_override=3600,
    priority=1  # High priority
)
```

## Job Execution

### Manual Execution

```bash
# Run specific job by ID
uv run python manage.py manage_container_job run-job <job-id>

# Run all pending jobs once
uv run python manage.py process_container_jobs --single-run

# Start job processor daemon
uv run python manage.py process_container_jobs
```

### Automatic Execution

The job processor daemon continuously polls for pending jobs:

```bash
# Start with default settings
uv run python manage.py process_container_jobs

# Custom polling interval and concurrency
uv run python manage.py process_container_jobs --poll-interval=3 --max-jobs=20

# Run with cleanup enabled
uv run python manage.py process_container_jobs --cleanup --cleanup-hours=48
```

### Job Processor Configuration

```python
# django_docker_manager/settings.py
CONTAINER_JOB_SETTINGS = {
    'POLL_INTERVAL': 5,        # Seconds between job polls
    'MAX_CONCURRENT': 10,      # Maximum concurrent jobs
    'RETRY_FAILED': True,      # Retry failed jobs
    'MAX_RETRIES': 3,          # Maximum retry attempts
    'RETRY_DELAY': 300,        # Seconds between retries
}
```

## Job Monitoring

### Job Status Tracking

```python
# Check job status
job = ContainerJob.objects.get(id="job-uuid")
print(f"Status: {job.status}")
print(f"Created: {job.created_at}")
print(f"Started: {job.started_at}")
print(f"Finished: {job.finished_at}")
print(f"Exit Code: {job.exit_code}")
```

### Real-time Log Streaming

```python
# Get job logs
job = ContainerJob.objects.get(id="job-uuid")
print("STDOUT:")
print(job.stdout_logs)
print("\nSTDERR:")
print(job.stderr_logs)

# Stream logs in real-time (via WebSocket)
# See admin interface for live log viewing
```

### Job Metrics

```python
# Job execution time
job = ContainerJob.objects.get(id="job-uuid")
if job.started_at and job.finished_at:
    duration = job.finished_at - job.started_at
    print(f"Execution time: {duration.total_seconds()} seconds")

# Resource usage (if available)
if job.container_stats:
    stats = json.loads(job.container_stats)
    print(f"Memory usage: {stats.get('memory_usage', 'N/A')}")
    print(f"CPU usage: {stats.get('cpu_usage', 'N/A')}")
```

## Job Management Operations

### Listing Jobs

```bash
# List all jobs
uv run python manage.py manage_container_job list

# Filter by status
uv run python manage.py manage_container_job list --status=running
uv run python manage.py manage_container_job list --status=failed

# Filter by date range
uv run python manage.py manage_container_job list --since="2024-01-01"
uv run python manage.py manage_container_job list --until="2024-12-31"

# Filter by template
uv run python manage.py manage_container_job list --template="data-processing"

# Filter by host
uv run python manage.py manage_container_job list --host="production-docker"
```

### Job Details

```bash
# Show detailed job information
uv run python manage.py manage_container_job show <job-id>

# Show job logs
uv run python manage.py manage_container_job logs <job-id>

# Show job configuration
uv run python manage.py manage_container_job config <job-id>
```

### Job Control

```bash
# Cancel running job
uv run python manage.py manage_container_job cancel <job-id>

# Retry failed job
uv run python manage.py manage_container_job retry <job-id>

# Clone job (create identical job)
uv run python manage.py manage_container_job clone <job-id>
```

### Bulk Operations

```bash
# Cancel all pending jobs
uv run python manage.py manage_container_job cancel --status=pending

# Retry all failed jobs
uv run python manage.py manage_container_job retry --status=failed

# Clean up old completed jobs
uv run python manage.py manage_container_job cleanup --older-than=7 --status=completed
```

## Job Prioritization

### Priority Levels

1. **Priority 1**: Critical/urgent jobs (highest)
2. **Priority 2**: High priority jobs
3. **Priority 3**: Normal priority jobs (default)
4. **Priority 4**: Low priority jobs
5. **Priority 5**: Background jobs (lowest)

### Priority-based Execution

```python
# Job processor respects priority order
def get_next_job():
    return ContainerJob.objects.filter(
        status='pending'
    ).order_by('priority', 'created_at').first()

# Set job priority
job.priority = 1  # High priority
job.save()
```

### Priority Examples

```python
# Critical system maintenance
job = ContainerJob.objects.create(
    template=maintenance_template,
    docker_host=host,
    priority=1,  # Critical
    command_override="python manage.py migrate"
)

# Regular data processing
job = ContainerJob.objects.create(
    template=etl_template,
    docker_host=host,
    priority=3   # Normal
)

# Background cleanup
job = ContainerJob.objects.create(
    template=cleanup_template,
    docker_host=host,
    priority=5   # Background
)
```

## Advanced Job Features

### Job Dependencies

```python
# Custom model extension for job dependencies
class JobDependency(models.Model):
    job = models.ForeignKey(ContainerJob, on_delete=models.CASCADE)
    depends_on = models.ForeignKey(
        ContainerJob,
        on_delete=models.CASCADE,
        related_name='dependents'
    )
    
    class Meta:
        unique_together = ['job', 'depends_on']

# Wait for dependencies before execution
def can_execute_job(job):
    dependencies = JobDependency.objects.filter(job=job)
    for dep in dependencies:
        if dep.depends_on.status not in ['completed']:
            return False
    return True
```

### Job Scheduling

```python
# Scheduled job execution
class ScheduledJob(models.Model):
    job_template = models.ForeignKey(ContainerTemplate, on_delete=models.CASCADE)
    docker_host = models.ForeignKey(DockerHost, on_delete=models.CASCADE)
    schedule = models.CharField(max_length=100)  # Cron format
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField()
    
    def create_job(self):
        return ContainerJob.objects.create(
            template=self.job_template,
            docker_host=self.docker_host,
            priority=3
        )
```

### Job Retries and Error Handling

```python
# Automatic retry configuration
class ContainerJob(models.Model):
    # ... existing fields ...
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    retry_delay = models.PositiveIntegerField(default=300)  # seconds
    
    def should_retry(self):
        return (self.status == 'failed' and 
                self.retry_count < self.max_retries and
                self.exit_code not in [125, 126, 127])  # Don't retry system errors
    
    def schedule_retry(self):
        if self.should_retry():
            self.status = 'pending'
            self.retry_count += 1
            self.started_at = None
            self.finished_at = None
            self.container_id = None
            self.save()
```

## Job Notifications

### Email Notifications

```python
# container_manager/notifications.py
from django.core.mail import send_mail
from django.conf import settings

def notify_job_completed(job):
    if job.status == 'completed':
        subject = f"Job {job.id} completed successfully"
        message = f"Job {job.template.name} finished in {job.execution_time}"
    else:
        subject = f"Job {job.id} failed"
        message = f"Job {job.template.name} failed with exit code {job.exit_code}"
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=['admin@example.com']
    )

# Signal handler for job completion
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=ContainerJob)
def job_status_changed(sender, instance, **kwargs):
    if instance.status in ['completed', 'failed']:
        notify_job_completed(instance)
```

### Webhook Notifications

```python
# Send webhook on job completion
import requests
import json

def send_webhook(job):
    webhook_url = settings.JOB_WEBHOOK_URL
    if not webhook_url:
        return
    
    payload = {
        'job_id': str(job.id),
        'status': job.status,
        'template': job.template.name,
        'docker_host': job.docker_host.name,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'finished_at': job.finished_at.isoformat() if job.finished_at else None,
        'exit_code': job.exit_code
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Webhook failed: {e}")
```

## Job Performance Analysis

### Execution Time Analysis

```python
# Analyze job performance
from django.db.models import Avg, Count, Max, Min
from datetime import timedelta

def analyze_job_performance(template_name=None, days=30):
    jobs = ContainerJob.objects.filter(
        status='completed',
        finished_at__gte=timezone.now() - timedelta(days=days)
    )
    
    if template_name:
        jobs = jobs.filter(template__name=template_name)
    
    # Calculate execution times
    execution_times = []
    for job in jobs:
        if job.started_at and job.finished_at:
            duration = (job.finished_at - job.started_at).total_seconds()
            execution_times.append(duration)
    
    if execution_times:
        return {
            'count': len(execution_times),
            'avg_time': sum(execution_times) / len(execution_times),
            'min_time': min(execution_times),
            'max_time': max(execution_times),
            'total_time': sum(execution_times)
        }
    
    return None
```

### Resource Usage Analysis

```python
# Track resource usage patterns
def analyze_resource_usage(template_name):
    jobs = ContainerJob.objects.filter(
        template__name=template_name,
        status='completed'
    ).exclude(container_stats__isnull=True)
    
    memory_usage = []
    cpu_usage = []
    
    for job in jobs:
        try:
            stats = json.loads(job.container_stats)
            if 'memory_usage' in stats:
                memory_usage.append(stats['memory_usage'])
            if 'cpu_usage' in stats:
                cpu_usage.append(stats['cpu_usage'])
        except (json.JSONDecodeError, KeyError):
            continue
    
    return {
        'memory': {
            'avg': sum(memory_usage) / len(memory_usage) if memory_usage else 0,
            'max': max(memory_usage) if memory_usage else 0,
            'samples': len(memory_usage)
        },
        'cpu': {
            'avg': sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
            'max': max(cpu_usage) if cpu_usage else 0,
            'samples': len(cpu_usage)
        }
    }
```

## Troubleshooting Jobs

### Common Job Failures

#### Container Creation Failed
```python
# Check Docker host connectivity
from container_manager.docker_service import docker_service

host = DockerHost.objects.get(name="your-host")
try:
    client = docker_service.get_client(host)
    client.ping()
    print("Docker host is accessible")
except Exception as e:
    print(f"Docker host error: {e}")
```

#### Image Pull Failures
```python
# Verify image exists
def check_image_availability(job):
    client = docker_service.get_client(job.docker_host)
    try:
        client.images.pull(job.template.docker_image)
        print(f"Image {job.template.docker_image} pulled successfully")
    except Exception as e:
        print(f"Image pull failed: {e}")
```

#### Resource Limit Exceeded
```bash
# Check job resource usage
uv run python manage.py manage_container_job show <job-id>

# Check host resources
docker system df
docker system events
```

#### Command Execution Errors
```python
# Debug command execution
job = ContainerJob.objects.get(id="job-uuid")
print(f"Command: {job.get_effective_command()}")
print(f"Exit code: {job.exit_code}")
print(f"Error logs: {job.stderr_logs}")
```

### Job Debugging

```python
# Enable debug logging for job execution
import logging

logging.getLogger('container_manager').setLevel(logging.DEBUG)

# Create debug job with verbose logging
job = ContainerJob.objects.create(
    template=template,
    docker_host=host,
    command_override="bash -x /app/debug_script.sh"  # Enable bash debugging
)
```

### Performance Issues

#### Slow Job Startup
- Check Docker image size
- Verify network connectivity
- Monitor resource availability
- Check for host overload

#### Job Timeouts
```python
# Analyze timeout patterns
timeout_jobs = ContainerJob.objects.filter(
    status='failed',
    stderr_logs__icontains='timeout'
)

for job in timeout_jobs:
    print(f"Job {job.id}: {job.template.name} - {job.timeout_override or job.template.timeout_seconds}s timeout")
```

## Best Practices

### Job Design
1. **Idempotent operations** - Jobs should be safe to retry
2. **Clear exit codes** - Use standard exit codes for different failure types
3. **Comprehensive logging** - Log all important operations
4. **Resource estimation** - Set appropriate limits based on testing
5. **Timeout configuration** - Set realistic timeouts for job duration

### Monitoring and Alerting
1. **Failed job alerts** - Monitor and alert on job failures
2. **Performance monitoring** - Track execution times and resource usage
3. **Queue depth monitoring** - Alert on job queue buildup
4. **Host health monitoring** - Ensure Docker hosts are healthy
5. **Log aggregation** - Centralize job logs for analysis

### Error Handling
1. **Graceful degradation** - Handle partial failures appropriately
2. **Retry strategies** - Implement intelligent retry logic
3. **Error categorization** - Classify errors for appropriate handling
4. **Rollback procedures** - Plan for job failure recovery
5. **Notification systems** - Alert stakeholders of critical failures

For monitoring job execution, see the [Monitoring Guide](monitoring.md).