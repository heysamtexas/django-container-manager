# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django application for full lifecycle management of Docker containers. Instead of using traditional async task queues like Celery or RQ, this system executes Django commands inside Docker containers with complete tracking of logs, status, and resource usage.

## Development Commands

### Environment Setup
```bash
# Initialize virtual environment and install dependencies
uv sync

# Run database migrations
uv run python manage.py migrate

# Create superuser for admin access
uv run python manage.py createsuperuser

# Run development server
uv run python manage.py runserver
```

### Code Quality
```bash
# Format code with ruff
uv run ruff format .

# Lint code with ruff
uv run ruff check .

# Fix auto-fixable linting issues
uv run ruff check --fix .
```

### Testing
```bash
# Run all tests
uv run python manage.py test

# Run tests with verbose output
uv run python manage.py test --verbosity=2

# Run specific test file
uv run python manage.py test container_manager.tests.DockerServiceTest

# Run tests for specific app
uv run python manage.py test container_manager
```

### Container Job Management
```bash
# Process container jobs (main worker command)
uv run python manage.py process_container_jobs

# Process jobs with custom settings
uv run python manage.py process_container_jobs --poll-interval=10 --max-jobs=5

# Process jobs for specific Docker host
uv run python manage.py process_container_jobs --host=production-host

# Run cleanup of old containers
uv run python manage.py process_container_jobs --cleanup --cleanup-hours=48

# Create a container job manually
uv run python manage.py manage_container_job create template-name host-name --name="My Job"

# List container jobs
uv run python manage.py manage_container_job list --status=running

# Show job details with logs
uv run python manage.py manage_container_job show JOB-UUID --logs

# Cancel a running job
uv run python manage.py manage_container_job cancel JOB-UUID
```

## Architecture Overview

### Core Models

**DockerHost**: Represents Docker daemon endpoints (TCP or Unix socket)
- Supports multiple Docker hosts for distributed execution
- Connection status monitoring and health checks
- TLS configuration for secure remote connections

**ContainerTemplate**: Reusable container definitions
- Docker image and command configuration
- Resource limits (CPU/memory) and timeout settings
- Environment variables and network assignments
- 12-factor app compatible with environment variable injection

**ContainerJob**: Individual job instances
- UUID-based identification for reliable tracking
- Status lifecycle: pending → running → completed/failed/timeout/cancelled
- Override capabilities for command and environment variables
- Execution timing and duration tracking

**ContainerExecution**: Execution logs and resource usage
- Stdout, stderr, and Docker daemon logs
- Memory and CPU usage statistics
- One-to-one relationship with ContainerJob

### Docker Integration Layer

**DockerService** (`container_manager/docker_service.py`):
- Multi-host Docker client management with connection caching
- Complete container lifecycle: create → start → monitor → cleanup
- Real-time log streaming and resource monitoring
- Timeout handling and automatic cleanup
- Error handling with detailed logging

### Job Processing System

**Management Commands**:
- `process_container_jobs`: Main worker daemon with database polling
- `manage_container_job`: Utility for manual job management
- Graceful shutdown handling (SIGINT/SIGTERM)
- Configurable concurrency and polling intervals

### Admin Interface

**Enhanced Django Admin**:
- Real-time status indicators with color coding
- Inline editing for environment variables and network assignments
- Bulk actions: start, stop, restart, cancel jobs
- Connection testing for Docker hosts
- HTMX integration for real-time updates
- Bootstrap5 styling for modern UI

## Key Patterns and Conventions

### Environment Variables
- All container configuration uses environment variables (12-factor app)
- Template-level variables with job-level overrides
- Secret marking for sensitive values (hidden in logs)
- JSON field for flexible override storage

### Resource Management
- Memory limits specified in MB (minimum 64MB)
- CPU limits as decimal cores (0.1 to 32.0)
- Automatic cleanup of old containers (configurable retention)
- Timeout enforcement with graceful termination

### Error Handling
- Custom exceptions: `DockerConnectionError`, `ContainerExecutionError`
- Comprehensive logging with structured error messages
- Connection health monitoring and retry logic
- Graceful degradation when Docker hosts are unavailable

### Testing Strategy
- Unit tests for all models and services
- Mock-based testing for Docker API interactions
- Integration tests for complete workflows
- Admin interface testing with Django test client
- Management command testing with output capture
- **Strongly prefer writing tests for the Django suite rather than doing inlines or shells**

## Database Schema

### Key Relationships
- ContainerTemplate → EnvironmentVariable (one-to-many)
- ContainerTemplate → NetworkAssignment (one-to-many)
- ContainerJob → ContainerTemplate (many-to-one)
- ContainerJob → DockerHost (many-to-one)
- ContainerJob → ContainerExecution (one-to-one)

