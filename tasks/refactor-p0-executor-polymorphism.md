# P0 Refactor: Eliminate Executor-Specific Model Logic

## Priority: P0 (Blocking)
**Impact:** CRITICAL - Removes tight coupling and enables true executor polymorphism
**Effort:** 3-5 hours  
**Risk:** MEDIUM - Requires careful extraction of business logic from models

## Problem Statement

The models contain executor-specific conditional logic that violates separation of concerns and makes testing complex:

```python
# CURRENT VIOLATION: Model knows executor implementation details
class ContainerJob(models.Model):
    def clean(self):
        # Model shouldn't know about executor internals!
        if self.executor_host and self.executor_type != self.executor_host.executor_type:
            raise ValidationError(
                f"Job executor type '{self.executor_type}' doesn't match "
                f"host executor type '{self.executor_host.executor_type}'"
            )
        
        # Model shouldn't validate executor-specific fields!
        if (self.executor_type != "docker" 
            and self.status == "running" 
            and not self.execution_id):
            raise ValidationError(
                f"execution_id required for {self.executor_type} executor"
            )

    def get_display_name(self):
        # Model shouldn't format executor-specific display logic!
        if self.executor_type == "docker":
            return f"{self.name} (Docker)"
        elif self.executor_type == "cloudrun":
            return f"{self.name} (Cloud Run)"
        # ... more conditional logic
```

**Architectural Violations:**
1. **Model knows executor internals** - Violates separation of concerns
2. **Conditional validation logic** - Different rules for different executors
3. **Display formatting in models** - Presentation logic in data layer
4. **Testing complexity** - Must test all executor-type combinations
5. **Tight coupling** - Can't change executors without changing models

## Solution: Extract to Executor Classes

### Clean Model - No Executor Knowledge
```python
class ContainerJob(models.Model):
    """Clean model focused only on job data, not executor specifics"""
    
    # CLEAN: No executor-specific validation
    def clean(self):
        # Only validate core business rules, not executor specifics
        if self.name and len(self.name) > 200:
            raise ValidationError("Job name too long")
    
    # CLEAN: No executor-specific display logic
    def get_display_name(self):
        return self.name or f"Job {self.id}"
    
    # CLEAN: Simple status checks, no executor conditions
    def can_be_cancelled(self):
        return self.status in ["pending", "running"]
```

### Executor Classes Handle Their Own Logic
```python
class BaseExecutor:
    """Base class defines polymorphic interface"""
    
    def validate_job(self, job: ContainerJob) -> List[str]:
        """Each executor validates its own requirements"""
        raise NotImplementedError
    
    def get_display_info(self, job: ContainerJob) -> Dict[str, str]:
        """Each executor provides its own display formatting"""
        raise NotImplementedError

class DockerExecutor(BaseExecutor):
    def validate_job(self, job: ContainerJob) -> List[str]:
        """Docker-specific validation"""
        errors = []
        if job.status == "running" and not job.execution_id:
            errors.append("Execution ID required for running Docker jobs")
        return errors
    
    def get_display_info(self, job: ContainerJob) -> Dict[str, str]:
        """Docker-specific display formatting"""
        return {
            "executor_name": "Docker Container",
            "execution_label": "Container ID",
            "execution_value": job.execution_id or "Not started"
        }

class CloudRunExecutor(BaseExecutor):
    def validate_job(self, job: ContainerJob) -> List[str]:
        """CloudRun-specific validation"""
        errors = []
        if job.status == "running" and not job.execution_id:
            errors.append("Execution ID required for running Cloud Run jobs")
        # Could have different validation rules than Docker
        return errors
    
    def get_display_info(self, job: ContainerJob) -> Dict[str, str]:
        """CloudRun-specific display formatting"""
        return {
            "executor_name": "Cloud Run Job",
            "execution_label": "Execution ID", 
            "execution_value": job.execution_id or "Not started"
        }
```

