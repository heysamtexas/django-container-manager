# Python API Reference

This guide documents the Python API for programmatically interacting with Django Multi-Executor Container Manager, including multi-cloud execution, routing, cost tracking, performance monitoring, and migration capabilities.

## Overview

The system provides a Django-based Python API through models, managers, and services. This allows for programmatic job creation, monitoring, and management within Django applications or custom scripts.

## Core Models

### DockerHost

Represents executor endpoints for container execution across multiple cloud providers.

```python
from container_manager.models import DockerHost

# Create a Docker host
docker_host = DockerHost.objects.create(
    name="production-docker",
    host_type="tcp",
    connection_string="tcp://docker.example.com:2376",
    executor_type="docker",
    is_active=True,
    tls_enabled=True,
    tls_verify=True,
    max_concurrent_jobs=50,
    description="Production Docker server"
)

# Create a Cloud Run executor
cloudrun_host = DockerHost.objects.create(
    name="gcp-cloudrun-us-central1",
    host_type="tcp",
    connection_string="https://run.googleapis.com",
    executor_type="cloudrun",
    executor_config={
        "project_id": "your-project-id",
        "region": "us-central1",
        "service_account": "container-manager@your-project.iam.gserviceaccount.com",
        "memory_limit": 2048,
        "cpu_limit": 2.0,
        "timeout_seconds": 3600
    },
    is_active=True,
    max_concurrent_jobs=1000
)
```

#### Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(100) | Unique host identifier |
| `host_type` | CharField(10) | "unix" or "tcp" |
| `connection_string` | CharField(500) | Executor endpoint URL |
| `executor_type` | CharField(50) | "docker", "cloudrun", "fargate", "azure" |
| `executor_config` | JSONField | Executor-specific configuration |
| `is_active` | BooleanField | Enable/disable host |
| `max_concurrent_jobs` | IntegerField | Maximum concurrent jobs |
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

## Multi-Cloud APIs

### ExecutorFactory

Central factory for managing different executor types.

```python
from container_manager.executors.factory import ExecutorFactory

# Create factory instance
factory = ExecutorFactory()

# Get available executors
available_executors = factory.get_available_executors()
print(f"Available executors: {available_executors}")

# Route job to best executor
best_executor = factory.route_job(job)
print(f"Routed to: {best_executor.name}")

# Get executor instance
executor = factory.get_executor(job)
success, execution_id = executor.launch_job(job)
```

### Cloud Run Executor

```python
from container_manager.executors.cloudrun import CloudRunExecutor

# Create Cloud Run executor
executor = CloudRunExecutor(cloudrun_host)

# Launch job on Cloud Run
success, execution_id = executor.launch_job(job)

# Check status
status = executor.check_status(execution_id)

# Get logs
logs = executor.get_logs(execution_id)

# Cleanup
executor.cleanup(execution_id)
```

## Routing APIs

### RoutingRuleSet

```python
from container_manager.models import RoutingRuleSet, RoutingRule

# Create routing ruleset
ruleset = RoutingRuleSet.objects.create(
    name="production-routing",
    description="Production routing rules",
    is_active=True
)

# Add routing rules
RoutingRule.objects.create(
    ruleset=ruleset,
    name="small-jobs-docker",
    condition="memory_mb <= 512 and timeout_seconds <= 300",
    target_executor="docker",
    priority=10
)

RoutingRule.objects.create(
    ruleset=ruleset,
    name="large-jobs-cloudrun",
    condition="memory_mb > 512 or timeout_seconds > 300",
    target_executor="cloudrun",
    priority=20
)
```

### Routing Engine

```python
from container_manager.routing.engine import RoutingEngine

# Create routing engine
engine = RoutingEngine()

# Evaluate routing for a job
best_executor = engine.route_job(job)

# Get routing explanation
explanation = engine.explain_routing(job)
print(f"Routing decision: {explanation}")

# Test routing rules
test_results = engine.test_routing_rules(template, show_evaluation=True)
```

## Cost Tracking APIs

### CostProfile

```python
from container_manager.cost.models import CostProfile
from decimal import Decimal

# Create cost profile
profile = CostProfile.objects.create(
    name="cloudrun-us-central1",
    executor_type="cloudrun",
    region="us-central1",
    cpu_cost_per_core_hour=Decimal("0.000024"),
    memory_cost_per_gb_hour=Decimal("0.0000025"),
    request_cost=Decimal("0.0000004"),
    currency="USD"
)

# Calculate cost for resource usage
cost_breakdown = profile.calculate_cost(
    cpu_hours=1.5,
    memory_gb_hours=2.0,
    requests=1
)
print(f"Total cost: ${cost_breakdown['total_cost']}")
```

### CostTracker

```python
from container_manager.cost.tracker import CostTracker

# Create cost tracker
tracker = CostTracker()

# Track job cost
cost_record = tracker.track_job_cost(job, cost_profile)

# Get cost analysis
analysis = tracker.get_cost_analysis(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    group_by=['executor_type']
)

# Check budget status
budget_status = tracker.check_budget_status(budget_id)
```

