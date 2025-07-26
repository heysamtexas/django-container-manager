# Monitoring and Logging Guide

This guide covers the current monitoring and logging capabilities in Django Docker Container Manager.

## Current Monitoring Features

### Django Admin Interface

The primary monitoring interface is the Django admin, which provides:

#### Job Status Overview
- Real-time job status indicators with color coding
- Job list with filtering by status, template, and host
- Bulk actions for job management (start, stop, cancel)
- Individual job detail views with execution logs

#### Docker Host Monitoring
- Host connection status indicators
- "Test Connection" bulk action to verify host availability
- Host configuration and status display

#### Container Template Management
- Template usage statistics
- Template configuration verification
- Environment variable and network assignment management

### Job Execution Tracking

#### Job Status Lifecycle
Jobs are tracked through these states:
- `pending` - Job created but not started
- `running` - Container is executing
- `completed` - Job finished successfully (exit code 0)
- `failed` - Job finished with error (non-zero exit code)
- `cancelled` - Job was manually cancelled

#### Execution Data Collected
For each job execution:
- Start and finish timestamps
- Container ID and Docker host used
- Exit code and status
- Complete stdout and stderr logs
- Execution duration calculation

### Management Command Monitoring

#### Process Container Jobs Command
```bash
uv run python manage.py process_container_jobs
```

Provides monitoring output:
- Job polling interval status
- Jobs processed count
- Error handling and retry information
- Graceful shutdown handling (SIGINT/SIGTERM)

#### Job Management Command
```bash
# List jobs with status
uv run python manage.py manage_container_job list --status=running

# Show detailed job information
uv run python manage.py manage_container_job show <job-id>

# View job logs
uv run python manage.py manage_container_job logs <job-id>
```

## Current Logging Implementation

### Application Logging

#### Docker Service Logging
The `DockerService` class includes comprehensive logging:
```python
# container_manager/docker_service.py
logger = logging.getLogger(__name__)

# Logs container lifecycle events
logger.info(f"Creating container for job {job.id}")
logger.info(f"Container {container.id} started successfully")
logger.error(f"Failed to create container: {str(e)}")
```

#### Management Command Logging
```python
# management/commands/process_container_jobs.py
self.stdout.write(f"Processing job {job.id}")
self.stdout.write(self.style.SUCCESS(f"Job {job.id} completed"))
self.stdout.write(self.style.ERROR(f"Job {job.id} failed"))
```

### Django Default Logging

Uses Django's standard logging configuration:
- Console output for development
- Standard Django request/response logging
- Error logging with stack traces
- SQL query logging in debug mode

### Job-Specific Logging

#### Container Output Capture
- Complete stdout logs stored in `ContainerExecution.stdout_logs`
- Complete stderr logs stored in `ContainerExecution.stderr_logs`
- Docker daemon logs captured during execution

#### Error Tracking
- Container creation failures logged with details
- Network connectivity issues tracked
- Resource limit violations recorded
- Timeout events logged with context

## Health Checking

### Docker Host Health
```python
# Via Django admin "Test Connection" action
def test_docker_host_connection(host):
    try:
        client = docker_service.get_client(host)
        client.ping()
        return "Connection successful"
    except Exception as e:
        return f"Connection failed: {str(e)}"
```

### Job Queue Monitoring
- Admin interface shows pending job count
- Running job count visible in admin lists
- Failed job identification through status filtering

## Performance Tracking

### Execution Time Tracking
```python
# Automatic calculation in ContainerJob model
@property
def execution_time(self):
    if self.started_at and self.finished_at:
        return self.finished_at - self.started_at
    return None
```

### Resource Usage
- Memory and CPU limits enforced per template
- Container resource consumption logged in Docker daemon
- Host resource availability checked during job assignment

## Error Handling and Debugging

### Container Execution Errors
```python
# DockerService error handling
try:
    container = client.containers.create(...)
except docker.errors.APIError as e:
    logger.error(f"Docker API error: {e}")
    raise DockerConnectionError(f"Failed to create container: {e}")
```

### Job Failure Analysis
- Exit codes captured and stored
- Error logs preserved for debugging
- Container state at failure recorded
- Host connectivity issues tracked

### Debug Information Available
- Container ID for failed jobs
- Complete command executed
- Environment variables used (secrets masked)
- Network configuration applied
- Resource limits enforced

## Admin Interface Features

### Real-time Status Updates
- Job status changes reflected immediately
- Color-coded status indicators:
  - Green: completed
  - Blue: running  
  - Yellow: pending
  - Red: failed
  - Gray: cancelled

### Filtering and Search
- Filter jobs by status, template, host, date
- Search by job ID or template name
- Date range filtering for historical analysis

### Bulk Operations
- Start multiple pending jobs
- Cancel running jobs
- Test multiple Docker host connections
- Export job data for analysis

## Log File Locations

### Development
- Console output via Django development server
- Django debug toolbar for SQL query analysis

### Production
Configure logging in `settings.py`:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django-docker-manager.log',
        },
    },
    'loggers': {
        'container_manager': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Monitoring Workflows

### Daily Operations
1. Check admin dashboard for failed jobs
2. Review pending job queue depth
3. Verify Docker host connectivity
4. Monitor execution times for performance issues

### Troubleshooting Failed Jobs
1. Navigate to failed job in admin interface
2. Review stderr logs for error messages
3. Check container exit code
4. Verify Docker host connectivity
5. Review template configuration
6. Check resource availability on host

### Performance Analysis
1. Filter completed jobs by template
2. Review execution time patterns
3. Identify resource-intensive templates
4. Monitor host resource usage trends
5. Optimize template configurations based on data

## Current Limitations

### No Built-in Alerting
- No automatic notifications for job failures
- No proactive monitoring of host health
- Manual monitoring required through admin interface

### Basic Metrics
- Limited to job count and status tracking
- No resource usage trending
- No performance benchmarking over time

### Log Management
- No log rotation configured by default
- No centralized log aggregation
- Limited structured logging format

## Extending Monitoring

For comprehensive monitoring enhancements, see the monitoring specifications in the `specs/` directory which outline:
- Advanced metrics collection
- Alerting and notification systems  
- Performance monitoring dashboards
- Centralized logging integration
- Health check endpoints

The current implementation provides solid foundations for monitoring job execution and system health, with room for enhancement based on operational needs.