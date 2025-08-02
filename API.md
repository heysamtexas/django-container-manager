# API Reference

Complete API documentation for Django Docker Container Manager, covering models, executors, management commands, and Python API usage patterns.

## Table of Contents

- [Overview](#overview)
- [Core Models](#core-models)
- [Executor System](#executor-system)
- [Management Commands](#management-commands)
- [Python API Usage](#python-api-usage)
- [Data Relationships](#data-relationships)
- [Error Handling](#error-handling)
- [Integration Patterns](#integration-patterns)
- [Performance Guide](#performance-guide)
- [Complete Reference](#complete-reference)

## Overview

### System Architecture

```mermaid
graph TD
    A[Python Application] --> B[ContainerJob Model]
    B --> C[ExecutorHost Selection]
    C --> D[ExecutorFactory]
    D --> E[Container Executor]
    E --> F[Container Runtime]
    
    subgraph "Models Layer"
        B --> G[EnvironmentVariableTemplate]
        B --> H[JobManager]
        C --> I[ExecutorHost]
    end
    
    subgraph "Execution Layer"
        E --> J[DockerExecutor]
        E --> K[CloudRunExecutor]
        E --> L[MockExecutor]
    end
    
    subgraph "Management Layer"
        M[Django Management Commands]
        N[Django Admin Interface]
        O[Background Job Processor]
        M --> B
        N --> B
        O --> B
    end
```

### API Access Methods

The system provides multiple interfaces for interaction:

| Interface | Use Case | Authentication | Access Level |
|-----------|----------|----------------|--------------|
| **Python API** | Programmatic access | Django auth | Full model access |
| **Django Admin** | Web management | Django superuser | GUI operations |
| **Management Commands** | CLI operations | System user | Administrative tasks |
| **Job Processor** | Background execution | System service | Automated processing |

### Key Concepts

- **ContainerJob**: Core model representing a containerized task
- **ExecutorHost**: Defines where containers run (Docker, Cloud Run, etc.)
- **Executor**: Backend implementation for container platforms
- **Environment Template**: Reusable environment variable configurations
- **Job Lifecycle**: pending → launching → running → completed/failed

## Core Models

### ContainerJob Model

The central model for managing containerized job executions.

```python
from container_manager.models import ContainerJob

class ContainerJob(models.Model):
    """
    Represents a containerized job execution request with full lifecycle tracking.
    
    Manages Docker container jobs from creation through completion, including
    resource monitoring, log collection, and status tracking.
    """
```

#### Fields Reference

| Field | Type | Description | Required | Default |
|-------|------|-------------|----------|---------|
| `id` | UUIDField | Unique job identifier | Auto | UUID4 |
| `docker_host` | ForeignKey | ExecutorHost for execution | Yes | None |
| `name` | CharField | Human-readable job name | No | "" |
| `status` | CharField | Current job status | Auto | "pending" |
| `docker_image` | CharField | Container image specification | Yes | None |
| `command` | TextField | Command to execute | No | "" |
| `working_directory` | CharField | Container working directory | No | "" |
| `memory_limit` | PositiveIntegerField | Memory limit in MB | No | None |
| `cpu_limit` | FloatField | CPU limit in cores | No | None |
| `timeout_seconds` | PositiveIntegerField | Maximum execution time | No | 3600 |
| `environment_template` | ForeignKey | Environment template | No | None |
| `override_environment` | TextField | Environment variable overrides | No | "" |
| `network_configuration` | JSONField | Container network settings | No | [] |
| `execution_id` | CharField | Runtime execution identifier | Auto | "" |
| `exit_code` | IntegerField | Process exit code | Auto | None |
| `started_at` | DateTimeField | Execution start time | Auto | None |
| `completed_at` | DateTimeField | Execution completion time | Auto | None |
| `max_memory_usage` | PositiveIntegerField | Peak memory usage in bytes | Auto | None |
| `cpu_usage_percent` | FloatField | Average CPU usage percentage | Auto | None |
| `stdout_log` | TextField | Container stdout output | Auto | "" |
| `stderr_log` | TextField | Container stderr output | Auto | "" |
| `clean_output` | TextField | Processed output without timestamps | Auto | "" |
| `created_at` | DateTimeField | Job creation time | Auto | Now |
| `updated_at` | DateTimeField | Last modification time | Auto | Now |
| `created_by` | ForeignKey | User who created the job | No | None |

#### Status Values

```python
STATUS_CHOICES = [
    ("pending", "Pending"),      # Job created, waiting for execution
    ("launching", "Launching"),  # Container being created
    ("running", "Running"),      # Container executing
    ("completed", "Completed"),  # Job finished successfully
    ("failed", "Failed"),        # Job execution failed
    ("timeout", "Timeout"),      # Job exceeded timeout limit
    ("cancelled", "Cancelled"),  # Job manually cancelled
]
```

#### Core Methods

**Job Creation and Management:**

```python
# Create a new job using the convenience manager
job = ContainerJob.objects.create_job(
    image="python:3.11-slim",
    command="python -c 'print(\"Hello World\")'",
    name="Example Job",
    memory_limit=256,  # 256MB
    cpu_limit=1.0,     # 1 CPU core
    timeout_seconds=600,
    environment_vars={
        "PYTHONPATH": "/app",
        "LOG_LEVEL": "INFO"
    }
)

# Standard Django model creation
job = ContainerJob.objects.create(
    docker_host=executor_host,
    docker_image="alpine:latest",
    command="echo 'Hello from Alpine'",
    name="Alpine Test",
    memory_limit=128,
    cpu_limit=0.5
)
```

**Status and Lifecycle Management:**

```python
# Check job status
current_status = job.status
is_finished = job.status in ["completed", "failed", "timeout", "cancelled"]

# Get execution duration
if job.duration:
    print(f"Job ran for: {job.duration}")

# Access execution identifier
execution_id = job.get_execution_identifier()
if execution_id:
    print(f"Container ID: {execution_id}")
```

**Environment Variable Management:**

```python
# Get resolved environment variables (template + overrides)
all_env_vars = job.get_all_environment_variables()

# Get only override variables
override_vars = job.get_override_environment_variables_dict()

# Set environment overrides
job.override_environment = """
DEBUG=true
WORKER_COUNT=4
API_TIMEOUT=30
"""
job.save()
```

**Log and Output Access:**

```python
# Access raw logs
raw_stdout = job.stdout_log
raw_stderr = job.stderr_log

# Get cleaned output (timestamps removed)
clean_output = job.clean_output

# Try to parse output as JSON
parsed_result = job.parsed_output
if parsed_result:
    print(f"Structured result: {parsed_result}")
```

**Network Configuration:**

```python
# Configure container networking
job.network_configuration = [
    {"network_name": "app-network", "aliases": ["worker"]},
    {"network_name": "data-network", "aliases": ["processor"]}
]

# Get network names
networks = job.get_network_names()  # ["app-network", "data-network"]
```

#### Custom Manager Methods

The `JobManager` provides convenient methods for job creation and querying:

```python
# Using the convenience manager
from container_manager.models import ContainerJob

# Create job with environment template
job = ContainerJob.objects.create_job(
    image="node:18-alpine",
    command="npm test",
    environment_template="nodejs-production",  # Template name
    environment_vars={"NODE_ENV": "test"},     # Override variables
    memory_limit=512,
    cpu_limit=1.5
)

# The manager handles template lookup and environment merging automatically
```

#### Properties and Computed Fields

```python
# Job duration calculation
duration = job.duration  # Returns timedelta or None

# Check if job is in terminal state
is_done = job.status in ["completed", "failed", "timeout", "cancelled"]

# Get clean output (cached property)
processed_output = job.clean_output_processed

# Parse JSON output if possible
json_result = job.parsed_output
```

### ExecutorHost Model

Represents execution environments where containers run.

```python
from container_manager.models import ExecutorHost

class ExecutorHost(models.Model):
    """
    Represents an execution environment (Docker daemon, Cloud Run, etc.).
    
    Manages connection details and capabilities for container execution hosts.
    """
```

#### Fields Reference

| Field | Type | Description | Required | Options |
|-------|------|-------------|----------|---------|
| `name` | CharField | Human-readable identifier | Yes | Unique |
| `host_type` | CharField | Connection type | Yes | "tcp", "unix" |
| `connection_string` | CharField | Connection configuration | Yes | URI format |
| `tls_enabled` | BooleanField | Enable TLS for TCP connections | No | False |
| `tls_verify` | BooleanField | Verify TLS certificates | No | False |
| `is_active` | BooleanField | Host availability status | No | True |
| `auto_pull_images` | BooleanField | Auto-pull missing images | No | True |
| `executor_type` | CharField | Executor backend type | Yes | See choices |
| `executor_config` | JSONField | Executor-specific configuration | No | {} |
| `max_concurrent_jobs` | PositiveIntegerField | Concurrent job limit | No | 10 |
| `weight` | PositiveIntegerField | Load balancing weight | No | 100 |
| `current_job_count` | PositiveIntegerField | Active jobs count | Auto | 0 |

#### Executor Types

```python
EXECUTOR_CHOICES = [
    ("docker", "Docker"),                    # Local or remote Docker
    ("cloudrun", "Google Cloud Run"),       # Google Cloud Run
    ("fargate", "AWS Fargate"),             # AWS Fargate
    ("scaleway", "Scaleway Containers"),    # Scaleway container platform
]
```

#### Configuration Examples

**Local Docker Host:**
```python
local_docker = ExecutorHost.objects.create(
    name="local-development",
    host_type="unix",
    connection_string="unix:///var/run/docker.sock",
    executor_type="docker",
    max_concurrent_jobs=5,
    weight=100,
    is_active=True
)
```

**Remote Docker Host:**
```python
remote_docker = ExecutorHost.objects.create(
    name="production-docker-01",
    host_type="tcp",
    connection_string="tcp://docker.example.com:2376",
    tls_enabled=True,
    tls_verify=True,
    executor_type="docker",
    max_concurrent_jobs=20,
    weight=200,
    executor_config={
        "timeout": 60,
        "auto_pull_images": True
    }
)
```

**Google Cloud Run:**
```python
cloudrun_host = ExecutorHost.objects.create(
    name="gcp-cloud-run",
    executor_type="cloudrun",
    weight=150,
    max_concurrent_jobs=100,
    executor_config={
        "project": "my-gcp-project",
        "region": "us-central1",
        "service_account": "containers@my-project.iam.gserviceaccount.com",
        "cpu": "2",
        "memory": "2Gi",
        "timeout": "900s"
    }
)
```

#### Methods

```python
# Check if host is available for new jobs
if host.is_available():
    print("Host ready for jobs")

# Get display name
display_name = host.get_display_name()  # "production-docker-01 (Docker)"

# Access related jobs
active_jobs = host.jobs.filter(status__in=["running", "launching"])
job_count = host.jobs.count()
```

### EnvironmentVariableTemplate Model

Manages reusable environment variable configurations.

```python
from container_manager.models import EnvironmentVariableTemplate

class EnvironmentVariableTemplate(models.Model):
    """
    Template for environment variable sets used across multiple jobs.
    
    Provides reusable environment configurations for consistent job execution.
    """
```

#### Fields Reference

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `name` | CharField | Template identifier | Yes (unique) |
| `description` | TextField | Template documentation | No |
| `environment_variables_text` | TextField | Variable definitions | No |
| `created_at` | DateTimeField | Creation timestamp | Auto |
| `updated_at` | DateTimeField | Last modification | Auto |
| `created_by` | ForeignKey | Creator user | No |

#### Usage Examples

**Creating Environment Templates:**

```python
# Development environment
dev_template = EnvironmentVariableTemplate.objects.create(
    name="python-development",
    description="Standard Python development environment",
    environment_variables_text="""
# Python configuration
DEBUG=true
PYTHONPATH=/app
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1

# Database configuration
DATABASE_URL=sqlite:///dev.db

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json

# Development tools
PYTEST_ARGS=--verbose
"""
)

# Production environment
prod_template = EnvironmentVariableTemplate.objects.create(
    name="python-production",
    description="Python production environment with security settings",
    environment_variables_text="""
# Python configuration
DEBUG=false
PYTHONPATH=/app
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1

# Database configuration
DATABASE_URL=postgresql://user:pass@db:5432/prod

# Security
SECURE_SSL_REDIRECT=true
SECURE_BROWSER_XSS_FILTER=true

# Performance
CACHE_URL=redis://redis:6379/0
WEB_CONCURRENCY=4

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
"""
)
```

#### Methods

```python
# Parse environment variables into dictionary
env_dict = template.get_environment_variables_dict()
print(env_dict)
# Output: {"DEBUG": "true", "PYTHONPATH": "/app", ...}

# Use template in job creation
job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python manage.py test",
    environment_template=template,  # Can use instance or name
    environment_vars={"TEST_WORKERS": "2"}  # Override specific variables
)
```

#### Environment Variable Format

The `environment_variables_text` field supports a simple KEY=value format:

```bash
# Comments start with # and are ignored
DEBUG=true
API_KEY=secret-key-here

# Values can contain spaces and special characters
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require

# Empty lines are ignored

# Multi-word values don't need quotes
WELCOME_MESSAGE=Hello World from Container

# Numbers and booleans are stored as strings
MAX_CONNECTIONS=100
ENABLE_CACHE=false
```

## Executor System

### Executor Interface

All executors implement the `ContainerExecutor` abstract base class:

```python
from container_manager.executors.base import ContainerExecutor

class ContainerExecutor(ABC):
    """Abstract interface for container execution backends"""
    
    @abstractmethod
    def launch_job(self, job: ContainerJob) -> tuple[bool, str]:
        """Launch a container job, return (success, execution_id_or_error)"""
        
    @abstractmethod
    def check_status(self, execution_id: str) -> str:
        """Check job status: 'running', 'exited', 'failed', 'not-found'"""
        
    @abstractmethod
    def get_logs(self, execution_id: str) -> tuple[str, str]:
        """Get logs, return (stdout, stderr)"""
        
    @abstractmethod
    def harvest_job(self, job: ContainerJob) -> bool:
        """Collect final results and clean up"""
        
    @abstractmethod
    def cleanup(self, execution_id: str) -> bool:
        """Force cleanup of execution resources"""
```

### ExecutorFactory

The `ExecutorFactory` creates and manages executor instances:

```python
from container_manager.executors.factory import ExecutorFactory

# Create factory instance
factory = ExecutorFactory()

# Get executor for a job
job = ContainerJob.objects.get(id=job_id)
executor = factory.get_executor(job)

# Get executor for a host
host = ExecutorHost.objects.get(name="production-docker")
executor = factory.get_executor(host)

# Check executor capabilities
capabilities = executor.get_capabilities()
print(capabilities)
# Output: {"supports_resource_limits": True, "supports_networking": True, ...}
```

### Docker Executor

The `DockerExecutor` provides Docker container management:

```python
from container_manager.executors.docker import DockerExecutor

# Executor capabilities
{
    "supports_resource_limits": True,
    "supports_networking": True,
    "supports_persistent_storage": True,
    "supports_secrets": False,
    "supports_gpu": True,
    "supports_scaling": False
}
```

**Key features:**
- Multi-host Docker support (local Unix socket, remote TCP)
- TLS encryption for remote connections
- Resource limits (memory, CPU)
- Container networking
- Log collection with timestamp processing
- Automatic cleanup
- Health monitoring

### Cloud Run Executor

The `CloudRunExecutor` integrates with Google Cloud Run:

```python
from container_manager.executors.cloudrun import CloudRunExecutor

# Executor capabilities
{
    "supports_resource_limits": True,
    "supports_networking": False,
    "supports_persistent_storage": False,
    "supports_secrets": True,
    "supports_gpu": False,
    "supports_scaling": True
}
```

**Configuration requirements:**
- Google Cloud project ID
- Service account with Cloud Run permissions
- Region specification
- Resource allocations

### Mock Executor

The `MockExecutor` provides testing and development support:

```python
from container_manager.executors.mock import MockExecutor

# Perfect for testing and development
mock_host = ExecutorHost.objects.create(
    name="test-mock",
    executor_type="mock",
    is_active=True
)

# Mock executor simulates job execution without real containers
job = ContainerJob.objects.create_job(
    image="test:latest",
    command="echo 'test'",
    docker_host=mock_host
)
```

## Management Commands

### process_container_jobs

The core job processor that executes container jobs in the background:

```bash
# Start job processor (runs continuously)
python manage.py process_container_jobs

# Run once and exit (useful for testing)
python manage.py process_container_jobs --once

# Custom poll interval (default: 5 seconds)
python manage.py process_container_jobs --poll-interval=10

# Verbose output for debugging
python manage.py process_container_jobs --verbosity=2

# Help and options
python manage.py process_container_jobs --help
```

**Command Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--poll-interval` | Seconds between job polls | 5 |
| `--once` | Run once and exit | False |
| `--verbosity` | Output verbosity (0-3) | 1 |

**Job Processing Flow:**

```mermaid
flowchart TD
    A[Poll for pending jobs] --> B{Jobs found?}
    B -->|No| C[Wait poll interval]
    C --> A
    B -->|Yes| D[Get available executor host]
    D --> E[Create executor instance]
    E --> F[Launch container job]
    F --> G[Monitor job status]
    G --> H{Job finished?}
    H -->|No| I[Continue monitoring]
    I --> G
    H -->|Yes| J[Harvest results]
    J --> K[Update job status]
    K --> L[Cleanup resources]
    L --> A
```

### cleanup_containers

Cleanup orphaned containers and jobs:

```bash
# Clean up old completed jobs
python manage.py cleanup_containers

# Clean up jobs older than 7 days
python manage.py cleanup_containers --days=7

# Dry run (show what would be cleaned)
python manage.py cleanup_containers --dry-run

# Force cleanup of stuck jobs
python manage.py cleanup_containers --force
```

### create_sample_data

Create sample data for testing and development:

```bash
# Create sample executor hosts and jobs
python manage.py create_sample_data

# Create specific number of jobs
python manage.py create_sample_data --jobs=10

# Create with specific executor type
python manage.py create_sample_data --executor-type=docker
```

## Python API Usage

### Basic Job Creation

```python
from container_manager.models import ContainerJob, ExecutorHost

# Get an available executor host
docker_host = ExecutorHost.objects.filter(
    executor_type="docker",
    is_active=True
).first()

if not docker_host:
    raise Exception("No Docker hosts available")

# Create a simple job
job = ContainerJob.objects.create_job(
    image="python:3.11-slim",
    command="python -c 'print(\"Hello from Python container\")'",
    name="Python Hello World",
    memory_limit=256,  # 256MB
    cpu_limit=1.0,     # 1 CPU core
    timeout_seconds=300
)

print(f"Created job: {job.id}")
print(f"Status: {job.status}")
```

### Advanced Job Configuration

```python
# Job with environment variables and networking
job = ContainerJob.objects.create_job(
    image="nginx:alpine",
    command="nginx -g 'daemon off;'",
    name="Web Server",
    memory_limit=512,
    cpu_limit=1.5,
    timeout_seconds=3600,
    working_directory="/usr/share/nginx/html",
    environment_vars={
        "NGINX_HOST": "localhost",
        "NGINX_PORT": "80"
    },
    network_configuration=[
        {"network_name": "web-network", "aliases": ["webserver"]},
        {"network_name": "app-network", "aliases": ["nginx"]}
    ]
)
```

### Job Monitoring

```python
import time
from container_manager.models import ContainerJob

def monitor_job(job_id):
    """Monitor job execution until completion"""
    job = ContainerJob.objects.get(id=job_id)
    
    print(f"Monitoring job: {job.name}")
    
    while job.status not in ["completed", "failed", "timeout", "cancelled"]:
        print(f"Status: {job.status}")
        
        if job.status == "running":
            # Get partial logs
            print(f"Recent output: {job.clean_output[-200:]}")
        
        time.sleep(5)
        job.refresh_from_db()
    
    # Job finished
    print(f"Final status: {job.status}")
    print(f"Exit code: {job.exit_code}")
    print(f"Duration: {job.duration}")
    
    if job.stdout_log:
        print(f"STDOUT:\n{job.clean_output}")
    
    if job.stderr_log:
        print(f"STDERR:\n{job.stderr_log}")

# Usage
job = ContainerJob.objects.create_job(
    image="ubuntu:22.04",
    command="bash -c 'echo Starting; sleep 10; echo Completed; date'",
    name="Sleep Test"
)

monitor_job(job.id)
```

### Batch Job Creation

```python
def create_batch_jobs(image, commands, batch_name="Batch"):
    """Create multiple jobs from a list of commands"""
    jobs = []
    
    # Get available hosts for load distribution
    hosts = list(ExecutorHost.objects.filter(
        executor_type="docker",
        is_active=True
    ).order_by("current_job_count"))
    
    if not hosts:
        raise Exception("No available executor hosts")
    
    for i, command in enumerate(commands):
        # Distribute jobs across hosts
        host = hosts[i % len(hosts)]
        
        job = ContainerJob.objects.create_job(
            image=image,
            command=command,
            name=f"{batch_name} Job {i+1}",
            docker_host=host,
            memory_limit=256,
            cpu_limit=0.5
        )
        jobs.append(job)
    
    return jobs

# Example usage
commands = [
    "python -c 'import time; time.sleep(5); print(\"Job 1 done\")'",
    "python -c 'import time; time.sleep(3); print(\"Job 2 done\")'", 
    "python -c 'import time; time.sleep(7); print(\"Job 3 done\")'",
]

batch_jobs = create_batch_jobs("python:3.11-slim", commands, "Python Batch")
print(f"Created {len(batch_jobs)} jobs")
```

### Environment Template Usage

```python
from container_manager.models import EnvironmentVariableTemplate

# Create reusable environment template
template = EnvironmentVariableTemplate.objects.create(
    name="web-app-production",
    description="Production web application environment",
    environment_variables_text="""
# Application settings
APP_ENV=production
DEBUG=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://app:password@db:5432/webapp
DB_POOL_SIZE=10

# Cache
CACHE_URL=redis://redis:6379/0
CACHE_TTL=3600

# Security
SECRET_KEY=production-secret-key
ALLOWED_HOSTS=webapp.example.com,api.example.com
"""
)

# Use template in multiple jobs
jobs = []

# Job 1: Web server
web_job = ContainerJob.objects.create_job(
    image="myapp:web",
    command="gunicorn app:application",
    name="Web Server",
    environment_template=template,
    environment_vars={
        "WEB_WORKERS": "4",
        "PORT": "8000"
    },
    memory_limit=1024,
    cpu_limit=2.0
)

# Job 2: Background worker
worker_job = ContainerJob.objects.create_job(
    image="myapp:worker",
    command="python worker.py",
    name="Background Worker", 
    environment_template=template,
    environment_vars={
        "WORKER_TYPE": "background",
        "QUEUE_NAME": "default"
    },
    memory_limit=512,
    cpu_limit=1.0
)

# Job 3: Database migration
migrate_job = ContainerJob.objects.create_job(
    image="myapp:migrate",
    command="python manage.py migrate",
    name="Database Migration",
    environment_template=template,
    environment_vars={
        "MIGRATION_TIMEOUT": "300"
    },
    memory_limit=256,
    cpu_limit=0.5
)

jobs = [web_job, worker_job, migrate_job]
print(f"Created {len(jobs)} jobs using template: {template.name}")
```

### Error Handling and Recovery

```python
from container_manager.models import ContainerJob, ExecutorHost
from container_manager.executors.exceptions import ExecutorError

def create_robust_job(image, command, **kwargs):
    """Create job with proper error handling"""
    try:
        # Check for available hosts
        available_hosts = ExecutorHost.objects.filter(
            is_active=True,
            executor_type="docker"
        )
        
        if not available_hosts.exists():
            raise Exception("No active Docker hosts available")
        
        # Create job with resource limits (required for safety)
        job = ContainerJob.objects.create_job(
            image=image,
            command=command,
            memory_limit=kwargs.get('memory_limit', 512),
            cpu_limit=kwargs.get('cpu_limit', 1.0),
            timeout_seconds=kwargs.get('timeout_seconds', 1800),
            **{k: v for k, v in kwargs.items() 
               if k not in ['memory_limit', 'cpu_limit', 'timeout_seconds']}
        )
        
        return job
        
    except Exception as e:
        print(f"Job creation failed: {e}")
        return None

def monitor_job_with_recovery(job):
    """Monitor job with failure recovery"""
    max_wait_time = 3600  # 1 hour
    start_time = time.time()
    
    while True:
        job.refresh_from_db()
        elapsed = time.time() - start_time
        
        if job.status in ["completed", "failed", "timeout", "cancelled"]:
            break
            
        if elapsed > max_wait_time:
            print(f"Job monitoring timeout after {max_wait_time} seconds")
            break
            
        print(f"Status: {job.status}, Elapsed: {elapsed:.0f}s")
        time.sleep(10)
    
    # Handle different completion scenarios
    if job.status == "completed":
        print(f"Job completed successfully (exit code: {job.exit_code})")
        return True
    elif job.status == "failed":
        print(f"Job failed (exit code: {job.exit_code})")
        print(f"Error output: {job.stderr_log}")
        return False
    elif job.status == "timeout":
        print("Job exceeded timeout limit")
        return False
    else:
        print(f"Job ended with status: {job.status}")
        return False

# Usage example
job = create_robust_job(
    image="python:3.11-slim",
    command="python -c 'import time; time.sleep(5); print(\"Success\")'",
    name="Robust Test Job",
    memory_limit=256,
    cpu_limit=0.5
)

if job:
    success = monitor_job_with_recovery(job)
    print(f"Job {'succeeded' if success else 'failed'}")
```

### QuerySet Operations

```python
from datetime import datetime, timedelta
from django.utils import timezone

# Get jobs by status
pending_jobs = ContainerJob.objects.filter(status="pending")
running_jobs = ContainerJob.objects.filter(status="running")
completed_jobs = ContainerJob.objects.filter(status="completed")

# Get recent jobs
recent_jobs = ContainerJob.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=24)
)

# Get jobs by executor host
docker_jobs = ContainerJob.objects.filter(
    docker_host__executor_type="docker"
)

# Get failed jobs with details
failed_jobs = ContainerJob.objects.filter(
    status="failed"
).select_related("docker_host", "environment_template")

for job in failed_jobs:
    print(f"Failed job: {job.name}")
    print(f"Host: {job.docker_host.name}")
    print(f"Exit code: {job.exit_code}")
    print(f"Error: {job.stderr_log[:200]}")

# Aggregate statistics
from django.db.models import Count, Avg, Max

stats = ContainerJob.objects.aggregate(
    total_jobs=Count('id'),
    avg_duration=Avg('completed_at') - Avg('started_at'),
    max_memory=Max('max_memory_usage'),
    completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
)

print(f"Job Statistics: {stats}")

# Jobs by time period
daily_counts = ContainerJob.objects.extra(
    select={'day': 'date(created_at)'}
).values('day').annotate(
    count=Count('id')
).order_by('day')
```

## Data Relationships

### Model Relationship Diagram

```mermaid
erDiagram
    ContainerJob ||--o{ ExecutorHost : "docker_host"
    ContainerJob ||--o| EnvironmentVariableTemplate : "environment_template"
    ContainerJob ||--o| User : "created_by"
    ExecutorHost ||--o{ ContainerJob : "jobs"
    EnvironmentVariableTemplate ||--o{ ContainerJob : "jobs"
    EnvironmentVariableTemplate ||--o| User : "created_by"
    
    ContainerJob {
        uuid id PK
        string name
        string status
        string docker_image
        text command
        int memory_limit
        float cpu_limit
        int timeout_seconds
        text override_environment
        json network_configuration
        string execution_id
        int exit_code
        datetime started_at
        datetime completed_at
        int max_memory_usage
        float cpu_usage_percent
        text stdout_log
        text stderr_log
        text clean_output
        datetime created_at
        datetime updated_at
    }
    
    ExecutorHost {
        int id PK
        string name
        string host_type
        string connection_string
        bool tls_enabled
        bool tls_verify
        bool is_active
        bool auto_pull_images
        string executor_type
        json executor_config
        int max_concurrent_jobs
        int weight
        int current_job_count
        datetime created_at
        datetime updated_at
    }
    
    EnvironmentVariableTemplate {
        int id PK
        string name
        text description
        text environment_variables_text
        datetime created_at
        datetime updated_at
    }
```

### Relationship Patterns

**One-to-Many Relationships:**

```python
# ExecutorHost → ContainerJobs
host = ExecutorHost.objects.get(name="production-docker")
host_jobs = host.jobs.all()
active_jobs = host.jobs.filter(status__in=["running", "launching"])

# EnvironmentVariableTemplate → ContainerJobs
template = EnvironmentVariableTemplate.objects.get(name="python-prod")
template_jobs = template.jobs.all()
recent_template_jobs = template.jobs.filter(
    created_at__gte=timezone.now() - timedelta(days=7)
)

# User → ContainerJobs
user_jobs = user.containerjob_set.all()
```

**Reverse Relationships:**

```python
# ContainerJob → ExecutorHost
job = ContainerJob.objects.get(id=job_id)
host_name = job.docker_host.name
host_type = job.docker_host.executor_type

# ContainerJob → EnvironmentVariableTemplate
if job.environment_template:
    template_name = job.environment_template.name
    base_env_vars = job.environment_template.get_environment_variables_dict()
```

### Query Optimization

**Using select_related for ForeignKey relationships:**

```python
# Efficient: Single query with JOIN
jobs = ContainerJob.objects.select_related(
    "docker_host", 
    "environment_template", 
    "created_by"
).filter(status="running")

for job in jobs:
    # No additional queries for related objects
    print(f"Job: {job.name}")
    print(f"Host: {job.docker_host.name}")
    print(f"Template: {job.environment_template.name if job.environment_template else 'None'}")
```

**Using prefetch_related for reverse relationships:**

```python
# Efficient: Separate queries with prefetch
hosts = ExecutorHost.objects.prefetch_related("jobs").filter(is_active=True)

for host in hosts:
    print(f"Host: {host.name}")
    # No additional queries for jobs
    for job in host.jobs.all():
        print(f"  Job: {job.name} ({job.status})")
```

## Error Handling

### Exception Hierarchy

```python
from container_manager.executors.exceptions import (
    ExecutorError,                 # Base executor exception
    ExecutorConnectionError,       # Connection failures  
    ExecutorResourceError,         # Resource limit issues
    ExecutorConfigurationError,    # Configuration problems
)

from django.core.exceptions import ValidationError
```

### Common Exception Scenarios

#### Job Creation Errors

```python
def create_job_safely(image, command, **kwargs):
    """Create job with comprehensive error handling"""
    try:
        # Validate required parameters
        if not image:
            raise ValueError("Docker image is required")
        
        if not command:
            raise ValueError("Command is required")
        
        # Check for available hosts
        host = kwargs.get('docker_host')
        if not host:
            host = ExecutorHost.objects.filter(
                executor_type="docker",
                is_active=True
            ).first()
            
            if not host:
                raise ExecutorConfigurationError("No active Docker hosts available")
        
        # Validate resource limits
        memory_limit = kwargs.get('memory_limit', 512)
        cpu_limit = kwargs.get('cpu_limit', 1.0)
        
        if memory_limit > 2048:  # 2GB limit
            raise ExecutorResourceError("Memory limit exceeds maximum (2048MB)")
        
        if cpu_limit > 2.0:  # 2 CPU limit
            raise ExecutorResourceError("CPU limit exceeds maximum (2.0 cores)")
        
        # Create job
        job = ContainerJob.objects.create_job(
            image=image,
            command=command,
            docker_host=host,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            **kwargs
        )
        
        return job, None
        
    except ValueError as e:
        return None, f"Validation error: {e}"
    except ExecutorConfigurationError as e:
        return None, f"Configuration error: {e}"
    except ExecutorResourceError as e:
        return None, f"Resource error: {e}"
    except ValidationError as e:
        return None, f"Model validation error: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

# Usage
job, error = create_job_safely(
    image="python:3.11",
    command="python app.py",
    name="Safe Job"
)

if error:
    print(f"Job creation failed: {error}")
else:
    print(f"Job created successfully: {job.id}")
```

#### Execution Monitoring Errors

```python
def monitor_job_execution(job_id, timeout=3600):
    """Monitor job with error handling and timeout"""
    try:
        job = ContainerJob.objects.get(id=job_id)
    except ContainerJob.DoesNotExist:
        return False, f"Job {job_id} not found"
    
    start_time = time.time()
    
    while True:
        try:
            job.refresh_from_db()
            
            # Check for terminal states
            if job.status in ["completed", "failed", "timeout", "cancelled"]:
                if job.status == "completed":
                    return True, f"Job completed successfully"
                else:
                    return False, f"Job {job.status}: {job.stderr_log[:200]}"
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return False, f"Monitoring timeout after {timeout} seconds"
            
            print(f"Job {job.status}, elapsed: {elapsed:.0f}s")
            time.sleep(5)
            
        except Exception as e:
            return False, f"Monitoring error: {e}"

# Usage
success, message = monitor_job_execution(job.id, timeout=1800)
print(f"Monitoring result: {message}")
```

#### Resource and Connection Errors

```python
from container_manager.executors.factory import ExecutorFactory

def test_executor_health(host):
    """Test executor connectivity and health"""
    try:
        factory = ExecutorFactory()
        executor = factory.get_executor(host)
        
        # Check health
        health = executor.get_health_status()
        
        if not health["healthy"]:
            return False, f"Executor unhealthy: {health['error']}"
        
        # Test capabilities
        capabilities = executor.get_capabilities()
        
        if not capabilities.get("supports_resource_limits"):
            return False, "Executor does not support resource limits"
        
        return True, f"Executor healthy (response time: {health['response_time']:.2f}s)"
        
    except ExecutorConnectionError as e:
        return False, f"Connection error: {e}"
    except ExecutorConfigurationError as e:
        return False, f"Configuration error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

# Test all active hosts
for host in ExecutorHost.objects.filter(is_active=True):
    healthy, message = test_executor_health(host)
    status = "✅" if healthy else "❌"
    print(f"{status} {host.name}: {message}")
```

### Recovery Patterns

#### Job Retry Logic

```python
def retry_failed_job(job_id, max_retries=3):
    """Retry a failed job with exponential backoff"""
    try:
        original_job = ContainerJob.objects.get(id=job_id)
        
        if original_job.status != "failed":
            return False, "Job is not in failed state"
        
        for attempt in range(max_retries):
            print(f"Retry attempt {attempt + 1}/{max_retries}")
            
            # Create new job with same configuration
            retry_job = ContainerJob.objects.create_job(
                image=original_job.docker_image,
                command=original_job.command,
                name=f"{original_job.name} (Retry {attempt + 1})",
                docker_host=original_job.docker_host,
                memory_limit=original_job.memory_limit,
                cpu_limit=original_job.cpu_limit,
                timeout_seconds=original_job.timeout_seconds,
                environment_template=original_job.environment_template,
                override_environment=original_job.override_environment
            )
            
            # Monitor retry job
            success, message = monitor_job_execution(retry_job.id)
            
            if success:
                return True, f"Job succeeded on retry {attempt + 1}"
            
            # Exponential backoff
            wait_time = 2 ** attempt
            print(f"Retry failed, waiting {wait_time} seconds...")
            time.sleep(wait_time)
        
        return False, f"Job failed after {max_retries} retries"
        
    except Exception as e:
        return False, f"Retry error: {e}"
```

#### Host Failover

```python
def create_job_with_failover(image, command, **kwargs):
    """Create job with automatic host failover"""
    # Get available hosts sorted by weight (highest first)
    available_hosts = ExecutorHost.objects.filter(
        executor_type="docker",
        is_active=True
    ).order_by("-weight")
    
    if not available_hosts:
        return None, "No available hosts"
    
    last_error = None
    
    for host in available_hosts:
        try:
            # Test host health first
            healthy, health_message = test_executor_health(host)
            if not healthy:
                print(f"Skipping unhealthy host {host.name}: {health_message}")
                continue
            
            # Try to create job on this host
            job = ContainerJob.objects.create_job(
                image=image,
                command=command,
                docker_host=host,
                **kwargs
            )
            
            return job, f"Job created on host: {host.name}"
            
        except Exception as e:
            last_error = e
            print(f"Failed to create job on {host.name}: {e}")
            continue
    
    return None, f"All hosts failed, last error: {last_error}"
```

## Integration Patterns

### Django Admin Integration

The system provides comprehensive Django admin integration for web-based management:

```python
# Accessing via Django admin
# Navigate to: /admin/container_manager/

# Admin interface features:
# - Real-time job status monitoring
# - Log viewing directly in browser
# - Bulk operations for job management
# - Executor host configuration
# - Environment template management
```

### Django Signals Integration

```python
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from container_manager.models import ContainerJob

@receiver(post_save, sender=ContainerJob)
def job_created_handler(sender, instance, created, **kwargs):
    """Handle job creation events"""
    if created:
        print(f"New job created: {instance.name} ({instance.id})")
        
        # Example: Send notification
        # send_job_notification(instance)
        
        # Example: Log job creation
        # audit_log.info(f"Job created by {instance.created_by}")

@receiver(post_save, sender=ContainerJob)
def job_status_changed_handler(sender, instance, **kwargs):
    """Handle job status changes"""
    if not kwargs.get('created') and 'status' in (kwargs.get('update_fields') or []):
        print(f"Job {instance.id} status changed to: {instance.status}")
        
        if instance.status == "completed":
            # Handle job completion
            print(f"Job completed with exit code: {instance.exit_code}")
        elif instance.status == "failed":
            # Handle job failure
            print(f"Job failed: {instance.stderr_log[:100]}")

@receiver(pre_delete, sender=ContainerJob)
def job_deleted_handler(sender, instance, **kwargs):
    """Handle job deletion"""
    print(f"Job being deleted: {instance.name} ({instance.id})")
    
    # Cleanup any associated resources
    if instance.execution_id:
        # Force cleanup if job is still running
        from container_manager.executors.factory import ExecutorFactory
        factory = ExecutorFactory()
        executor = factory.get_executor(instance)
        executor.cleanup(instance.execution_id)
```

### Custom Management Commands

```python
# Create custom management command in myapp/management/commands/
from django.core.management.base import BaseCommand
from container_manager.models import ContainerJob

class Command(BaseCommand):
    help = 'Run data processing pipeline'
    
    def add_arguments(self, parser):
        parser.add_argument('--dataset', required=True, help='Dataset to process')
        parser.add_argument('--workers', type=int, default=4, help='Number of workers')
    
    def handle(self, *args, **options):
        dataset = options['dataset']
        workers = options['workers']
        
        # Create processing jobs
        jobs = []
        for i in range(workers):
            job = ContainerJob.objects.create_job(
                image="data-processor:latest",
                command=f"python process.py --dataset={dataset} --worker={i}",
                name=f"Data Processing Worker {i+1}",
                memory_limit=1024,
                cpu_limit=2.0,
                environment_vars={
                    "DATASET": dataset,
                    "WORKER_ID": str(i),
                    "TOTAL_WORKERS": str(workers)
                }
            )
            jobs.append(job)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {len(jobs)} processing jobs for dataset: {dataset}'
            )
        )
        
        # Monitor job completion
        self._monitor_jobs(jobs)
    
    def _monitor_jobs(self, jobs):
        """Monitor jobs until completion"""
        import time
        
        while True:
            # Refresh job statuses
            for job in jobs:
                job.refresh_from_db()
            
            # Check if all jobs are done
            statuses = [job.status for job in jobs]
            if all(status in ["completed", "failed", "timeout", "cancelled"] for status in statuses):
                break
            
            # Show progress
            completed = sum(1 for status in statuses if status == "completed")
            failed = sum(1 for status in statuses if status == "failed")
            running = sum(1 for status in statuses if status == "running")
            
            self.stdout.write(f"Progress: {completed} completed, {failed} failed, {running} running")
            time.sleep(10)
        
        # Final results
        completed_jobs = [job for job in jobs if job.status == "completed"]
        failed_jobs = [job for job in jobs if job.status == "failed"]
        
        self.stdout.write(
            self.style.SUCCESS(f'Processing complete: {len(completed_jobs)} succeeded, {len(failed_jobs)} failed')
        )
```

### REST API Integration

If you're using Django REST Framework, you can create API endpoints:

```python
# serializers.py
from rest_framework import serializers
from container_manager.models import ContainerJob, ExecutorHost

class ContainerJobSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    host_name = serializers.CharField(source='docker_host.name', read_only=True)
    
    class Meta:
        model = ContainerJob
        fields = [
            'id', 'name', 'status', 'docker_image', 'command',
            'memory_limit', 'cpu_limit', 'timeout_seconds',
            'exit_code', 'created_at', 'started_at', 'completed_at',
            'duration', 'host_name', 'clean_output'
        ]
        read_only_fields = [
            'id', 'status', 'exit_code', 'started_at', 'completed_at',
            'duration', 'host_name', 'clean_output'
        ]
    
    def get_duration(self, obj):
        if obj.duration:
            return obj.duration.total_seconds()
        return None

# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

class ContainerJobViewSet(viewsets.ModelViewSet):
    queryset = ContainerJob.objects.all()
    serializer_class = ContainerJobSerializer
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get job logs"""
        job = self.get_object()
        return Response({
            'stdout': job.stdout_log,
            'stderr': job.stderr_log,
            'clean_output': job.clean_output
        })
    
    @action(detail=False, methods=['post'])
    def batch_create(self, request):
        """Create multiple jobs"""
        jobs_data = request.data.get('jobs', [])
        created_jobs = []
        
        for job_data in jobs_data:
            job = ContainerJob.objects.create_job(**job_data)
            created_jobs.append(job)
        
        serializer = self.get_serializer(created_jobs, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# urls.py
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'jobs', views.ContainerJobViewSet)
urlpatterns = router.urls
```

### Webhook Integration

```python
import requests
from django.conf import settings

def send_job_webhook(job, event_type):
    """Send webhook notification for job events"""
    webhook_url = getattr(settings, 'CONTAINER_JOB_WEBHOOK_URL', None)
    if not webhook_url:
        return
    
    payload = {
        'event': event_type,
        'job': {
            'id': str(job.id),
            'name': job.name,
            'status': job.status,
            'image': job.docker_image,
            'host': job.docker_host.name,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'exit_code': job.exit_code,
            'duration': job.duration.total_seconds() if job.duration else None
        },
        'timestamp': timezone.now().isoformat()
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        print(f"Webhook sent for job {job.id}: {event_type}")
    except requests.exceptions.RequestException as e:
        print(f"Webhook failed for job {job.id}: {e}")

# Use in signal handlers
@receiver(post_save, sender=ContainerJob)
def webhook_job_events(sender, instance, created, **kwargs):
    if created:
        send_job_webhook(instance, 'job.created')
    elif instance.status == 'completed':
        send_job_webhook(instance, 'job.completed')
    elif instance.status == 'failed':
        send_job_webhook(instance, 'job.failed')
```

## Performance Guide

### Database Optimization

#### Query Optimization

```python
# Inefficient: N+1 queries
jobs = ContainerJob.objects.filter(status="running")
for job in jobs:
    print(f"Job: {job.name}, Host: {job.docker_host.name}")  # Extra query per job

# Efficient: Single query with JOIN
jobs = ContainerJob.objects.select_related("docker_host").filter(status="running")
for job in jobs:
    print(f"Job: {job.name}, Host: {job.docker_host.name}")  # No extra queries

# Complex optimization with multiple relationships
jobs = ContainerJob.objects.select_related(
    "docker_host",
    "environment_template",
    "created_by"
).prefetch_related(
    "docker_host__jobs"  # If you need related jobs
).filter(
    created_at__gte=timezone.now() - timedelta(days=7)
)
```

#### Bulk Operations

```python
# Bulk job creation
jobs_data = [
    {
        "docker_image": "python:3.11",
        "command": f"python process.py --batch={i}",
        "name": f"Batch Job {i}",
        "memory_limit": 512,
        "cpu_limit": 1.0
    }
    for i in range(100)
]

# Get host for all jobs
host = ExecutorHost.objects.filter(is_active=True).first()

# Create jobs in bulk
jobs = ContainerJob.objects.bulk_create([
    ContainerJob(
        docker_host=host,
        **job_data
    )
    for job_data in jobs_data
])

print(f"Created {len(jobs)} jobs in bulk")

# Bulk status updates (for administrative operations)
ContainerJob.objects.filter(
    status="pending",
    created_at__lt=timezone.now() - timedelta(hours=1)
).update(status="cancelled")
```

#### Index Usage

The models include optimized indexes for common query patterns:

```python
# These queries use indexes efficiently:

# Status + creation time (cjob_status_created_idx)
recent_completed = ContainerJob.objects.filter(
    status="completed",
    created_at__gte=timezone.now() - timedelta(days=1)
)

# User + status (cjob_created_by_status_idx)
user_failed_jobs = ContainerJob.objects.filter(
    created_by=user,
    status="failed"
)

# Host + status (cjob_host_status_idx)
host_running_jobs = ContainerJob.objects.filter(
    docker_host=host,
    status="running"
)

# Single status (cjob_status_idx)
all_pending = ContainerJob.objects.filter(status="pending")
```

### Resource Management

#### Memory Optimization

```python
def process_large_job_batch(job_ids):
    """Process large number of jobs efficiently"""
    
    # Process in chunks to avoid memory issues
    chunk_size = 100
    
    for i in range(0, len(job_ids), chunk_size):
        chunk = job_ids[i:i + chunk_size]
        
        # Use only() to load only required fields
        jobs = ContainerJob.objects.filter(
            id__in=chunk
        ).only(
            'id', 'status', 'docker_host_id', 'name'
        ).select_related('docker_host')
        
        for job in jobs:
            # Process job
            print(f"Processing {job.name} on {job.docker_host.name}")
        
        # Clear Django query cache
        jobs._result_cache = None

# Use iterator() for very large querysets
def process_all_completed_jobs():
    """Process all completed jobs without loading into memory"""
    
    for job in ContainerJob.objects.filter(status="completed").iterator():
        # Process one job at a time
        process_job_results(job)
        
        # Explicitly manage memory if needed
        job = None
```

#### Connection Pooling

```python
# Configure database connection pooling in settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'container_manager',
        'USER': 'container_manager',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'OPTIONS': {
                'MAX_CONNS': 20,
                'CONN_MAX_AGE': 600,  # 10 minutes
            }
        },
        'CONN_MAX_AGE': 600,
    }
}
```

### Caching Strategies

#### Model-Level Caching

```python
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key

def get_job_stats(host_id):
    """Get job statistics with caching"""
    cache_key = f"job_stats_{host_id}"
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = ContainerJob.objects.filter(
            docker_host_id=host_id
        ).aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            failed=Count('id', filter=Q(status='failed')),
            avg_duration=Avg(
                F('completed_at') - F('started_at'),
                filter=Q(status='completed')
            )
        )
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, 300)
    
    return stats

def invalidate_job_stats_cache(host_id):
    """Invalidate job statistics cache"""
    cache_key = f"job_stats_{host_id}"
    cache.delete(cache_key)

# Use in signal handlers to invalidate cache
@receiver(post_save, sender=ContainerJob)
def invalidate_stats_on_job_change(sender, instance, **kwargs):
    if instance.docker_host_id:
        invalidate_job_stats_cache(instance.docker_host_id)
```

#### Query Result Caching

```python
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

class JobDashboardView(TemplateView):
    template_name = 'job_dashboard.html'
    
    @method_decorator(cache_page(60))  # Cache for 1 minute
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # These queries will be cached
        context['recent_jobs'] = ContainerJob.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).select_related('docker_host')[:10]
        
        context['host_stats'] = ExecutorHost.objects.annotate(
            job_count=Count('jobs'),
            active_jobs=Count('jobs', filter=Q(jobs__status='running'))
        ).filter(is_active=True)
        
        return context
```

### Batch Processing Optimization

#### Efficient Job Processing

```python
from container_manager.executors.factory import ExecutorFactory

def process_jobs_efficiently():
    """Optimized job processing with batch operations"""
    
    # Get all pending jobs with related data in single query
    pending_jobs = ContainerJob.objects.filter(
        status="pending"
    ).select_related(
        "docker_host", 
        "environment_template"
    ).order_by("created_at")
    
    if not pending_jobs:
        return 0
    
    # Group jobs by executor host to batch process
    jobs_by_host = {}
    for job in pending_jobs:
        host_id = job.docker_host_id
        if host_id not in jobs_by_host:
            jobs_by_host[host_id] = []
        jobs_by_host[host_id].append(job)
    
    factory = ExecutorFactory()
    total_processed = 0
    
    for host_id, host_jobs in jobs_by_host.items():
        if not host_jobs:
            continue
            
        host = host_jobs[0].docker_host
        executor = factory.get_executor(host)
        
        # Process jobs for this host
        for job in host_jobs:
            try:
                success, result = executor.launch_job(job)
                if success:
                    job.execution_id = result
                    job.status = "launching"
                    job.save()
                    total_processed += 1
                else:
                    job.status = "failed"
                    job.stderr_log = result
                    job.save()
                    
            except Exception as e:
                job.status = "failed"
                job.stderr_log = str(e)
                job.save()
    
    return total_processed
```

## Complete Reference

### Model Field Reference

#### ContainerJob Fields

| Field | Type | Null | Blank | Default | Choices | Validators |
|-------|------|------|-------|---------|---------|------------|
| `id` | UUIDField | No | No | uuid4 | - | - |
| `docker_host` | ForeignKey | No | No | - | ExecutorHost | - |
| `name` | CharField(200) | No | Yes | "" | - | - |
| `status` | CharField(20) | No | No | "pending" | STATUS_CHOICES | - |
| `description` | TextField | No | Yes | "" | - | - |
| `docker_image` | CharField(500) | No | Yes | "" | - | - |
| `command` | TextField | No | Yes | "" | - | - |
| `working_directory` | CharField(500) | No | Yes | "" | - | - |
| `memory_limit` | PositiveIntegerField | Yes | Yes | None | - | - |
| `cpu_limit` | FloatField | Yes | Yes | None | - | MinValue(0.1), MaxValue(32.0) |
| `timeout_seconds` | PositiveIntegerField | No | No | 3600 | - | - |
| `environment_template` | ForeignKey | Yes | Yes | None | EnvironmentVariableTemplate | - |
| `network_configuration` | JSONField | No | Yes | list | - | - |
| `override_environment` | TextField | No | Yes | "" | - | - |
| `execution_id` | CharField(255) | No | Yes | "" | - | - |
| `exit_code` | IntegerField | Yes | Yes | None | - | - |
| `started_at` | DateTimeField | Yes | Yes | None | - | - |
| `completed_at` | DateTimeField | Yes | Yes | None | - | - |
| `executor_metadata` | JSONField | No | Yes | dict | - | - |
| `max_memory_usage` | PositiveIntegerField | Yes | Yes | None | - | - |
| `cpu_usage_percent` | FloatField | Yes | Yes | None | - | - |
| `stdout_log` | TextField | No | Yes | "" | - | - |
| `stderr_log` | TextField | No | Yes | "" | - | - |
| `docker_log` | TextField | No | Yes | "" | - | - |
| `clean_output` | TextField | No | Yes | "" | - | - |
| `created_at` | DateTimeField | No | No | auto_now_add | - | - |
| `updated_at` | DateTimeField | No | No | auto_now | - | - |
| `created_by` | ForeignKey | Yes | Yes | None | User | - |

#### ExecutorHost Fields

| Field | Type | Null | Blank | Default | Choices | Validators |
|-------|------|------|---------|---------|---------|------------|
| `id` | AutoField | No | No | auto | - | - |
| `name` | CharField(100) | No | No | - | - | unique |
| `host_type` | CharField(10) | No | No | "unix" | HOST_TYPE_CHOICES | - |
| `connection_string` | CharField(500) | No | No | - | - | - |
| `tls_enabled` | BooleanField | No | No | False | - | - |
| `tls_verify` | BooleanField | No | No | False | - | - |
| `is_active` | BooleanField | No | No | True | - | - |
| `auto_pull_images` | BooleanField | No | No | True | - | - |
| `executor_type` | CharField(50) | No | No | "docker" | EXECUTOR_CHOICES | - |
| `executor_config` | JSONField | No | Yes | dict | - | - |
| `max_concurrent_jobs` | PositiveIntegerField | No | No | 10 | - | - |
| `weight` | PositiveIntegerField | No | No | 100 | - | MinValue(1), MaxValue(1000) |
| `current_job_count` | PositiveIntegerField | No | No | 0 | - | - |
| `created_at` | DateTimeField | No | No | auto_now_add | - | - |
| `updated_at` | DateTimeField | No | No | auto_now | - | - |

#### EnvironmentVariableTemplate Fields

| Field | Type | Null | Blank | Default | Validators |
|-------|------|------|---------|---------|------------|
| `id` | AutoField | No | No | auto | - |
| `name` | CharField(100) | No | No | - | unique |
| `description` | TextField | No | Yes | "" | - |
| `environment_variables_text` | TextField | No | Yes | "" | - |
| `created_at` | DateTimeField | No | No | auto_now_add | - |
| `updated_at` | DateTimeField | No | No | auto_now | - |
| `created_by` | ForeignKey | Yes | Yes | None | - |

### Method Reference

#### ContainerJob Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `get_execution_identifier()` | str | Get unified execution ID |
| `set_execution_identifier(id)` | None | Set execution ID |
| `get_all_environment_variables()` | dict | Get merged environment variables |
| `get_override_environment_variables_dict()` | dict | Parse override environment text |
| `get_network_names()` | list | Get network names from configuration |
| `can_use_executor(type)` | bool | Check executor compatibility |

#### ExecutorHost Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `is_available()` | bool | Check if host is available |
| `get_display_name()` | str | Get formatted display name |

#### EnvironmentVariableTemplate Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `get_environment_variables_dict()` | dict | Parse environment text to dict |

### Manager Reference

#### ContainerJob.objects (JobManager)

| Method | Parameters | Return Type | Description |
|--------|------------|-------------|-------------|
| `create_job()` | image, command, name, environment_template, environment_vars, **kwargs | ContainerJob | Convenience job creation method |

### Signal Reference

#### Available Signals

| Signal | Sender | When Fired | Parameters |
|--------|--------|------------|------------|
| `pre_save` | ContainerJob | Before job save | instance, raw, using |
| `post_save` | ContainerJob | After job save | instance, created, raw, using |
| `pre_delete` | ContainerJob | Before job delete | instance, using |
| `post_delete` | ContainerJob | After job delete | instance, using |

## LLM Agent Guidelines

### Behavioral Constraints

- **DO**: Always validate model states before performing operations
- **DO**: Use job.is_terminal_status before assuming job completion
- **DO**: Check executor host health before creating jobs
- **DO**: Include resource limits in all ContainerJob creation examples
- **DO NOT**: Modify job status directly without proper state transitions
- **DO NOT**: Create jobs without validating required fields
- **DO NOT**: Access container internals bypassing the executor interface
- **DO NOT**: Ignore job execution failures or timeout conditions
- **LIMITS**: Maximum 10 concurrent jobs per operation, 2GB memory per job

### Security Requirements

- **Model access**: Only use documented public methods and properties
- **Data validation**: Always validate input data before model operations
- **Resource constraints**: Include memory_limit and cpu_limit in job creation
- **User context**: Never create jobs that could escalate privileges
- **Sensitive data**: Never log or expose credentials, tokens, or secrets
- **Container security**: Only create jobs with validated, trusted images

### Safe Operation Patterns

- **Job creation process**:
  1. Validate ExecutorHost availability and health
  2. Set explicit resource limits (memory_limit, cpu_limit)
  3. Validate image source and command safety
  4. Create job with appropriate timeout settings
  5. Monitor job status transitions properly
- **State management**:
  1. Always check current job status before operations
  2. Use is_terminal_status property for completion checking
  3. Handle state transitions appropriately (pending → running → completed/failed)
  4. Implement proper cleanup for failed or cancelled jobs

### Error Handling

- **If job creation fails**: Log detailed error, validate input parameters, check host availability
- **If job execution fails**: Collect logs, update status properly, do not retry automatically
- **If resource limits exceeded**: Terminate job safely, log resource usage details
- **If model validation fails**: Return clear error messages, do not persist invalid data
- **If executor unavailable**: Mark host unhealthy, redirect to available hosts

### Validation Requirements

- [ ] All job creation examples include resource limits
- [ ] Model state checking implemented before all operations
- [ ] Error handling examples cover common failure scenarios
- [ ] No direct database manipulation bypassing model methods
- [ ] All container jobs specify non-root user execution where possible
- [ ] Timeout settings appropriate for operation types
- [ ] Job cleanup procedures documented for all scenarios
- [ ] Resource monitoring patterns included in examples

### API Safety Boundaries

- **NEVER directly modify**: job.status field without proper state validation
- **NEVER bypass**: executor interface for container operations
- **NEVER create**: jobs without memory and CPU limits in production
- **NEVER ignore**: job execution timeouts or resource exhaustion
- **NEVER expose**: internal container details or credentials in logs
- **NEVER allow**: unlimited job creation or resource allocation
- **NEVER skip**: job completion verification before accessing results

---

This comprehensive API reference provides complete documentation for all models, methods, and integration patterns in the Django Docker Container Manager system.