### Clean Service Layer
```python
class JobValidationService:
    """Service layer handles executor polymorphism"""
    
    def __init__(self, executor_factory: ExecutorFactory):
        self.executor_factory = executor_factory
    
    def validate_job(self, job: ContainerJob) -> List[str]:
        """Use executor polymorphism for validation"""
        executor = self.executor_factory.get_executor(job.executor_host)
        return executor.validate_job(job)
    
    def get_job_display_info(self, job: ContainerJob) -> Dict[str, str]:
        """Use executor polymorphism for display"""
        executor = self.executor_factory.get_executor(job.executor_host)
        return executor.get_display_info(job)
```

## Implementation Plan

### Step 1: Extract Validation Logic (1.5 hours)
**Goal:** Move executor-specific validation from models to executors

#### Update Base Executor
```python
# container_manager/executors/base.py
class BaseExecutor:
    def validate_job_for_execution(self, job: ContainerJob) -> List[str]:
        """Validate job can be executed by this executor"""
        errors = []
        
        # Common validations all executors need
        if not job.template:
            errors.append("Job must have a template")
        
        # Let subclasses add executor-specific validations
        errors.extend(self._validate_executor_specific(job))
        return errors
    
    def _validate_executor_specific(self, job: ContainerJob) -> List[str]:
        """Override in subclasses for executor-specific validation"""
        return []
```

#### Update Model Validation
```python
# container_manager/models.py
class ContainerJob(models.Model):
    def clean(self):
        """Clean model validation - no executor specifics"""
        errors = []
        
        # Only core business validations
        if self.name and len(self.name) > 200:
            errors.append("Job name cannot exceed 200 characters")
        
        if self.override_command and len(self.override_command) > 2000:
            errors.append("Override command too long")
        
        if errors:
            raise ValidationError(errors)
    
    # REMOVE: All executor-specific validation logic
```

### Step 2: Extract Display Logic (1 hour)
**Goal:** Move executor-specific display formatting to executors

#### Add Display Methods to Executors
```python
# Each executor handles its own display logic
class DockerExecutor(BaseExecutor):
    def get_execution_display(self, job: ContainerJob) -> Dict[str, str]:
        return {
            "type_name": "Docker Container",
            "id_label": "Container ID",
            "id_value": job.execution_id or "Not assigned",
            "status_detail": self._get_docker_status_detail(job)
        }

class CloudRunExecutor(BaseExecutor):
    def get_execution_display(self, job: ContainerJob) -> Dict[str, str]:
        return {
            "type_name": "Cloud Run Execution", 
            "id_label": "Execution ID",
            "id_value": job.execution_id or "Not assigned",
            "status_detail": self._get_cloudrun_status_detail(job)
        }
```

#### Clean Model Display Methods
```python
# container_manager/models.py
class ContainerJob(models.Model):
    def get_display_name(self):
        """Simple display name without executor specifics"""
        return self.name or f"Job {str(self.id)[:8]}"
    
    # REMOVE: All executor-specific display methods
    # Let the service layer handle executor-specific formatting
```

### Step 3: Create Polymorphic Service Layer (1 hour)
**Goal:** Service layer uses executor polymorphism instead of conditionals

```python
# container_manager/services.py (NEW FILE)
class JobManagementService:
    """Service layer for job operations using executor polymorphism"""
    
    def __init__(self, executor_factory: ExecutorFactory):
        self.executor_factory = executor_factory
    
    def validate_job_for_execution(self, job: ContainerJob) -> List[str]:
        """Polymorphic validation"""
        executor = self.executor_factory.get_executor(job.executor_host)
        return executor.validate_job_for_execution(job)
    
    def get_job_execution_details(self, job: ContainerJob) -> Dict[str, str]:
        """Polymorphic display formatting"""
        executor = self.executor_factory.get_executor(job.executor_host)
        return executor.get_execution_display(job)
    
    def prepare_job_for_launch(self, job: ContainerJob) -> bool:
        """Polymorphic job preparation"""
        executor = self.executor_factory.get_executor(job.executor_host)
        
        # Use executor-specific validation
        errors = executor.validate_job_for_execution(job)
        if errors:
            raise ValidationError(errors)
        
        # Use executor-specific preparation
        return executor.prepare_job(job)
```

