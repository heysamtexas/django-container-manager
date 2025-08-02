# Docker Integration Guide

## Overview

This Django application provides sophisticated full lifecycle management of Docker containers, enabling you to execute Django management commands inside Docker containers with complete tracking of logs, status, and resource usage. Instead of traditional async task queues like Celery or RQ, this system leverages Docker's isolation and resource management capabilities.

### Core Architecture

```mermaid
graph TD
    A[Django Management Command] --> B[JobManager]
    B --> C[ExecutorHost Selection]
    C --> D[DockerExecutor]
    D --> E[Container Creation]
    E --> F[Container Launch]
    F --> G[Execution Monitoring]
    G --> H[Log Collection]
    H --> I[Resource Tracking]
    I --> J[Cleanup]
    
    subgraph "Docker Host"
        E --> K[Docker Daemon]
        K --> L[Container Runtime]
        L --> M[Resource Limits]
        M --> N[Network Isolation]
    end
    
    subgraph "Database Tracking"
        B --> O[ContainerJob]
        O --> P[ExecutionMetadata]
        P --> Q[Logs & Metrics]
    end
```

### Execution Flow

The system follows a comprehensive container lifecycle:

```mermaid
sequenceDiagram
    participant User as User/Management Command
    participant JobMgr as JobManager
    participant Executor as DockerExecutor
    participant Docker as Docker Daemon
    participant DB as Database
    
    User->>JobMgr: Create ContainerJob
    JobMgr->>DB: Save job (status: pending)
    JobMgr->>Executor: launch_job()
    
    Executor->>Docker: Create container
    Docker-->>Executor: Container ID
    Executor->>Docker: Start container
    Docker-->>Executor: Running confirmation
    
    Executor->>DB: Update job (status: running)
    
    loop Monitor Execution
        Executor->>Docker: Check status
        Docker-->>Executor: Container status
        Executor->>DB: Update job status
    end
    
    Executor->>Docker: Get logs
    Docker-->>Executor: stdout/stderr
    Executor->>Docker: Get resource stats
    Docker-->>Executor: Memory/CPU usage
    
    Executor->>DB: Update final results
    Executor->>Docker: Cleanup container
    Docker-->>Executor: Cleanup complete
```

## Docker Daemon Configuration

### Local Development Setup

#### Docker Desktop Configuration

For local development, ensure Docker Desktop is properly configured:

```bash
# Verify Docker is running
docker version

# Check Docker daemon status
docker info

# Test container creation
docker run --rm hello-world
```

#### Unix Socket Permissions

The system primarily uses Unix socket communication with the Docker daemon:

```bash
# Check socket permissions
ls -la /var/run/docker.sock

# Add user to docker group (requires logout/login)
sudo usermod -aG docker $USER

# Verify access
docker ps
```

#### Resource Allocation

Configure Docker Desktop resource limits appropriate for your container jobs:

- **Memory**: Minimum 4GB recommended for container workloads
- **CPU**: 2+ cores for concurrent job execution
- **Disk**: Adequate space for image storage and container logs

### Remote Docker Daemon

For production deployments or remote Docker hosts:

#### TCP Connection Configuration

```python
# ExecutorHost configuration for remote Docker
remote_host = ExecutorHost.objects.create(
    name="production-docker-01",
    host_type="tcp",
    connection_string="tcp://docker.example.com:2376",
    tls_enabled=True,
    tls_verify=True,
    executor_type="docker",
    is_active=True
)
```

#### TLS Certificate Setup

For secure TCP connections:

```bash
# Generate client certificates
mkdir -p ~/.docker/certs
cd ~/.docker/certs

# Copy CA certificate, client certificate, and key
cp ca.pem ~/.docker/certs/
cp cert.pem ~/.docker/certs/
cp key.pem ~/.docker/certs/

# Set appropriate permissions
chmod 400 ~/.docker/certs/key.pem
chmod 444 ~/.docker/certs/cert.pem
chmod 444 ~/.docker/certs/ca.pem
```

#### Network Security

Configure firewall rules for Docker daemon access:

```bash
# Allow Docker daemon port (2376 for TLS)
sudo ufw allow from trusted.network.0.0/16 to any port 2376

# Block unencrypted Docker daemon port
sudo ufw deny 2375
```

### Production Considerations

#### Daemon Security Hardening

```json
// /etc/docker/daemon.json
{
  "hosts": ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2376"],
  "tls": true,
  "tlscert": "/etc/docker/certs/server-cert.pem",
  "tlskey": "/etc/docker/certs/server-key.pem",
  "tlsverify": true,
  "tlscacert": "/etc/docker/certs/ca.pem",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "userland-proxy": false,
  "live-restore": true
}
```

#### Resource Limits and Monitoring

```bash
# System-wide container limits
echo 'DefaultLimitNOFILE=65536' >> /etc/systemd/system/docker.service.d/limits.conf

# Memory accounting
echo 'cgroup_enable=memory swapaccount=1' >> /boot/firmware/cmdline.txt
```

## Container Configuration

### Base Images

Choose appropriate base images for your workloads:

```python
# Lightweight for simple tasks
job = ContainerJob.objects.create_job(
    image="alpine:3.18",
    command="echo 'Hello from Alpine'",
    memory_limit=64,
    cpu_limit=0.5
)

# Python workloads
job = ContainerJob.objects.create_job(
    image="python:3.11-slim",
    command="python -c 'import sys; print(sys.version)'",
    memory_limit=256,
    cpu_limit=1.0
)

# Complex applications
job = ContainerJob.objects.create_job(
    image="node:18-alpine",
    command="npm test",
    memory_limit=512,
    cpu_limit=1.5,
    timeout_seconds=1800
)
```

### Image Management

#### Image Pulling Strategies

```python
# Enable automatic image pulling (default)
docker_host = ExecutorHost.objects.create(
    name="auto-pull-host",
    connection_string="unix:///var/run/docker.sock",
    auto_pull_images=True,  # Will pull missing images
    executor_type="docker"
)

# Disable automatic pulling for security
docker_host = ExecutorHost.objects.create(
    name="locked-host",
    connection_string="unix:///var/run/docker.sock",
    auto_pull_images=False,  # Only use local images
    executor_type="docker"
)
```

#### Private Registry Configuration

```python
# Configure private registry access
docker_host = ExecutorHost.objects.create(
    name="private-registry-host",
    connection_string="unix:///var/run/docker.sock",
    executor_config={
        "registry_auth": {
            "username": "registry_user",
            "password": "registry_password",
            "email": "user@example.com",
            "serveraddress": "registry.example.com"
        }
    },
    executor_type="docker"
)

# Use private registry image
job = ContainerJob.objects.create_job(
    image="registry.example.com/my-app:latest",
    command="./run-tests.sh"
)
```

### Container Networking

#### Network Configuration

