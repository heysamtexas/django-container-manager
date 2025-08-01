# Job Creation Guide

This guide demonstrates how to create container jobs using the Django Container Manager's convenient APIs.

## Quick Start

The simplest way to create a job is using the `create_job()` convenience method:

```python
from container_manager.models import ContainerJob, ExecutorHost
from django.contrib.auth.models import User

# Get or create required objects
host = ExecutorHost.objects.get(name="local-docker")
user = User.objects.get(username="admin")

# Create a simple job
job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python -c 'print(\"Hello, World!\")'",
    docker_host=host,
    created_by=user
)
```

## Environment Variables

### Using Dictionary Interface

The most convenient way to set environment variables is with a Python dictionary:

```python
job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python app.py",
    environment_vars={
        "DEBUG": "true",
        "DATABASE_URL": "postgresql://localhost/mydb",
        "WORKER_COUNT": "4"
    },
    docker_host=host,
    created_by=user
)
```

### Using Environment Templates

Environment templates allow you to reuse common configurations:

```python
# Using template by name
job = ContainerJob.objects.create_job(
    image="python:3.11",
    environment_template="production-web",
    docker_host=host,
    created_by=user
)

# Using template instance
from container_manager.models import EnvironmentVariableTemplate

template = EnvironmentVariableTemplate.objects.get(name="production-web")
job = ContainerJob.objects.create_job(
    image="python:3.11",
    environment_template=template,
    docker_host=host,
    created_by=user
)
```

### Combining Templates and Overrides

You can use templates as a base and override specific variables:

```python
job = ContainerJob.objects.create_job(
    image="python:3.11",
    environment_template="production-web",
    environment_vars={
        "DEBUG": "false",  # Override template value
        "CUSTOM_SETTING": "special-value"  # Add new variable
    },
    docker_host=host,
    created_by=user
)
```

The final environment will merge template variables with your overrides, where overrides take precedence.

## Complete Example

Here's a comprehensive example showing all available parameters:

```python
job = ContainerJob.objects.create_job(
    image="node:18",
    command="npm start",
    name="web-server-prod",
    environment_template="web-defaults",
    environment_vars={
        "NODE_ENV": "production",
        "PORT": "3000",
        "LOG_LEVEL": "info"
    },
    memory_limit=512,  # MB
    cpu_limit=1.5,     # cores
    timeout_seconds=7200,  # 2 hours
    docker_host=host,
    created_by=user
)
```

## Error Handling

The convenience method provides clear error messages:

```python
try:
    job = ContainerJob.objects.create_job(
        image="python:3.11",
        environment_template="nonexistent-template",
        docker_host=host,
        created_by=user
    )
except ValueError as e:
    print(f"Template error: {e}")
    # Output: Template error: Environment template 'nonexistent-template' not found
```

## Backward Compatibility

The traditional `create()` method continues to work unchanged:

```python
# Old way still works
job = ContainerJob.objects.create(
    docker_image="ubuntu:22.04",
    docker_host=host,
    created_by=user,
    override_environment="DEBUG=true\nENV=production"
)
```

## Best Practices

### 1. Use Environment Templates for Common Configurations

Create reusable templates for different environments:

```python
# Create templates
EnvironmentVariableTemplate.objects.create(
    name="web-production",
    environment_variables_text="DEBUG=false\nLOG_LEVEL=info\nWORKER_COUNT=4"
)

EnvironmentVariableTemplate.objects.create(
    name="web-development", 
    environment_variables_text="DEBUG=true\nLOG_LEVEL=debug\nWORKER_COUNT=1"
)

# Use them in jobs
prod_job = ContainerJob.objects.create_job(
    image="myapp:latest",
    environment_template="web-production",
    docker_host=prod_host,
    created_by=user
)
```

### 2. Override Only What Changes

When using templates, only override variables that differ:

```python
# Good: Only override what's different
job = ContainerJob.objects.create_job(
    image="myapp:latest",
    environment_template="web-production",
    environment_vars={"LOG_LEVEL": "debug"},  # Just this one change
    docker_host=host,
    created_by=user
)
```

### 3. Use Descriptive Job Names

```python
job = ContainerJob.objects.create_job(
    image="postgres:15",
    name="database-backup-daily",
    command="pg_dump mydb > /backup/$(date +%Y%m%d).sql",
    docker_host=host,
    created_by=user
)
```

## Migration from Direct ORM Usage

If you're currently using direct ORM calls, migration is straightforward:

```python
# Before
job = ContainerJob.objects.create(
    docker_image="python:3.11",
    command="python script.py",
    override_environment="DEBUG=true\nENV=prod",
    docker_host=host,
    created_by=user
)

# After - much cleaner!
job = ContainerJob.objects.create_job(
    image="python:3.11",
    command="python script.py", 
    environment_vars={"DEBUG": "true", "ENV": "prod"},
    docker_host=host,
    created_by=user
)
```

The convenience method handles all the environment variable formatting and template merging automatically.