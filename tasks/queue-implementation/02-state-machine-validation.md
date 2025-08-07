# Task: Implement State Machine Validation

## Objective
Implement robust state machine validation for ContainerJob to prevent invalid status transitions and ensure data integrity.

## Success Criteria
- [ ] State machine with valid transitions defined
- [ ] `transition_to()` method for safe state changes
- [ ] Model-level validation prevents invalid transitions
- [ ] Clear error messages for invalid transitions
- [ ] All state transition tests pass

## Implementation Details

### Job Status States

```python
class Status(models.TextChoices):
    PENDING = 'pending', 'Pending'
    QUEUED = 'queued', 'Queued'  
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'
    RETRYING = 'retrying', 'Retrying'
```

### Valid Transitions Map

```python
VALID_TRANSITIONS = {
    Status.PENDING: [Status.QUEUED, Status.RUNNING, Status.CANCELLED],
    Status.QUEUED: [Status.RUNNING, Status.CANCELLED],
    Status.RUNNING: [Status.COMPLETED, Status.FAILED, Status.CANCELLED],
    Status.FAILED: [Status.RETRYING, Status.CANCELLED],
    Status.RETRYING: [Status.QUEUED, Status.CANCELLED],
    Status.COMPLETED: [],  # Terminal state
    Status.CANCELLED: [],  # Terminal state
}
```

### State Machine Methods

```python
def can_transition_to(self, new_status):
    """Check if transition to new status is valid"""
    valid_transitions = self.VALID_TRANSITIONS.get(self.status, [])
    return new_status in valid_transitions

def transition_to(self, new_status, save=True):
    """Safely transition to new status with validation"""
    if not self.can_transition_to(new_status):
        raise ValueError(
            f"Invalid transition from {self.status} to {new_status}. "
            f"Valid transitions: {self.VALID_TRANSITIONS.get(self.status, [])}"
        )
    
    old_status = self.status
    self.status = new_status
    
    # Update timestamps based on status
    if new_status == self.Status.RUNNING and not self.launched_at:
        self.launched_at = timezone.now()
    elif new_status == self.Status.COMPLETED and not self.completed_at:
        self.completed_at = timezone.now()
    
    if save:
        update_fields = ['status']
        if hasattr(self, '_update_fields'):
            update_fields.extend(self._update_fields)
        self.save(update_fields=update_fields)
        
    logger.info(f"Job {self.id}: {old_status} -> {new_status}")
    return True

def save(self, *args, **kwargs):
    """Override save to validate state transitions"""
    if self.pk:  # Existing object - check for status changes
        try:
            old_obj = ContainerJob.objects.get(pk=self.pk)
            if old_obj.status != self.status:
                # Validate transition
                if not old_obj.can_transition_to(self.status):
                    raise ValueError(
                        f"Invalid status transition: {old_obj.status} -> {self.status}"
                    )
        except ContainerJob.DoesNotExist:
            pass  # New object, no validation needed
    
    super().save(*args, **kwargs)
```

### Service Integration Helper

```python
def mark_as_queued(self, scheduled_for=None):
    """Mark job as queued with proper state transition"""
    self.transition_to(self.Status.QUEUED, save=False)
    self.queued_at = timezone.now()
    if scheduled_for:
        self.scheduled_for = scheduled_for
    self.save(update_fields=['status', 'queued_at', 'scheduled_for'])

def mark_as_running(self):
    """Mark job as running with proper state transition"""
    self.transition_to(self.Status.RUNNING, save=False)
    self.launched_at = timezone.now()
    self.save(update_fields=['status', 'launched_at'])

def mark_as_completed(self):
    """Mark job as completed with proper state transition"""
    self.transition_to(self.Status.COMPLETED, save=False)
    self.completed_at = timezone.now()
    self.save(update_fields=['status', 'completed_at'])

def mark_as_failed(self, should_retry=False):
    """Mark job as failed, optionally setting up retry"""
    if should_retry and self.retry_count < self.max_retries:
        self.transition_to(self.Status.RETRYING, save=False)
        self.retry_count += 1
        self.save(update_fields=['status', 'retry_count'])
    else:
        self.transition_to(self.Status.FAILED)
```

## Files to Modify
- `container_manager/models.py` - Add state machine validation to ContainerJob

## Testing Requirements
- [ ] Test all valid state transitions work
- [ ] Test all invalid transitions raise ValueError
- [ ] Test terminal states (completed, cancelled) cannot transition
- [ ] Test concurrent state changes don't cause race conditions
- [ ] Test save() validation prevents invalid direct status changes
- [ ] Test helper methods work correctly

## Dependencies
- Depends on: `01-queue-model-fields.md` (needs the new fields)

## Database Constraints (Optional Enhancement)

```python
# Add database-level constraints for critical validations
class Meta:
    constraints = [
        models.CheckConstraint(
            check=models.Q(
                status__in=['pending', 'queued', 'cancelled'],
                launched_at__isnull=True
            ) | models.Q(
                status__in=['running', 'completed', 'failed'],
                launched_at__isnull=False
            ),
            name='launched_at_matches_status'
        ),
        models.CheckConstraint(
            check=models.Q(status='completed', completed_at__isnull=False) |
                  models.Q(status__ne='completed'),
            name='completed_jobs_have_timestamp'
        )
    ]
```

## Notes
- State machine prevents data corruption from invalid transitions
- Helper methods provide clean API for common operations
- Logging provides visibility into state changes
- Database constraints add additional safety layer
- Clear error messages help with debugging