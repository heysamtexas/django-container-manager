# Task: Update API Documentation for Queue Features

## Objective
Update project documentation to cover new queue management features, API changes, and usage patterns.

## Success Criteria
- [ ] API reference updated with queue methods
- [ ] Model documentation includes queue fields
- [ ] Management command help updated
- [ ] Migration guide created
- [ ] Deployment examples provided
- [ ] All documentation is accurate and helpful

## Implementation Details

### API Reference Updates

```markdown
# API Documentation Updates

## Queue Management API

### JobQueueManager

The `JobQueueManager` class provides high-level queue operations.

#### Methods

##### `queue_job(job, schedule_for=None, priority=None)`

Add a job to the queue for execution.

**Parameters:**
- `job` (ContainerJob): Job instance to queue
- `schedule_for` (datetime, optional): When to execute the job
- `priority` (int, optional): Job priority (0-100, higher = more priority)

**Returns:**
- `ContainerJob`: The queued job instance

**Raises:**
- `ValueError`: If job cannot be queued (already queued, completed, etc.)

**Example:**
```python
from container_manager.queue import queue_manager
from container_manager.models import ContainerJob

# Queue job immediately
job = ContainerJob.objects.create(command="echo hello")
queue_manager.queue_job(job)

# Queue with high priority
queue_manager.queue_job(job, priority=80)

# Schedule for later
from django.utils import timezone
from datetime import timedelta

schedule_time = timezone.now() + timedelta(hours=2)
queue_manager.queue_job(job, schedule_for=schedule_time)
```

##### `get_ready_jobs(limit=None, exclude_ids=None)`

Get jobs ready for launching.

**Parameters:**
- `limit` (int, optional): Maximum number of jobs to return
- `exclude_ids` (list, optional): Job IDs to exclude from results

**Returns:**
- `QuerySet`: ContainerJob instances ready to launch, ordered by priority then FIFO

**Example:**
```python
# Get next 5 jobs ready to launch
ready_jobs = queue_manager.get_ready_jobs(limit=5)

for job in ready_jobs:
    print(f"Job {job.id}: {job.name} (priority: {job.priority})")
```

##### `launch_job_with_retry(job)`

Launch a job with sophisticated retry logic.

**Parameters:**
- `job` (ContainerJob): Job to launch

**Returns:**
- `dict`: Result with keys:
  - `success` (bool): Whether launch was successful
  - `error` (str): Error message if failed
  - `retry_scheduled` (bool): Whether retry was scheduled

**Example:**
```python
result = queue_manager.launch_job_with_retry(job)

if result['success']:
    print(f"Job {job.id} launched successfully")
elif result['retry_scheduled']:
    print(f"Job {job.id} failed, retry scheduled: {result['error']}")
else:
    print(f"Job {job.id} permanently failed: {result['error']}")
```

##### `launch_next_batch(max_concurrent=5, timeout=30)`

Launch multiple jobs up to concurrency limit.

**Parameters:**
- `max_concurrent` (int): Maximum concurrent jobs to launch
- `timeout` (int): Timeout in seconds for job acquisition

**Returns:**
- `dict`: Result with keys:
  - `launched` (int): Number of jobs launched
  - `errors` (list): List of error messages

**Example:**
```python
# Launch up to 10 jobs concurrently
result = queue_manager.launch_next_batch(max_concurrent=10)

print(f"Launched {result['launched']} jobs")
if result['errors']:
    print(f"Errors: {result['errors']}")
```

##### `get_queue_stats()`

Get current queue statistics.

**Returns:**
- `dict`: Statistics with keys:
  - `queued` (int): Jobs ready to launch
  - `scheduled` (int): Jobs scheduled for future
  - `running` (int): Currently running jobs
  - `launch_failed` (int): Jobs that failed to launch

**Example:**
```python
stats = queue_manager.get_queue_stats()
print(f"Queue depth: {stats['queued']}")
print(f"Running: {stats['running']}")
print(f"Scheduled: {stats['scheduled']}")
```

### ContainerJob Model Updates

#### New Fields

##### Queue State Fields

- `queued_at` (DateTimeField): When job was added to queue
- `scheduled_for` (DateTimeField): When job should be executed
- `launched_at` (DateTimeField): When job container was launched
- `retry_count` (IntegerField): Number of launch attempts made
- `max_retries` (IntegerField): Maximum launch attempts allowed
- `priority` (IntegerField): Job priority (0-100)

##### Error Information Fields

- `last_error` (TextField): Last error message from failed launch
- `last_error_at` (DateTimeField): When the last error occurred
- `retry_strategy` (CharField): Retry strategy to use

#### New Properties

##### `is_queued`

Returns `True` if job is queued but not yet launched.

```python
if job.is_queued:
    print("Job is waiting in queue")
```

##### `is_ready_to_launch`

Returns `True` if job is ready to launch now.

```python
if job.is_ready_to_launch:
    print("Job can be launched immediately")
```

##### `queue_status`

Returns human-readable queue status string.

**Possible values:**
- `'not_queued'`: Job is not in queue
- `'queued'`: Job is ready to launch
- `'scheduled'`: Job is scheduled for future
- `'launched'`: Job has been launched
- `'launch_failed'`: Job failed to launch after max retries

```python
print(f"Queue status: {job.queue_status}")
```

#### New Methods

##### `mark_as_queued(scheduled_for=None)`

Transition job to queued state.

```python
job.mark_as_queued()  # Queue immediately
job.mark_as_queued(scheduled_for=future_time)  # Schedule for later
```

##### `mark_as_running()`

Transition job to running state.

```python
job.mark_as_running()  # Sets launched_at timestamp
```

##### `mark_as_completed()`

Transition job to completed state.

```python
job.mark_as_completed()  # Sets completed_at timestamp
```

##### `mark_as_failed(should_retry=False)`

Transition job to failed state, optionally setting up retry.

```python
job.mark_as_failed()  # Permanent failure
job.mark_as_failed(should_retry=True)  # May retry if under limit
```
```