### Important Fields
- `ContainerJob.id`: UUID primary key for reliable job identification
- `ContainerJob.status`: Enum with lifecycle states
- `ContainerJob.override_environment`: JSON field for variable overrides
- `ContainerTemplate.timeout_seconds`: Job execution timeout
- `DockerHost.connection_string`: Docker daemon connection URL

## Common Workflows

### Setting Up a New Container Template
1. Create DockerHost entry with connection details
2. Test connection using admin interface
3. Create ContainerTemplate with image and resource limits
4. Add environment variables and network assignments as needed
5. Test with a single job before bulk usage

### Running Container Jobs
1. Jobs start in 'pending' status
2. Worker command polls database for pending jobs
3. Docker container is created and started
4. Real-time logs are collected and stored
5. Job transitions to completed/failed based on exit code
6. Optional automatic cleanup removes containers

### Monitoring and Debugging
1. Use Django admin for real-time job monitoring
2. View logs directly in admin interface
3. Use management commands for detailed job inspection
4. Check Docker host connectivity status
5. Monitor resource usage through execution records

### Scaling and Distribution
1. Add multiple DockerHost entries for distributed execution
2. Run multiple worker processes with host filtering
3. Use database-level job queuing for coordination
4. Configure resource limits per template
5. Set up cleanup schedules for maintenance

## Executor Configuration Reference

### DockerHost.executor_config Field
This JSON field stores executor-specific configuration for each host. The exact structure depends on the executor type:

#### Docker Executor
```json
{
  "base_url": "tcp://docker-host:2376",
  "tls_verify": true,
  "tls_ca_cert": "/path/to/ca.pem",
  "tls_client_cert": "/path/to/cert.pem", 
  "tls_client_key": "/path/to/key.pem",
  "timeout": 30
}
```

#### Google Cloud Run Executor
```json
{
  "project": "my-gcp-project",
  "region": "us-central1",
  "service_account": "container-runner@my-project.iam.gserviceaccount.com",
  "vpc_connector": "projects/my-project/locations/us-central1/connectors/my-vpc",
  "cpu_limit": "2",
  "memory_limit": "2Gi",
  "max_retries": 3,
  "task_timeout": "3600s"
}
```

#### AWS Fargate Executor
```json
{
  "cluster": "my-ecs-cluster",
  "subnets": ["subnet-12345", "subnet-67890"],
  "security_groups": ["sg-abcdef"],
  "execution_role_arn": "arn:aws:iam::123456789:role/ecsTaskExecutionRole",
  "task_role_arn": "arn:aws:iam::123456789:role/ecsTaskRole",
  "platform_version": "LATEST",
  "assign_public_ip": "ENABLED"
}
```

### ContainerJob.executor_metadata Field
This JSON field stores runtime data populated by executors during job execution. It tracks executor-specific identifiers and state:

#### Docker Executor Metadata
```json
{
  "container_name": "job-abc123-worker",
  "container_id": "a1b2c3d4e5f6...",
  "network": "bridge",
  "volumes": ["/tmp/job-data:/data"],
  "ports": {"8080/tcp": 32768},
  "image_digest": "sha256:abcd1234..."
}
```

#### Google Cloud Run Metadata
```json
{
  "job_name": "job-abc123",
  "execution_name": "job-abc123-exec-001",
  "region": "us-central1",
  "project": "my-gcp-project",
  "service_url": "https://job-abc123-run-service.a.run.app",
  "revision": "job-abc123-00001-abc",
  "generation": 1
}
```

#### AWS Fargate Metadata
```json
{
  "task_arn": "arn:aws:ecs:us-east-1:123456789:task/my-cluster/abc123def456",
  "task_definition": "my-job-task:5",
  "cluster": "my-ecs-cluster",
  "launch_type": "FARGATE",
  "platform_version": "1.4.0",
  "availability_zone": "us-east-1a",
  "private_ip": "10.0.1.100"
}
```

### Usage Patterns

#### Executor Selection
The system uses simple weight-based routing to select hosts:
```python
# Higher weight = higher preference
DockerHost.objects.create(
    name="production-docker",
    executor_type="docker", 
    weight=200,  # Preferred
    executor_config={"base_url": "tcp://prod-docker:2376"}
)

DockerHost.objects.create(
    name="development-docker",
    executor_type="docker",
    weight=100,  # Lower priority
    executor_config={"base_url": "unix:///var/run/docker.sock"}
)
```