### Step 4: Update Management Commands (1 hour)
**Goal:** Commands use service layer instead of model conditionals

```python
# container_manager/management/commands/manage_container_job.py
class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor_factory = ExecutorFactory()
        self.job_service = JobManagementService(self.executor_factory)
    
    def _display_execution_details(self, job):
        """Use service layer for polymorphic display"""
        details = self.job_service.get_job_execution_details(job)
        
        # Clean, non-conditional display
        self.stdout.write(f"Executor: {details['type_name']}")
        self.stdout.write(f"{details['id_label']}: {details['id_value']}")
        self.stdout.write(f"Status: {details['status_detail']}")
    
    def _validate_job_for_run(self, job_id):
        """Use service layer for polymorphic validation"""
        try:
            job = ContainerJob.objects.get(id=job_id)
        except ContainerJob.DoesNotExist:
            raise CommandError(f'Job "{job_id}" not found')
        
        # Use polymorphic validation instead of conditionals
        errors = self.job_service.validate_job_for_execution(job)
        if errors:
            raise CommandError(f"Job validation failed: {'; '.join(errors)}")
        
        return job
```

### Step 5: Update Admin Interface (30 minutes)
**Goal:** Admin uses service layer for consistent display

```python
# container_manager/admin.py
@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_service = JobManagementService(ExecutorFactory())
    
    def get_execution_details(self, obj):
        """Polymorphic execution details for admin"""
        details = self.job_service.get_job_execution_details(obj)
        return f"{details['type_name']}: {details['id_value']}"
    get_execution_details.short_description = 'Execution Details'
    
    list_display = ['name', 'status', 'executor_type', 'get_execution_details']
```

### Step 6: Massive Test Simplification (1 hour)
**Goal:** Tests become executor-agnostic

```python
# container_manager/tests/test_job_management.py
class JobManagementTest(TestCase):
    def setUp(self):
        self.job_service = JobManagementService(ExecutorFactory())
    
    def test_validation_works_for_all_executors(self):
        """Test polymorphic validation"""
        executor_types = ["docker", "cloudrun", "mock"]
        
        for executor_type in executor_types:
            host = self.create_executor_host(executor_type=executor_type)
            job = self.create_job(executor_host=host)
            
            # Same interface for all executors!
            errors = self.job_service.validate_job_for_execution(job)
            self.assertEqual(len(errors), 0)
    
    def test_display_works_for_all_executors(self):
        """Test polymorphic display"""
        executor_types = ["docker", "cloudrun", "mock"]
        
        for executor_type in executor_types:
            host = self.create_executor_host(executor_type=executor_type)
            job = self.create_job(executor_host=host, execution_id="test-123")
            
            # Same interface for all executors!
            details = self.job_service.get_job_execution_details(job)
            
            # All executors provide same interface
            self.assertIn('type_name', details)
            self.assertIn('id_label', details) 
            self.assertIn('id_value', details)
            self.assertEqual(details['id_value'], "test-123")
```

## Files Requiring Updates

### Core Model Files
- ✅ `container_manager/models.py` - Remove executor conditionals
- ✅ `container_manager/services.py` - NEW: Service layer

### Executor Files
- ✅ `container_manager/executors/base.py` - Add validation/display methods
- ✅ `container_manager/executors/docker.py` - Implement executor-specific logic
- ✅ `container_manager/executors/cloudrun.py` - Implement executor-specific logic
- ✅ `container_manager/executors/mock.py` - Implement executor-specific logic

### Management Commands  
- ✅ `container_manager/management/commands/manage_container_job.py` - Use service layer
- ✅ `container_manager/management/commands/process_container_jobs.py` - Use service layer

### Admin Interface
- ✅ `container_manager/admin.py` - Use service layer for display

### Test Files
- ✅ All test files - Simplify to use service layer
- ✅ Remove executor-conditional test logic

