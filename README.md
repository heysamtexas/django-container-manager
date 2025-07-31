# Django Container Manager

[![PyPI version](https://badge.fury.io/py/django-container-manager.svg)](https://badge.fury.io/py/django-container-manager)
[![Python Support](https://img.shields.io/pypi/pyversions/django-container-manager.svg)](https://pypi.org/project/django-container-manager/)
[![Django Support](https://img.shields.io/badge/django-4.2%20|%205.0%20|%205.1%20|%205.2-blue.svg)](https://docs.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern Django app for container orchestration with multi-executor support. Run containerized jobs across Docker, Google Cloud Run, AWS Fargate, and custom platforms with unified management, monitoring, and scaling.

## ✨ Features

- 🐳 **Multi-executor support**: Docker, Google Cloud Run, AWS Fargate, Mock executor
- 📊 **Job lifecycle tracking**: Status monitoring, logs, metrics, and resource usage
- 🎛️ **Admin interface**: Beautiful Django admin integration with real-time updates
- 🔧 **Job processor**: Background daemon for container job execution
- 📦 **Environment overrides**: Job-level customization of commands and variables
- 🚀 **Production ready**: Comprehensive error handling, logging, and monitoring
- 🔒 **Security first**: TLS support, resource limits, and safe container execution

## 🚀 Quick Start

### Installation

```bash
pip install django-container-manager
```

### Basic Setup

1. **Add to your Django project:**

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    # ... your other apps
    'container_manager',  # Add this
]
```

2. **Run migrations:**

```bash
python manage.py migrate
```

3. **Create a superuser (for development):**

```bash
python manage.py createsuperuser  # Only needed for local development
python manage.py runserver        # Visit http://localhost:8000/admin/
```

4. **Start the job processor (CRITICAL for job execution):**

```bash
python manage.py process_container_jobs
```

## 📖 Usage

### Creating Your First Container Job

1. **Create Executor Host** (in Django admin or via shell):

```python
from container_manager.models import ExecutorHost

host = ExecutorHost.objects.create(
    name="local-docker",
    executor_type="docker",
    connection_string="unix:///var/run/docker.sock",
    weight=100
)
```

2. **Create Environment Template (optional):**

```python
from container_manager.models import EnvironmentVariableTemplate

env_template = EnvironmentVariableTemplate.objects.create(
    name="hello-world-env",
    environment_variables_text="""
DEBUG=true
LOG_LEVEL=info
TIMEOUT=300
"""
)
```

3. **Create and Run Job:**

```python
from container_manager.models import ContainerJob

job = ContainerJob.objects.create(
    docker_host=host,
    name="My First Container Job",
    docker_image="hello-world",
    timeout_seconds=60,
    memory_limit=128,  # MB
    cpu_limit=0.5,     # cores
    environment_template=env_template  # optional
)
```

The job will be automatically picked up by the job processor and executed!

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

## 🔧 Job Processing

The core job processor daemon is started with:

```bash
# Start the job processor (keeps running)
python manage.py process_container_jobs

# Run once and exit (useful for testing)
python manage.py process_container_jobs --once

# Custom poll interval
python manage.py process_container_jobs --poll-interval=10
```

**This command is essential** - without it running, no jobs will be executed. It continuously polls for pending jobs and manages their lifecycle.

### Job Management

Job creation and management is handled through the Django admin interface, which provides:

- **Interactive job creation** with real-time validation
- **Status monitoring** and job lifecycle tracking
- **Log viewing** directly in the admin interface
- **Bulk operations** for managing multiple jobs
- **Executor host management** and configuration

## 📊 Monitoring & Admin Interface

The Django admin interface provides:

- **Job status monitoring** with real-time updates
- **Log viewing** directly in the browser  
- **Execution tracking** with start/completion times
- **Bulk operations** for managing multiple jobs
- **Executor host management** and configuration
- **Environment variable templates** with override support

## 🔒 Security Features

- **Resource limits**: Memory and CPU constraints per job
- **Network isolation**: Configurable network policies
- **TLS support**: Secure connections to remote Docker hosts
- **Environment variable masking**: Hide sensitive data in logs
- **Privileged container controls**: Disable dangerous operations

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

### Running Tests

```bash
# Run all tests
python manage.py test

# Run with coverage
pytest --cov=container_manager

# Run specific test categories
pytest -m unit  # Unit tests only
pytest -m integration  # Integration tests only
```

### Code Quality

```bash
# Format and lint with ruff
uv run ruff format .
uv run ruff check .

# Type checking
uv run mypy container_manager
```

## 📚 Documentation

- **Full Documentation**: [django-container-manager.readthedocs.io](https://django-container-manager.readthedocs.io/)
- **API Reference**: [API Documentation](https://django-container-manager.readthedocs.io/en/latest/api/)
- **Deployment Guide**: [Production Deployment](https://django-container-manager.readthedocs.io/en/latest/deployment/)

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
