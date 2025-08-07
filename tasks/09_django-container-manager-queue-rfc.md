# RFC: Queue Management for django-container-manager

**Title:** Add Queue State Management to ContainerJob Model  
**Type:** Feature Enhancement  
**Status:** Draft  
**Author:** Django Container Manager Demo Contributors  
**Date:** August 7, 2025  
**Version:** 1.0  

## Executive Summary

This RFC proposes adding explicit queue management functionality to the `django-container-manager` library by separating queue state from container execution state. The current `ContainerJob` model conflates these concerns, making it difficult to implement common workflow patterns like batch processing, job scheduling, and resource-aware execution.

**Key Proposal:**
- Add queue state fields to `ContainerJob` model (`queued_at`, `launched_at`, `scheduled_for`)
- Provide `JobQueueManager` service for queue operations
- Include management command for queue processing (`process_container_jobs --queue-mode`)
- Maintain full backward compatibility with existing usage patterns

**Benefits:**
- Enables proper task queuing and batch processing
- Supports scheduled job execution
- Allows resource-aware job launching
- Provides foundation for multi-worker distributed processing
- Maintains all existing functionality

## Problem Analysis

### Current Architecture Limitation

The existing `ContainerJob` model uses a single `status` field to represent both queue state ("I want this job to run") and execution state ("This container is currently running"). This conflation creates several problems:

```python
# Current problematic patterns
ContainerJob.objects.filter(status='pending')  # Queue state or execution state?
ContainerJob.objects.filter(status='running')  # Definitely execution state
ContainerJob.objects.filter(status='failed')   # Launch failure or execution failure?
```

### Specific Problems

#### 1. **No True Task Queuing**
- Cannot queue jobs for later execution
- Cannot implement "queue 1000 jobs, execute 10 at a time" patterns
- No way to pause/resume job processing

#### 2. **Ambiguous Failure States**
- Job launch failures pollute execution status
- Cannot distinguish between "failed to start container" vs "container ran but failed"
- Retry logic becomes complex and error-prone

#### 3. **Resource Management Issues**
- No way to queue jobs when system is at capacity
- Cannot implement intelligent scheduling based on available resources
- Risk of resource exhaustion from simultaneous job launches

#### 4. **Scheduling Limitations**
- No native support for scheduled/delayed job execution
- Cannot implement cron-like job scheduling
- No way to queue jobs for future execution

#### 5. **Multi-Worker Complexity**
- Difficult to implement distributed job processing
- Race conditions in job assignment across workers
- No clear ownership of queued vs running jobs

### Real-World Impact

These limitations prevent implementing common enterprise workflow patterns:

```python
# Currently impossible patterns
batch_processor = BatchProcessor(max_concurrent=5)  # Resource limits
scheduled_job = ScheduledJob(run_at=future_time)    # Future scheduling  
job_queue = JobQueue()                              # True queuing
job_queue.add_job(my_job)                          # Queue for later
job_queue.process_next_batch()                     # Controlled execution
```

## Detailed Use Cases

### Use Case 1: Admin-Driven Workflow Queue

**Scenario:** Admin creates multiple workflow tasks through Django admin interface. Tasks should be queued and executed by background process with resource limits.

**Current Problem:**
```python
# Admin creates job - it launches immediately
job = ContainerJob.objects.create(command="...", status="pending")
# No way to control when/how it launches
# No resource limits
# Potential system overload
```

**Desired Behavior:**
```python
# Admin queues job for later execution
job = ContainerJob.objects.create(command="...", queued_at=timezone.now())
# Background processor launches when resources available
# Clear separation between "queued" and "running"
```

### Use Case 2: Batch Processing

**Scenario:** Process 1000 documents through analysis pipeline, but only run 10 containers simultaneously due to memory constraints.

**Current Problem:**
- No way to queue all 1000 jobs safely
- Risk of memory exhaustion if all launch at once
- No built-in rate limiting or resource awareness

**Desired Behavior:**
```python
# Queue all 1000 jobs
for doc in documents:
    job = ContainerJob.objects.create(
        command=f"analyze_document {doc.path}",
        queued_at=timezone.now()
    )

# Process in controlled batches
queue_manager.launch_next_batch(max_concurrent=10)
```

### Use Case 3: Scheduled Job Execution

