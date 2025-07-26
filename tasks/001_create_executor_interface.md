# Task 001: Create Container Executor Interface

## Objective
Create the abstract base class that defines the contract for all container execution backends (Docker, Cloud Run, Fargate, etc.). This interface will be the foundation for the multi-cloud abstraction layer.

## Git Strategy  
- Branch: `task-001-executor-interface`
- Commit pattern: "Add [component]: [what it does]"
- First commit: "Add ContainerExecutor abstract base class"

## Prerequisites
- Current fire-and-monitor architecture working
- Understanding of existing DockerService methods
- Familiarity with Python ABC pattern

## Implementation Steps

1. [ ] Create new file `container_manager/executors/__init__.py`
2. [ ] Create new file `container_manager/executors/base.py` with ContainerExecutor ABC
3. [ ] Define abstract methods with proper type hints and docstrings
4. [ ] Add custom exception classes for executor-specific errors
5. [ ] Create simple factory function for executor instantiation
6. [ ] Add comprehensive docstrings with usage examples
7. [ ] Run ruff format and check before committing

## Code Quality Requirements
- Cyclomatic complexity < 5 per method (interface methods should be simple)
- No nested try/except blocks in interface definition
- Use early returns in factory function
- Clear type hints for all method signatures
- Comprehensive docstrings with examples

## Detailed Implementation

### File Structure
```
container_manager/
├── executors/
│   ├── __init__.py          # Factory function and imports
│   ├── base.py              # ContainerExecutor ABC
│   └── exceptions.py        # Custom exception classes
```

### ContainerExecutor Interface
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from container_manager.models import ContainerJob

class ContainerExecutor(ABC):
    """Abstract interface for container execution backends"""
    
    def __init__(self, config: Dict):
        """Initialize executor with configuration"""
        self.config = config
        self.name = self.__class__.__name__.replace('Executor', '').lower()
    
    @abstractmethod
    def launch_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """
        Launch a container job.
        
        Args:
            job: ContainerJob instance to execute
            
        Returns:
            Tuple of (success: bool, execution_id_or_error: str)
            
        Example:
            success, execution_id = executor.launch_job(job)
            if success:
                job.external_execution_id = execution_id
        """
        pass
    
    @abstractmethod
    def check_status(self, execution_id: str) -> str:
        """
        Check the status of a running execution.
        
        Args:
            execution_id: Provider-specific execution identifier
            
        Returns:
            Status string: 'running', 'exited', 'failed', 'not-found'
        """
        pass
    
    @abstractmethod
    def get_logs(self, execution_id: str) -> Tuple[str, str]:
        """
        Retrieve logs from completed or running execution.
        
        Args:
            execution_id: Provider-specific execution identifier
            
        Returns:
            Tuple of (stdout: str, stderr: str)
        """
        pass
    
    @abstractmethod
    def harvest_job(self, job: ContainerJob) -> bool:
        """
        Collect final results and update job status.
        
        Args:
            job: ContainerJob instance to harvest
            
        Returns:
            bool: True if harvesting successful
        """
        pass
    
    @abstractmethod
    def cleanup(self, execution_id: str) -> bool:
        """
        Force cleanup of execution resources.
        
        Args:
            execution_id: Provider-specific execution identifier
            
        Returns:
            bool: True if cleanup successful
        """
        pass
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Return executor capabilities.
        
        Returns:
            Dict with capability flags like:
            {'supports_resource_limits': True, 'supports_networking': False}
        """
        return {
            'supports_resource_limits': False,
            'supports_networking': False,
            'supports_persistent_storage': False,
            'supports_secrets': False,
        }
```

### Exception Classes
```python
class ExecutorError(Exception):
    """Base exception for executor-related errors"""
    pass

class ExecutorConnectionError(ExecutorError):
    """Raised when executor cannot connect to backend service"""
    pass

class ExecutorConfigurationError(ExecutorError):
    """Raised when executor configuration is invalid"""
    pass

class ExecutorResourceError(ExecutorError):
    """Raised when executor lacks resources to execute job"""
    pass

class ExecutorAuthenticationError(ExecutorError):
    """Raised when executor authentication fails"""
    pass
```

### Factory Function
```python
def get_executor(executor_type: str, config: Optional[Dict] = None) -> ContainerExecutor:
    """
    Factory function to create executor instances.
    
    Args:
        executor_type: Type of executor ('docker', 'cloudrun', etc.)
        config: Optional configuration override
        
    Returns:
        ContainerExecutor instance
        
    Raises:
        ExecutorConfigurationError: If executor type unknown or config invalid
    """
    if not executor_type:
        raise ExecutorConfigurationError("executor_type cannot be empty")
    
    # Import executors locally to avoid circular imports
    if executor_type == 'docker':
        from .docker import DockerExecutor
        return DockerExecutor(config or {})
    
    if executor_type == 'cloudrun':
        from .cloudrun import CloudRunExecutor  
        return CloudRunExecutor(config or {})
    
    if executor_type == 'mock':
        from .mock import MockExecutor
        return MockExecutor(config or {})
    
    raise ExecutorConfigurationError(f"Unknown executor type: {executor_type}")
```

## Testing Criteria
- [ ] Import `ContainerExecutor` successfully
- [ ] Cannot instantiate abstract base class directly
- [ ] Factory function raises appropriate errors for invalid inputs
- [ ] All abstract methods are properly defined with type hints
- [ ] Exception hierarchy is correct
- [ ] Docstrings are comprehensive and include examples

## Decision Points
- **Interface Design**: Should `launch_job` be async? Current sync approach matches existing patterns
- **Error Handling**: Should methods return Results/Optional or raise exceptions? Using tuple returns for launch_job to match existing patterns
- **Configuration**: Should config be passed to constructor or methods? Constructor keeps it simple

## Success Criteria
- [ ] Abstract base class `ContainerExecutor` created with all required methods
- [ ] Custom exception classes defined in hierarchy
- [ ] Factory function creates appropriate executor instances
- [ ] All code follows ruff formatting standards
- [ ] Comprehensive docstrings with usage examples
- [ ] No cyclomatic complexity warnings
- [ ] Ready for concrete implementations to inherit from interface

## Next Task Preparation
After completing this task, the next task will be `002_refactor_docker_service.md` which will extract existing Docker functionality into a `DockerExecutor` that implements this interface.

Key information to pass forward:
- Interface method signatures and expected behavior
- Exception classes available for error handling
- Factory function pattern for creating executors
- Configuration pattern established in constructor