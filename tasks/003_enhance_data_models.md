# Task 003: Enhance Data Models for Multi-Executor Support

## Objective
Add fields to `ContainerJob` and `DockerHost` models to support multiple executor types, track cloud provider execution IDs, and enable intelligent job routing while maintaining backward compatibility.

## Git Strategy  
- Branch: `task-003-enhance-models`
- Commit pattern: "Add [field/model]: [purpose]"
- Commits: "Add multi-executor fields to ContainerJob", "Add executor config to DockerHost", "Create database migration"

## Prerequisites
- Task 001 completed (ContainerExecutor interface)
- Task 002 completed (DockerExecutor implementation)
- Understanding of Django model migrations
- Current job processing must continue working during migration

## Implementation Steps

1. [ ] Add new fields to `ContainerJob` model
2. [ ] Add new fields to `DockerHost` model  
3. [ ] Create Django migration with sensible defaults
4. [ ] Update model admin interfaces to show new fields
5. [ ] Add model methods for executor routing
6. [ ] Update model `__str__` methods to include executor info
7. [ ] Run ruff format and check before committing

## Code Quality Requirements
- Maintain backward compatibility during migration
- Use early returns in model methods
- Keep method complexity low
- Add comprehensive help_text for admin interface
- Include proper field validation

## Detailed Implementation

### ContainerJob Model Enhancements

```python
class ContainerJob(models.Model):
    # Existing fields remain unchanged...
    
    # Multi-executor support
    executor_type = models.CharField(
        max_length=50,
        default='docker',
        choices=[
            ('docker', 'Docker'),
            ('cloudrun', 'Google Cloud Run'),
            ('fargate', 'AWS Fargate'),
            ('scaleway', 'Scaleway Containers'),
            ('mock', 'Mock (Testing)'),
        ],
        help_text="Container execution backend to use for this job"
    )
    
    external_execution_id = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Cloud provider's execution/job ID (e.g., Cloud Run job name, Fargate task ARN)"
    )
    
    executor_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific data like regions, URLs, resource identifiers"
    )
    
    # Routing and preferences
    preferred_executor = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Preferred executor type for this job (overrides routing rules)"
    )
    
    routing_reason = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Reason why this executor was chosen (for debugging/analytics)"
    )
    
    # Cost and resource tracking
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated execution cost in USD"
    )
    
    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Actual execution cost in USD (if available)"
    )
```

### DockerHost Model Enhancements

```python
class DockerHost(models.Model):
    # Existing fields remain unchanged...
    
    # Multi-executor support
    executor_type = models.CharField(
        max_length=50,
        default='docker',
        choices=[
            ('docker', 'Docker'),
            ('cloudrun', 'Google Cloud Run'),
            ('fargate', 'AWS Fargate'),
            ('scaleway', 'Scaleway Containers'),
        ],
        help_text="Type of container executor this host represents"
    )
    
    executor_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Executor-specific configuration (credentials, regions, etc.)"
    )
    
    # Resource and capacity management
    max_concurrent_jobs = models.PositiveIntegerField(
        default=10,
        help_text="Maximum number of concurrent jobs for this executor"
    )
    
    current_job_count = models.PositiveIntegerField(
        default=0,
        help_text="Currently running job count (updated by worker process)"
    )
    
    # Cost tracking
    cost_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated cost per hour for this executor"
    )
    
    cost_per_job = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated cost per job execution"
    )
    
    # Health and performance
    average_startup_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Average container startup time in seconds"
    )
    
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful health check timestamp"
    )
    
    health_check_failures = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive health check failures"
    )
```

### Model Method Additions

#### ContainerJob Methods
```python
class ContainerJob(models.Model):
    # ... fields ...
    
    def get_execution_identifier(self) -> str:
        """Get the appropriate execution ID for this job's executor"""
        if self.executor_type == 'docker':
            return self.container_id
        
        return self.external_execution_id or ''
    
    def set_execution_identifier(self, execution_id: str) -> None:
        """Set the execution ID for this job's executor"""
        if self.executor_type == 'docker':
            self.container_id = execution_id
        else:
            self.external_execution_id = execution_id
    
    def can_use_executor(self, executor_type: str) -> bool:
        """Check if this job can run on the specified executor type"""
        if self.preferred_executor:
            return self.preferred_executor == executor_type
            
        # Check template compatibility
        if hasattr(self.template, 'supported_executors'):
            return executor_type in self.template.supported_executors
            
        return True  # Default: all jobs can run anywhere
    
    def estimate_resources(self) -> Dict[str, Any]:
        """Estimate resource requirements for routing decisions"""
        return {
            'memory_mb': self.template.memory_limit or 512,
            'cpu_cores': self.template.cpu_limit or 1.0,
            'timeout_seconds': self.template.timeout_seconds,
            'storage_required': bool(self.template.working_directory),
        }
    
    def __str__(self):
        executor_info = f" ({self.executor_type})" if self.executor_type != 'docker' else ""
        return f"{self.name or self.template.name} ({self.status}){executor_info}"
```

