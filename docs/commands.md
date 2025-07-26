# Management Commands Reference

This guide documents all Django management commands available in Django Docker Container Manager.

## Overview

The system provides two main management commands for container job processing and management:

1. `process_container_jobs` - Main worker daemon for processing jobs
2. `manage_container_job` - Utility for manual job operations

## process_container_jobs

**Purpose**: Main worker daemon that continuously polls for and executes pending container jobs.

### Basic Usage

```bash
# Start job processor with default settings
uv run python manage.py process_container_jobs

# Start with custom polling interval
uv run python manage.py process_container_jobs --poll-interval=10

# Process with maximum concurrent jobs
uv run python manage.py process_container_jobs --max-jobs=20

# Run single processing cycle (no continuous polling)
uv run python manage.py process_container_jobs --single-run
```

### Command Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--poll-interval` | Integer | 5 | Seconds between database polls for pending jobs |
| `--max-jobs` | Integer | 10 | Maximum number of concurrent job executions |
| `--single-run` | Flag | False | Process pending jobs once and exit |
| `--host` | String | None | Limit processing to specific Docker host |
| `--cleanup` | Flag | False | Enable automatic cleanup of old containers |
| `--cleanup-hours` | Integer | 24 | Hours after which to clean up completed containers |

### Operational Examples

#### Production Worker
```bash
# Production settings: 3-second polling, up to 50 concurrent jobs
uv run python manage.py process_container_jobs --poll-interval=3 --max-jobs=50
```

#### Development Worker
```bash
# Development settings: slower polling, fewer concurrent jobs
uv run python manage.py process_container_jobs --poll-interval=10 --max-jobs=5
```

#### Host-Specific Processing
```bash
# Process jobs only on specific Docker host
uv run python manage.py process_container_jobs --host=production-host
```

#### Cleanup Mode
```bash
# Enable automatic cleanup of containers older than 48 hours
uv run python manage.py process_container_jobs --cleanup --cleanup-hours=48
```

#### One-Time Processing
```bash
# Process all pending jobs once and exit
uv run python manage.py process_container_jobs --single-run
```

### Process Behavior

#### Job Selection
- Polls database every `--poll-interval` seconds
- Selects pending jobs ordered by priority (1=highest, 5=lowest) and creation time
- Respects Docker host availability and active status

#### Concurrency Management
- Maintains up to `--max-jobs` concurrent executions
- Spawns new processes for each job execution
- Monitors running jobs and updates status in real-time

#### Graceful Shutdown
- Handles SIGINT (Ctrl+C) and SIGTERM signals
- Waits for running jobs to complete before exiting
- Updates job status to reflect interruption

#### Error Handling
- Docker connection failures logged and jobs marked as failed
- Container execution errors captured with exit codes
- Database connectivity issues handled with retry logic

### Output Examples

```bash
$ uv run python manage.py process_container_jobs
Starting container job processor...
Poll interval: 5 seconds
Max concurrent jobs: 10
Press Ctrl+C to stop gracefully

[2024-01-15 10:30:15] Processing job abc123... (template: data-processing)
[2024-01-15 10:30:16] Job abc123 started successfully
[2024-01-15 10:30:45] Job abc123 completed (exit code: 0)
[2024-01-15 10:30:50] Processing job def456... (template: report-generation)
```

## manage_container_job

**Purpose**: Utility command for manual container job management and operations.

### Subcommands

#### create
Create a new container job from template.

```bash
# Basic job creation
uv run python manage.py manage_container_job create <template-name> <host-name>

# Create with custom name
uv run python manage.py manage_container_job create template-name host-name --name="Custom Job Name"

# Create with command override
uv run python manage.py manage_container_job create template-name host-name --command="python custom_script.py"

# Create with resource overrides
uv run python manage.py manage_container_job create template-name host-name \
    --memory=2048 \
    --cpu=2.0 \
    --timeout=7200
```