**Scenario:** Schedule data processing jobs to run during off-peak hours (e.g., 2 AM daily).

**Current Problem:**
- No native scheduling support
- Would need external cron + immediate job launching
- No visibility into scheduled jobs in Django admin

**Desired Behavior:**
```python
# Schedule job for future execution
job = ContainerJob.objects.create(
    command="daily_report_generation",
    queued_at=timezone.now(),
    scheduled_for=timezone.now().replace(hour=2, minute=0, second=0)
)
```

### Use Case 4: Resource-Aware Processing

**Scenario:** Launch jobs based on available system memory and CPU, preventing resource exhaustion.

**Current Problem:**
- No built-in resource management
- Jobs launch regardless of system load
- Potential for resource contention and failures

**Desired Behavior:**
```python
# Queue processor checks resources before launching
resource_manager = ResourceManager(max_memory_gb=16, max_concurrent=5)
ready_jobs = ContainerJob.objects.filter(
    queued_at__isnull=False,
    launched_at__isnull=True
)
for job in ready_jobs:
    if resource_manager.can_launch(job):
        queue_manager.launch_job(job)
```

### Use Case 5: Multi-Worker Job Processing

**Scenario:** Multiple worker processes sharing the same job queue, with leader election and job distribution.

**Current Problem:**
- Race conditions in job assignment
- No built-in support for distributed processing
- Difficult to implement fault tolerance

**Desired Behavior:**
```python
# Multiple workers can safely process same queue
python manage.py process_container_jobs --queue-mode --worker-id=worker-1
python manage.py process_container_jobs --queue-mode --worker-id=worker-2
```

### Use Case 6: Retry Logic for Launch Failures

**Scenario:** Docker daemon temporarily unavailable - jobs should retry launch without affecting execution status.

**Current Problem:**
```python
# Launch failure pollutes execution status
try:
    launch_job(job)
except DockerConnectionError:
    job.status = 'failed'  # But it never actually ran!
```

**Desired Behavior:**
```python
# Launch failure doesn't affect execution tracking
try:
    launch_job(job)
    job.launched_at = timezone.now()
except DockerConnectionError:
    job.retry_count += 1
    if job.retry_count >= job.max_retries:
        job.queued_at = None  # Remove from queue
        job.launch_failed = True  # Different from execution failure
```

## Proposed Solution Architecture

### Database Schema Enhancement

Add queue state fields to existing `ContainerJob` model:

```python
class ContainerJob(models.Model):
    # All existing fields remain unchanged for backward compatibility
    
    # NEW: Queue State Fields
    queued_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="When job was added to queue for execution"
    )
    
    scheduled_for = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="When job should be launched (for scheduled execution)"
    )
    
    launched_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="When job container was actually launched"
    )
    
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of launch attempts made"
    )
    
    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum launch attempts before giving up"
    )
    
    # NEW: Queue State Properties
    @property
    def is_queued(self):
        """Job is queued for execution but not yet launched"""
        return self.queued_at is not None and self.launched_at is None
    
    @property
    def is_ready_to_launch(self):
        """Job is ready to launch (queued and scheduled time has passed)"""
        if not self.is_queued:
            return False
        if self.scheduled_for and self.scheduled_for > timezone.now():
            return False
        if self.retry_count >= self.max_retries:
            return False
        return True
    
    @property
    def queue_status(self):
        """Human-readable queue status"""
        if not self.queued_at:
            return 'not_queued'
        elif not self.launched_at:
            if self.scheduled_for and self.scheduled_for > timezone.now():
                return 'scheduled'
            elif self.retry_count >= self.max_retries:
                return 'launch_failed'
            else:
                return 'queued'
        else:
            return 'launched'
    
    class Meta:
        # Add composite indexes for efficient queue queries
        indexes = [
            models.Index(fields=['queued_at', 'launched_at']),
            models.Index(fields=['scheduled_for', 'queued_at']),
            models.Index(fields=['queued_at', 'retry_count']),
        ]
```

### Queue Management API

Provide high-level API for queue operations:

