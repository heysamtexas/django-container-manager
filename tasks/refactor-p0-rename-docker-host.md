# P0 Refactor: Rename DockerHost → ExecutorHost

## Priority: P0 (Blocking)
**Impact:** HIGH - Eliminates naming confusion and improves architectural clarity
**Effort:** 3-4 hours
**Risk:** LOW - Straightforward rename with comprehensive find/replace

## Problem Statement

The `DockerHost` model name is misleading and creates confusion:

```python
# CONFUSING: Model called "DockerHost" but runs Cloud Run!
class DockerHost(models.Model):
    executor_type = models.CharField(default="docker")  # But can be "cloudrun"!
    
# CONFUSING: "Docker" host running Cloud Run jobs
cloudrun_host = DockerHost.objects.create(
    name="cloudrun-prod",
    executor_type="cloudrun",  # This is not Docker!
    connection_string="projects/my-project/locations/us-central1"
)
```

**Core Issues:**
1. **Misleading name**: `DockerHost` hosts non-Docker executors
2. **Cognitive dissonance**: Reading code is confusing
3. **Extensibility confusion**: Adding new executors seems wrong
4. **Documentation complexity**: Need to explain why "DockerHost" runs CloudRun

## Solution: Rename to ExecutorHost

### New Clear Model Name
```python
# CLEAR: Model name matches actual purpose
class ExecutorHost(models.Model):
    """Host configuration for any executor type (Docker, Cloud Run, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    executor_type = models.CharField(max_length=50, default="docker")
    connection_config = models.JSONField(default=dict)  # Flexible config
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.executor_type.title()})"
    
    def get_display_name(self):
        """Get user-friendly display name"""
        if self.executor_type == "docker":
            return f"{self.name} (Docker)"
        elif self.executor_type == "cloudrun":
            config = self.connection_config
            region = config.get("region", "unknown")
            return f"{self.name} (Cloud Run - {region})"
        else:
            return f"{self.name} ({self.executor_type.title()})"
```

### Clear Usage Patterns
```python
# NOW MAKES SENSE: ExecutorHost can host any executor
docker_host = ExecutorHost.objects.create(
    name="docker-prod", 
    executor_type="docker",
    connection_config={"host": "tcp://docker.prod:2376", "tls": True}
)

cloudrun_host = ExecutorHost.objects.create(
    name="cloudrun-prod",
    executor_type="cloudrun", 
    connection_config={"project_id": "my-project", "region": "us-central1"}
)

mock_host = ExecutorHost.objects.create(
    name="test-mock",
    executor_type="mock",
    connection_config={"delay_seconds": 1}
)
```

## Implementation Plan

### Step 1: Rename Model Class (30 minutes)
**File:** `container_manager/models.py`

```python
# RENAME: DockerHost → ExecutorHost
class ExecutorHost(models.Model):
    """Host configuration for any executor type"""
    # Keep all existing fields
    name = models.CharField(max_length=100, unique=True)
    executor_type = models.CharField(max_length=50, default="docker")
    # ... all other fields remain the same
    
    class Meta:
        verbose_name = "Executor Host"
        verbose_name_plural = "Executor Hosts"
        ordering = ['name']
```

### Step 2: Update All Model References (1 hour)
**Files to update systematically:**

```python
# container_manager/models.py
class ContainerJob(models.Model):
    executor_host = models.ForeignKey(
        ExecutorHost,  # Changed from DockerHost
        related_name="jobs", 
        on_delete=models.CASCADE
    )

class ContainerTemplate(models.Model):
    preferred_executor_host = models.ForeignKey(
        ExecutorHost,  # Changed from DockerHost
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
```

### Step 3: Create Migration (30 minutes)
**File:** `container_manager/migrations/0017_rename_dockerhost_executorhost.py`

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('container_manager', '0016_unify_execution_identifiers'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DockerHost',
            new_name='ExecutorHost',
        ),
        # Update related field names for clarity
        migrations.RenameField(
            model_name='containerjob',
            old_name='docker_host',
            new_name='executor_host',
        ),
        migrations.RenameField(
            model_name='containertemplate', 
            old_name='preferred_docker_host',
            new_name='preferred_executor_host',
        ),
    ]
