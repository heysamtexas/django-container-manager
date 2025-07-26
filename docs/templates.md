# Container Template Guide

This guide covers creating and managing container templates for Django Docker Container Manager.

## Overview

Container templates are reusable configurations that define how containers should be created and executed. They specify Docker images, commands, resource limits, environment variables, and network configurations.

## Template Components

### Basic Template Structure

```python
{
    "name": "template-name",
    "description": "Template description",
    "docker_image": "image:tag",
    "command": "command to execute",
    "working_directory": "/path/to/workdir",
    "memory_limit": 1024,      # MB
    "cpu_limit": 1.0,          # CPU cores
    "timeout_seconds": 3600,   # Seconds
    "auto_remove": True,       # Remove container after completion
    "environment_variables": [],
    "network_assignments": []
}
```

### Required Fields

- **name**: Unique identifier for the template
- **docker_image**: Docker image to use for containers
- **command**: Command to execute inside the container

### Optional Fields

- **description**: Human-readable description
- **working_directory**: Working directory inside container (default: `/`)
- **memory_limit**: Memory limit in MB (default: no limit)
- **cpu_limit**: CPU limit in cores (default: no limit)
- **timeout_seconds**: Execution timeout (default: 3600 seconds)
- **auto_remove**: Remove container after completion (default: True)

## Creating Templates

### Via Django Admin

1. Navigate to the Django admin interface
2. Go to **Container Templates**
3. Click **Add Container Template**
4. Fill in the template details
5. Save the template

### Via Django Shell

```python
from container_manager.models import ContainerTemplate, EnvironmentVariable, NetworkAssignment

# Create basic template
template = ContainerTemplate.objects.create(
    name="hello-world",
    description="Simple hello world task",
    docker_image="ubuntu:22.04",
    command="echo 'Hello from container!'",
    memory_limit=256,
    cpu_limit=0.5,
    timeout_seconds=300
)

# Add environment variables
EnvironmentVariable.objects.create(
    template=template,
    key="MESSAGE",
    value="Hello World",
    is_secret=False
)

# Add network assignment
NetworkAssignment.objects.create(
    template=template,
    network_name="app-network",
    aliases=["hello-task"]
)
```

### Via Management Command

```bash
# Create template from JSON file
uv run python manage.py manage_container_job create-template template.json

# Example template.json
{
    "name": "data-processor",
    "description": "Process CSV data files",
    "docker_image": "python:3.12-slim",
    "command": "python process_data.py",
    "working_directory": "/app",
    "memory_limit": 2048,
    "cpu_limit": 2.0,
    "timeout_seconds": 7200,
    "environment_variables": [
        {
            "key": "INPUT_FILE",
            "value": "/data/input.csv",
            "is_secret": false
        }
    ]
}
```

## Template Examples

### Basic Python Script

```python
{
    "name": "python-script",
    "description": "Execute Python script",
    "docker_image": "python:3.12-slim",
    "command": "python /app/script.py",
    "working_directory": "/app",
    "memory_limit": 512,
    "cpu_limit": 1.0,
    "timeout_seconds": 1800,
    "auto_remove": True,
    "environment_variables": [
        {
            "key": "PYTHONPATH",
            "value": "/app",
            "is_secret": False
        }
    ]
}
```

### Django Management Command

```python
{
    "name": "django-migrate",
    "description": "Run Django database migrations",
    "docker_image": "myapp:latest",
    "command": "python manage.py migrate",
    "working_directory": "/app",
    "memory_limit": 1024,
    "cpu_limit": 1.0,
    "timeout_seconds": 600,
    "environment_variables": [
        {
            "key": "DATABASE_URL",
            "value": "postgresql://user:pass@db:5432/myapp",
            "is_secret": True
        },
        {
            "key": "SECRET_KEY",
            "value": "django-secret-key",
            "is_secret": True
        }
    ],
    "network_assignments": [
        {
            "network_name": "app-network",
            "aliases": ["migration-runner"]
        }
    ]
}
```

### Data Processing Pipeline

```python
{
    "name": "etl-pipeline",
    "description": "Extract, Transform, Load data pipeline",
    "docker_image": "apache/airflow:2.7.0",
    "command": "python /opt/airflow/dags/etl_pipeline.py",
    "working_directory": "/opt/airflow",
    "memory_limit": 4096,
    "cpu_limit": 4.0,
    "timeout_seconds": 14400,  # 4 hours
    "environment_variables": [
        {
            "key": "AIRFLOW__CORE__SQL_ALCHEMY_CONN",
            "value": "postgresql://airflow:password@postgres:5432/airflow",
            "is_secret": True
        },
        {
            "key": "AIRFLOW__CORE__EXECUTOR",
            "value": "LocalExecutor",
            "is_secret": False
        },
        {
            "key": "AWS_ACCESS_KEY_ID",
            "value": "your-access-key",
            "is_secret": True
        },
        {
            "key": "AWS_SECRET_ACCESS_KEY",
            "value": "your-secret-key",
            "is_secret": True
        }
    ]
}
```