#### DockerHost Methods
```python
class DockerHost(models.Model):
    # ... fields ...
    
    def is_available(self) -> bool:
        """Check if this executor is available for new jobs"""
        if not self.is_active:
            return False
            
        if self.current_job_count >= self.max_concurrent_jobs:
            return False
            
        # Check health status
        if self.health_check_failures >= 3:
            return False
            
        return True
    
    def get_capacity_info(self) -> Dict[str, Any]:
        """Get current capacity information"""
        return {
            'current_jobs': self.current_job_count,
            'max_jobs': self.max_concurrent_jobs,
            'available_slots': max(0, self.max_concurrent_jobs - self.current_job_count),
            'utilization_percent': (self.current_job_count / self.max_concurrent_jobs) * 100,
        }
    
    def increment_job_count(self) -> None:
        """Thread-safe increment of current job count"""
        from django.db import transaction
        
        with transaction.atomic():
            self.refresh_from_db()
            if self.current_job_count < self.max_concurrent_jobs:
                self.current_job_count += 1
                self.save(update_fields=['current_job_count'])
    
    def decrement_job_count(self) -> None:
        """Thread-safe decrement of current job count"""
        from django.db import transaction
        
        with transaction.atomic():
            self.refresh_from_db()
            if self.current_job_count > 0:
                self.current_job_count -= 1
                self.save(update_fields=['current_job_count'])
    
    def __str__(self):
        executor_info = f" ({self.executor_type})" if self.executor_type != 'docker' else ""
        return f"{self.name}{executor_info} ({self.connection_string})"
```

### Migration Strategy

#### Create Migration File
```python
# Generated migration with sensible defaults
class Migration(migrations.Migration):
    dependencies = [
        ('container_manager', '0003_dockerhost_auto_pull_images'),
    ]

    operations = [
        # ContainerJob enhancements
        migrations.AddField(
            model_name='containerjob',
            name='executor_type',
            field=models.CharField(default='docker', max_length=50),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='external_execution_id',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='containerjob',
            name='executor_metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        # ... additional fields ...
        
        # DockerHost enhancements  
        migrations.AddField(
            model_name='dockerhost',
            name='executor_type',
            field=models.CharField(default='docker', max_length=50),
        ),
        # ... additional fields ...
    ]
```

### Admin Interface Updates

#### ContainerJob Admin
```python
@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'job_name', 'template', 'docker_host', 
        'executor_type', 'status', 'duration_display', 'created_at'
    )
    list_filter = (
        'status', 'executor_type', 'docker_host', 
        'template', 'created_at'
    )
    
    fieldsets = (
        ('Job Information', {
            'fields': ('id', 'template', 'docker_host', 'name', 'status')
        }),
        ('Executor Configuration', {
            'fields': (
                'executor_type', 'preferred_executor', 'routing_reason',
                'external_execution_id', 'executor_metadata'
            ),
            'classes': ('collapse',)
        }),
        ('Cost Tracking', {
            'fields': ('estimated_cost', 'actual_cost'),
            'classes': ('collapse',)
        }),
        # ... existing fieldsets ...
    )
```

#### DockerHost Admin
```python
@admin.register(DockerHost) 
class DockerHostAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'executor_type', 'host_type', 'connection_string',
        'current_job_count', 'max_concurrent_jobs', 'is_active', 
        'connection_status', 'created_at'
    )
    list_filter = ('executor_type', 'host_type', 'is_active')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'executor_type', 'host_type', 'connection_string', 'is_active')
        }),
        ('Executor Configuration', {
            'fields': ('executor_config', 'max_concurrent_jobs', 'current_job_count'),
        }),
        ('Cost and Performance', {
            'fields': (
                'cost_per_hour', 'cost_per_job', 
                'average_startup_time', 'last_health_check', 'health_check_failures'
            ),
            'classes': ('collapse',)
        }),
        # ... existing fieldsets ...
    )
    
    def capacity_display(self, obj):
        """Show current capacity utilization"""
        info = obj.get_capacity_info()
        return f"{info['current_jobs']}/{info['max_jobs']} ({info['utilization_percent']:.1f}%)"
    capacity_display.short_description = 'Capacity'
```

## Testing Criteria
- [ ] Migration runs successfully on existing data
- [ ] All existing jobs get `executor_type='docker'` by default
- [ ] New model methods work correctly
- [ ] Admin interface displays new fields properly
- [ ] Backward compatibility maintained for existing code
- [ ] Foreign key relationships preserved
- [ ] JSON fields handle empty defaults correctly

## Validation Rules
```python
def clean(self):
    """Model validation for ContainerJob"""
    super().clean()
    
    # Validate executor type matches docker_host
    if self.docker_host and self.executor_type != self.docker_host.executor_type:
        raise ValidationError(
            f"Job executor type '{self.executor_type}' doesn't match "
            f"host executor type '{self.docker_host.executor_type}'"
        )
    
    # Validate external_execution_id for non-docker executors
    if self.executor_type != 'docker' and self.status == 'running' and not self.external_execution_id:
        raise ValidationError(
            f"external_execution_id required for {self.executor_type} executor"
        )
```

## Decision Points
- **Field Names**: Use `executor_type` vs `backend_type`? → `executor_type` for clarity
- **JSON Schema**: Validate executor_config structure? → Keep flexible for now, validate in executors
- **Migration Safety**: Run migration during downtime? → No, design for zero-downtime

## Success Criteria
- [ ] All new fields added to models with appropriate defaults
- [ ] Database migration runs without errors
- [ ] Admin interface shows all new fields in logical groupings
- [ ] Model methods enable executor routing logic
- [ ] Backward compatibility preserved for existing jobs
- [ ] Cost tracking fields ready for future billing integration
- [ ] Capacity management fields enable resource planning
- [ ] All validation rules work correctly

## Next Task Preparation
After completing this task, Task 004 will create the executor factory and routing logic. Key information to pass forward:

- `ContainerJob.executor_type` determines which executor to use
- `ContainerJob.can_use_executor()` enables routing validation
- `DockerHost.is_available()` enables capacity checking
- Cost tracking fields are in place for future billing
- Migration preserves all existing functionality