```python
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class JobQueueManager:
    """High-level API for job queue management"""
    
    def queue_job(self, job, schedule_for=None):
        """
        Add job to queue for execution.
        
        Args:
            job: ContainerJob instance
            schedule_for: datetime for scheduled execution (optional)
        """
        job.queued_at = timezone.now()
        if schedule_for:
            job.scheduled_for = schedule_for
        job.retry_count = 0
        job.save()
        logger.info(f"Queued job {job.id} for execution")
        return job
    
    def get_ready_jobs(self, limit=None):
        """
        Get jobs ready for launching.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            QuerySet of ContainerJob instances ready to launch
        """
        queryset = ContainerJob.objects.filter(
            queued_at__isnull=False,
            launched_at__isnull=True,
            retry_count__lt=models.F('max_retries')
        ).filter(
            models.Q(scheduled_for__isnull=True) | 
            models.Q(scheduled_for__lte=timezone.now())
        ).order_by('queued_at')
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def launch_job(self, job):
        """
        Launch a queued job.
        
        Args:
            job: ContainerJob instance to launch
            
        Returns:
            bool: True if launched successfully, False otherwise
        """
        from container_manager.services import job_service
        
        try:
            with transaction.atomic():
                # Refresh job to check current state
                job.refresh_from_db()
                
                # Verify job is still ready to launch
                if not job.is_ready_to_launch:
                    logger.warning(f"Job {job.id} no longer ready to launch")
                    return False
                
                # Attempt to launch
                result = job_service.launch_job(job)
                
                if result.success:
                    job.launched_at = timezone.now()
                    job.save()
                    logger.info(f"Successfully launched job {job.id}")
                    return True
                else:
                    # Launch failed - increment retry count
                    job.retry_count += 1
                    job.save()
                    logger.warning(f"Failed to launch job {job.id} (attempt {job.retry_count}): {result.error}")
                    return False
                    
        except Exception as e:
            # Handle unexpected errors
            job.retry_count += 1
            job.save()
            logger.error(f"Error launching job {job.id}: {e}")
            return False
    
    def launch_next_batch(self, max_concurrent=5, max_memory_gb=None):
        """
        Launch up to max_concurrent ready jobs.
        
        Args:
            max_concurrent: Maximum number of jobs to launch
            max_memory_gb: Maximum memory usage limit (optional)
            
        Returns:
            int: Number of jobs successfully launched
        """
        # Check current resource usage
        running_jobs = ContainerJob.objects.filter(
            launched_at__isnull=False,
            status='running'
        )
        
        current_running = running_jobs.count()
        if current_running >= max_concurrent:
            logger.debug(f"Already at max concurrent jobs ({current_running}/{max_concurrent})")
            return 0
        
        # Calculate available slots
        available_slots = max_concurrent - current_running
        
        # Get ready jobs
        ready_jobs = self.get_ready_jobs(limit=available_slots)
        
        # Launch jobs
        launched_count = 0
        for job in ready_jobs:
            if self.launch_job(job):
                launched_count += 1
        
        logger.info(f"Launched {launched_count} jobs from queue")
        return launched_count
    
    def process_queue(self, max_concurrent=5, poll_interval=10):
        """
        Continuously process job queue.
        
        Args:
            max_concurrent: Maximum concurrent jobs
            poll_interval: Seconds between queue checks
        """
        import time
        import signal
        
        logger.info(f"Starting queue processor (max_concurrent={max_concurrent})")
        
        # Graceful shutdown handling
        shutdown = False
        def signal_handler(sig, frame):
            nonlocal shutdown
            logger.info("Received shutdown signal")
            shutdown = True
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        while not shutdown:
            try:
                # Launch ready jobs
                launched = self.launch_next_batch(max_concurrent=max_concurrent)
                
                # Log activity
                if launched > 0:
                    logger.info(f"Processed queue: launched {launched} jobs")
                
                # Wait before next iteration
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.exception(f"Error in queue processing: {e}")
                time.sleep(poll_interval)  # Continue processing after error
        
        logger.info("Queue processor shutting down")

# Module-level instance for easy importing
queue_manager = JobQueueManager()
```

### Management Command

Provide command-line interface for queue processing:

```python
# management/commands/process_container_jobs.py
from django.core.management.base import BaseCommand
from container_manager.queue import queue_manager

class Command(BaseCommand):
    help = 'Process container job queue'

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue-mode',
            action='store_true',
            help='Run in queue processing mode (launches queued jobs)'
        )
        parser.add_argument(
            '--max-concurrent',
            type=int,
            default=5,
            help='Maximum concurrent jobs when in queue mode (default: 5)'
        )
        parser.add_argument(
            '--poll-interval',
            type=int,
            default=10,
            help='Polling interval in seconds (default: 10)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process queue once and exit (don\'t run continuously)'
        )

    def handle(self, *args, **options):
        if options['queue_mode']:
            if options['once']:
                # Single queue processing run
                launched = queue_manager.launch_next_batch(
                    max_concurrent=options['max_concurrent']
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Launched {launched} jobs from queue')
                )
            else:
                # Continuous queue processing
                queue_manager.process_queue(
                    max_concurrent=options['max_concurrent'],
                    poll_interval=options['poll_interval']
                )
        else:
            # Original behavior - process existing running jobs
            self.stdout.write('Use --queue-mode to process job queue')
```

### Django Admin Integration

Enhance admin interface with queue management:

```python
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from container_manager.models import ContainerJob
from container_manager.queue import queue_manager

@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'name', 'queue_status_display', 'execution_status', 
        'queued_at', 'launched_at', 'retry_count'
    ]
    list_filter = ['status', 'queued_at', 'launched_at', 'retry_count']
    search_fields = ['name', 'command']
    readonly_fields = ['launched_at', 'retry_count']
    
    def queue_status_display(self, obj):
        """Display queue status with color coding"""
        status = obj.queue_status
        colors = {
            'not_queued': 'gray',
            'queued': 'blue',
            'scheduled': 'orange', 
            'launched': 'green',
            'launch_failed': 'red'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(status, 'black'),
            status.replace('_', ' ').title()
        )
    queue_status_display.short_description = 'Queue Status'
    
    def execution_status(self, obj):
        """Display container execution status"""
        return obj.status or 'Not Started'
    execution_status.short_description = 'Execution Status'
    
    actions = ['queue_for_execution', 'schedule_for_later', 'remove_from_queue']
    
    def queue_for_execution(self, request, queryset):
        """Admin action to queue jobs for execution"""
        count = 0
        for job in queryset:
            if not job.is_queued:
                queue_manager.queue_job(job)
                count += 1
        self.message_user(request, f'Queued {count} jobs for execution')
    queue_for_execution.short_description = 'Queue selected jobs for execution'
    
    def schedule_for_later(self, request, queryset):
        """Admin action to schedule jobs (would show form for datetime)"""
        # Implementation would show form to collect schedule datetime
        pass
    
    def remove_from_queue(self, request, queryset):
        """Admin action to remove jobs from queue"""
        count = 0
        for job in queryset.filter(queued_at__isnull=False, launched_at__isnull=True):
            job.queued_at = None
            job.scheduled_for = None
            job.retry_count = 0
            job.save()
            count += 1
        self.message_user(request, f'Removed {count} jobs from queue')
    remove_from_queue.short_description = 'Remove selected jobs from queue'
```

## Benefits Analysis

### For Library Users

#### 1. **Enables Advanced Workflow Patterns**
- Batch processing with resource limits
- Scheduled job execution
- Multi-worker distributed processing
- Proper retry logic for transient failures

#### 2. **Improved Resource Management**
- Control concurrent job execution
- Prevent system resource exhaustion
- Memory and CPU aware scheduling
- Graceful handling of capacity limits

#### 3. **Better Operational Visibility**
- Clear separation of queue state vs execution state
- Enhanced Django admin interface for queue management
- Comprehensive logging and monitoring hooks
- Better debugging of job lifecycle issues

#### 4. **Production-Ready Features**
- Atomic job state transitions
- Race condition prevention in multi-worker scenarios
- Graceful error handling and recovery
- Built-in retry logic with exponential backoff

### For Library Maintainers

#### 1. **Positions Library as Enterprise-Ready**
- Supports common enterprise workflow patterns
- Provides foundation for advanced features
- Demonstrates thoughtful architectural design
- Attracts larger user base and contributions

#### 2. **Maintains Backward Compatibility**
- All existing code continues to work unchanged
- New features are opt-in only
- Gradual migration path for existing users
- No breaking changes to public APIs

#### 3. **Extensible Architecture**
- Foundation for future enhancements (priority queues, job dependencies, etc.)
- Pluggable resource management strategies
- Hooks for custom scheduling algorithms
- Support for different queue backends