```

### Step 4: Update All Code References (1.5 hours)
**Comprehensive find/replace across codebase:**

#### Management Commands
```python
# container_manager/management/commands/manage_container_job.py
try:
    executor_host = ExecutorHost.objects.get(name=host_name, is_active=True)
except ExecutorHost.DoesNotExist:
    raise CommandError(f'Executor host "{host_name}" not found or inactive')

# Display updates
self.stdout.write(f"Host: {job.executor_host.name}")
```

#### Executors
```python
# container_manager/executors/factory.py
class ExecutorFactory:
    def get_executor(self, executor_host: ExecutorHost):
        """Get executor instance for the given host"""
        if executor_host.executor_type == "docker":
            return DockerExecutor(executor_host.connection_config)
        elif executor_host.executor_type == "cloudrun":
            return CloudRunExecutor(executor_host.connection_config)
        # ...
```

#### Admin Interface
```python
# container_manager/admin.py
@admin.register(ExecutorHost)
class ExecutorHostAdmin(admin.ModelAdmin):
    list_display = ['name', 'executor_type', 'is_active']
    list_filter = ['executor_type', 'is_active']
    search_fields = ['name']
```

#### Tests
```python
# All test files
self.executor_host = ExecutorHost.objects.create(
    name="test-host",
    executor_type="docker",
    connection_config={"host": "tcp://localhost:2376"}
)
```

### Step 5: Update Field Names for Consistency (30 minutes)
**Rename foreign key fields for clarity:**

```python
# OLD: Confusing field names
job.docker_host  # Confusing when it's a Cloud Run host!

# NEW: Clear field names  
job.executor_host  # Clear regardless of executor type
template.preferred_executor_host  # Clear purpose
```

### Step 6: Update Documentation & Strings (30 minutes)
```python
# Update help_text, verbose_name, and docstrings
class ExecutorHost(models.Model):
    connection_config = models.JSONField(
        default=dict,
        help_text="Executor-specific connection configuration"
    )
    
    class Meta:
        verbose_name = "Executor Host"
        verbose_name_plural = "Executor Hosts"
```

## Files Requiring Updates

### Core Model Files
- ✅ `container_manager/models.py` - Main model rename
- ✅ `container_manager/admin.py` - Admin interface

### Executor Files  
- ✅ `container_manager/executors/factory.py` - Factory method updates
- ✅ `container_manager/executors/docker.py` - Config access updates
- ✅ `container_manager/executors/cloudrun.py` - Config access updates
- ✅ `container_manager/executors/fallback.py` - Host selection logic

### Management Commands
- ✅ `container_manager/management/commands/manage_container_job.py`
- ✅ `container_manager/management/commands/process_container_jobs.py`
- ✅ `container_manager/management/commands/create_sample_data.py`
- ✅ `container_manager/management/commands/cleanup_containers.py`

### Other Files
- ✅ `container_manager/bulk_operations.py` - Bulk processing
- ✅ `container_manager/docker_service.py` - Service layer

### Test Files (Comprehensive)
- ✅ All test files that reference DockerHost
- ✅ All test files that create test hosts
- ✅ Management command tests
- ✅ Executor tests

## Configuration Field Cleanup

### Standardize Connection Config
```python
# OLD: Mixed field approach
class DockerHost(models.Model):
    connection_string = models.CharField(max_length=500)
    tls_enabled = models.BooleanField(default=False)
    tls_verify = models.BooleanField(default=False) 
    executor_config = models.JSONField(default=dict)  # Separate field!

# NEW: Unified configuration
class ExecutorHost(models.Model):
    connection_config = models.JSONField(
        default=dict,
        help_text="All executor configuration in one place"
    )
    
    # Example configs:
    # Docker: {"host": "tcp://host:2376", "tls": True, "verify": False}
    # CloudRun: {"project_id": "proj", "region": "us-central1"} 
    # Mock: {"delay_seconds": 1, "failure_rate": 0.1}