## Benefits After Implementation

### 1. True Polymorphism
```python
# BEFORE: Conditional nightmare in every operation
def display_job_info(job):
    if job.executor_type == "docker":
        return f"Container: {job.container_id}"
    elif job.executor_type == "cloudrun":
        return f"Execution: {job.external_execution_id}"
    # ... more conditions

# AFTER: Clean polymorphic interface
def display_job_info(job):
    details = job_service.get_job_execution_details(job)
    return f"{details['type_name']}: {details['id_value']}"
```

### 2. Separation of Concerns
```python
# Models focus on data
class ContainerJob(models.Model):
    # Only core fields and business rules
    
# Executors focus on execution logic
class DockerExecutor(BaseExecutor):
    # Only Docker-specific behavior
    
# Service layer coordinates
class JobManagementService:
    # Only orchestration and polymorphism
```

### 3. Easy Testing
```python
# Test each layer independently
class ModelTest(TestCase):
    def test_job_model_core_behavior(self):
        # Test only core model behavior, no executor specifics
        
class ExecutorTest(TestCase):
    def test_docker_executor_behavior(self):
        # Test only Docker executor behavior
        
class ServiceTest(TestCase):
    def test_polymorphic_operations(self):
        # Test service layer coordination
```

### 4. Easy Extension
```python
# Adding new executor becomes trivial
class KubernetesExecutor(BaseExecutor):
    def validate_job_for_execution(self, job):
        # K8s-specific validation
        
    def get_execution_display(self, job):
        # K8s-specific display
        
# No changes needed to models, commands, or admin!
```

## Database Impact

### Schema Changes
**None!** This is pure code refactoring without database changes.

### Model Changes
- Remove validation methods with conditional logic
- Simplify display methods
- Keep all fields exactly the same

## Testing Strategy

### Unit Tests by Layer
```python
# Test models in isolation
class ContainerJobModelTest(TestCase):
    def test_core_validation_only(self):
        # Test only core business rules
        
# Test executors in isolation  
class DockerExecutorTest(TestCase):
    def test_docker_specific_validation(self):
        # Test only Docker behavior
        
# Test service layer polymorphism
class JobManagementServiceTest(TestCase):
    def test_polymorphic_validation(self):
        # Test service coordinates executors correctly
```

### Integration Tests
```python
class PolymorphicIntegrationTest(TestCase):
    def test_end_to_end_polymorphism(self):
        """Test entire stack works polymorphically"""
        for executor_type in ["docker", "cloudrun", "mock"]:
            # Same test flow for all executor types
            host = self.create_host(executor_type)
            job = self.create_job(host)
            
            # All operations work the same way
            self.assertTrue(job_service.validate_job_for_execution(job))
            details = job_service.get_job_execution_details(job)
            self.assertIsInstance(details, dict)
```

## Success Metrics

### Quantitative
- **Conditional removal**: Eliminate 20+ conditional code blocks
- **Test simplification**: Reduce test complexity by 50%
- **Code organization**: Clear separation between layers

### Qualitative
- **Maintainability**: Easy to add new executor types
- **Testability**: Each layer can be tested in isolation
- **Readability**: Code flows logically without conditionals

## Timeline

### Phase 1: Foundation (2 hours)
- Create service layer
- Extract validation logic to executors
- Update base executor interface

### Phase 2: Refactor Usage (2 hours)
- Update management commands to use service layer
- Update admin interface
- Remove conditional logic from models

### Phase 3: Testing (1 hour)
- Simplify test suite
- Add service layer tests
- Verify polymorphic behavior

**Total: 5 hours for complete transformation**

## Dependencies

### Prerequisites
- Execution identifier refactor completed
- ExecutorHost rename completed  
- All tests currently passing

### Enables
- Clean database rebuild (no conditional logic)
- Easy addition of new executor types
- Simplified testing across the board

This refactor completes the architectural cleanup by establishing true separation of concerns and polymorphic behavior throughout the system.