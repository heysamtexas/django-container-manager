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