```python
# Simple bridge networking (default)
job = ContainerJob.objects.create_job(
    image="nginx:alpine",
    command="nginx -g 'daemon off;'",
    network_configuration=[
        {"network_name": "bridge", "aliases": []}
    ]
)

# Custom network with aliases
job = ContainerJob.objects.create_job(
    image="redis:alpine",
    command="redis-server",
    network_configuration=[
        {
            "network_name": "app-network", 
            "aliases": ["cache", "redis-primary"]
        }
    ]
)

# Multi-network configuration
job = ContainerJob.objects.create_job(
    image="app:latest",
    command="./start-service.sh",
    network_configuration=[
        {"network_name": "frontend-network", "aliases": ["api"]},
        {"network_name": "backend-network", "aliases": ["service"]}
    ]
)
```

#### Network Creation

```bash
# Create custom networks before job execution
docker network create app-network
docker network create backend-network --driver bridge --subnet=172.20.0.0/16
```

### Volume Management

#### Temporary File Handling

The system automatically manages temporary files within containers. For persistent data:

```python
# Note: Direct volume mounting not exposed in current API
# Use init containers or data containers for complex storage needs

# Example: Data initialization container
init_job = ContainerJob.objects.create_job(
    image="alpine:latest",
    command="wget -O /tmp/data.csv https://example.com/dataset.csv",
    name="data-downloader"
)

# Processing container that uses prepared data
process_job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python process_data.py",
    name="data-processor"
)
```

#### Log Volume Management

Logs are automatically collected and stored in the Django database:

```python
# Access logs after job completion
completed_job = ContainerJob.objects.get(id=job_id)
print("STDOUT:", completed_job.stdout_log)
print("STDERR:", completed_job.stderr_log)
print("Clean Output:", completed_job.clean_output)

# Parse structured output
if completed_job.parsed_output:
    result_data = completed_job.parsed_output
```

## ExecutorHost Setup

### Docker Executor Configuration

```python
# Local Unix socket host (development)
local_host = ExecutorHost.objects.create(
    name="local-docker",
    host_type="unix",
    connection_string="unix:///var/run/docker.sock",
    executor_type="docker",
    max_concurrent_jobs=5,
    weight=100,
    is_active=True
)

# Remote TCP host (production)
remote_host = ExecutorHost.objects.create(
    name="production-docker-01",
    host_type="tcp", 
    connection_string="tcp://docker.example.com:2376",
    tls_enabled=True,
    tls_verify=True,
    executor_type="docker",
    max_concurrent_jobs=20,
    weight=200,  # Higher weight = more preferred
    is_active=True,
    executor_config={
        "timeout": 60,
        "auto_pull_images": True
    }
)
```

### Connection String Formats

| Host Type | Format | Example | Use Case |
|-----------|--------|---------|----------|
| Unix Socket | `unix://` | `unix:///var/run/docker.sock` | Local development |
| TCP | `tcp://` | `tcp://192.168.1.100:2376` | Remote hosts |
| Secure TCP | `tcp://` with TLS | `tcp://docker.example.com:2376` | Production |

### Health Checking

The system automatically verifies Docker host health:

```python
from container_manager.executors.factory import ExecutorFactory

# Check host health
executor = ExecutorFactory.create_executor("docker", {"docker_host": docker_host})
health = executor.get_health_status()

if health["healthy"]:
    print(f"Host healthy, response time: {health['response_time']:.2f}s")
else:
    print(f"Host unhealthy: {health['error']}")
```

### Load Balancing

Configure multiple Docker hosts for load distribution:

```python
# Multiple hosts with different weights
hosts = [
    {"name": "docker-01", "weight": 100, "max_jobs": 10},
    {"name": "docker-02", "weight": 150, "max_jobs": 15}, 
    {"name": "docker-03", "weight": 200, "max_jobs": 20}
]

for host_config in hosts:
    ExecutorHost.objects.create(
        name=host_config["name"],
        connection_string=f"tcp://{host_config['name']}.example.com:2376",
        executor_type="docker",
        weight=host_config["weight"],
        max_concurrent_jobs=host_config["max_jobs"],
        is_active=True
    )
```

## Container Job Configuration

### Basic Job Creation

```python
from container_manager.models import ContainerJob, ExecutorHost

# Get a Docker host
docker_host = ExecutorHost.objects.filter(
    executor_type="docker", 
    is_active=True
).first()

# Create a simple job
job = ContainerJob.objects.create(
    docker_host=docker_host,
    docker_image="python:3.11-slim",
    command="python -c 'print(\"Hello Docker World\")'",
    name="hello-world-job",
    memory_limit=256,
    cpu_limit=1.0,
    timeout_seconds=300
)
```

### Using the Convenience Manager

```python
# Simplified job creation with environment variables
job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python app.py",
    name="data-processing-job",
    environment_vars={
        "DEBUG": "false",
        "WORKERS": "4",
        "LOG_LEVEL": "INFO"
    },
    memory_limit=512,
    cpu_limit=2.0,
    timeout_seconds=1800
)
```

### Resource Limits

#### Memory Limits

```python
# Memory limit configuration (in MB)
jobs = [
    # Lightweight task
    {"image": "alpine:latest", "memory": 64, "desc": "Basic shell commands"},
    
    # Standard application  
    {"image": "python:3.11", "memory": 256, "desc": "Python scripts"},
    
    # Memory-intensive processing
    {"image": "datascience:latest", "memory": 2048, "desc": "Data analysis"},
]

for job_config in jobs:
    ContainerJob.objects.create_job(
        image=job_config["image"],
        command="echo 'Processing...'",
        memory_limit=job_config["memory"],
        name=job_config["desc"]
    )
```

#### CPU Limits

```python
# CPU limit configuration (in cores)
cpu_configs = [
    {"cores": 0.5, "use_case": "Background tasks"},
    {"cores": 1.0, "use_case": "Standard processing"},
    {"cores": 2.0, "use_case": "CPU-intensive work"},
]

for config in cpu_configs:
    ContainerJob.objects.create_job(
        image="ubuntu:22.04",
        command="stress --cpu 1 --timeout 60s",
        cpu_limit=config["cores"],
        name=f"cpu-test-{config['cores']}-cores"
    )
```

### Command Formats

#### Shell vs Exec Form

```python
# Shell form (supports shell features)
shell_job = ContainerJob.objects.create_job(
    image="bash:latest",
    command="echo $HOME && ls -la /tmp && date",  # Shell features
    name="shell-command"
)

# Exec form (direct execution, more secure)
exec_job = ContainerJob.objects.create_job(
    image="python:3.11",
    command='python -c "import os; print(os.getcwd())"',  # Direct execution
    name="exec-command"
)

# Complex multi-step commands
complex_job = ContainerJob.objects.create_job(
    image="node:18",
    command="/bin/bash -c 'npm install && npm test && npm run build'",
    name="build-and-test",
    timeout_seconds=1800
)
```

### Working Directory Configuration

```python
# Set working directory for command execution
job = ContainerJob.objects.create_job(
    image="node:18",
    command="npm test",
    working_directory="/app",
    name="node-app-test"
)
```

## Environment Variable Management