### For Django Ecosystem

#### 1. **Standard Patterns for Container Management**
- Establishes best practices for Django + containers
- Provides reference implementation for queue management
- Enables ecosystem of compatible tools and extensions
- Reduces fragmentation in container management approaches

#### 2. **Fills Gap in Django Toolchain**
- Complements existing tools (Celery, Django-RQ) with container-specific features
- Provides Docker-native alternative to traditional task queues
- Enables containerized microservices patterns in Django
- Supports hybrid architectures (some tasks in containers, some in processes)

## Implementation Considerations

### Database Performance

#### Indexing Strategy
```sql
-- Efficient queue queries
CREATE INDEX idx_container_job_queue_ready 
ON container_manager_containerjob (queued_at, launched_at) 
WHERE queued_at IS NOT NULL AND launched_at IS NULL;

-- Scheduled job queries  
CREATE INDEX idx_container_job_scheduled 
ON container_manager_containerjob (scheduled_for, queued_at)
WHERE scheduled_for IS NOT NULL;

-- Retry count queries
CREATE INDEX idx_container_job_retries
ON container_manager_containerjob (queued_at, retry_count)
WHERE queued_at IS NOT NULL;
```

#### Query Optimization
- Use `select_for_update()` to prevent race conditions in job assignment
- Implement efficient pagination for large job queues
- Consider partitioning strategies for high-volume deployments
- Monitor query performance and add indexes as needed

### Concurrency Safety

#### Atomic Operations
```python
with transaction.atomic():
    # Lock job for update to prevent race conditions
    job = ContainerJob.objects.select_for_update().get(id=job_id)
    
    if job.is_ready_to_launch:
        # Launch job and update state atomically
        result = job_service.launch_job(job)
        if result.success:
            job.launched_at = timezone.now()
            job.save()
```

#### Multi-Worker Coordination
- Use database-level locking for job assignment
- Implement leader election for queue processing coordination
- Handle worker failures gracefully
- Provide hooks for custom distributed locking strategies

### Error Handling Classification

#### Transient vs Permanent Errors
```python
class ErrorClassifier:
    TRANSIENT_ERRORS = [
        'ConnectionError',           # Docker daemon unavailable
        'ResourceTemporaryUnavailable',  # System resource limits
        'TimeoutError',            # Network timeouts
    ]
    
    PERMANENT_ERRORS = [
        'ImageNotFound',           # Docker image doesn't exist
        'InvalidConfiguration',    # Job configuration errors
        'PermissionDenied',       # Authorization failures
    ]
    
    def should_retry(self, exception):
        """Determine if job should be retried based on error type"""
        return exception.__class__.__name__ in self.TRANSIENT_ERRORS
```

#### Retry Strategies
- Exponential backoff for transient failures
- Immediate failure for permanent errors
- Configurable retry limits per job type
- Dead letter queue for permanently failed jobs

### Resource Management Hooks

#### Memory and CPU Awareness
```python
class ResourceManager:
    def can_launch_job(self, job):
        """Check if system has resources to launch job"""
        current_usage = self.get_current_resource_usage()
        estimated_usage = job.estimated_memory_mb or 512  # Default 512MB
        
        return (current_usage['memory_mb'] + estimated_usage) < self.max_memory_mb
    
    def get_current_resource_usage(self):
        """Get current system resource usage"""
        # Implementation would check Docker stats, system metrics, etc.
        pass
```

#### Pluggable Resource Strategies
- Interface for custom resource management strategies  
- Built-in strategies for memory, CPU, storage limits
- Integration with monitoring systems (Prometheus, etc.)
- Support for cloud platform resource APIs

## Migration Strategy

### Phase 1: Database Schema (Non-Breaking)

```python
# Migration 0002_add_queue_fields.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('container_manager', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='containerjob',
            name='queued_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='scheduled_for',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='launched_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='retry_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='max_retries',
            field=models.IntegerField(default=3),
        ),
        # Add composite indexes for efficient queries
        migrations.RunSQL(
            "CREATE INDEX idx_container_job_queue_ready ON container_manager_containerjob (queued_at, launched_at) WHERE queued_at IS NOT NULL AND launched_at IS NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_container_job_queue_ready;"
        ),
    ]
```

### Phase 2: API and Command Integration