**Options:**
- `--name`: Custom job name
- `--command`: Override template command
- `--memory`: Override memory limit (MB)
- `--cpu`: Override CPU limit (cores)
- `--timeout`: Override timeout (seconds)

#### run
Create and immediately execute a container job.

```bash
# Create and run job
uv run python manage.py manage_container_job run <template-name> <host-name>

# Run with overrides
uv run python manage.py manage_container_job run template-name host-name \
    --command="echo 'Hello World'" \
    --name="Test Job"
```

#### list
List container jobs with filtering options.

```bash
# List all jobs
uv run python manage.py manage_container_job list

# Filter by status
uv run python manage.py manage_container_job list --status=running
uv run python manage.py manage_container_job list --status=failed
uv run python manage.py manage_container_job list --status=completed

# Filter by template
uv run python manage.py manage_container_job list --template=data-processing

# Filter by host
uv run python manage.py manage_container_job list --host=production-docker

# Filter by date range
uv run python manage.py manage_container_job list --since="2024-01-01"
uv run python manage.py manage_container_job list --until="2024-01-31"

# Limit results
uv run python manage.py manage_container_job list --limit=50
```

**Filter Options:**
- `--status`: Filter by job status (pending, running, completed, failed, cancelled)
- `--template`: Filter by template name
- `--host`: Filter by Docker host name
- `--since`: Filter jobs created after date (YYYY-MM-DD)
- `--until`: Filter jobs created before date (YYYY-MM-DD)
- `--limit`: Limit number of results

#### show
Display detailed information about a specific job.

```bash
# Show job details
uv run python manage.py manage_container_job show <job-id>

# Show with logs
uv run python manage.py manage_container_job show <job-id> --logs

# Show with environment variables
uv run python manage.py manage_container_job show <job-id> --env
```

**Options:**
- `--logs`: Include stdout/stderr logs in output
- `--env`: Include environment variables in output

#### cancel
Cancel a running or pending job.

```bash
# Cancel specific job
uv run python manage.py manage_container_job cancel <job-id>

# Cancel all pending jobs for template
uv run python manage.py manage_container_job cancel --template=template-name --status=pending

# Cancel all running jobs on host
uv run python manage.py manage_container_job cancel --host=host-name --status=running
```

**Options:**
- `--template`: Cancel jobs matching template
- `--host`: Cancel jobs on specific host
- `--status`: Cancel jobs with specific status

#### cleanup
Clean up old container jobs and their containers.

```bash
# Clean up completed jobs older than 7 days
uv run python manage.py manage_container_job cleanup --older-than=7 --status=completed

# Clean up failed jobs older than 30 days
uv run python manage.py manage_container_job cleanup --older-than=30 --status=failed

# Clean up all finished jobs older than 14 days
uv run python manage.py manage_container_job cleanup --older-than=14 --status=completed,failed

# Dry run (show what would be cleaned up)
uv run python manage.py manage_container_job cleanup --older-than=7 --dry-run
```

**Options:**
- `--older-than`: Days threshold for cleanup
- `--status`: Comma-separated list of statuses to clean up
- `--dry-run`: Show what would be cleaned up without doing it

### Usage Examples

#### Daily Operations

```bash
# Check current job queue
uv run python manage.py manage_container_job list --status=pending,running

# Review failed jobs from today
uv run python manage.py manage_container_job list --status=failed --since="$(date +%Y-%m-%d)"

# Clean up old completed jobs
uv run python manage.py manage_container_job cleanup --older-than=7 --status=completed
```

#### Troubleshooting

```bash
# Examine failed job details
uv run python manage.py manage_container_job show <job-id> --logs

# Cancel stuck jobs
uv run python manage.py manage_container_job cancel --status=running --host=problematic-host

# List recent failures for pattern analysis
uv run python manage.py manage_container_job list --status=failed --limit=20
```

#### Bulk Operations

```bash
# Cancel all pending jobs for maintenance
uv run python manage.py manage_container_job cancel --status=pending

# Clean up everything older than 30 days
uv run python manage.py manage_container_job cleanup --older-than=30 --status=completed,failed,cancelled
```

