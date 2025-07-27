# P0 Refactor: Clean Database Schema Rebuild

## Priority: P0 (Blocking)
**Impact:** CRITICAL - Fresh start with clean architecture, no legacy baggage
**Effort:** 2-3 hours
**Risk:** LOW - No production data to preserve, complete freedom to rebuild

## Problem Statement

After the previous 3 refactors, we'll have a much cleaner codebase but the database schema will still carry legacy:

```python
# LEGACY MIGRATION HISTORY: Accumulated complexity over 15 migrations
0001_initial.py                    # Original design
0002_alter_containerjob_container_id.py
0003_dockerhost_auto_pull_images.py
0004_containerexecution_clean_output_and_more.py
0005_add_multi_executor_support.py  # Added executor complexity
0006_add_routing_models.py
0007_add_cost_tracking.py
0008_add_performance_monitoring.py
0009_create_migration_models.py
0010_simplify_models_add_weight.py
0011_add_environment_variables_text.py
0012_remove_environment_variable_model.py
0013_add_environment_variable_template.py
0014_add_missing_test_fields.py
0015_add_last_health_check_field.py
0016_unify_execution_identifiers.py     # Our refactor
0017_rename_dockerhost_executorhost.py  # Our refactor
```

**Legacy Issues:**
1. **Migration cruft**: 17+ migrations with historical complexity
2. **Field artifacts**: Remnants of old design decisions
3. **Index confusion**: Indexes created/modified across many migrations
4. **Constraint inconsistency**: Rules added piecemeal over time
5. **Performance questions**: Non-optimal indexes from incremental changes

## Solution: Nuclear Option - Fresh Schema

Since we have **no production data to preserve**, we can:
1. **Delete all migrations** 
2. **Rebuild from scratch** with clean, optimal schema
3. **Apply all architectural improvements** from day 1
4. **Remove all legacy artifacts** and cruft

### Benefits of Nuclear Approach
- **Clean slate**: Optimal schema design from first principles
- **Performance**: Properly designed indexes and constraints
- **Simplicity**: Single migration instead of 17+ complex ones
- **Documentation**: Clear schema that reflects actual architecture

## Implementation Plan

### Step 1: Backup Current State (15 minutes)
```bash
# Save current working directory state
git add -A
git commit -m "Pre-database-rebuild snapshot"

# Export any test data we want to recreate
python manage.py dumpdata container_manager --indent=2 > backup_data.json

# Document current schema for reference
python manage.py sqlmigrate container_manager 0015 > old_schema.sql
```

### Step 2: Nuclear Migration Reset (30 minutes)

#### Delete All Migration Files
```bash
# Remove all existing migrations
rm container_manager/migrations/0*.py

# Keep only __init__.py
ls container_manager/migrations/
# Should show only: __init__.py
```

#### Drop and Recreate Database
```bash
# For SQLite (development)
rm db.sqlite3

# For PostgreSQL (if using)
# dropdb django_docker_dev && createdb django_docker_dev
```

### Step 3: Create Clean Initial Migration (1 hour)
**File:** `container_manager/migrations/0001_initial.py`

