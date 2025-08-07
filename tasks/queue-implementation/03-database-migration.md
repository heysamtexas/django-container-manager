# Task: Create Database Migration for Queue Fields

## Objective
Create Django migration to add queue management fields to the ContainerJob model with proper database indexes.

## Success Criteria
- [ ] Migration created with all new fields
- [ ] Database indexes created for optimal query performance
- [ ] Migration runs successfully on clean database
- [ ] All existing data preserved (if any)
- [ ] Rollback migration works correctly

## Implementation Details

### Migration Operations

```python
# migrations/XXXX_add_queue_fields.py
from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator

class Migration(migrations.Migration):
    dependencies = [
        ('container_manager', 'XXXX_previous_migration'),
    ]

    operations = [
        # Add queue state fields
        migrations.AddField(
            model_name='containerjob',
            name='queued_at',
            field=models.DateTimeField(
                blank=True, 
                null=True, 
                help_text='When job was added to queue for execution'
            ),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='scheduled_for',
            field=models.DateTimeField(
                blank=True, 
                null=True, 
                help_text='When job should be launched (for scheduled execution)'
            ),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='launched_at',
            field=models.DateTimeField(
                blank=True, 
                null=True, 
                help_text='When job container was actually launched'
            ),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='retry_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of launch attempts made'
            ),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='max_retries',
            field=models.IntegerField(
                default=3,
                help_text='Maximum launch attempts before giving up'
            ),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='priority',
            field=models.IntegerField(
                default=50,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
                help_text='Job priority (0-100, higher numbers = higher priority)'
            ),
        ),
        
        # Add database indexes for efficient querying
        migrations.RunSQL(
            "CREATE INDEX idx_containerjob_queue_ready ON container_manager_containerjob (queued_at, launched_at) WHERE queued_at IS NOT NULL AND launched_at IS NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_containerjob_queue_ready;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_containerjob_scheduled ON container_manager_containerjob (scheduled_for, queued_at) WHERE scheduled_for IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_containerjob_scheduled;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_containerjob_priority_queue ON container_manager_containerjob (priority DESC, queued_at) WHERE queued_at IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_containerjob_priority_queue;"
        ),
        
        # Add individual field indexes
        migrations.AddIndex(
            model_name='containerjob',
            index=models.Index(fields=['queued_at'], name='idx_containerjob_queued_at'),
        ),
        migrations.AddIndex(
            model_name='containerjob',
            index=models.Index(fields=['launched_at'], name='idx_containerjob_launched_at'),
        ),
        migrations.AddIndex(
            model_name='containerjob',
            index=models.Index(fields=['scheduled_for'], name='idx_containerjob_scheduled_for'),
        ),
        migrations.AddIndex(
            model_name='containerjob',
            index=models.Index(fields=['priority'], name='idx_containerjob_priority'),
        ),
        
        # Composite indexes for common queries
        migrations.AddIndex(
            model_name='containerjob',
            index=models.Index(fields=['queued_at', 'retry_count'], name='idx_containerjob_queue_retry'),
        ),
        migrations.AddIndex(
            model_name='containerjob',
            index=models.Index(fields=['status', 'queued_at'], name='idx_containerjob_status_queue'),
        ),
    ]
```

### Database Constraints (Optional Enhancement)

```python
# Additional operations for database-level validation
migrations.RunSQL(
    """
    ALTER TABLE container_manager_containerjob 
    ADD CONSTRAINT check_priority_range 
    CHECK (priority >= 0 AND priority <= 100);
    """,
    reverse_sql="ALTER TABLE container_manager_containerjob DROP CONSTRAINT IF EXISTS check_priority_range;"
),

migrations.RunSQL(
    """
    ALTER TABLE container_manager_containerjob 
    ADD CONSTRAINT check_retry_count_positive 
    CHECK (retry_count >= 0);
    """,
    reverse_sql="ALTER TABLE container_manager_containerjob DROP CONSTRAINT IF EXISTS check_retry_count_positive;"
),

migrations.RunSQL(
    """
    ALTER TABLE container_manager_containerjob 
    ADD CONSTRAINT check_max_retries_positive 
    CHECK (max_retries >= 0);
    """,
    reverse_sql="ALTER TABLE container_manager_containerjob DROP CONSTRAINT IF EXISTS check_max_retries_positive;"
),
```

## Files to Create
- `container_manager/migrations/XXXX_add_queue_fields.py`

## Testing Requirements
- [ ] Migration runs successfully with `python manage.py migrate`
- [ ] Migration rollback works with `python manage.py migrate container_manager XXXX`
- [ ] Database indexes are created correctly
- [ ] Field constraints work as expected
- [ ] No data loss during migration

## Migration Testing Commands

```bash
# Test migration
python manage.py makemigrations container_manager
python manage.py migrate container_manager

# Test rollback
python manage.py migrate container_manager XXXX_previous_migration

# Test forward again
python manage.py migrate container_manager

# Verify indexes were created
python manage.py dbshell
\d+ container_manager_containerjob  # PostgreSQL
.schema container_manager_containerjob  # SQLite
```

## Dependencies
- Depends on: `01-queue-model-fields.md` (model changes must be made first)

## Performance Considerations

The partial indexes are designed for optimal performance:

1. **Queue Ready Jobs**: `WHERE queued_at IS NOT NULL AND launched_at IS NULL`
   - Optimizes queries for jobs ready to launch
   
2. **Scheduled Jobs**: `WHERE scheduled_for IS NOT NULL`  
   - Optimizes queries for jobs scheduled for future execution
   
3. **Priority Queue**: `priority DESC, queued_at` with `WHERE queued_at IS NOT NULL`
   - Optimizes priority-based job ordering

## Notes
- Use partial indexes to optimize specific query patterns
- All new fields default to NULL/0 for compatibility
- Database constraints add additional data integrity
- Migration is reversible for safe rollback
- Consider database-specific optimizations (PostgreSQL vs SQLite vs MySQL)