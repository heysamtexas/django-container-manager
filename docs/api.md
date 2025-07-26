# Python API Reference

This guide documents the Python API for programmatically interacting with Django Docker Container Manager.

## Overview

The system provides a Django-based Python API through models, managers, and services. This allows for programmatic job creation, monitoring, and management within Django applications or custom scripts.

## Core Models

### DockerHost

Represents Docker daemon endpoints for container execution.

```python
from container_manager.models import DockerHost

# Create a Docker host
host = DockerHost.objects.create(
    name="production-docker",
    host_type="tcp",
    connection_string="tcp://docker.example.com:2376",
    is_active=True,
    tls_enabled=True,
    tls_verify=True,
    description="Production Docker server"
)
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(100) | Unique host identifier |
| `host_type` | CharField(10) | "unix" or "tcp" |
| `connection_string` | CharField(500) | Docker daemon URL |
| `is_active` | BooleanField | Enable/disable host |
| `tls_enabled` | BooleanField | Use TLS encryption |
| `tls_verify` | BooleanField | Verify TLS certificates |
| `description` | TextField | Host description |
| `created_at` | DateTimeField | Creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |

#### Methods

```python
# Check if host is available for job execution
if host.is_available():
    print("Host is ready for jobs")

# Get display name for host
display_name = host.get_display_name()

# String representation
str(host)  # Returns host name
```

#### Querysets

```python
# Get active hosts
active_hosts = DockerHost.objects.filter(is_active=True)

# Get hosts by type
tcp_hosts = DockerHost.objects.filter(host_type="tcp")
unix_hosts = DockerHost.objects.filter(host_type="unix")

# Get hosts with TLS
secure_hosts = DockerHost.objects.filter(tls_enabled=True)
```

### ContainerTemplate

Defines reusable container configurations.

```python
from container_manager.models import ContainerTemplate

# Create a template
template = ContainerTemplate.objects.create(
    name="data-processor",
    description="Process CSV data files",
    docker_image="python:3.12-slim",
    command="python process_data.py",
    working_directory="/app",
    memory_limit=1024,  # MB
    cpu_limit=1.0,      # CPU cores
    timeout_seconds=3600,
    auto_remove=True
)
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(100) | Unique template name |
| `description` | TextField | Template description |
| `docker_image` | CharField(500) | Docker image reference |
| `command` | TextField | Default command to execute |
| `working_directory` | CharField(255) | Container working directory |
| `memory_limit` | PositiveIntegerField | Memory limit in MB |
| `cpu_limit` | FloatField | CPU limit in cores |
| `timeout_seconds` | PositiveIntegerField | Execution timeout |
| `auto_remove` | BooleanField | Remove container after completion |
| `is_active` | BooleanField | Enable/disable template |

#### Methods

```python
# Get effective configuration for job
config = template.get_effective_config()

# Get environment variables
env_vars = template.get_environment_variables()

# Get network assignments
networks = template.get_network_assignments()

# Check if template is ready for use
if template.is_ready():
    print("Template is configured and active")
```

#### Related Objects

```python
# Environment variables (one-to-many)
template.environment_variables.create(
    key="INPUT_FILE",
    value="/data/input.csv",
    is_secret=False
)

# Network assignments (one-to-many)
template.network_assignments.create(
    network_name="app-network",
    aliases=["data-processor"]
)

# Get all environment variables
env_vars = template.environment_variables.all()

# Get all network assignments
networks = template.network_assignments.all()
```

### ContainerJob

Represents individual job executions.