```

## Testing Strategy

### Verification Tests
```python
class ExecutorHostRenameTest(TestCase):
    def test_model_renamed_correctly(self):
        """Test ExecutorHost model works correctly"""
        host = ExecutorHost.objects.create(
            name="test-executor",
            executor_type="docker",
            connection_config={"host": "tcp://localhost:2376"}
        )
        
        self.assertEqual(str(host), "test-executor (Docker)")
        self.assertTrue(host.is_active)
    
    def test_all_executor_types_supported(self):
        """Test clear naming for all executor types"""
        test_cases = [
            ("docker", "Docker Host (Docker)"),
            ("cloudrun", "CloudRun Host (Cloudrun)"), 
            ("mock", "Mock Host (Mock)")
        ]
        
        for executor_type, expected_str in test_cases:
            host = ExecutorHost.objects.create(
                name=f"{executor_type.title()} Host",
                executor_type=executor_type
            )
            self.assertIn(executor_type.title(), str(host))
```

### Migration Verification
```python
def test_migration_preserves_data(self):
    """Test that renaming migration preserves all data"""
    # After migration, all data should be intact
    host_count = ExecutorHost.objects.count()
    job_count = ContainerJob.objects.count()
    
    # Verify relationships still work
    for job in ContainerJob.objects.all():
        self.assertIsInstance(job.executor_host, ExecutorHost)
```

## Benefits After Implementation

### 1. Clear Naming
```python
# BEFORE: Confusing
cloudrun_host = DockerHost.objects.create(executor_type="cloudrun")  # What?!

# AFTER: Crystal clear
cloudrun_host = ExecutorHost.objects.create(executor_type="cloudrun")  # Makes sense!
```

### 2. Easier Documentation
```python
# Clear documentation becomes possible
class ExecutorHost(models.Model):
    """
    Host configuration for any executor type.
    
    Supports Docker, Cloud Run, Mock, and future executor types.
    Each executor type uses connection_config differently:
    - Docker: {"host": "tcp://...", "tls": true}
    - CloudRun: {"project_id": "...", "region": "..."}
    - Mock: {"delay_seconds": 1}
    """
```

### 3. Logical Extensions
```python
# Adding new executor types feels natural
kubernetes_host = ExecutorHost.objects.create(
    name="k8s-cluster",
    executor_type="kubernetes", 
    connection_config={
        "kubeconfig": "/path/to/config",
        "namespace": "default"
    }
)
```

### 4. Better Admin Interface
```python
@admin.register(ExecutorHost)
class ExecutorHostAdmin(admin.ModelAdmin):
    list_display = ['name', 'executor_type', 'is_active', 'get_display_name']
    list_filter = ['executor_type', 'is_active']
    
    def get_display_name(self, obj):
        return obj.get_display_name()
    get_display_name.short_description = 'Display Name'
```

## Database Impact

### Schema Changes
```sql
-- Rename table
ALTER TABLE container_manager_dockerhost 
RENAME TO container_manager_executorhost;

-- Rename foreign key fields
ALTER TABLE container_manager_containerjob 
RENAME COLUMN docker_host_id TO executor_host_id;

-- Update indexes and constraints automatically handled by Django
```

### Zero Data Loss
- All existing data preserved
- All relationships maintained
- Only names change, not structure

## Success Metrics

### Quantitative
- **All tests pass** after rename
- **All admin interfaces** work correctly
- **All management commands** function properly

### Qualitative
- **Code reads naturally** - ExecutorHost makes sense
- **Documentation flows** - No need to explain naming confusion
- **Extension feels logical** - Adding new executors is intuitive

## Timeline

### Phase 1: Core Rename (1 hour)
- Rename model class
- Create migration
- Update core model references

### Phase 2: Code Updates (2 hours)
- Update all file references
- Update foreign key field names
- Update admin interface

### Phase 3: Testing & Verification (1 hour)
- Run full test suite
- Update test files
- Verify admin interface works

**Total: 4 hours for complete rename**

## Dependencies

### Prerequisites
- Execution identifier refactor completed first
- All tests currently passing
- Clean git state

### Enables Future Work
- Makes executor polymorphism refactor cleaner
- Prepares for database rebuild
- Simplifies new executor type additions

## Risk Mitigation

### Low Risk Factors
- **Straightforward rename**: No logic changes
- **Django handles**: Migration complexity automatically
- **Comprehensive tests**: Will catch any missed references

### Validation Plan
- **Test each step**: Run tests after each major change
- **Admin verification**: Check admin interface works
- **Management commands**: Verify all commands function

This refactor eliminates naming confusion and makes the codebase much more intuitive to understand and extend.