### Error Classification and Retry Strategies

```markdown
## Error Classification

The queue system automatically classifies errors to determine retry behavior.

### Error Types

#### Transient Errors (Will Retry)
- Connection errors (Docker daemon unavailable)
- Resource constraints (out of memory, disk full)
- Network timeouts
- System overload conditions

#### Permanent Errors (No Retry)
- Image not found
- Invalid configuration
- Permission denied
- Command not found

#### Unknown Errors
- Treated as transient with conservative retry limits

### Retry Strategies

#### Available Strategies

- `'default'`: 3 attempts, 2-60 second backoff
- `'aggressive'`: 5 attempts, 1-30 second backoff  
- `'conservative'`: 2 attempts, 5-300 second backoff
- `'high_priority'`: 5 attempts, 0.5-15 second backoff

#### Configuring Retry Strategy

```python
# Set retry strategy on job
job.retry_strategy = 'aggressive'
job.save()

# Or when creating
job = ContainerJob.objects.create(
    command="echo test",
    retry_strategy='high_priority'
)
```

#### Custom Retry Strategy

```python
from container_manager.retry import RetryStrategy, RETRY_STRATEGIES

# Define custom strategy
RETRY_STRATEGIES['custom'] = RetryStrategy(
    max_attempts=4,
    base_delay=1.5,
    max_delay=120.0,
    backoff_factor=1.8
)
```

### Management Command Updates

#### Queue Mode Options

##### `--queue-mode`
Run in queue processing mode (launches queued jobs).

##### `--max-concurrent N`
Maximum concurrent jobs (default: 5).

##### `--poll-interval N`  
Polling interval in seconds (default: 10).

##### `--once`
Process queue once and exit (don't run continuously).

##### `--timeout N`
Timeout for job acquisition in seconds (default: 30).

#### Examples

```bash
# Continuous queue processing
python manage.py process_container_jobs --queue-mode

# Single queue run
python manage.py process_container_jobs --queue-mode --once

# High concurrency with fast polling  
python manage.py process_container_jobs --queue-mode --max-concurrent=20 --poll-interval=5

# Dry run to see queue status
python manage.py process_container_jobs --queue-mode --dry-run
```

#### Signal Handling

- `SIGTERM/SIGINT`: Graceful shutdown (waits for running jobs)
- `SIGUSR1`: Print queue status to logs/stdout

```bash
# Get queue status from running processor
kill -USR1 <process_pid>

# Graceful shutdown
kill -TERM <process_pid>
```
```

### Django Admin Integration

```markdown
## Django Admin Queue Management

### Enhanced List View

The admin interface now shows:

- **Queue Status**: Color-coded status indicators
- **Priority**: Visual priority indicators  
- **Timestamps**: Queue, launch, and completion times
- **Retry Information**: Attempt counts and error details

### Admin Actions

#### Bulk Operations

- **Queue selected jobs**: Add jobs to queue
- **Remove from queue**: Remove jobs from queue
- **Cancel selected jobs**: Stop running jobs
- **Retry failed jobs**: Requeue failed jobs with reset retry count
- **Set priority**: Change job priority (high/normal/low)

#### Individual Job Actions

- **Queue/Dequeue**: Toggle job queue status
- **Cancel**: Stop running job
- **View Logs**: See execution logs in popup

### Filtering and Search

#### Queue Status Filter
- Not Queued
- Queued (Ready)  
- Scheduled (Future)
- Launched
- Launch Failed

#### Search Fields
- Job name and command
- Docker image
- Job ID

### Queue Statistics

Access queue statistics at `/admin/container_manager/containerjob/queue-stats/`

Shows:
- Queue depth and ready jobs
- Currently running jobs
- Scheduled jobs count
- Jobs completed/failed today
- High priority jobs in queue
```

## Files to Create/Modify
- `docs/api-reference.md` - Updated API documentation
- `docs/queue-management.md` - New queue management guide
- `README.md` - Add queue features to overview
- `container_manager/models.py` - Add comprehensive docstrings

## Documentation Structure

```
docs/
├── api-reference.md          # Complete API documentation
├── queue-management.md       # Queue usage guide
├── deployment.md            # Deployment examples
├── migration-guide.md       # Migration from older versions
└── troubleshooting.md       # Common issues and solutions
```

## Testing Documentation

```bash
# Test that all documented examples work
python manage.py shell < docs/examples/queue_examples.py

# Validate API reference examples
python -m doctest docs/api-reference.md
```

## Dependencies
- Depends on: All queue implementation tasks
- Requires: Complete queue feature implementation

## Documentation Standards
- All public methods must have docstrings
- Include parameter types and descriptions
- Provide realistic usage examples
- Cover both success and error scenarios
- Include performance considerations
- Show deployment configurations

## Notes
- Documentation should be beginner-friendly
- Include troubleshooting for common issues
- Show integration patterns with Django
- Cover both programmatic and admin usage
- Provide migration path from existing code
- Include performance tuning recommendations