Add queue management API and commands while maintaining backward compatibility:

```python
# Existing immediate launch still works
job = ContainerJob.objects.create(command="...")
job_service.launch_job(job)  # Launches immediately as before

# New queue-based workflow
job = ContainerJob.objects.create(command="...")
queue_manager.queue_job(job)  # Queues for later execution
```

### Phase 3: Documentation and Examples

- Update library documentation with queue management examples
- Provide migration guide for existing users
- Create example projects demonstrating queue patterns
- Add performance tuning recommendations

### Backward Compatibility Guarantees

#### Existing Code Continues to Work
```python
# All existing patterns remain functional
job = ContainerJob.objects.create(...)
result = job_service.launch_job(job)    # Still works

# Existing management commands unchanged
python manage.py process_container_jobs  # Original behavior preserved
```

#### Opt-In Queue Features
```python
# Queue features are explicitly opt-in
if job.queued_at:
    # Job is using new queue system
    pass
else:
    # Job is using traditional immediate launch
    pass
```

#### Default Behaviors
- New fields default to `NULL` (no queue behavior)
- Existing jobs are unaffected by new fields
- Management commands maintain original behavior unless `--queue-mode` specified
- Admin interface shows queue fields only when relevant

## Reference Implementation

### Django Container Manager Demo Project

Our demo project serves as a reference implementation showcasing queue management patterns:

**Repository:** `django-container-manager-demo`  
**Use Cases Demonstrated:**
- Admin-driven workflow queuing
- Batch processing with resource limits
- Scheduled job execution
- Multi-worker coordination
- Error handling and retry logic

#### Example: Admin Workflow Queue

```python
# workflows/admin.py
@admin.action(description='Queue crawler jobs')
def queue_crawler_jobs(modeladmin, request, queryset):
    """Queue multiple URLs for crawling"""
    for url_obj in queryset:
        job = ContainerJob.objects.create(
            name=f"crawler-{url_obj.domain}",
            command=f"python manage.py crawl_webpage {url_obj.url}",
            docker_image="django-app:latest",
            memory_limit=512,
        )
        queue_manager.queue_job(job)
    
    message = f'Queued {len(queryset)} crawler jobs'
    modeladmin.message_user(request, message)
```

#### Example: Background Queue Processor

```python
# Start queue processor
python manage.py process_container_jobs --queue-mode --max-concurrent=5

# Queue jobs through admin interface
# Jobs are automatically launched when resources available
# Results harvested and stored in database
```

#### Example: Scheduled Batch Processing

```python
# workflows/management/commands/schedule_daily_reports.py
def handle(self, *args, **options):
    """Schedule daily report generation jobs"""
    tomorrow_2am = timezone.now().replace(
        hour=2, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    
    for report_type in ['sales', 'inventory', 'analytics']:
        job = ContainerJob.objects.create(
            name=f"daily-{report_type}-report",
            command=f"python manage.py generate_report {report_type}",
            docker_image="report-generator:latest",
        )
        queue_manager.queue_job(job, schedule_for=tomorrow_2am)
```

## Conclusion

This RFC proposes a natural evolution of the `django-container-manager` library that addresses fundamental limitations in the current architecture. By separating queue state from execution state, we enable a wide range of workflow patterns that are currently difficult or impossible to implement.

The proposed changes are:
- **Backward compatible** - all existing code continues to work
- **Opt-in** - new features don't affect existing usage
- **Well-architected** - proper separation of concerns and extensible design
- **Production-ready** - handles concurrency, errors, and resource management properly

### Implementation Priority

1. **High Priority**: Database schema and basic queue management API
2. **Medium Priority**: Management command and admin integration  
3. **Lower Priority**: Advanced features (resource management, scheduling)

### Success Metrics

- Existing library users can upgrade without code changes
- New queue features enable previously impossible workflow patterns
- Library adoption increases due to enterprise-ready capabilities
- Community contributions grow around queue management extensions

We believe this enhancement will significantly increase the library's value proposition while maintaining the simplicity and reliability that make it valuable today.

---

**Request for Feedback**

We welcome feedback on:
- API design and usability
- Implementation approach and priorities
- Migration strategy and backward compatibility
- Additional use cases or requirements
- Performance considerations and optimizations

**Contact:** [Demo project maintainer contact information]