### Environment Templates

Create reusable environment configurations:

```python
from container_manager.models import EnvironmentVariableTemplate

# Development environment template
dev_template = EnvironmentVariableTemplate.objects.create(
    name="python-development",
    description="Standard Python development environment",
    environment_variables_text="""
DEBUG=true
LOG_LEVEL=DEBUG
PYTHONPATH=/app
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
DATABASE_URL=sqlite:///dev.db
"""
)

# Production environment template  
prod_template = EnvironmentVariableTemplate.objects.create(
    name="python-production",
    description="Python production environment",
    environment_variables_text="""
DEBUG=false
LOG_LEVEL=INFO
PYTHONPATH=/app
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
DATABASE_URL=postgresql://user:pass@db:5432/prod
REDIS_URL=redis://redis:6379/0
"""
)
```

### Using Templates with Jobs

```python
# Use template directly
job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python manage.py test",
    environment_template="python-development",
    name="django-tests"
)

# Override template variables
job = ContainerJob.objects.create_job(
    image="python:3.11", 
    command="python manage.py migrate",
    environment_template="python-production",
    environment_vars={
        "DATABASE_URL": "postgresql://user:pass@prod-db:5432/myapp",
        "DEBUG": "false"  # Override template value
    },
    name="production-migration"
)
```

### Secure Secret Handling

```python
# Avoid secrets in environment template text
# Use environment variable overrides for secrets
job = ContainerJob.objects.create_job(
    image="app:latest",
    command="./deploy.sh",
    environment_template="base-config",
    environment_vars={
        "API_KEY": os.environ["SECRET_API_KEY"],
        "DB_PASSWORD": os.environ["SECRET_DB_PASSWORD"]
    },
    name="secure-deployment"
)
```

### Variable Interpolation

Environment variables support basic key=value format:

```python
# Complex environment configuration
complex_env = EnvironmentVariableTemplate.objects.create(
    name="microservice-config",
    environment_variables_text="""
# Service configuration
SERVICE_NAME=user-service
SERVICE_PORT=8080
SERVICE_VERSION=1.2.3

# Database configuration  
DB_HOST=postgres.internal
DB_PORT=5432
DB_NAME=userdb
DB_POOL_SIZE=10

# Cache configuration
CACHE_TYPE=redis
CACHE_HOST=redis.internal
CACHE_TTL=3600

# Monitoring
METRICS_ENABLED=true
HEALTH_CHECK_PATH=/health
LOG_FORMAT=json
"""
)
```

## Security Considerations

### Container Isolation

#### User Namespaces

```python
# Configure non-root user execution
# Note: User configuration handled by base image
job = ContainerJob.objects.create_job(
    image="python:3.11-slim",  # Uses non-root user by default
    command="whoami && id",
    name="security-check"
)
```

#### Security Contexts

```mermaid
graph TD
    A[Container Creation] --> B[Resource Limits Applied]
    B --> C[Network Isolation]
    C --> D[User Namespace Isolation]
    D --> E[Read-only Root Filesystem]
    E --> F[Capabilities Dropped]
    F --> G[Security Profile Applied]
    
    subgraph "Security Boundaries"
        H[Host Kernel]
        I[Container Runtime] 
        J[Process Isolation]
        K[Filesystem Isolation]
        L[Network Namespace]
    end
```

### Image Security

#### Trusted Registries

```python
# Configure trusted registry
secure_host = ExecutorHost.objects.create(
    name="secure-docker-host",
    connection_string="unix:///var/run/docker.sock",
    executor_config={
        "allowed_registries": [
            "docker.io",
            "registry.example.com",
            "gcr.io/my-project"
        ],
        "require_signed_images": True
    },
    executor_type="docker"
)
```

#### Image Scanning Integration

```bash
# Pre-job image scanning (external process)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image python:3.11-slim

# Only proceed with job if scan passes
```

### Network Security

#### Container Network Isolation

```python
# Isolated network for sensitive jobs
isolated_job = ContainerJob.objects.create_job(
    image="secure-app:latest",
    command="./process-sensitive-data.sh",
    network_configuration=[
        {"network_name": "isolated-network", "aliases": []}
    ],
    name="secure-processing"
)
```

### Resource Security

#### Preventing Resource Exhaustion

```python
# System-wide security limits (enforced by LLM Agent Guidelines)
SECURITY_LIMITS = {
    "max_memory_mb": 2048,      # 2GB maximum
    "max_cpu_cores": 2.0,       # 2 CPU cores maximum  
    "max_timeout_seconds": 3600, # 1 hour maximum
}

# Validate against security limits before job creation
def create_secure_job(image, command, **kwargs):
    memory = kwargs.get('memory_limit', 0)
    cpu = kwargs.get('cpu_limit', 0)
    timeout = kwargs.get('timeout_seconds', 300)
    
    if memory > SECURITY_LIMITS['max_memory_mb']:
        raise ValueError(f"Memory limit {memory}MB exceeds maximum {SECURITY_LIMITS['max_memory_mb']}MB")
    
    if cpu > SECURITY_LIMITS['max_cpu_cores']:
        raise ValueError(f"CPU limit {cpu} exceeds maximum {SECURITY_LIMITS['max_cpu_cores']} cores")
        
    if timeout > SECURITY_LIMITS['max_timeout_seconds']:
        raise ValueError(f"Timeout {timeout}s exceeds maximum {SECURITY_LIMITS['max_timeout_seconds']}s")
    
    return ContainerJob.objects.create_job(image=image, command=command, **kwargs)
```

### Docker Daemon Security

#### Socket Permissions

```bash
# Secure Docker socket permissions
sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock

# Audit socket access
sudo auditctl -w /var/run/docker.sock -p wa -k docker-socket
```

#### TLS Configuration

```bash
# Generate secure TLS certificates
mkdir -p /etc/docker/certs
cd /etc/docker/certs

# Create CA private key
openssl genrsa -aes256 -out ca-key.pem 4096

# Create CA certificate
openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem

# Create server private key and certificate
openssl genrsa -out server-key.pem 4096
openssl req -subj "/CN=docker-host" -sha256 -new -key server-key.pem -out server.csr
openssl x509 -req -days 365 -sha256 -in server.csr -CA ca.pem -CAkey ca-key.pem -out server-cert.pem

# Set secure permissions
chmod 400 ca-key.pem server-key.pem
chmod 444 ca.pem server-cert.pem
```

## Monitoring and Logging

### Container Logs

#### Automatic Log Collection

```python
# Logs are automatically collected during job execution
def monitor_job_progress(job_id):
    job = ContainerJob.objects.get(id=job_id)
    
    # Real-time status checking
    from container_manager.executors.factory import ExecutorFactory
    executor = ExecutorFactory.create_executor("docker", {"docker_host": job.docker_host})
    
    status = executor.check_status(job.get_execution_identifier())
    print(f"Current status: {status}")
    
    # Get current logs (if container is running)
    if status == "running":
        stdout, stderr = executor.get_logs(job.get_execution_identifier())
        print(f"Recent output: {stdout[-500:]}")  # Last 500 chars
```

