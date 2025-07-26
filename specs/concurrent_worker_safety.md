# Concurrent Worker Safety Specification

## Problem Statement

The current `process_container_jobs` management command has a race condition when multiple worker processes are running simultaneously. Multiple workers can pick up the same pending job, leading to:

- Duplicate job execution attempts
- Container creation conflicts
- Resource waste
- Inconsistent job status
- Potential Docker daemon errors

## Current Implementation Risk

**Unsafe Flow:**
1. Worker A: `SELECT * FROM jobs WHERE status='pending'` → Gets job 123
2. Worker B: `SELECT * FROM jobs WHERE status='pending'` → Gets same job 123  
3. Both workers attempt to process job 123 simultaneously
4. Race condition occurs

**Impact:**
- System is NOT safe for multiple workers
- Production deployments must use single worker process
- Limits scalability and throughput

## Proposed Solutions

### Option 1: Database Locking (Recommended)

Use `select_for_update()` to implement atomic job claiming:

```python
# Atomic job claiming
with transaction.atomic():
    job = ContainerJob.objects.select_for_update().filter(
        status='pending',
        docker_host__is_active=True
    ).order_by('created_at').first()
    
    if job:
        job.status = 'claimed'
        job.claimed_at = timezone.now()
        job.save()

# Now safe to process without race condition
if job:
    docker_service.execute_job(job)
```

**Benefits:**
- Database-level atomicity
- Works with any number of workers
- Handles worker failures via timeout
- Minimal code changes required

### Option 2: Compare-and-Swap Pattern

Atomic status transitions without row locking:

```python
# Attempt to claim job atomically
jobs = ContainerJob.objects.filter(status='pending')[:10]
for job in jobs:
    updated = ContainerJob.objects.filter(
        id=job.id,
        status='pending'  # Only update if still pending
    ).update(status='running')
    
    if updated == 1:
        # Successfully claimed job
        docker_service.execute_job(job)
        break
```

**Benefits:**
- No database locking
- High concurrency
- Simple implementation

**Drawbacks:**
- Potential busy-waiting
- Less efficient for high contention

### Option 3: External Queue System

Replace database polling with dedicated queue:

- **Redis/SQS:** External message queue
- **Celery/RQ:** Task queue frameworks
- **Database Queue:** Dedicated queue table

**Benefits:**
- Natural deduplication
- Better scalability
- Industry standard pattern

**Drawbacks:**
- Additional infrastructure
- More complex deployment
- Migration effort

## Implementation Plan

### Phase 1: Add Job Claiming (Recommended)

1. **Add new job status:**
   ```python
   STATUS_CHOICES = [
       ('pending', 'Pending'),
       ('claimed', 'Claimed'),      # NEW
       ('running', 'Running'),
       ('completed', 'Completed'),
       ('failed', 'Failed'),
       ('timeout', 'Timeout'),
       ('cancelled', 'Cancelled'),
   ]
   ```

2. **Add claimed timestamp:**
   ```python
   claimed_at = models.DateTimeField(null=True, blank=True)
   claimed_by = models.CharField(max_length=100, blank=True)  # Worker ID
   ```

3. **Implement atomic claiming:**
   - Use `select_for_update()` in `process_pending_jobs()`
   - Add claimed job timeout mechanism
   - Update status transitions

4. **Add cleanup for stale claims:**
   ```python
   # Reset jobs claimed > 10 minutes ago back to pending
   stale_cutoff = timezone.now() - timedelta(minutes=10)
   ContainerJob.objects.filter(
       status='claimed',
       claimed_at__lt=stale_cutoff
   ).update(status='pending', claimed_at=None)
   ```

### Phase 2: Enhanced Monitoring

1. **Worker identification:**
   - Add worker PID/hostname to claimed jobs
   - Track worker activity in logs

2. **Metrics:**
   - Jobs claimed per worker
   - Claim timeout events
   - Worker collision attempts

3. **Admin improvements:**
   - Show claimed jobs in admin
   - Display worker information
   - Manual claim release

## Configuration Options

```python
# settings.py
CONTAINER_MANAGER = {
    'WORKER_CLAIM_TIMEOUT_MINUTES': 10,    # Reset stale claims
    'ENABLE_WORKER_SAFETY': True,          # Enable/disable locking
    'WORKER_ID_PREFIX': 'worker',          # Worker identification
}
```

## Migration Strategy

1. **Database migration:** Add new fields
2. **Backward compatibility:** Old workers continue working
3. **Gradual rollout:** Enable locking per deployment
4. **Monitoring:** Track claim timeouts and collisions

## Testing Requirements

1. **Unit tests:** Job claiming logic
2. **Integration tests:** Multiple worker simulation
3. **Load tests:** High concurrency scenarios
4. **Failure tests:** Worker crash recovery

## Priority and Timeline

**Priority:** Medium - High (for production multi-worker deployments)

**Effort:** 1-2 days implementation + testing

**Dependencies:** None - can implement incrementally

**Rollback plan:** Disable locking via feature flag

## Notes

- Current single-worker deployments are safe
- This is a requirement for scaling beyond one worker
- Database locking is the most pragmatic solution
- Consider external queues for very high throughput needs

## Related Issues

- Monitor for Django connection pool exhaustion under high concurrency
- Consider database-specific optimizations (PostgreSQL advisory locks)
- Document deployment patterns for multiple workers