```python
# Clean initial migration with all improvements baked in
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial = True
    
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Clean ExecutorHost (not DockerHost!)
        migrations.CreateModel(
            name='ExecutorHost',
            fields=[
                ('id', models.BigAutoField(primary_key=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('executor_type', models.CharField(
                    max_length=50, 
                    default='docker',
                    choices=[
                        ('docker', 'Docker'),
                        ('cloudrun', 'Cloud Run'), 
                        ('mock', 'Mock'),
                    ],
                    db_index=True  # Optimal indexing from day 1
                )),
                ('connection_config', models.JSONField(
                    default=dict,
                    help_text="Executor-specific connection configuration"
                )),
                ('is_active', models.BooleanField(default=True, db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_health_check', models.DateTimeField(null=True, blank=True)),
            ],
            options={
                'verbose_name': 'Executor Host',
                'verbose_name_plural': 'Executor Hosts',
                'ordering': ['name'],
            },
        ),
        
        # Environment Variable Templates
        migrations.CreateModel(
            name='EnvironmentVariableTemplate',
            fields=[
                ('id', models.BigAutoField(primary_key=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('environment_variables_text', models.TextField(
                    blank=True,
                    help_text="Environment variables, one per line in KEY=value format"
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    'auth.User', 
                    on_delete=models.SET_NULL, 
                    null=True
                )),
            ],
            options={
                'verbose_name': 'Environment Variable Template',
                'verbose_name_plural': 'Environment Variable Templates', 
                'ordering': ['name'],
            },
        ),
        
        # Clean ContainerTemplate
        migrations.CreateModel(
            name='ContainerTemplate',
            fields=[
                ('id', models.BigAutoField(primary_key=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('docker_image', models.CharField(max_length=500)),
                ('command', models.TextField(blank=True)),
                ('working_dir', models.CharField(max_length=500, blank=True)),
                ('environment_variables_text', models.TextField(blank=True)),
                ('cpu_limit', models.DecimalField(
                    max_digits=6, 
                    decimal_places=2, 
                    null=True, 
                    blank=True
                )),
                ('memory_limit_mb', models.IntegerField(null=True, blank=True)),
                ('timeout_seconds', models.IntegerField(default=3600)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    'auth.User', 
                    on_delete=models.SET_NULL, 
                    null=True
                )),
                ('environment_template', models.ForeignKey(
                    'EnvironmentVariableTemplate',
                    on_delete=models.SET_NULL,
                    null=True,
                    blank=True
                )),
            ],
            options={
                'verbose_name': 'Container Template',
                'verbose_name_plural': 'Container Templates',
                'ordering': ['name'],
            },
        ),
        
        # Clean ContainerJob with unified execution_id
        migrations.CreateModel(
            name='ContainerJob',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, 
                    default=uuid.uuid4, 
                    editable=False
                )),
                ('name', models.CharField(max_length=200, blank=True)),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'Pending'),
                        ('running', 'Running'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                        ('timeout', 'Timeout'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='pending',
                    db_index=True  # Optimal indexing
                )),
                
                # CLEAN: Single unified execution identifier
                ('execution_id', models.CharField(
                    max_length=255, 
                    blank=True,
                    help_text="Unified execution identifier for all executor types"
                )),
                
                ('exit_code', models.IntegerField(null=True, blank=True)),
                ('override_command', models.TextField(blank=True)),
                ('override_environment', models.JSONField(
                    default=dict,
                    help_text="Override environment variables"
                )),
                
                # Timestamps
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('started_at', models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                
                # Foreign Keys
                ('template', models.ForeignKey(
                    'ContainerTemplate',
                    related_name='jobs',
                    on_delete=models.CASCADE
                )),
                ('executor_host', models.ForeignKey(
                    'ExecutorHost',
                    related_name='jobs', 
                    on_delete=models.CASCADE
                )),
                ('created_by', models.ForeignKey(
                    'auth.User',
                    on_delete=models.SET_NULL,
                    null=True
                )),
            ],
            options={
                'verbose_name': 'Container Job',
                'verbose_name_plural': 'Container Jobs',
                'ordering': ['-created_at'],
            },
        ),
        
        # ContainerExecution
        migrations.CreateModel(
            name='ContainerExecution',
            fields=[
                ('id', models.BigAutoField(primary_key=True)),
                ('stdout_log', models.TextField(blank=True)),
                ('stderr_log', models.TextField(blank=True)),
                ('docker_log', models.TextField(blank=True)),
                ('clean_output', models.TextField(blank=True)),
                ('parsed_output', models.JSONField(null=True, blank=True)),
                ('max_memory_usage', models.BigIntegerField(null=True, blank=True)),
                ('cpu_usage_percent', models.DecimalField(
                    max_digits=5, 
                    decimal_places=2, 
                    null=True, 
                    blank=True
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('job', models.OneToOneField(
                    'ContainerJob',
                    related_name='execution',
                    on_delete=models.CASCADE
                )),
            ],
            options={
                'verbose_name': 'Container Execution',
                'verbose_name_plural': 'Container Executions',
            },
        ),
        
        # Optimal indexes from day 1
        migrations.RunSQL([
            # Job lookup optimizations
            "CREATE INDEX container_job_status_created_idx ON container_manager_containerjob(status, created_at);",
            "CREATE INDEX container_job_host_status_idx ON container_manager_containerjob(executor_host_id, status);",
            
            # Host lookup optimizations  
            "CREATE INDEX executor_host_type_active_idx ON container_manager_executorhost(executor_type, is_active);",
        ]),
    ]
```