```python
from container_manager.models import ContainerJob

# Create a job
job = ContainerJob.objects.create(
    template=template,
    docker_host=host,
    priority=3,
    command_override="python custom_script.py",
    memory_limit_override=2048,
    timeout_override=7200
)
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDField | Unique job identifier |
| `template` | ForeignKey | Container template to use |
| `docker_host` | ForeignKey | Docker host for execution |
| `status` | CharField(20) | Job execution status |
| `priority` | PositiveIntegerField | Execution priority (1-5) |
| `command_override` | TextField | Override template command |
| `memory_limit_override` | PositiveIntegerField | Override memory limit |
| `cpu_limit_override` | FloatField | Override CPU limit |
| `timeout_override` | PositiveIntegerField | Override timeout |
| `override_environment` | JSONField | Environment variable overrides |
| `container_id` | CharField(100) | Docker container ID |
| `exit_code` | IntegerField | Container exit code |
| `created_at` | DateTimeField | Job creation time |
| `started_at` | DateTimeField | Execution start time |
| `finished_at` | DateTimeField | Execution end time |

#### Status Values

```python
STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('running', 'Running'), 
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]
```

#### Properties

```python
# Get execution duration
duration = job.execution_time  # Returns timedelta or None

# Get effective command (with overrides)
command = job.get_effective_command()

# Get effective memory limit
memory = job.get_effective_memory_limit()

# Get effective CPU limit
cpu = job.get_effective_cpu_limit()

# Get effective timeout
timeout = job.get_effective_timeout()

# Check if job is in terminal state
if job.is_finished():
    print("Job has completed execution")

# Check if job can be cancelled
if job.can_be_cancelled():
    job.cancel()
```

#### Methods

```python
# Cancel a running job
job.cancel()

# Get all environment variables (template + overrides)
env_vars = job.get_all_environment_variables()

# Update job status
job.update_status('running')

# Mark job as started
job.mark_started(container_id="container_123")

# Mark job as finished
job.mark_finished(exit_code=0)
```

#### Querysets

```python
# Filter by status
pending_jobs = ContainerJob.objects.filter(status='pending')
running_jobs = ContainerJob.objects.filter(status='running')
failed_jobs = ContainerJob.objects.filter(status='failed')

# Filter by priority
high_priority = ContainerJob.objects.filter(priority__lte=2)

# Filter by template
template_jobs = ContainerJob.objects.filter(template=template)

# Filter by date range
from datetime import datetime, timedelta
recent_jobs = ContainerJob.objects.filter(
    created_at__gte=datetime.now() - timedelta(days=7)
)

# Complex filtering
failed_today = ContainerJob.objects.filter(
    status='failed',
    finished_at__date=datetime.now().date()
)

# Order by priority and creation time
next_jobs = ContainerJob.objects.filter(
    status='pending'
).order_by('priority', 'created_at')
```

### ContainerExecution

Stores execution logs and metadata.

```python
from container_manager.models import ContainerExecution

# Access execution data (automatically created with job)
execution = job.execution
print(f"Stdout: {execution.stdout_logs}")
print(f"Stderr: {execution.stderr_logs}")
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `job` | OneToOneField | Associated container job |
| `stdout_logs` | TextField | Standard output logs |
| `stderr_logs` | TextField | Standard error logs |
| `container_stats` | JSONField | Resource usage statistics |
| `created_at` | DateTimeField | Creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |

#### Methods

```python
# Get combined logs
all_logs = execution.get_combined_logs()

# Check if logs contain errors
if execution.has_errors():
    print("Execution produced error output")

# Get log summary
summary = execution.get_log_summary()
```

### EnvironmentVariable

Template-level environment variable configuration.

```python
from container_manager.models import EnvironmentVariable

# Create environment variable
env_var = EnvironmentVariable.objects.create(
    template=template,
    key="DATABASE_URL",
    value="postgresql://user:pass@db:5432/myapp",
    is_secret=True
)
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `template` | ForeignKey | Associated template |
| `key` | CharField(255) | Variable name |
| `value` | TextField | Variable value |
| `is_secret` | BooleanField | Mark as sensitive |

### NetworkAssignment

Template-level network configuration.

```python
from container_manager.models import NetworkAssignment