#### Log Processing

```python
# Access processed logs after completion
completed_job = ContainerJob.objects.get(id=job_id, status="completed")

# Raw logs with timestamps
print("Raw STDOUT:", completed_job.stdout_log)
print("Raw STDERR:", completed_job.stderr_log)

# Clean output (timestamps removed)
print("Clean Output:", completed_job.clean_output)

# Parsed output (JSON if applicable)
if completed_job.parsed_output:
    import json
    result_data = completed_job.parsed_output
    print("Structured Result:", json.dumps(result_data, indent=2))
```

### Resource Monitoring

#### Real-time Resource Tracking

```python
# Resource usage is automatically tracked
def analyze_job_performance(job_id):
    job = ContainerJob.objects.get(id=job_id)
    
    if job.max_memory_usage:
        memory_mb = job.max_memory_usage / (1024 * 1024)
        print(f"Peak memory usage: {memory_mb:.2f} MB")
    
    if job.cpu_usage_percent:
        print(f"Average CPU usage: {job.cpu_usage_percent:.2f}%")
    
    if job.duration:
        print(f"Execution time: {job.duration}")
        
    # Resource efficiency analysis
    if job.memory_limit and job.max_memory_usage:
        efficiency = (job.max_memory_usage / (1024 * 1024)) / job.memory_limit * 100
        print(f"Memory efficiency: {efficiency:.1f}%")
```

### Health Monitoring

#### Docker Host Health Checks

```python
from container_manager.models import ExecutorHost
from container_manager.executors.factory import ExecutorFactory

def check_all_docker_hosts():
    """Monitor health of all Docker hosts"""
    hosts = ExecutorHost.objects.filter(executor_type="docker", is_active=True)
    
    for host in hosts:
        try:
            executor = ExecutorFactory.create_executor("docker", {"docker_host": host})
            health = executor.get_health_status()
            
            if health["healthy"]:
                print(f"✅ {host.name}: Healthy ({health['response_time']:.2f}s)")
            else:
                print(f"❌ {host.name}: Unhealthy - {health['error']}")
                
                # Optionally deactivate unhealthy hosts
                # host.is_active = False
                # host.save()
                
        except Exception as e:
            print(f"🔥 {host.name}: Error checking health - {e}")
```

#### Job Monitoring Dashboard

```python
def container_job_dashboard():
    """Simple dashboard for container job monitoring"""
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Job status summary
    status_counts = ContainerJob.objects.values('status').annotate(count=Count('id'))
    print("📊 Job Status Summary:")
    for status in status_counts:
        print(f"  {status['status']}: {status['count']}")
    
    # Recent activity (last 24 hours)
    yesterday = datetime.now() - timedelta(days=1)
    recent_jobs = ContainerJob.objects.filter(created_at__gte=yesterday)
    
    print(f"\n🕐 Recent Activity (last 24h): {recent_jobs.count()} jobs")
    
    # Failed jobs requiring attention
    failed_jobs = ContainerJob.objects.filter(status="failed").order_by('-created_at')[:5]
    if failed_jobs:
        print("\n🚨 Recent Failures:")
        for job in failed_jobs:
            print(f"  {job.name or 'Unnamed'} ({job.id}) - {job.created_at}")
```

### Log Aggregation

#### Centralized Logging Strategy

```python
# Configure structured logging for container jobs
import logging
import json
from django.conf import settings

def setup_container_logging():
    """Configure structured logging for container job tracking"""
    
    # Create container-specific logger
    container_logger = logging.getLogger('container_manager.jobs')
    
    # JSON formatter for log aggregation
    class ContainerJobFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                'timestamp': self.formatTime(record),
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
            }
            
            # Add job-specific context if available
            if hasattr(record, 'job_id'):
                log_data['job_id'] = record.job_id
            if hasattr(record, 'execution_id'):
                log_data['execution_id'] = record.execution_id
            if hasattr(record, 'docker_host'):
                log_data['docker_host'] = record.docker_host
                
            return json.dumps(log_data)
    
    # Configure handler
    handler = logging.StreamHandler()
    handler.setFormatter(ContainerJobFormatter())
    container_logger.addHandler(handler)
    container_logger.setLevel(logging.INFO)
    
    return container_logger

# Usage in job processing
logger = setup_container_logging()

def log_job_event(job, event, **kwargs):
    logger.info(
        f"Job {event}: {job.name or 'unnamed'}",
        extra={
            'job_id': str(job.id),
            'execution_id': job.get_execution_identifier(),
            'docker_host': job.docker_host.name,
            **kwargs
        }
    )
```

## Advanced Docker Features

### Multi-stage Builds

Optimize container images for the job execution environment:

```dockerfile
# Example optimized Dockerfile for job containers
FROM python:3.11 AS builder

# Install build dependencies
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry export -f requirements.txt | pip install --no-cache-dir -r /dev/stdin

# Production stage
FROM python:3.11-slim AS runtime

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Add non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

# Application code
COPY app/ /app/
WORKDIR /app

# Default command
CMD ["python", "main.py"]
```

### Docker Compose Integration

Development environment setup:

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  django-container-manager:
    build: .
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DEBUG=true
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/container_manager
    depends_on:
      - postgres
      - redis
    networks:
      - app-network

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=container_manager
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app-network

  redis:
    image: redis:7-alpine
    networks:
      - app-network

volumes:
  postgres_data:

networks:
  app-network:
    driver: bridge
```

### Container Orchestration

#### Kubernetes Integration

```yaml
# k8s-job-executor.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: django-container-manager-config
data:
  settings.py: |
    CONTAINER_MANAGER_SETTINGS = {
        'DOCKER_TIMEOUT': 60,
        'AUTO_PULL_IMAGES': True,
        'IMMEDIATE_CLEANUP': False,
        'MAX_CONCURRENT_JOBS': 50
    }

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-container-manager
spec:
  replicas: 3
  selector:
    matchLabels:
      app: django-container-manager
  template:
    metadata:
      labels:
        app: django-container-manager
    spec:
      containers:
      - name: django-app
        image: myregistry/django-container-manager:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        volumeMounts:
        - name: docker-socket
          mountPath: /var/run/docker.sock
        - name: config
          mountPath: /app/config
      volumes:
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
      - name: config
        configMap:
          name: django-container-manager-config
```

### Registry Management

#### Private Registry Configuration

```python
# Configure multiple registries
registry_configs = [
    {
        "name": "docker-hub",
        "url": "https://index.docker.io/v1/",
        "auth_required": False
    },
    {
        "name": "company-registry", 
        "url": "https://registry.company.com",
        "auth_required": True,
        "username": "service-account",
        "password": "secure-token"
    },
    {
        "name": "gcr",
        "url": "https://gcr.io",
        "auth_required": True,
        "credential_helper": "gcloud"
    }
]

