# Task: Add Queue State Fields to ContainerJob Model

## Objective
Add queue management fields to the existing `ContainerJob` model to enable queue functionality while maintaining clean separation between queue state and execution state.

## Success Criteria
- [ ] Queue state fields added to ContainerJob model
- [ ] Proper field types and constraints implemented
- [ ] Model properties for queue state queries
- [ ] All tests pass after model changes

## Implementation Details

### Fields to Add

```python
# Queue State Fields
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

# Fix from Guilfoyle's review: Priority as IntegerField, not CharField
priority = models.IntegerField(
    default=50,  # Normal priority
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    help_text="Job priority (0-100, higher numbers = higher priority)"
)
```

### Model Properties to Add

```python
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
```

### Database Indexes to Add

```python
class Meta:
    # Add composite indexes for efficient queue queries
    indexes = [
        models.Index(fields=['queued_at', 'launched_at']),
        models.Index(fields=['scheduled_for', 'queued_at']),
        models.Index(fields=['queued_at', 'retry_count']),
        models.Index(fields=['priority', 'queued_at']),  # For priority queue ordering
    ]
```

## Files to Modify
- `container_manager/models.py` - Add fields and properties to ContainerJob

## Testing Requirements
- [ ] Test model field validation
- [ ] Test property methods return correct values
- [ ] Test database constraints work properly
- [ ] Test model creation with new fields

## Dependencies
None - this is the foundation task.

## Priority Constants
Add these constants for common priority values:

```python
# Priority constants
PRIORITY_HIGH = 80
PRIORITY_NORMAL = 50
PRIORITY_LOW = 20
```

## Notes
- All new fields default to NULL/empty to maintain compatibility
- Priority field replaces any existing CharField priority with proper integer scale
- Properties provide clean interface for queue state queries
- Indexes optimize common queue operation queries