### Machine Learning Training

```python
{
    "name": "ml-training",
    "description": "Train machine learning model",
    "docker_image": "tensorflow/tensorflow:2.13.0-gpu",
    "command": "python train_model.py --epochs=100 --batch-size=32",
    "working_directory": "/workspace",
    "memory_limit": 8192,  # 8GB
    "cpu_limit": 8.0,
    "timeout_seconds": 86400,  # 24 hours
    "environment_variables": [
        {
            "key": "NVIDIA_VISIBLE_DEVICES",
            "value": "0,1",
            "is_secret": False
        },
        {
            "key": "CUDA_VISIBLE_DEVICES",
            "value": "0,1",
            "is_secret": False
        },
        {
            "key": "TF_FORCE_GPU_ALLOW_GROWTH",
            "value": "true",
            "is_secret": False
        },
        {
            "key": "WANDB_API_KEY",
            "value": "your-wandb-key",
            "is_secret": True
        }
    ]
}
```

### Report Generation

```python
{
    "name": "monthly-report",
    "description": "Generate monthly business report",
    "docker_image": "reporting-app:latest",
    "command": "python generate_report.py --month=$(date +%Y-%m)",
    "working_directory": "/app",
    "memory_limit": 2048,
    "cpu_limit": 2.0,
    "timeout_seconds": 3600,
    "environment_variables": [
        {
            "key": "DATABASE_URL",
            "value": "postgresql://readonly:pass@analytics-db:5432/analytics",
            "is_secret": True
        },
        {
            "key": "S3_BUCKET",
            "value": "company-reports",
            "is_secret": False
        },
        {
            "key": "AWS_ACCESS_KEY_ID",
            "value": "report-uploader-key",
            "is_secret": True
        }
    ],
    "network_assignments": [
        {
            "network_name": "analytics-network",
            "aliases": ["report-generator"]
        }
    ]
}
```

### Web Scraping Task

```python
{
    "name": "web-scraper",
    "description": "Scrape data from websites",
    "docker_image": "selenium/standalone-chrome:latest",
    "command": "python scraper.py --urls=/data/urls.txt",
    "working_directory": "/app",
    "memory_limit": 1024,
    "cpu_limit": 1.0,
    "timeout_seconds": 7200,  # 2 hours
    "environment_variables": [
        {
            "key": "SELENIUM_HUB_HOST",
            "value": "localhost",
            "is_secret": False
        },
        {
            "key": "USER_AGENT",
            "value": "Mozilla/5.0 (compatible; WebScraper/1.0)",
            "is_secret": False
        },
        {
            "key": "PROXY_URL",
            "value": "http://proxy:8080",
            "is_secret": True
        }
    ]
}
```

## Environment Variables

### Variable Types

#### Regular Variables
```python
{
    "key": "LOG_LEVEL",
    "value": "INFO",
    "is_secret": False
}
```

#### Secret Variables
```python
{
    "key": "API_KEY",
    "value": "secret-api-key-value",
    "is_secret": True  # Will be masked in logs
}
```

### Dynamic Variables

You can use dynamic values in environment variables:

```python
{
    "key": "JOB_ID",
    "value": "{{job.id}}",  # Replaced with actual job ID
    "is_secret": False
},
{
    "key": "TIMESTAMP",
    "value": "{{job.created_at}}",  # Replaced with job creation time
    "is_secret": False
},
{
    "key": "DOCKER_HOST",
    "value": "{{job.docker_host.name}}",  # Replaced with Docker host name
    "is_secret": False
}
```

### Environment Variable Inheritance

Templates can inherit environment variables from:

1. **Global settings** - Defined in Django settings
2. **Docker host configuration** - Host-specific variables
3. **Template variables** - Template-specific variables
4. **Job overrides** - Per-job variable overrides

Priority order (highest to lowest):
1. Job overrides
2. Template variables
3. Docker host variables
4. Global settings

## Network Configuration

### Single Network Assignment

```python
{
    "network_assignments": [
        {
            "network_name": "app-network",
            "aliases": ["worker-task"]
        }
    ]
}
```

### Multiple Networks

```python
{
    "network_assignments": [
        {
            "network_name": "frontend-network",
            "aliases": ["api-client"]
        },
        {
            "network_name": "backend-network", 
            "aliases": ["db-client", "cache-client"]
        }
    ]
}
```

### Network Creation

Ensure networks exist before using them:

```bash
# Create custom networks
docker network create app-network
docker network create backend-network --driver bridge
docker network create isolated-network --internal
```

## Resource Management

### Memory Limits