# Use specific registry
job = ContainerJob.objects.create_job(
    image="registry.company.com/my-app:v1.2.3",
    command="./run-production-task.sh",
    name="production-task"
)
```

### Image Caching

#### Optimizing Image Pull Performance

```python
# Pre-warm image cache
def prewarm_image_cache(images, docker_host):
    """Pre-pull commonly used images to improve job startup time"""
    from container_manager.executors.factory import ExecutorFactory
    
    executor = ExecutorFactory.create_executor("docker", {"docker_host": docker_host})
    client = executor._get_client(docker_host)
    
    for image in images:
        try:
            print(f"Pre-warming {image}...")
            client.images.pull(image)
            print(f"✅ {image} cached")
        except Exception as e:
            print(f"❌ Failed to cache {image}: {e}")

# Common images to pre-warm
common_images = [
    "python:3.11-slim",
    "node:18-alpine", 
    "alpine:latest",
    "ubuntu:22.04",
    "postgres:15"
]

# Pre-warm on all active Docker hosts
for host in ExecutorHost.objects.filter(executor_type="docker", is_active=True):
    prewarm_image_cache(common_images, host)
```

## Troubleshooting Guide

### Common Docker Issues

#### Permission Denied Accessing Docker Socket

```mermaid
flowchart TD
    A[Permission Denied Error] --> B{User in docker group?}
    B -->|No| C[Add user to docker group]
    C --> D[sudo usermod -aG docker $USER]
    D --> E[Logout and login again]
    E --> F[Test: docker ps]
    
    B -->|Yes| G{Socket permissions correct?}
    G -->|No| H[Fix socket permissions]
    H --> I[sudo chmod 666 /var/run/docker.sock]
    I --> F
    
    G -->|Yes| J{Docker daemon running?}
    J -->|No| K[Start Docker daemon]
    K --> L[sudo systemctl start docker]
    L --> F
    
    J -->|Yes| M[Check Docker daemon logs]
    M --> N[sudo journalctl -u docker.service]
```

**Solution Steps:**

```bash
# 1. Check current user groups
groups $USER

# 2. Add user to docker group if not present
sudo usermod -aG docker $USER

# 3. Verify socket permissions
ls -la /var/run/docker.sock

# 4. Fix permissions if needed
sudo chmod 666 /var/run/docker.sock

# 5. Restart Docker daemon
sudo systemctl restart docker

# 6. Test access
docker ps
```

#### Container Fails to Start

```python
# Debug container startup failures
def debug_container_failure(job_id):
    job = ContainerJob.objects.get(id=job_id)
    
    if job.status == "failed":
        print(f"Job {job.id} failed to start")
        print(f"Image: {job.docker_image}")
        print(f"Command: {job.command}")
        print(f"Host: {job.docker_host.name}")
        
        # Check Docker daemon logs
        print("\n--- Docker Logs ---")
        print(job.docker_log or "No Docker logs available")
        
        # Check stderr for error messages
        print("\n--- Container STDERR ---") 
        print(job.stderr_log or "No stderr output")
        
        # Verify image exists
        from container_manager.executors.factory import ExecutorFactory
        executor = ExecutorFactory.create_executor("docker", {"docker_host": job.docker_host})
        client = executor._get_client(job.docker_host)
        
        try:
            image = client.images.get(job.docker_image)
            print(f"\n✅ Image {job.docker_image} exists locally")
            print(f"Image ID: {image.id}")
            print(f"Tags: {image.tags}")
        except Exception as e:
            print(f"\n❌ Image {job.docker_image} not found: {e}")
```

#### Image Pull Failures

```bash
# Diagnose image pull issues

# 1. Test manual pull
docker pull python:3.11-slim

# 2. Check registry connectivity
docker login registry.example.com

# 3. Verify DNS resolution
nslookup registry.example.com

# 4. Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
echo $NO_PROXY

# 5. Test with different tag
docker pull python:3.11  # without -slim suffix
```

#### Network Connectivity Issues

```python
# Debug container networking
def debug_network_connectivity(job_id):
    job = ContainerJob.objects.get(id=job_id)
    networks = job.get_network_names()
    
    print(f"Configured networks: {networks}")
    
    # Check if networks exist
    from container_manager.executors.factory import ExecutorFactory
    executor = ExecutorFactory.create_executor("docker", {"docker_host": job.docker_host})
    client = executor._get_client(job.docker_host)
    
    for network_name in networks:
        try:
            network = client.networks.get(network_name)
            print(f"✅ Network {network_name} exists")
            print(f"   Driver: {network.attrs['Driver']}")
            print(f"   Subnet: {network.attrs.get('IPAM', {}).get('Config', [{}])[0].get('Subnet', 'N/A')}")
        except Exception as e:
            print(f"❌ Network {network_name} not found: {e}")
            
    # List all available networks
    print("\nAvailable networks:")
    for network in client.networks.list():
        print(f"  - {network.name} ({network.attrs['Driver']})")
```

#### Resource Limit Exceeded

```python
# Monitor and diagnose resource issues
def diagnose_resource_limits(job_id):
    job = ContainerJob.objects.get(id=job_id)
    
    print(f"Resource Configuration:")
    print(f"  Memory Limit: {job.memory_limit}MB")
    print(f"  CPU Limit: {job.cpu_limit} cores")
    print(f"  Timeout: {job.timeout_seconds}s")
    
    print(f"\nActual Usage:")
    print(f"  Peak Memory: {job.max_memory_usage / (1024*1024) if job.max_memory_usage else 'N/A':.2f}MB")
    print(f"  Avg CPU: {job.cpu_usage_percent or 'N/A'}%")
    print(f"  Duration: {job.duration or 'N/A'}")
    
    # Check for resource exhaustion indicators
    if job.stderr_log and "killed" in job.stderr_log.lower():
        print("\n⚠️  Container may have been killed due to memory exhaustion")
        
    if job.status == "timeout":
        print("\n⚠️  Job exceeded timeout limit")
        
    # Recommend resource adjustments
    if job.max_memory_usage and job.memory_limit:
        memory_usage_pct = (job.max_memory_usage / (1024*1024)) / job.memory_limit * 100
        if memory_usage_pct > 90:
            recommended_memory = int(job.memory_limit * 1.5)
            print(f"\n💡 Consider increasing memory limit to {recommended_memory}MB")
```

### Debugging Techniques

#### Docker Daemon Log Examination

```bash
# View Docker daemon logs
sudo journalctl -u docker.service -f

# View recent Docker daemon activity
sudo journalctl -u docker.service --since "1 hour ago"

# Debug specific container events
docker events --filter container=<container_id>

# View daemon configuration
docker system info
```

#### Container Inspection Commands

```bash
# Inspect container configuration
docker inspect <container_id>

# View container processes
docker top <container_id>

# Execute commands in running container
docker exec -it <container_id> /bin/bash

# View container filesystem changes
docker diff <container_id>

# Check container resource usage
docker stats <container_id>
```

#### Network Debugging

```bash
# List Docker networks
docker network ls