### Step 4: Clean Model Definitions (30 minutes)
**Goal:** Ensure models match the clean migration exactly

```python
# container_manager/models.py - Clean version after all refactors
class ExecutorHost(models.Model):
    """Host configuration for any executor type"""
    EXECUTOR_CHOICES = [
        ('docker', 'Docker'),
        ('cloudrun', 'Cloud Run'),
        ('mock', 'Mock'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    executor_type = models.CharField(
        max_length=50, 
        default='docker', 
        choices=EXECUTOR_CHOICES
    )
    connection_config = models.JSONField(
        default=dict,
        help_text="Executor-specific connection configuration"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Executor Host"
        verbose_name_plural = "Executor Hosts"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_executor_type_display()})"

class ContainerJob(models.Model):
    """Individual container job instances - clean and simple"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # CLEAN: Single unified execution identifier
    execution_id = models.CharField(max_length=255, blank=True)
    
    exit_code = models.IntegerField(null=True, blank=True)
    override_command = models.TextField(blank=True)
    override_environment = models.JSONField(default=dict)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Foreign Keys
    template = models.ForeignKey(ContainerTemplate, related_name='jobs', on_delete=models.CASCADE)
    executor_host = models.ForeignKey(ExecutorHost, related_name='jobs', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # CLEAN: Simple methods without conditional logic
    def set_execution_identifier(self, execution_id: str) -> None:
        """Set execution identifier - works for all executor types"""
        self.execution_id = execution_id
    
    def get_execution_identifier(self) -> str:
        """Get execution identifier - works for all executor types"""
        return self.execution_id
    
    @property
    def duration(self):
        """Calculate job duration if completed"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return str(delta).split('.')[0]  # Remove microseconds
        return None
    
    def can_be_cancelled(self):
        """Simple business logic without executor conditionals"""
        return self.status in ['pending', 'running']
    
    class Meta:
        verbose_name = "Container Job"
        verbose_name_plural = "Container Jobs"
        ordering = ['-created_at']
```

### Step 5: Recreate Database and Test (30 minutes)
```bash
# Create fresh migration
python manage.py makemigrations container_manager

# Apply clean migration
python manage.py migrate

# Create superuser for testing
python manage.py createsuperuser

# Run all tests to verify everything works
python manage.py test

# Create sample data for testing
python manage.py create_sample_data
```

### Step 6: Performance Optimization (15 minutes)
**Goal:** Add optimal indexes based on actual usage patterns

```python
# Add additional indexes if needed based on query patterns
class Migration(migrations.Migration):
    dependencies = [
        ('container_manager', '0001_initial'),
    ]
    
    operations = [
        migrations.RunSQL([
            # Add any additional performance indexes discovered during testing
            "CREATE INDEX CONCURRENTLY container_job_execution_lookup ON container_manager_containerjob(execution_id) WHERE execution_id != '';",
        ]),
    ]
```

## Files Requiring Updates

### Migration Files
- ✅ **DELETE**: All existing migration files (0001-0017)
- ✅ **CREATE**: Single clean `0001_initial.py`
- ✅ **VERIFY**: Models match migration exactly

### Model Files  
- ✅ `container_manager/models.py` - Ensure clean state matches migration
- ✅ Remove any remaining legacy code or comments

### Test Data
- ✅ `container_manager/management/commands/create_sample_data.py` - Update for new schema
- ✅ Test fixtures - Update for clean schema

### Documentation
- ✅ Update any schema documentation
- ✅ Update API documentation if needed

## Benefits After Implementation

### 1. Clean Migration History
```bash
# BEFORE: Accumulated complexity
0001_initial.py
0002_alter_containerjob_container_id.py
# ... 15 more migrations with historical baggage

# AFTER: Single clean migration
0001_initial.py  # Perfect schema from day 1
```

### 2. Optimal Database Performance
```sql
-- Optimal indexes designed for actual usage
CREATE INDEX container_job_status_created_idx ON container_manager_containerjob(status, created_at);
CREATE INDEX container_job_host_status_idx ON container_manager_containerjob(executor_host_id, status);
CREATE INDEX executor_host_type_active_idx ON container_manager_executorhost(executor_type, is_active);
```