#### Job Monitoring and Debugging
The metadata field helps track and debug job execution:
```python
job = ContainerJob.objects.get(id="job-uuid")
print(f"Container ID: {job.executor_metadata.get('container_id')}")
print(f"Network: {job.executor_metadata.get('network')}")

# For Cloud Run jobs
print(f"Job URL: {job.executor_metadata.get('service_url')}")
print(f"Execution: {job.executor_metadata.get('execution_name')}")
```

#### Custom Executor Implementation
When creating custom executors, populate these fields appropriately:
```python
class MyCustomExecutor(ContainerExecutor):
    def launch_job(self, job):
        # Your custom launch logic
        result = self.my_platform.create_job(job.template.docker_image)
        
        # Store relevant identifiers in metadata
        job.executor_metadata = {
            "platform_job_id": result.job_id,
            "endpoint": result.endpoint_url,
            "region": self.config["region"],
            "custom_field": "my_value"
        }
        job.save()
        return True, result.job_id
```

## Job Customization Reference

### ContainerJob.override_command Field
This field allows you to override the template's default command for specific job instances. The command format depends on your container's entry point and shell.

#### Command Patterns

**Single Binary Commands:**
```bash
python main.py --config=production --verbose
node server.js --port=8080 --env=prod
./my-binary --input-file=/data/input.txt
```

**Shell Commands with Logic:**
```bash
bash -c "echo 'Starting job at $(date)' && python process.py && echo 'Job completed'"
sh -c "if [ -f /data/input.csv ]; then python import.py; else echo 'No input file'; fi"
```

**Multi-Step Operations:**
```bash
bash -c "pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput && gunicorn app:application"
sh -c "cd /app && npm install && npm run build && npm start"
```

**Script Execution:**
```bash
/bin/bash /scripts/deploy.sh --environment=staging --skip-tests
python /scripts/data_pipeline.py --start-date=2024-01-01 --end-date=2024-12-31
```

**Data Processing Examples:**
```bash
python etl.py --source=s3://bucket/data/ --dest=/tmp/processed --format=parquet
R -e "source('/scripts/analysis.R'); run_analysis('2024-01-01', '2024-12-31')"
```

#### Best Practices
- Use absolute paths for scripts and binaries
- Quote complex commands to avoid shell parsing issues
- Use `bash -c` for commands with shell operators (&&, ||, |)
- Test commands in your container image before deployment
- Consider using environment variables for dynamic values

### ContainerJob.override_environment Field
This JSON field allows you to add or override environment variables for specific jobs. Variables merge with template defaults, with job overrides taking precedence.

#### Environment Variable Patterns

**Application Configuration:**
```json
{
  "DEBUG": "false",
  "LOG_LEVEL": "warning", 
  "APP_ENV": "production",
  "WORKER_PROCESSES": "4",
  "TIMEOUT": "300"
}
```

**Database Configuration:**
```json
{
  "DATABASE_URL": "postgresql://user:pass@prod-db:5432/myapp",
  "DB_HOST": "prod-cluster.company.com",
  "DB_NAME": "production_db",
  "DB_USER": "app_user",
  "DB_PASSWORD": "secure_password",
  "DB_SSL_MODE": "require"
}
```

**API and Service Integration:**
```json
{
  "API_KEY": "sk-1234567890abcdef",
  "API_BASE_URL": "https://api.company.com/v2",
  "WEBHOOK_URL": "https://hooks.company.com/job-completed",
  "REDIS_URL": "redis://cache.company.com:6379/0",
  "ELASTICSEARCH_URL": "https://search.company.com:9200"
}
```

**File and Storage Paths:**
```json
{
  "INPUT_FILE": "/data/batch_20240126.csv",
  "OUTPUT_DIR": "/results/daily_reports", 
  "BACKUP_LOCATION": "s3://company-backups/jobs/",
  "TEMP_DIR": "/tmp/job_workspace",
  "CONFIG_FILE": "/config/production.yaml"
}
```

**Feature Flags and Toggles:**
```json
{
  "ENABLE_NEW_FEATURE": "true",
  "USE_EXPERIMENTAL_ALGORITHM": "false",
  "PARALLEL_PROCESSING": "true",
  "SEND_NOTIFICATIONS": "true",
  "SKIP_VALIDATION": "false"
}
```

**Cloud Provider Configuration:**
```json
{
  "AWS_REGION": "us-west-2",
  "AWS_S3_BUCKET": "company-data-prod",
  "GCP_PROJECT": "company-prod-123456",
  "AZURE_STORAGE_ACCOUNT": "companyprod",
  "CLOUD_PROVIDER": "aws"
}
```

**Job-Specific Parameters:**
```json
{
  "BATCH_ID": "20240126_001",
  "JOB_TYPE": "daily_report",
  "CUSTOMER_ID": "cust_12345",
  "PROCESSING_DATE": "2024-01-26",
  "RETRY_COUNT": "3",
  "EMAIL_RECIPIENTS": "admin@company.com,ops@company.com"
}
```

