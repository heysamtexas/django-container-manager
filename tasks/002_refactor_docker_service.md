# Task 002: Refactor Docker Service to DockerExecutor

## Objective
Extract existing Docker functionality from `docker_service.py` into a `DockerExecutor` class that implements the `ContainerExecutor` interface, maintaining backward compatibility while enabling multi-cloud abstraction.

## Git Strategy  
- Branch: `task-002-docker-executor`
- Commit pattern: "Refactor [component]: [change description]"
- Commits: "Extract DockerExecutor class", "Update docker_service to use executor", "Add backward compatibility layer"

## Prerequisites
- Task 001 completed (ContainerExecutor interface exists)
- Understanding of current `docker_service.py` implementation
- All existing functionality must continue working

## Implementation Steps

1. [ ] Create `container_manager/executors/docker.py`
2. [ ] Implement `DockerExecutor` class inheriting from `ContainerExecutor`
3. [ ] Move Docker-specific methods from `docker_service.py` to `DockerExecutor`
4. [ ] Update `docker_service.py` to use `DockerExecutor` internally
5. [ ] Ensure all existing tests still pass
6. [ ] Add specific tests for `DockerExecutor` class
7. [ ] Run ruff format and check before committing

## Code Quality Requirements
- Maintain existing method signatures for backward compatibility
- Use early returns instead of nested conditions
- Keep cyclomatic complexity < 10 per method
- No nested try/except blocks
- Extract complex logic into helper methods

## Detailed Implementation

### DockerExecutor Class Structure
```python
from typing import Dict, List, Tuple
import docker
from django.conf import settings
from .base import ContainerExecutor
from .exceptions import ExecutorConnectionError, ExecutorError
from ..models import ContainerJob

class DockerExecutor(ContainerExecutor):
    """Docker-based container executor"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self._clients: Dict[str, docker.DockerClient] = {}
        self.docker_host = config.get('docker_host')
        
    def launch_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """Launch job using Docker API"""
        try:
            container_id = self._create_container(job)
            if not container_id:
                return False, "Failed to create container"
                
            success = self._start_container(job, container_id)
            if not success:
                return False, "Failed to start container"
                
            return True, container_id
            
        except Exception as e:
            return False, str(e)
    
    def check_status(self, execution_id: str) -> str:
        """Check Docker container status"""
        # Implementation from existing check_container_status
        
    def get_logs(self, execution_id: str) -> Tuple[str, str]:
        """Get Docker container logs"""
        # Implementation from existing get_container_logs
        
    def harvest_job(self, job: ContainerJob) -> bool:
        """Harvest completed Docker job"""
        # Implementation from existing harvest_completed_job
        
    def cleanup(self, execution_id: str) -> bool:
        """Cleanup Docker container"""
        # Implementation from existing remove_container
        
    def get_capabilities(self) -> Dict[str, bool]:
        """Docker executor capabilities"""
        return {
            'supports_resource_limits': True,
            'supports_networking': True,
            'supports_persistent_storage': True,
            'supports_secrets': False,
        }
```

### Method Migration Pattern
For each method being moved:

1. **Copy method from `docker_service.py`**
2. **Adapt to executor interface**
3. **Remove Docker-specific assumptions**
4. **Add proper error handling with early returns**
5. **Update method signature if needed**

Example migration:
```python
# Before (in docker_service.py)
def create_container(self, job: ContainerJob, environment: Optional[Dict] = None) -> str:
    # Existing implementation
    
# After (in DockerExecutor)
def _create_container(self, job: ContainerJob) -> str:
    """Create Docker container for job (internal method)"""
    if job.status != 'pending':
        raise ExecutorError(f"Cannot create container for job in status {job.status}")
        
    try:
        client = self._get_client(job.docker_host)
        # ... existing implementation with early returns
    except docker.errors.DockerException as e:
        raise ExecutorConnectionError(f"Docker API error: {e}")
```

### Backward Compatibility Layer
Update `docker_service.py` to delegate to `DockerExecutor`:

```python
class DockerService:
    """Backward compatibility wrapper around DockerExecutor"""
    
    def __init__(self):
        self._executor = None
        
    def _get_executor(self, docker_host):
        """Get or create DockerExecutor for host"""
        if not self._executor:
            from .executors.docker import DockerExecutor
            self._executor = DockerExecutor({'docker_host': docker_host})
        return self._executor
    
    def launch_job(self, job: ContainerJob) -> bool:
        """Legacy method - delegates to DockerExecutor"""
        executor = self._get_executor(job.docker_host)
        success, execution_id = executor.launch_job(job)
        if success:
            job.external_execution_id = execution_id
            job.save()
        return success
        
    # Keep all existing method signatures for compatibility
```

## Method Migration Checklist

### Core Methods to Move:
- [ ] `_build_container_labels()` → `DockerExecutor._build_labels()`
- [ ] `create_container()` → `DockerExecutor._create_container()`
- [ ] `start_container()` → `DockerExecutor._start_container()`
- [ ] `check_container_status()` → `DockerExecutor.check_status()`
- [ ] `get_container_logs()` → `DockerExecutor.get_logs()`
- [ ] `harvest_completed_job()` → `DockerExecutor.harvest_job()`
- [ ] `remove_container()` → `DockerExecutor.cleanup()`

### Helper Methods to Move:
- [ ] `_should_auto_pull_images()` → `DockerExecutor._should_pull_image()`
- [ ] `get_client()` → `DockerExecutor._get_client()`
- [ ] `_collect_execution_data()` → `DockerExecutor._collect_data()`
- [ ] `_cleanup_container_after_execution()` → `DockerExecutor._immediate_cleanup()`

### Configuration Methods:
- [ ] Move Docker-specific settings handling
- [ ] Add executor-specific configuration validation
- [ ] Preserve existing environment variable handling

## Testing Criteria
- [ ] All existing tests pass without modification
- [ ] New `DockerExecutor` tests cover all public methods
- [ ] Backward compatibility layer works identically to old implementation
- [ ] Docker client caching still functions correctly
- [ ] Container labels are preserved exactly
- [ ] Error handling maintains existing behavior

## Error Handling Updates
```python
# Replace generic exceptions with executor-specific ones
try:
    client = docker.from_env()
except docker.errors.DockerException as e:
    raise ExecutorConnectionError(f"Cannot connect to Docker: {e}")

# Use early returns instead of nested conditions
def _validate_job(self, job: ContainerJob) -> None:
    if not job:
        raise ExecutorError("Job cannot be None")
    
    if job.status != 'pending':
        raise ExecutorError(f"Job must be pending, got {job.status}")
    
    if not job.template:
        raise ExecutorError("Job must have a template")
```

## Decision Points
- **Method Signatures**: Keep existing signatures or standardize to interface? → Keep existing for compatibility
- **Client Caching**: Keep per-executor or global? → Keep per-executor for isolation
- **Error Types**: Map Docker errors to executor errors? → Yes, for abstraction

## Success Criteria
- [ ] `DockerExecutor` class implements all `ContainerExecutor` methods
- [ ] All existing Docker functionality preserved
- [ ] Backward compatibility maintained through `docker_service.py`
- [ ] No breaking changes to existing API
- [ ] All tests pass
- [ ] Code follows ruff formatting standards
- [ ] Container labels and metadata preserved
- [ ] Performance characteristics unchanged

## Next Task Preparation
After completing this task, Task 003 will enhance the data models to support multi-executor tracking. Key information to pass forward:

- `DockerExecutor` handles `execution_id` as Docker container ID
- Existing Docker labels pattern should be maintained
- Backward compatibility patterns established
- Error handling conversion from Docker exceptions to executor exceptions