# Inspect network configuration
docker network inspect bridge

# Test network connectivity from container
docker run --rm --network=<network_name> alpine ping -c 3 google.com

# View network interfaces in container
docker exec <container_id> ip addr show
```

#### Resource Usage Analysis

```python
# Advanced resource monitoring
def analyze_resource_patterns():
    """Analyze resource usage patterns across all jobs"""
    from django.db.models import Avg, Max, Count
    from datetime import datetime, timedelta
    
    # Memory usage analysis
    memory_stats = ContainerJob.objects.filter(
        max_memory_usage__isnull=False
    ).aggregate(
        avg_memory=Avg('max_memory_usage'),
        max_memory=Max('max_memory_usage'),
        job_count=Count('id')
    )
    
    print("Memory Usage Statistics:")
    print(f"  Average: {memory_stats['avg_memory'] / (1024*1024):.2f}MB")
    print(f"  Peak: {memory_stats['max_memory'] / (1024*1024):.2f}MB")
    print(f"  Jobs analyzed: {memory_stats['job_count']}")
    
    # CPU usage patterns
    cpu_stats = ContainerJob.objects.filter(
        cpu_usage_percent__isnull=False
    ).aggregate(
        avg_cpu=Avg('cpu_usage_percent'),
        max_cpu=Max('cpu_usage_percent')
    )
    
    print(f"\nCPU Usage Statistics:")
    print(f"  Average: {cpu_stats['avg_cpu']:.2f}%") 
    print(f"  Peak: {cpu_stats['max_cpu']:.2f}%")
    
    # Identify resource-intensive jobs
    print(f"\nTop Resource Consumers:")
    high_memory_jobs = ContainerJob.objects.filter(
        max_memory_usage__isnull=False
    ).order_by('-max_memory_usage')[:5]
    
    for job in high_memory_jobs:
        memory_mb = job.max_memory_usage / (1024*1024)
        print(f"  {job.name or 'Unnamed'}: {memory_mb:.2f}MB")
```

### Performance Issues

#### Slow Image Pulls

```python
# Optimize image pull performance
def optimize_image_pulls():
    """Implement strategies to speed up image pulls"""
    
    # 1. Use image layer caching
    print("Implementing image optimization strategies:")
    
    # 2. Pre-warm commonly used images
    common_images = [
        "python:3.11-slim",
        "alpine:latest", 
        "ubuntu:22.04"
    ]
    
    for host in ExecutorHost.objects.filter(executor_type="docker", is_active=True):
        print(f"\nPre-warming images on {host.name}:")
        for image in common_images:
            # Check if image exists
            from container_manager.executors.factory import ExecutorFactory
            executor = ExecutorFactory.create_executor("docker", {"docker_host": host})
            client = executor._get_client(host)
            
            try:
                client.images.get(image)
                print(f"  ✅ {image} (cached)")
            except:
                print(f"  📥 Pulling {image}...")
                client.images.pull(image)
                print(f"  ✅ {image} (pulled)")
```

#### Container Startup Delays

```python
# Measure and optimize container startup time
def measure_startup_performance():
    """Analyze container startup performance"""
    from django.db.models import Avg, F
    from datetime import timedelta
    
    # Calculate startup times (launched to running)
    jobs_with_timing = ContainerJob.objects.filter(
        started_at__isnull=False,
        created_at__isnull=False
    ).annotate(
        startup_seconds=F('started_at') - F('created_at')
    )
    
    avg_startup = jobs_with_timing.aggregate(
        avg_startup=Avg('startup_seconds')
    )['avg_startup']
    
    if avg_startup:
        avg_seconds = avg_startup.total_seconds()
        print(f"Average container startup time: {avg_seconds:.2f}s")
        
        if avg_seconds > 10:
            print("⚠️  Startup time is high. Consider:")
            print("   - Using smaller base images")
            print("   - Pre-warming image cache")
            print("   - Optimizing Docker daemon configuration")
            print("   - Using image layer caching")
```

#### Log Collection Bottlenecks

```python
# Optimize log collection performance
def optimize_log_collection():
    """Configure efficient log collection"""
    
    # Monitor log sizes
    large_log_jobs = ContainerJob.objects.filter(
        stdout_log__isnull=False
    ).extra(
        select={'log_size': 'LENGTH(stdout_log)'}
    ).filter(
        log_size__gt=1024*1024  # > 1MB
    ).order_by('-log_size')[:10]
    
    print("Jobs with large logs:")
    for job in large_log_jobs:
        log_size_mb = len(job.stdout_log or '') / (1024*1024)
        print(f"  {job.name or 'Unnamed'}: {log_size_mb:.2f}MB")
    
    print("\nLog optimization recommendations:")
    print("  - Set log rotation in container applications") 
    print("  - Use structured logging (JSON)")
    print("  - Consider external log aggregation")
    print("  - Implement log size limits")
```

## Best Practices

### Production-Ready Docker Usage

#### Resource Planning

```python
# Resource planning guidelines
RESOURCE_GUIDELINES = {
    "micro_tasks": {
        "memory_limit": 128,     # MB
        "cpu_limit": 0.5,        # cores
        "timeout_seconds": 300,   # 5 minutes
        "examples": ["simple scripts", "basic data validation"]
    },
    "standard_tasks": {
        "memory_limit": 512,     # MB  
        "cpu_limit": 1.0,        # cores
        "timeout_seconds": 1800,  # 30 minutes
        "examples": ["API calls", "data processing", "file operations"]
    },
    "heavy_tasks": {
        "memory_limit": 2048,    # MB
        "cpu_limit": 2.0,        # cores
        "timeout_seconds": 3600,  # 1 hour
        "examples": ["machine learning", "large data analysis", "complex builds"]
    }
}

def recommend_resources(task_description):
    """Recommend resource allocation based on task type"""
    for category, config in RESOURCE_GUIDELINES.items():
        print(f"\n{category.replace('_', ' ').title()}:")
        print(f"  Memory: {config['memory_limit']}MB")
        print(f"  CPU: {config['cpu_limit']} cores")
        print(f"  Timeout: {config['timeout_seconds']}s")
        print(f"  Examples: {', '.join(config['examples'])}")