#### Variable Priority and Merging
Environment variables are merged in this order (later values override earlier ones):

1. **Container Image defaults** (FROM ubuntu:22.04, etc.)
2. **Template environment variables** (EnvironmentVariable models)
3. **Job override_environment** (this field)
4. **Runtime executor variables** (e.g., Cloud Run service account)

Example of variable merging:
```python
# Template has:
template_vars = {"DEBUG": "false", "PORT": "8080", "ENV": "dev"}

# Job override has:
job_override = {"DEBUG": "true", "DATABASE_URL": "postgresql://..."}

# Final environment:
final_env = {
    "DEBUG": "true",        # Job override wins
    "PORT": "8080",         # From template
    "ENV": "dev",           # From template  
    "DATABASE_URL": "postgresql://..."  # Added by job
}
```

#### Security Considerations
- **Never log sensitive environment variables** (passwords, API keys, tokens)
- **Use secrets management** for production credentials
- **Validate input** for environment variables that affect security
- **Rotate credentials** regularly for API keys and database passwords
- **Consider encryption** for sensitive configuration stored in the database

#### Dynamic Environment Variables
You can programmatically set environment variables when creating jobs:

```python
# Create job with dynamic environment
import datetime

job = ContainerJob.objects.create(
    template=data_template,
    docker_host=production_host,
    name=f"Daily Report {datetime.date.today()}",
    override_environment={
        "PROCESSING_DATE": datetime.date.today().isoformat(),
        "OUTPUT_FILE": f"report_{datetime.date.today().strftime('%Y%m%d')}.pdf",
        "BATCH_ID": f"batch_{int(datetime.datetime.now().timestamp())}",
    }
)
```

## Development Guidelines

### Adding New Features
- Follow Django patterns and conventions
- Add comprehensive tests for new functionality
- Update admin interface for new models
- Document management commands and usage
- Consider 12-factor app principles

### Code Style
- Use ruff for formatting and linting (configured in pyproject.toml)
- Follow Django naming conventions
- Write descriptive docstrings for classes and methods
- Use type hints where beneficial
- Keep templates and static files organized

### Code Complexity and Design
- Be very mindful of cyclomatic complexity when generating code
- Prefer early return to nesting if statements
- Avoid nested try/except blocks
- Keep functions and methods focused and concise

### Version Control Best Practices
- Remember to commit often as a means of checkpointing your progress. Do not be shy to rollback, branch, or use git to its fullest potential.

### Security Considerations
- Never log sensitive environment variables
- Use TLS for remote Docker connections
- Validate all user inputs in admin forms
- Implement proper access controls
- Regularly update dependencies

## Code Quality Notes

### Linting and Formatting
- Use ruff for linting and formatting
- Don't get too stuck on the really pedantic rules that just force you to eat input and output tokens
- Be sane about code style and formatting

## Dependencies

### Core Dependencies
- **Django 5.2+**: Web framework and admin interface
- **docker**: Python Docker API client
- **channels**: WebSocket support for real-time features
- **channels-redis**: Redis channel layer for production

### Development Dependencies
- **ruff**: Code formatting and linting
- **uv**: Fast Python package manager

### Frontend Dependencies (CDN)
- **Bootstrap 5**: Modern CSS framework
- **HTMX**: Dynamic HTML without JavaScript complexity

## Configuration

### Environment Variables
- `DJANGO_SETTINGS_MODULE`: Django settings module
- `DEBUG`: Enable debug mode (development only)
- `SECRET_KEY`: Django secret key for production
- `DATABASE_URL`: Database connection string (optional)

### Django Settings
- `CHANNEL_LAYERS`: Redis configuration for channels
- `STATIC_URL` and `STATIC_ROOT`: Static file serving
- `LOGGING`: Configure logging levels and handlers

## Troubleshooting

### Common Issues
1. **Docker connection failures**: Check host connectivity and permissions
2. **Job timeouts**: Increase timeout_seconds in template
3. **Resource limits**: Verify Docker host has sufficient resources
4. **Log collection**: Ensure containers have proper output streams
5. **Admin interface**: Check HTMX and Bootstrap CDN availability

### Debug Commands
```bash
# Test Docker host connectivity
uv run python manage.py manage_container_job create test-template test-host

# Check job status
uv run python manage.py manage_container_job show JOB-UUID

# View container logs
docker logs CONTAINER-ID

# Check worker process status
ps aux | grep process_container_jobs
```

This system provides a robust foundation for Django-based container orchestration with comprehensive tracking, monitoring, and management capabilities.