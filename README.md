# Django Docker Container Manager

[![PyPI version](https://badge.fury.io/py/django-container-manager.svg)](https://badge.fury.io/py/django-container-manager)
[![Python Support](https://img.shields.io/pypi/pyversions/django-container-manager.svg)](https://pypi.org/project/django-container-manager/)
[![Django Support](https://img.shields.io/badge/django-4.2%20|%205.0%20|%205.1%20|%205.2-blue.svg)](https://docs.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**The most comprehensive Docker container management system for Django.** Execute Django commands inside Docker containers with complete lifecycle tracking, resource monitoring, and multi-platform support. Eliminate the complexity of Celery/RQ while gaining powerful containerized job execution.

Transform your Django application into a container orchestration platform with full observability, automatic resource management, and production-ready security controls.

## Why Choose This Over Celery?

- **🎯 Django-native design**: Built for Django from the ground up, not adapted from generic queuing
- **🐳 Container-first architecture**: Docker containers as first-class execution environments with full isolation
- **📊 Complete observability**: Track every aspect of job execution - logs, metrics, resource usage, timings
- **🔧 Zero infrastructure dependencies**: No Redis, RabbitMQ, or external queue management required
- **🌐 Multi-cloud ready**: Single codebase supports local Docker, remote hosts, Google Cloud Run, AWS Fargate
- **⚡ Production hardened**: Built-in security controls, resource limits, error handling, and monitoring
- **🔍 Real-time visibility**: Django admin integration with live job status and log viewing

## ✨ Key Features

- 🐳 **Multi-executor support**: Docker local/remote, Google Cloud Run, AWS Fargate, Mock executor
- 📊 **Complete lifecycle tracking**: Status monitoring, logs, metrics, and resource usage
- 🎛️ **Django admin integration**: Beautiful web interface with real-time job monitoring
- 🔧 **Background job processor**: Automatic container job execution and management
- 📦 **Environment management**: Template-based environment variables with job-level overrides
- 🔒 **Production security**: TLS support, resource limits, container isolation, and safe execution
- 📈 **Resource monitoring**: Memory and CPU usage tracking with configurable limits
- 🌐 **Cloud-native**: Built for containerized environments and cloud deployment

## 🏗️ Architecture Overview

```mermaid
graph TD
    A[Django Management Command] --> B[ContainerJob Model]
    B --> C[ExecutorHost Selection]
    C --> D[Docker/Cloud Executor]
    D --> E[Container Launch]
    E --> F[Real-time Monitoring]
    F --> G[Log Collection]
    G --> H[Resource Tracking]
    H --> I[Cleanup & Results]
    
    subgraph "Django Application"
        B --> J[Admin Interface]
        B --> K[Django ORM]
        K --> L[Database Storage]
    end
    
    subgraph "Execution Environment"
        D --> M[Local Docker]
        D --> N[Remote Docker]
        D --> O[Cloud Run]
        D --> P[AWS Fargate]
    end
```

**Core Components:**

- **ContainerJob**: Django model representing a containerized task
- **ExecutorHost**: Defines where containers run (local, remote, cloud)
- **Executors**: Pluggable backends for different container platforms
- **Job Processor**: Background service that manages the job lifecycle
- **Admin Interface**: Web UI for job creation, monitoring, and management

## 🚀 Quick Start

### Prerequisites

- **Docker**: [Install Docker](https://docs.docker.com/get-docker/) and ensure it's running
- **Python 3.8+**: Compatible with Python 3.8, 3.9, 3.10, 3.11, 3.12
- **Django 4.2+**: Compatible with Django 4.2, 5.0, 5.1, 5.2

```bash
# Verify Docker is running
docker --version
docker ps
```

### Installation

```bash
# Install from PyPI
pip install django-container-manager

# Or with uv (recommended)
uv add django-container-manager
```

### 5-Minute Setup

1. **Add to Django settings:**

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    # ... your other apps
    'container_manager',  # Add this line
]
```

2. **Run migrations:**

```bash
python manage.py migrate
```

3. **Create superuser and start admin:**

```bash
python manage.py createsuperuser
python manage.py runserver  # Visit http://localhost:8000/admin/
```

4. **Start the job processor (required for job execution):**

```bash
# In a separate terminal
python manage.py process_container_jobs
```

### Your First Container Job

Create and run your first containerized task in under 2 minutes:

1. **Set up Docker executor** (via Django shell):

```python
python manage.py shell

from container_manager.models import ExecutorHost

# Create local Docker executor
docker_host = ExecutorHost.objects.create(
    name="local-docker",
    executor_type="docker",
    connection_string="unix:///var/run/docker.sock",
    is_active=True
)
```

2. **Create a simple job:**

```python
from container_manager.models import ContainerJob

# Create a "Hello World" container job
job = ContainerJob.objects.create_job(
    image="hello-world",
    name="My First Container Job",
    memory_limit=128,  # 128MB
    cpu_limit=0.5,     # 0.5 CPU cores
    timeout_seconds=300
)

print(f"Created job: {job.id}")
```

3. **Monitor execution** (the job processor will automatically pick it up):

```python
# Refresh the job to see updated status
job.refresh_from_db()
print(f"Status: {job.status}")
print(f"Output: {job.clean_output}")
```

**That's it!** Your first container job is running. Visit the Django admin to see real-time status updates and logs.

## 📖 Real-World Usage Examples

### Example 1: Data Processing Pipeline

Run a Python data processing script in an isolated container:

```python
from container_manager.models import ContainerJob

# Process CSV data with pandas
job = ContainerJob.objects.create_job(
    image="python:3.11-slim",
    command="pip install pandas && python -c \"import pandas as pd; print('Processing complete')\"",
    name="Data Processing Job",
    memory_limit=1024,  # 1GB for data processing
    cpu_limit=2.0,      # 2 CPU cores
    timeout_seconds=1800  # 30 minutes
)
```

### Example 2: Automated Testing

Run tests in a clean container environment:

```python
# Run pytest in isolated environment
test_job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="/bin/bash -c 'pip install pytest && pytest --verbose'",
    name="Test Suite Execution",
    environment_vars={
        "PYTHONPATH": "/app",
        "TEST_ENV": "container",
        "PYTEST_ARGS": "--tb=short"
    },
    memory_limit=512,
    cpu_limit=1.0
)
```

### Example 3: Image Processing

Process images with ImageMagick in a containerized environment:

```python
# Image processing pipeline
image_job = ContainerJob.objects.create_job(
    image="dpokidov/imagemagick:latest",
    command="convert -version && echo 'ImageMagick ready for processing'",
    name="Image Processing Pipeline",
    memory_limit=2048,  # 2GB for image processing
    cpu_limit=1.5,
    timeout_seconds=3600  # 1 hour
)
```

### Example 4: Database Operations

Run database migrations or data imports:

```python
# Database migration in container
db_job = ContainerJob.objects.create_job(
    image="postgres:15",
    command="psql --version && echo 'Database operations ready'",
    name="Database Migration",
    environment_vars={
        "POSTGRES_HOST": "db.example.com",
        "POSTGRES_DB": "myapp",
        "POSTGRES_USER": "admin"
        # Note: Use secrets management for passwords in production
    },
    memory_limit=256,
    cpu_limit=0.5
)
```

### Environment Variables

Environment variables can be easily added to templates using a simple text format:

```python
env_template.environment_variables_text = """
# Database configuration
DATABASE_URL=postgresql://user:pass@host:5432/db
DB_POOL_SIZE=10

# API settings  
API_KEY=your-secret-key
API_TIMEOUT=30

# Feature flags
DEBUG=false
ENABLE_CACHE=true
"""
```

**Format rules:**
- One variable per line: `KEY=value`
- Comments start with `#` and are ignored
- Values can contain spaces and `=` characters
- Empty lines are ignored

### Advanced Configuration

```python
# settings.py
CONTAINER_MANAGER = {
    "AUTO_PULL_IMAGES": True,
    "IMMEDIATE_CLEANUP": True,
    "MAX_CONCURRENT_JOBS": 10,
    "POLL_INTERVAL": 5,
    "DEFAULT_MEMORY_LIMIT": 512,
    "DEFAULT_CPU_LIMIT": 1.0,
    "CLEANUP_HOURS": 24,
}

# Enable executor factory for multi-cloud support
USE_EXECUTOR_FACTORY = True
```

## 🌥️ Multi-Cloud Support

### Google Cloud Run

```python
# Configure Cloud Run executor
host = ExecutorHost.objects.create(
    name="gcp-cloud-run",
    executor_type="cloudrun",
    weight=150,
    executor_config={
        "project": "my-gcp-project",
        "region": "us-central1",
        "cpu_limit": "2",
        "memory_limit": "2Gi",
    }
)
```

### AWS Fargate

```python
# Configure Fargate executor
host = ExecutorHost.objects.create(
    name="aws-fargate",
    executor_type="fargate",
    weight=120,
    executor_config={
        "cluster": "my-ecs-cluster",
        "subnets": ["subnet-12345", "subnet-67890"],
        "security_groups": ["sg-abcdef"],
    }
)
```

## 🔧 Job Processing & Monitoring

### Starting the Job Processor

The background job processor is essential for job execution:

```bash
# Production: Keep running continuously
python manage.py process_container_jobs

# Development: Run once and exit
python manage.py process_container_jobs --once

# Custom polling: Check for jobs every 10 seconds
python manage.py process_container_jobs --poll-interval=10
```

> **Critical**: Without the job processor running, no containers will be executed. This service manages the complete job lifecycle from container creation to cleanup.

### Real-time Monitoring

Monitor job execution through multiple interfaces:

#### Django Admin Interface
- **Live job status updates** with automatic refresh
- **Real-time log viewing** directly in the browser
- **Resource usage tracking** (memory, CPU, execution time)
- **Bulk operations** for managing multiple jobs
- **Executor host management** and health monitoring

#### Command Line Monitoring
```python
# Check job status programmatically
from container_manager.models import ContainerJob

# View recent jobs
recent_jobs = ContainerJob.objects.filter(
    created_at__gte=timezone.now() - timedelta(hours=24)
)

for job in recent_jobs:
    print(f"{job.name}: {job.status} ({job.duration})")
```

#### Production Monitoring
```python
# Health check endpoint example
def health_check():
    from container_manager.models import ExecutorHost
    
    unhealthy_hosts = []
    for host in ExecutorHost.objects.filter(is_active=True):
        # Check host health (implement based on your needs)
        if not host.is_available():
            unhealthy_hosts.append(host.name)
    
    return {
        'healthy': len(unhealthy_hosts) == 0,
        'unhealthy_hosts': unhealthy_hosts
    }
```

## 🔒 Production Security

Built-in security features for production deployment:

- **Resource limits**: Strict memory (max 2GB) and CPU (max 2 cores) constraints
- **Container isolation**: Non-privileged containers with security contexts
- **Network isolation**: Configurable network policies and container networking
- **TLS support**: Secure connections to remote Docker hosts and registries
- **Secret management**: Environment variable masking and secure credential handling
- **Access controls**: Role-based permissions through Django's auth system

### Security Best Practices

```python
# Secure job creation with resource limits
secure_job = ContainerJob.objects.create_job(
    image="trusted-registry.company.com/app:latest",
    command="python secure_task.py",
    memory_limit=512,    # Always set memory limits
    cpu_limit=1.0,       # Always set CPU limits
    timeout_seconds=900, # 15-minute timeout
    environment_vars={
        "LOG_LEVEL": "INFO",
        # Never put secrets in environment_vars in code
        # Use Django secrets management instead
    }
)
```

See the **[Docker Integration Guide](DOCKER.md)** for comprehensive security configuration.

## 🛠️ Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/samtexas/django-container-manager.git
cd django-container-manager

# Install with uv (recommended)
uv sync --extra dev

# Or with pip
pip install -e ".[dev]"
```

### ⚡ Quick Development Commands

**For vibe coding with Claude Code:**

```bash
# Run tests (fast feedback)
make test

# Quality check (before commits)
make check

# Fix formatting/linting
make fix

# Pre-commit check (fix + test)
make ready

# Test coverage report
make coverage
```

### 🚀 Release Automation

**One-command releases:**

```bash
# Quick patch release (1.0.3 → 1.0.4)
make release-patch

# Minor release (1.0.3 → 1.1.0) 
make release-minor

# Major release (1.0.3 → 2.0.0)
make release-major
```

Each release automatically:
- Fixes code formatting
- Runs full test suite  
- Bumps version number
- Creates git commit and tag
- Pushes to GitHub
- Creates GitHub release
- Triggers PyPI publication via GitHub Actions

**Security:** Releases use GitHub environment protection for enhanced security and audit logging. See [CLAUDE.md](CLAUDE.md#-pypi-environment-protection) for full details.

### Manual Development Commands

```bash
# Run all tests
uv run python manage.py test

# Run with coverage
uv run coverage run --source=container_manager manage.py test
uv run coverage report

# Format and lint with ruff
uv run ruff format .
uv run ruff check .

# Build package
uv run python -m build
```

**See [VIBE_CODING.md](VIBE_CODING.md) for complete automation reference.**

## 📚 Documentation

### Core Documentation

- **[Docker Integration Guide](DOCKER.md)** - Comprehensive Docker setup, configuration, and best practices
- **[Installation Guide](INSTALL.md)** - Detailed installation instructions for all platforms
- **[API Reference](API.md)** - Complete API documentation and examples
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

### Development Documentation

- **[Contributing Guide](CONTRIBUTING.md)** - Development setup, testing, and contribution guidelines
- **[Internal Documentation](CLAUDE.md)** - Technical implementation details and development notes

### External Resources

- **PyPI Package**: [django-container-manager](https://pypi.org/project/django-container-manager/)
- **Source Code**: [GitHub Repository](https://github.com/samtexas/django-container-manager)
- **Issue Tracker**: [GitHub Issues](https://github.com/samtexas/django-container-manager/issues)

## 🤖 LLM Agent Guidelines

### Behavioral Constraints

- **DO**: Test every code example in a clean environment before including
- **DO**: Verify all installation commands work on the target system
- **DO**: Keep examples simple and immediately runnable
- **DO**: Link to detailed documentation for complex topics
- **DO NOT**: Include misleading performance claims or unsupported features
- **DO NOT**: Add examples that require external services without clear setup
- **DO NOT**: Promise functionality that doesn't exist or is experimental
- **LIMITS**: README should be scannable in under 5 minutes

### Security Requirements

- **Never include**: Real credentials, API keys, or production URLs in examples
- **Always use**: Placeholder values like `your-registry.com` or `your-project-id`
- **Validate examples**: Ensure no security anti-patterns in code samples
- **Credential guidance**: Direct users to proper credential management documentation

### Safe Operation Patterns

- **Example validation process**:
  1. Create clean test environment
  2. Follow README instructions exactly as written
  3. Verify each step produces expected output
  4. Document any prerequisites or assumptions
- **Link validation**: Test all internal and external links for accuracy
- **Version consistency**: Ensure examples match current codebase capabilities

### Error Handling

- **If examples fail**: Update examples, don't ignore failures
- **If installation doesn't work**: Revise instructions, add troubleshooting notes
- **If technical accuracy questioned**: Cross-reference with CLAUDE.md and codebase
- **When unsure**: Ask for clarification rather than guessing

### Validation Requirements

- [ ] All code examples tested in clean environment
- [ ] Installation steps verified on target platforms
- [ ] No credentials or sensitive information in examples
- [ ] All links functional and point to correct resources
- [ ] Technical claims verified against actual codebase capabilities
- [ ] Examples use only documented, stable features

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up development environment
- Code style and testing requirements  
- Submitting pull requests
- Reporting bugs and feature requests

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **PyPI**: [https://pypi.org/project/django-container-manager/](https://pypi.org/project/django-container-manager/)
- **Source Code**: [https://github.com/samtexas/django-container-manager](https://github.com/samtexas/django-container-manager)
- **Issue Tracker**: [https://github.com/samtexas/django-container-manager/issues](https://github.com/samtexas/django-container-manager/issues)
- **Documentation**: [https://django-container-manager.readthedocs.io/](https://django-container-manager.readthedocs.io/)

---

**For the Django community**