```

#### Security Hardening

```python
# Security checklist for production
def security_audit():
    """Audit Docker security configuration"""
    
    print("🔒 Docker Security Audit")
    print("=" * 50)
    
    # Check ExecutorHost configurations
    hosts = ExecutorHost.objects.filter(executor_type="docker", is_active=True)
    
    for host in hosts:
        print(f"\n📍 {host.name}:")
        
        # TLS configuration
        if host.host_type == "tcp":
            if host.tls_enabled:
                print("  ✅ TLS enabled")
                if host.tls_verify:
                    print("  ✅ TLS verification enabled")
                else:
                    print("  ⚠️  TLS verification disabled")
            else:
                print("  ❌ TLS disabled for TCP connection")
        
        # Connection string security
        if "://localhost" in host.connection_string or "://127.0.0.1" in host.connection_string:
            print("  ✅ Local connection")
        else:
            print("  ℹ️  Remote connection - ensure network security")
        
        # Resource limits
        if host.max_concurrent_jobs > 50:
            print("  ⚠️  High concurrent job limit - monitor resource usage")
        else:
            print("  ✅ Reasonable concurrent job limit")
    
    # Check job configurations
    recent_jobs = ContainerJob.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    )
    
    print(f"\n📊 Recent Jobs Analysis (last 7 days): {recent_jobs.count()} jobs")
    
    # Resource limit analysis
    unlimited_memory = recent_jobs.filter(memory_limit__isnull=True).count()
    unlimited_cpu = recent_jobs.filter(cpu_limit__isnull=True).count()
    
    if unlimited_memory > 0:
        print(f"  ⚠️  {unlimited_memory} jobs without memory limits")
    if unlimited_cpu > 0:
        print(f"  ⚠️  {unlimited_cpu} jobs without CPU limits")
    
    # High resource usage
    high_memory_jobs = recent_jobs.filter(memory_limit__gt=1024).count()
    high_cpu_jobs = recent_jobs.filter(cpu_limit__gt=2.0).count()
    
    print(f"  📈 {high_memory_jobs} jobs with >1GB memory")
    print(f"  📈 {high_cpu_jobs} jobs with >2 CPU cores")
```

#### Monitoring and Alerting

```python
# Production monitoring setup
def setup_production_monitoring():
    """Configure monitoring and alerting for production"""
    
    import logging
    from django.core.mail import send_mail
    from django.conf import settings
    
    # Custom alert system
    class ContainerJobAlert:
        def __init__(self):
            self.logger = logging.getLogger('container_manager.alerts')
        
        def check_failed_jobs(self):
            """Alert on job failures"""
            recent_failures = ContainerJob.objects.filter(
                status="failed",
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_failures > 5:  # Threshold
                self.send_alert(
                    f"High failure rate: {recent_failures} jobs failed in last hour",
                    level="error"
                )
        
        def check_resource_usage(self):
            """Alert on high resource usage"""
            high_memory_jobs = ContainerJob.objects.filter(
                status="running",
                memory_limit__gte=1024
            ).count()
            
            if high_memory_jobs > 10:  # Threshold
                self.send_alert(
                    f"High memory usage: {high_memory_jobs} jobs using >1GB",
                    level="warning"
                )
        
        def check_host_health(self):
            """Alert on host health issues"""
            from container_manager.executors.factory import ExecutorFactory
            
            unhealthy_hosts = []
            for host in ExecutorHost.objects.filter(executor_type="docker", is_active=True):
                try:
                    executor = ExecutorFactory.create_executor("docker", {"docker_host": host})
                    health = executor.get_health_status()
                    if not health["healthy"]:
                        unhealthy_hosts.append(host.name)
                except Exception:
                    unhealthy_hosts.append(host.name)
            
            if unhealthy_hosts:
                self.send_alert(
                    f"Unhealthy Docker hosts: {', '.join(unhealthy_hosts)}",
                    level="error"
                )
        
        def send_alert(self, message, level="info"):
            """Send alert via logging and email"""
            self.logger.log(
                getattr(logging, level.upper()),
                f"Container Manager Alert: {message}"
            )
            
            if level in ["error", "critical"] and hasattr(settings, 'ADMINS'):
                send_mail(
                    subject=f"Container Manager Alert - {level.upper()}",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin[1] for admin in settings.ADMINS],
                    fail_silently=True
                )
    
    return ContainerJobAlert()
```

#### Capacity Planning

```python
# Capacity planning tools
def capacity_planning_analysis():
    """Analyze capacity requirements and usage patterns"""
    
    from django.db.models import Sum, Avg, Count
    from datetime import datetime, timedelta
    
    print("📊 Capacity Planning Analysis")
    print("=" * 50)
    
    # Historical usage patterns
    time_periods = [
        ("Last 24 hours", timedelta(hours=24)),
        ("Last 7 days", timedelta(days=7)), 
        ("Last 30 days", timedelta(days=30))
    ]
    
    for period_name, period_delta in time_periods:
        since = datetime.now() - period_delta
        period_jobs = ContainerJob.objects.filter(created_at__gte=since)
        
        stats = period_jobs.aggregate(
            total_jobs=Count('id'),
            avg_memory=Avg('memory_limit'),
            total_memory=Sum('memory_limit'),
            avg_cpu=Avg('cpu_limit'),
            total_cpu=Sum('cpu_limit')
        )
        
        print(f"\n📅 {period_name}:")
        print(f"  Total jobs: {stats['total_jobs'] or 0}")
        print(f"  Avg memory per job: {stats['avg_memory'] or 0:.1f}MB")
        print(f"  Total memory used: {stats['total_memory'] or 0:.1f}MB")
        print(f"  Avg CPU per job: {stats['avg_cpu'] or 0:.2f} cores")
        print(f"  Total CPU hours: {stats['total_cpu'] or 0:.2f}")
    
    # Peak usage analysis
    print(f"\n🔝 Peak Usage Analysis:")
    
    # Find peak concurrent usage (approximation)
    peak_analysis = """
    SELECT DATE_TRUNC('hour', started_at) as hour,
           COUNT(*) as concurrent_jobs,
           SUM(memory_limit) as total_memory,
           SUM(cpu_limit) as total_cpu
    FROM container_manager_containerjob 
    WHERE started_at IS NOT NULL 
      AND started_at >= NOW() - INTERVAL '7 days'
    GROUP BY hour
    ORDER BY concurrent_jobs DESC
    LIMIT 5;
    """
    
    print("  Run this SQL query for detailed peak analysis:")
    print(f"  {peak_analysis}")
    
    # Capacity recommendations
    active_hosts = ExecutorHost.objects.filter(
        executor_type="docker", 
        is_active=True
    ).count()
    
    total_capacity = ExecutorHost.objects.filter(
        executor_type="docker",
        is_active=True
    ).aggregate(
        total_slots=Sum('max_concurrent_jobs')
    )['total_slots'] or 0
    
    print(f"\n💾 Current Capacity:")
    print(f"  Active Docker hosts: {active_hosts}")
    print(f"  Total job slots: {total_capacity}")
    print(f"  Recommended monitoring threshold: {int(total_capacity * 0.8)} jobs")
```

## Integration Examples

### Management Command Integration

```python
# Example: Custom management command using container jobs
from django.core.management.base import BaseCommand
from container_manager.models import ContainerJob, ExecutorHost