```python
# Memory limits in MB
"memory_limit": 256    # 256 MB
"memory_limit": 1024   # 1 GB
"memory_limit": 4096   # 4 GB
"memory_limit": None   # No limit (not recommended)
```

### CPU Limits

```python
# CPU limits as decimal cores
"cpu_limit": 0.5       # Half a CPU core
"cpu_limit": 1.0       # One full CPU core
"cpu_limit": 2.5       # Two and half CPU cores
"cpu_limit": None      # No limit (not recommended)
```

### Timeout Configuration

```python
# Timeout in seconds
"timeout_seconds": 300     # 5 minutes
"timeout_seconds": 3600    # 1 hour
"timeout_seconds": 86400   # 24 hours
```

## Template Validation

### Validation Rules

Templates are automatically validated for:

- **Name uniqueness** - No duplicate template names
- **Docker image format** - Valid image references
- **Resource limits** - Reasonable memory/CPU values
- **Environment variables** - Valid key/value pairs
- **Network names** - Valid Docker network names
- **Command syntax** - Basic command validation

### Custom Validation

```python
# container_manager/models.py
def clean(self):
    # Custom validation logic
    if self.memory_limit and self.memory_limit < 64:
        raise ValidationError("Memory limit must be at least 64MB")
    
    if self.cpu_limit and self.cpu_limit > 8:
        raise ValidationError("CPU limit cannot exceed 8 cores")
    
    if not self.command.strip():
        raise ValidationError("Command cannot be empty")
```

## Template Management

### Listing Templates

```bash
# List all templates
uv run python manage.py manage_container_job list-templates

# Filter by pattern
uv run python manage.py manage_container_job list-templates --name-pattern="django-*"
```

### Template Export/Import

```bash
# Export template to JSON
uv run python manage.py manage_container_job export-template template-name > template.json

# Import template from JSON
uv run python manage.py manage_container_job import-template template.json
```

### Template Copying

```python
# Via Django shell - copy existing template
from container_manager.models import ContainerTemplate

original = ContainerTemplate.objects.get(name="original-template")
copy = ContainerTemplate.objects.create(
    name="copied-template",
    description=f"Copy of {original.name}",
    docker_image=original.docker_image,
    command=original.command,
    memory_limit=original.memory_limit,
    cpu_limit=original.cpu_limit,
    timeout_seconds=original.timeout_seconds
)

# Copy environment variables
for env_var in original.environment_variables.all():
    copy.environment_variables.create(
        key=env_var.key,
        value=env_var.value,
        is_secret=env_var.is_secret
    )
```

## Best Practices

### Template Design

1. **Use specific image tags** - Avoid `latest` tag for reproducibility
2. **Set resource limits** - Always specify memory and CPU limits
3. **Use meaningful names** - Template names should be descriptive
4. **Document templates** - Add clear descriptions
5. **Environment isolation** - Use separate templates for different environments

### Security Considerations

1. **Mark secrets properly** - Set `is_secret=True` for sensitive values
2. **Minimize privileges** - Use non-root users in containers when possible
3. **Network segmentation** - Use appropriate networks for isolation
4. **Image security** - Use trusted, regularly updated base images
5. **Resource limits** - Prevent resource exhaustion attacks

### Performance Optimization

1. **Image size** - Use slim/alpine images when possible
2. **Layer caching** - Design Dockerfiles for optimal layer caching
3. **Resource allocation** - Right-size memory and CPU limits
4. **Timeout tuning** - Set appropriate timeouts for task duration
5. **Network optimization** - Minimize cross-network communication

### Template Organization

```python
# Naming conventions
"environment-service-purpose"
"prod-api-migration"
"dev-worker-etl"
"staging-report-monthly"

# Template families
"django-*"          # Django-related templates
"ml-*"              # Machine learning templates
"etl-*"             # Data pipeline templates
"report-*"          # Reporting templates
```

## Troubleshooting

### Common Issues

#### Template Validation Errors
```bash
# Check template validation
uv run python manage.py shell -c "
from container_manager.models import ContainerTemplate
template = ContainerTemplate.objects.get(name='your-template')
template.full_clean()
"
```

#### Image Pull Failures
```bash
# Test image availability
docker pull your-image:tag

# Check Docker host connectivity
uv run python manage.py shell -c "
from container_manager.docker_service import docker_service
from container_manager.models import DockerHost
host = DockerHost.objects.first()
client = docker_service.get_client(host)
print(client.images.list())
"
```

#### Resource Limit Issues
- Ensure Docker daemon supports cgroup limits
- Check available system resources
- Verify container runtime configuration

#### Network Configuration Problems
- Ensure networks exist before creating jobs
- Check network connectivity between containers
- Verify firewall rules and security groups

For job execution details, see the [Job Management Guide](jobs.md).