### Output Formats

#### List Output
```bash
$ uv run python manage.py manage_container_job list --limit=5
Job ID                               Template         Host            Status      Created
abc123-def4-5678-9abc-def123456789  data-processing  local-docker    completed   2024-01-15 10:30:15
def456-789a-bcde-f012-345678901234  report-gen       prod-docker     running     2024-01-15 11:15:22
ghi789-012b-cdef-3456-789012345678  cleanup-task     local-docker    pending     2024-01-15 11:45:30
```

#### Show Output
```bash
$ uv run python manage.py manage_container_job show abc123-def4-5678-9abc-def123456789
Job Details:
  ID: abc123-def4-5678-9abc-def123456789
  Template: data-processing
  Docker Host: local-docker
  Status: completed
  Exit Code: 0
  Created: 2024-01-15 10:30:15
  Started: 2024-01-15 10:30:16
  Finished: 2024-01-15 10:30:45
  Duration: 0:00:29
  Container ID: container_abc123
  Command: python process_data.py --input=/data/input.csv
```

## Environment Variables

### Command Configuration
Commands respect these environment variables:

```bash
# Docker connection timeout
DOCKER_TIMEOUT=60

# Default polling interval
DEFAULT_POLL_INTERVAL=5

# Default max concurrent jobs
DEFAULT_MAX_JOBS=10

# Enable debug logging
DJANGO_LOG_LEVEL=DEBUG
```

## Automation and Scheduling

### Systemd Service
```ini
# /etc/systemd/system/django-docker-worker.service
[Unit]
Description=Django Docker Container Manager Worker
After=network.target

[Service]
Type=simple
User=django
WorkingDirectory=/path/to/django-docker-manager
ExecStart=/path/to/venv/bin/python manage.py process_container_jobs --poll-interval=3 --max-jobs=20
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Cron Jobs
```bash
# Daily cleanup of old jobs
0 2 * * * /path/to/venv/bin/python /path/to/manage.py manage_container_job cleanup --older-than=7 --status=completed,failed

# Hourly status check
0 * * * * /path/to/venv/bin/python /path/to/manage.py manage_container_job list --status=failed --since="1 hour ago" | mail -s "Failed Jobs Report" admin@example.com
```

### Docker Compose
```yaml
# Worker service in docker-compose.yml
worker:
  build: .
  command: python manage.py process_container_jobs --poll-interval=5 --max-jobs=15
  environment:
    - DATABASE_URL=postgresql://user:pass@db:5432/dbname
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  restart: unless-stopped
```

## Error Handling

### Common Exit Codes
- **0**: Success
- **1**: General application error
- **2**: Command line argument error
- **3**: Database connection error
- **4**: Docker connection error
- **5**: Job execution error

### Error Messages
Commands provide descriptive error messages:
```bash
$ uv run python manage.py manage_container_job show invalid-job-id
Error: Job with ID 'invalid-job-id' not found

$ uv run python manage.py manage_container_job create nonexistent-template local-docker
Error: Template 'nonexistent-template' does not exist
```

## Best Practices

### Production Usage
1. **Use systemd services** for reliable worker process management
2. **Monitor worker health** with process supervision
3. **Set appropriate polling intervals** to balance responsiveness and database load
4. **Configure log rotation** for command output
5. **Regular cleanup** of old jobs to manage database size

### Development Usage
1. **Use longer polling intervals** to reduce development database churn
2. **Single-run mode** for testing and debugging
3. **Verbose logging** for troubleshooting
4. **Small concurrent job limits** for resource conservation

### Operational Procedures
1. **Graceful shutdowns** using SIGTERM for maintenance
2. **Job queue monitoring** to prevent backlog buildup
3. **Regular cleanup** of completed and failed jobs
4. **Host-specific processing** for maintenance and scaling

For more details on job lifecycle management, see the [Job Management Guide](jobs.md).