### CostBudget

```python
from container_manager.cost.models import CostBudget

# Create budget
budget = CostBudget.objects.create(
    name="Monthly Production Budget",
    budget_amount=Decimal("1000.00"),
    currency="USD",
    period="monthly",
    warning_threshold=80.0,
    critical_threshold=95.0
)

# Check budget status
current_spending = budget.get_current_spending()
percentage = budget.get_spending_percentage()
thresholds = budget.check_thresholds()

if thresholds['warning_exceeded']:
    print(f"Warning: {percentage:.1f}% of budget used")
```

## Performance Monitoring APIs

### PerformanceTracker

```python
from container_manager.performance.tracker import performance_tracker

# Track operation performance
with performance_tracker.track_operation(
    job_id=job.id,
    executor_type="cloudrun",
    host_name="gcp-cloudrun-us-central1",
    operation_type="launch"
) as context:
    # Perform operation
    success, execution_id = executor.launch_job(job)
    
    # Add custom metrics
    context.add_metric("custom_metric", 42.0)

# Get performance metrics
metrics = performance_tracker.get_metrics(
    executor_type="cloudrun",
    start_date=datetime.now() - timedelta(days=7)
)

# Generate performance report
report = performance_tracker.generate_report(
    executor_types=["docker", "cloudrun"],
    include_recommendations=True
)
```

### ExecutorPerformanceMetric

```python
from container_manager.performance.models import ExecutorPerformanceMetric

# Query performance metrics
metrics = ExecutorPerformanceMetric.objects.filter(
    executor_type="cloudrun",
    timestamp__gte=datetime.now() - timedelta(days=1)
)

# Calculate averages
avg_launch_time = metrics.aggregate(
    avg_launch=models.Avg('launch_time_ms')
)['avg_launch']

# Get performance summary
summary = ExecutorPerformanceMetric.get_performance_summary(
    executor_type="cloudrun",
    days=30
)
```

## Migration APIs

### MigrationPlan

```python
from container_manager.migration.models import MigrationPlan, JobMigration

# Create migration plan
plan = MigrationPlan.objects.create(
    name="docker-to-cloudrun-migration",
    description="Migrate jobs from Docker to Cloud Run",
    source_executor_type="docker",
    target_executor_type="cloudrun",
    job_filter_criteria={"status": "pending"},
    migration_strategy="gradual",
    batch_size=10,
    batch_interval_seconds=60
)

# Get migration status
status = plan.get_migration_status()
print(f"Migration progress: {status['progress_percentage']:.1f}%")
```

### LiveJobMigrator

```python
from container_manager.migration.engine import live_migrator

# Create migration plan
plan = live_migrator.create_migration_plan(
    name="emergency-migration",
    source_executor_type="docker",
    target_executor_type="cloudrun",
    job_filter_criteria={"status": "running"},
    migration_strategy="immediate"
)

# Validate migration plan
is_valid, issues = live_migrator.validate_migration_plan(plan)
if not is_valid:
    print(f"Migration issues: {issues}")

# Execute migration
success = live_migrator.execute_migration_plan(plan)
if success:
    print("Migration completed successfully")
```

### Migration Monitoring

```python
# Monitor active migrations
active_migrations = live_migrator.get_active_migrations()

for migration in active_migrations:
    status = migration.get_migration_status()
    print(f"Migration {migration.name}: {status['jobs_migrated']}/{status['total_jobs']}")

# Get migration metrics
metrics = live_migrator.get_migration_metrics(plan)
print(f"Success rate: {metrics['success_rate']:.1f}%")
print(f"Average migration time: {metrics['avg_migration_time_seconds']:.1f}s")
```

## Advanced Usage Patterns

### Multi-Cloud Job Distribution

```python
def distribute_jobs_across_clouds(template_name, job_count=100):
    """Distribute jobs across multiple cloud providers for optimal performance."""
    
    template = ContainerTemplate.objects.get(name=template_name)
    factory = ExecutorFactory()
    
    # Get available executors
    executors = factory.get_available_executors()
    print(f"Available executors: {list(executors.keys())}")
    
    jobs_created = []
    for i in range(job_count):
        # Create job
        job = ContainerJob.objects.create(
            template=template,
            name=f"{template_name}-job-{i}",
            priority=random.randint(1, 5)
        )
        
        # Route to best executor
        best_executor = factory.route_job(job)
        job.docker_host = best_executor
        job.executor_type = best_executor.executor_type
        job.save()
        
        jobs_created.append(job)
    
    return jobs_created

# Usage
jobs = distribute_jobs_across_clouds("data-processing", 50)
print(f"Created {len(jobs)} jobs across multiple executors")
```

### Cost-Aware Job Scheduling