# Create network assignment
network = NetworkAssignment.objects.create(
    template=template,
    network_name="app-network",
    aliases=["api-service", "backend"]
)
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `template` | ForeignKey | Associated template |
| `network_name` | CharField(100) | Docker network name |
| `aliases` | JSONField | Container aliases in network |

## DockerService

Service class for Docker operations.

```python
from container_manager.docker_service import docker_service

# Get Docker client for host
client = docker_service.get_client(host)

# Execute a job
success = docker_service.execute_job(job)

# Create container for job
container = docker_service.create_container(job)

# Start container
docker_service.start_container(container, job)

# Monitor container execution
docker_service.monitor_container(container, job)

# Clean up container
docker_service.cleanup_container(container)
```

### Methods

#### execute_job(job)
Execute complete job lifecycle.

```python
# Full job execution
try:
    success = docker_service.execute_job(job)
    if success:
        print(f"Job {job.id} completed successfully")
    else:
        print(f"Job {job.id} failed")
except Exception as e:
    print(f"Job execution error: {e}")
```

#### get_client(docker_host)
Get Docker client for specified host.

```python
# Get client with connection caching
client = docker_service.get_client(host)

# Use client for Docker operations
containers = client.containers.list()
images = client.images.list()
```

#### create_container(job)
Create Docker container for job.

```python
# Create container without starting
container = docker_service.create_container(job)
print(f"Created container: {container.id}")
```

## Common Usage Patterns

### Job Creation and Execution

```python
# Complete job creation workflow
def create_and_run_job(template_name, host_name, **overrides):
    # Get template and host
    template = ContainerTemplate.objects.get(name=template_name)
    host = DockerHost.objects.get(name=host_name)
    
    # Create job with overrides
    job = ContainerJob.objects.create(
        template=template,
        docker_host=host,
        **overrides
    )
    
    # Execute job
    success = docker_service.execute_job(job)
    return job, success

# Usage
job, success = create_and_run_job(
    "data-processor",
    "production-docker",
    command_override="python process_large_file.py",
    memory_limit_override=4096,
    priority=1
)
```

### Batch Job Processing

```python
# Process multiple jobs
def process_pending_jobs(max_concurrent=5):
    pending_jobs = ContainerJob.objects.filter(
        status='pending'
    ).order_by('priority', 'created_at')[:max_concurrent]
    
    results = []
    for job in pending_jobs:
        try:
            success = docker_service.execute_job(job)
            results.append((job, success))
        except Exception as e:
            print(f"Error processing job {job.id}: {e}")
            results.append((job, False))
    
    return results
```

### Job Monitoring

```python
# Monitor job status
def monitor_jobs(job_ids):
    jobs = ContainerJob.objects.filter(id__in=job_ids)
    
    status_summary = {}
    for job in jobs:
        status = job.status
        if status not in status_summary:
            status_summary[status] = 0
        status_summary[status] += 1
    
    return status_summary

# Get execution statistics
def get_execution_stats(template_name, days=7):
    from datetime import datetime, timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    jobs = ContainerJob.objects.filter(
        template__name=template_name,
        created_at__gte=cutoff
    )
    
    stats = {
        'total': jobs.count(),
        'completed': jobs.filter(status='completed').count(),
        'failed': jobs.filter(status='failed').count(),
        'avg_duration': None
    }
    
    # Calculate average duration for completed jobs
    completed_jobs = jobs.filter(
        status='completed',
        execution_time__isnull=False
    )
    
    if completed_jobs.exists():
        total_duration = sum(
            job.execution_time.total_seconds() 
            for job in completed_jobs
        )
        stats['avg_duration'] = total_duration / completed_jobs.count()
    
    return stats
```

### Template Management