### 3. Clean Schema Documentation
```python
# Models that perfectly reflect actual architecture
class ExecutorHost(models.Model):
    """Host configuration for any executor type - crystal clear purpose"""
    
class ContainerJob(models.Model):  
    """Individual job instances - unified execution_id, no legacy fields"""
```

### 4. Fast Development Database Setup
```bash
# BEFORE: Complex setup
python manage.py migrate  # Runs 17+ complex migrations

# AFTER: Instant setup
python manage.py migrate  # Runs 1 optimal migration
```

## Database Impact

### Schema Comparison
**Before:** Accumulated over 17 migrations
- Multiple index creation/modification operations
- Field additions, removals, renames across many migrations
- Constraint changes spread across multiple files
- Performance characteristics unknown

**After:** Single optimal migration
- All indexes designed for actual query patterns
- All fields present from day 1 with correct types
- All constraints properly designed
- Optimal performance characteristics

### Data Impact
**Zero impact** - No production data exists to preserve.

## Testing Strategy

### Schema Validation
```python
class CleanSchemaTest(TestCase):
    def test_clean_migration_creates_expected_schema(self):
        """Test that our clean migration creates the expected database structure"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'container_manager_executorhost',
                'container_manager_containerjob', 
                'container_manager_containertemplate',
                'container_manager_containerexecution',
                'container_manager_environmentvariabletemplate'
            ]
            
            for table in expected_tables:
                self.assertIn(table, tables)
    
    def test_optimal_indexes_exist(self):
        """Test that performance indexes were created"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = [row[0] for row in cursor.fetchall()]
            
            # Verify our performance indexes exist
            self.assertIn('container_job_status_created_idx', indexes)
            self.assertIn('executor_host_type_active_idx', indexes)
```

### Functional Validation
```python
class CleanModelTest(TestCase):
    def test_unified_execution_id_works_perfectly(self):
        """Test that unified execution_id works for all executor types"""
        executor_types = ['docker', 'cloudrun', 'mock']
        
        for executor_type in executor_types:
            host = ExecutorHost.objects.create(
                name=f"{executor_type}-host",
                executor_type=executor_type
            )
            job = ContainerJob.objects.create(
                template=self.template,
                executor_host=host
            )
            
            # Clean unified interface works perfectly
            job.set_execution_identifier(f"{executor_type}-exec-123")
            self.assertEqual(job.get_execution_identifier(), f"{executor_type}-exec-123")
            self.assertEqual(job.execution_id, f"{executor_type}-exec-123")
```

## Success Metrics

### Quantitative
- **Migration count**: 17+ migrations → 1 clean migration
- **Migration time**: Complex multi-step → Single fast operation
- **Schema size**: Optimized field types and indexes
- **Test performance**: Faster test database creation

### Qualitative
- **Developer experience**: Clean schema is easy to understand
- **Performance**: Optimal indexes from day 1
- **Maintainability**: No legacy artifacts or cruft
- **Documentation**: Schema perfectly matches architecture

## Timeline

### Phase 1: Preparation (30 minutes)
- Backup current state
- Document current schema for reference
- Verify all tests pass before starting

### Phase 2: Nuclear Reset (45 minutes)
- Delete all migration files
- Drop and recreate database
- Create clean initial migration

### Phase 3: Validation (45 minutes)
- Run migrations
- Verify schema correctness
- Run full test suite
- Create sample data

### Phase 4: Optimization (30 minutes)
- Add performance indexes
- Verify query performance
- Document new schema

**Total: 2.5 hours for complete clean rebuild**

## Dependencies

### Prerequisites
- All 3 previous refactors completed (execution IDs, rename, polymorphism)
- All tests passing with clean architecture
- No production data to preserve

### Enables
- Fast development environment setup
- Optimal database performance
- Clean foundation for future development
- Easy new developer onboarding

## Risk Mitigation

### Very Low Risk
- **No production data**: Complete freedom to rebuild
- **Comprehensive tests**: Will catch any schema issues
- **Git backup**: Can always revert to previous state

### Validation Plan
- **Test at each step**: Verify migration creates expected schema
- **Run full test suite**: Ensure all functionality preserved
- **Performance testing**: Verify optimal query performance

This refactor completes the architectural transformation by providing a clean database foundation that perfectly matches our improved code architecture.