```python
def schedule_cost_aware_jobs(max_budget=100.0):
    """Schedule jobs based on cost constraints."""
    
    from container_manager.cost.tracker import CostTracker
    
    tracker = CostTracker()
    pending_jobs = ContainerJob.objects.filter(status='pending')
    
    scheduled_jobs = []
    total_estimated_cost = 0.0
    
    for job in pending_jobs:
        # Estimate job cost
        estimated_cost = tracker.estimate_job_cost(job)
        
        if total_estimated_cost + estimated_cost <= max_budget:
            # Execute job
            executor = ExecutorFactory().get_executor(job)
            success, execution_id = executor.launch_job(job)
            
            if success:
                scheduled_jobs.append(job)
                total_estimated_cost += estimated_cost
                print(f"Scheduled job {job.id}, estimated cost: ${estimated_cost:.4f}")
        else:
            print(f"Skipping job {job.id} - would exceed budget")
    
    print(f"Total estimated cost: ${total_estimated_cost:.2f}")
    return scheduled_jobs
```

### Performance-Based Routing

```python
def route_based_on_performance(job):
    """Route job based on historical performance data."""
    
    from container_manager.performance.tracker import performance_tracker
    
    # Get performance metrics for each executor type
    executor_types = ["docker", "cloudrun"]
    performance_scores = {}
    
    for executor_type in executor_types:
        metrics = performance_tracker.get_recent_metrics(
            executor_type=executor_type,
            hours=24
        )
        
        if metrics:
            # Calculate performance score (lower is better)
            avg_launch_time = sum(m.launch_time_ms for m in metrics) / len(metrics)
            failure_rate = sum(1 for m in metrics if m.success_rate < 95) / len(metrics)
            
            performance_scores[executor_type] = avg_launch_time + (failure_rate * 10000)
    
    # Choose best performing executor
    if performance_scores:
        best_executor_type = min(performance_scores.keys(), 
                               key=lambda x: performance_scores[x])
        
        # Get host for best executor type
        host = DockerHost.objects.filter(
            executor_type=best_executor_type,
            is_active=True
        ).first()
        
        return host
    
    # Fallback to default routing
    return ExecutorFactory().route_job(job)
```

### Migration with Rollback

```python
def safe_migration_with_rollback(source_type, target_type):
    """Perform migration with automatic rollback on failure."""
    
    # Create migration plan
    plan = live_migrator.create_migration_plan(
        name=f"{source_type}-to-{target_type}-safe",
        source_executor_type=source_type,
        target_executor_type=target_type,
        job_filter_criteria={"status": "pending"},
        migration_strategy="gradual",
        rollback_enabled=True,
        max_failure_rate=10.0  # Roll back if >10% failures
    )
    
    try:
        # Execute migration
        success = live_migrator.execute_migration_plan(plan)
        
        if success:
            print("Migration completed successfully")
            return True
        else:
            print("Migration failed, initiating rollback")
            rollback_success = live_migrator.rollback_migration(plan)
            if rollback_success:
                print("Rollback completed successfully")
            else:
                print("Rollback failed - manual intervention required")
            return False
            
    except Exception as e:
        print(f"Migration error: {e}")
        print("Initiating emergency rollback")
        live_migrator.rollback_migration(plan)
        return False
```

### Real-time Monitoring Dashboard

```python
def get_realtime_dashboard_data():
    """Get real-time data for monitoring dashboard."""
    
    from django.db.models import Count, Avg
    from datetime import datetime, timedelta
    
    # Job statistics
    job_stats = ContainerJob.objects.aggregate(
        total=Count('id'),
        running=Count('id', filter=Q(status='running')),
        completed_today=Count('id', filter=Q(
            status='completed',
            finished_at__date=datetime.now().date()
        )),
        failed_today=Count('id', filter=Q(
            status='failed',
            finished_at__date=datetime.now().date()
        ))
    )
    
    # Executor utilization
    executor_utilization = {}
    for host in DockerHost.objects.filter(is_active=True):
        running_jobs = ContainerJob.objects.filter(
            docker_host=host,
            status='running'
        ).count()
        
        utilization = (running_jobs / host.max_concurrent_jobs) * 100
        executor_utilization[host.name] = {
            'running_jobs': running_jobs,
            'max_jobs': host.max_concurrent_jobs,
            'utilization_percent': utilization
        }
    
    # Recent performance metrics
    recent_metrics = ExecutorPerformanceMetric.objects.filter(
        timestamp__gte=datetime.now() - timedelta(hours=1)
    ).values('executor_type').annotate(
        avg_launch_time=Avg('launch_time_ms'),
        avg_success_rate=Avg('success_rate')
    )
    
    # Cost tracking
    cost_tracker = CostTracker()
    daily_cost = cost_tracker.get_daily_cost(datetime.now().date())
    
    return {
        'job_stats': job_stats,
        'executor_utilization': executor_utilization,
        'performance_metrics': list(recent_metrics),
        'daily_cost': float(daily_cost),
        'timestamp': datetime.now().isoformat()
    }

# Usage in Django view
def dashboard_api(request):
    data = get_realtime_dashboard_data()
    return JsonResponse(data)
```

For more usage examples, see the specific guides for [Job Management](jobs.md), [Templates](templates.md), [Docker Hosts](docker-hosts.md), [Multi-Cloud Setup](multi-cloud-setup.md), and [Migration Guide](migration-guide.md).