```python
# Template configuration
def configure_template(name, image, command, **config):
    template, created = ContainerTemplate.objects.get_or_create(
        name=name,
        defaults={
            'docker_image': image,
            'command': command,
            **config
        }
    )
    
    if not created:
        # Update existing template
        for key, value in config.items():
            setattr(template, key, value)
        template.save()
    
    return template

# Add environment variables
def add_template_env_vars(template, env_vars):
    for key, value in env_vars.items():
        is_secret = key.upper() in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']
        
        EnvironmentVariable.objects.update_or_create(
            template=template,
            key=key,
            defaults={
                'value': value,
                'is_secret': is_secret
            }
        )

# Usage
template = configure_template(
    name="api-worker",
    image="myapp:latest",
    command="python worker.py",
    memory_limit=1024,
    cpu_limit=1.0,
    timeout_seconds=3600
)

add_template_env_vars(template, {
    'DATABASE_URL': 'postgresql://user:pass@db:5432/myapp',
    'API_KEY': 'secret-api-key',
    'LOG_LEVEL': 'INFO'
})
```

### Error Handling

```python
# Robust job execution with error handling
def safe_execute_job(job):
    try:
        # Validate job before execution
        if not job.template.is_active:
            raise ValueError(f"Template {job.template.name} is inactive")
        
        if not job.docker_host.is_active:
            raise ValueError(f"Docker host {job.docker_host.name} is inactive")
        
        # Execute job
        success = docker_service.execute_job(job)
        
        if success:
            print(f"Job {job.id} completed successfully")
        else:
            print(f"Job {job.id} failed with exit code {job.exit_code}")
            
        return success
        
    except Exception as e:
        # Log error and update job status
        print(f"Job execution error: {e}")
        job.status = 'failed'
        job.save()
        return False
```

### Query Optimization

```python
# Optimized queries for large datasets
def get_job_summary():
    from django.db.models import Count, Avg
    
    # Use aggregation for efficient counting
    summary = ContainerJob.objects.aggregate(
        total_jobs=Count('id'),
        completed_jobs=Count('id', filter=Q(status='completed')),
        failed_jobs=Count('id', filter=Q(status='failed')),
        avg_duration=Avg('execution_time')
    )
    
    return summary

# Efficient related object loading
def get_jobs_with_templates():
    # Use select_related to avoid N+1 queries
    return ContainerJob.objects.select_related(
        'template', 'docker_host'
    ).prefetch_related(
        'template__environment_variables',
        'template__network_assignments'
    )
```

## Django Shell Usage

Access the API through Django shell:

```bash
# Start Django shell
uv run python manage.py shell

# Import models
from container_manager.models import *
from container_manager.docker_service import docker_service

# Create and execute jobs interactively
template = ContainerTemplate.objects.first()
host = DockerHost.objects.first()
job = ContainerJob.objects.create(template=template, docker_host=host)
docker_service.execute_job(job)
```

## Integration Examples

### Custom Management Commands

```python
# management/commands/custom_job_processor.py
from django.core.management.base import BaseCommand
from container_manager.models import ContainerJob
from container_manager.docker_service import docker_service

class Command(BaseCommand):
    help = 'Process jobs for specific template'
    
    def add_arguments(self, parser):
        parser.add_argument('template_name')
        parser.add_argument('--max-jobs', type=int, default=5)
    
    def handle(self, *args, **options):
        jobs = ContainerJob.objects.filter(
            template__name=options['template_name'],
            status='pending'
        )[:options['max_jobs']]
        
        for job in jobs:
            success = docker_service.execute_job(job)
            if success:
                self.stdout.write(f"Job {job.id} completed")
            else:
                self.stdout.write(f"Job {job.id} failed")
```

### REST API Integration

```python
# views.py - Create REST endpoints
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ContainerJob
from .serializers import ContainerJobSerializer

class ContainerJobViewSet(viewsets.ModelViewSet):
    queryset = ContainerJob.objects.all()
    serializer_class = ContainerJobSerializer
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        job = self.get_object()
        success = docker_service.execute_job(job)
        return Response({'success': success, 'status': job.status})
```

For more usage examples, see the specific guides for [Job Management](jobs.md), [Templates](templates.md), and [Docker Hosts](docker-hosts.md).