class Command(BaseCommand):
    help = 'Process data files using containerized workers'
    
    def add_arguments(self, parser):
        parser.add_argument('--input-file', required=True)
        parser.add_argument('--workers', type=int, default=1)
        parser.add_argument('--memory', type=int, default=512)
    
    def handle(self, *args, **options):
        input_file = options['input_file']
        workers = options['workers']
        memory_limit = options['memory']
        
        # Get available Docker host
        docker_host = ExecutorHost.objects.filter(
            executor_type="docker",
            is_active=True
        ).first()
        
        if not docker_host:
            self.stdout.write(
                self.style.ERROR('No active Docker hosts available')
            )
            return
        
        # Create processing jobs
        jobs = []
        for i in range(workers):
            job = ContainerJob.objects.create_job(
                image="data-processor:latest",
                command=f"python process.py --input {input_file} --worker {i}",
                name=f"data-worker-{i}",
                memory_limit=memory_limit,
                cpu_limit=1.0,
                environment_vars={
                    "WORKER_ID": str(i),
                    "INPUT_FILE": input_file,
                    "LOG_LEVEL": "INFO"
                }
            )
            jobs.append(job)
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(jobs)} processing jobs')
        )
        
        # Monitor job completion
        from container_manager.management.commands.process_container_jobs import Command as ProcessCommand
        process_cmd = ProcessCommand()
        process_cmd.handle(once=True)
        
        # Report results
        completed = sum(1 for job in jobs if job.status == "completed")
        failed = sum(1 for job in jobs if job.status == "failed")
        
        self.stdout.write(f'Results: {completed} completed, {failed} failed')
```

### API Integration

```python
# Example: REST API for job management
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

class ContainerJobViewSet(viewsets.ModelViewSet):
    queryset = ContainerJob.objects.all()
    serializer_class = ContainerJobSerializer
    
    @action(detail=False, methods=['post'])
    def create_batch(self, request):
        """Create multiple jobs in batch"""
        jobs_data = request.data.get('jobs', [])
        created_jobs = []
        
        for job_data in jobs_data:
            job = ContainerJob.objects.create_job(
                image=job_data['image'],
                command=job_data['command'],
                name=job_data.get('name', ''),
                memory_limit=job_data.get('memory_limit', 256),
                cpu_limit=job_data.get('cpu_limit', 1.0),
                environment_vars=job_data.get('environment_vars', {})
            )
            created_jobs.append(job)
        
        serializer = self.get_serializer(created_jobs, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get job logs"""
        job = get_object_or_404(ContainerJob, pk=pk)
        
        return Response({
            'stdout': job.stdout_log,
            'stderr': job.stderr_log,
            'clean_output': job.clean_output,
            'parsed_output': job.parsed_output
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel running job"""
        job = get_object_or_404(ContainerJob, pk=pk)
        
        if job.status not in ['running', 'launching']:
            return Response(
                {'error': 'Job is not running'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cancel job via executor
        from container_manager.executors.factory import ExecutorFactory
        executor = ExecutorFactory.create_executor("docker", {"docker_host": job.docker_host})
        
        success = executor.cleanup(job.get_execution_identifier())
        if success:
            job.status = "cancelled"
            job.save()
            return Response({'status': 'cancelled'})
        else:
            return Response(
                {'error': 'Failed to cancel job'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
```

### Webhook Integration

```python
# Example: Webhook notifications for job events
import requests
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=ContainerJob)
def job_status_webhook(sender, instance, **kwargs):
    """Send webhook notification on job status changes"""
    
    # Only send for status changes
    if kwargs.get('update_fields') and 'status' not in kwargs['update_fields']:
        return
    
    webhook_url = getattr(settings, 'CONTAINER_JOB_WEBHOOK_URL', None)
    if not webhook_url:
        return
    
    payload = {
        'job_id': str(instance.id),
        'job_name': instance.name,
        'status': instance.status,
        'image': instance.docker_image,
        'docker_host': instance.docker_host.name,
        'created_at': instance.created_at.isoformat(),
        'started_at': instance.started_at.isoformat() if instance.started_at else None,
        'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
        'exit_code': instance.exit_code,
        'duration': str(instance.duration) if instance.duration else None
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        import logging
        logger = logging.getLogger('container_manager.webhooks')
        logger.warning(f"Failed to send webhook for job {instance.id}: {e}")
```

## LLM Agent Guidelines

### Behavioral Constraints

- **DO**: Always specify resource limits (memory, CPU) for container jobs
- **DO**: Use non-root users in container configurations
- **DO**: Verify Docker daemon health before creating jobs
- **DO**: Document all security implications of Docker configurations
- **DO NOT**: Create containers with privileged access or host network mode
- **DO NOT**: Mount sensitive host directories (/etc, /var/run, /root, etc.)
- **DO NOT**: Allow unlimited resource allocation for containers
- **DO NOT**: Create containers without explicit security contexts
- **LIMITS**: Maximum 2GB memory, 2 CPU cores per container job

### Security Requirements

- **Container isolation**: All containers MUST run with user namespaces enabled
- **Resource limits**: Every container job MUST have memory and CPU limits set
- **Network security**: Containers MUST use bridge networking, never host mode
- **Volume restrictions**: Only allow mounting of designated safe directories
- **Registry security**: Only pull images from trusted, configured registries
- **Privilege dropping**: Containers MUST run as non-root user (UID > 1000)
- **Read-only root**: Container root filesystem MUST be read-only when possible

### Safe Operation Patterns

- **Container job creation process**:
  1. Validate image source and registry
  2. Set explicit resource limits (memory ≤ 2GB, CPU ≤ 2.0)
  3. Configure non-root user execution
  4. Verify Docker host availability and health
  5. Set execution timeout (max 1 hour)
  6. Enable container isolation features
- **Docker daemon interaction**:
  1. Always check daemon connectivity before operations
  2. Verify sufficient resources available before job creation
  3. Monitor container resource usage during execution
  4. Implement proper cleanup after job completion

### Error Handling

- **If Docker daemon unavailable**: Mark host as unhealthy, do not queue jobs
- **If container fails to start**: Log detailed error, do not retry without investigation
- **If resource limits exceeded**: Terminate container immediately, mark job as failed
- **If security validation fails**: Reject job creation, log security violation
- **If image pull fails**: Check registry access, validate image name, document failure

### Validation Requirements

- [ ] All container jobs have explicit resource limits set
- [ ] No privileged containers or host network mode configurations
- [ ] All volume mounts restricted to safe, designated directories
- [ ] Container user configurations specify non-root execution
- [ ] Docker daemon security settings verified and documented
- [ ] Image registry configurations use only trusted sources
- [ ] Network isolation properly configured for all containers
- [ ] Cleanup procedures documented and tested for job completion

### Critical Security Boundaries

- **NEVER allow**: `privileged: true` in container configurations
- **NEVER mount**: `/`, `/etc`, `/var/run/docker.sock`, `/root`, or other system directories
- **NEVER use**: `network_mode: host` for container networking
- **NEVER run**: containers without explicit user specification (default root)
- **NEVER permit**: unlimited memory or CPU allocation
- **NEVER skip**: Docker daemon health checks before job creation
- **NEVER ignore**: container security scanning results

---

This comprehensive Docker integration guide provides everything needed to understand, configure, and effectively use the Docker container management capabilities of this Django application. The documentation includes practical examples, security guidelines, troubleshooting procedures, and best practices for production deployment.