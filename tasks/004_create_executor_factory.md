# Task 004: Create Executor Factory and Routing Logic

## Objective
Create a factory class that intelligently routes jobs to appropriate executors based on configuration rules, resource requirements, and availability. This central component will manage executor selection and instantiation.

## Git Strategy  
- Branch: `task-004-executor-factory`
- Commit pattern: "Add [component]: [functionality]"
- Commits: "Add ExecutorFactory class", "Add routing rules engine", "Add capacity management"

## Prerequisites
- Task 001 completed (ContainerExecutor interface)
- Task 002 completed (DockerExecutor implementation)
- Task 003 completed (Enhanced data models)
- Understanding of Django settings configuration

## Implementation Steps

1. [ ] Create `container_manager/executors/factory.py`
2. [ ] Implement `ExecutorFactory` class with routing logic
3. [ ] Create routing rules configuration system
4. [ ] Add capacity and availability checking
5. [ ] Implement fallback mechanisms for executor failures
6. [ ] Add caching for executor instances
7. [ ] Create comprehensive tests for routing decisions
8. [ ] Run ruff format and check before committing

## Code Quality Requirements
- Use early returns for routing decisions
- Keep routing logic complexity low (< 10 per method)
- No nested try/except blocks
- Clear separation between routing and instantiation
- Comprehensive logging for routing decisions

## Detailed Implementation

### ExecutorFactory Class

```python
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache

from ..models import ContainerJob, DockerHost
from .base import ContainerExecutor
from .exceptions import ExecutorConfigurationError, ExecutorResourceError

logger = logging.getLogger(__name__)

class ExecutorFactory:
    """Factory for creating and routing to appropriate container executors"""
    
    def __init__(self):
        self._executor_cache: Dict[str, ContainerExecutor] = {}
        self._routing_rules = self._load_routing_rules()
        self._executor_configs = self._load_executor_configs()
    
    def route_job(self, job: ContainerJob) -> str:
        """
        Determine the best executor type for a job.
        
        Args:
            job: ContainerJob to route
            
        Returns:
            str: Executor type ('docker', 'cloudrun', etc.)
            
        Raises:
            ExecutorResourceError: If no suitable executor available
        """
        # Check preferred executor first
        if job.preferred_executor:
            if self._is_executor_available(job.preferred_executor):
                return job.preferred_executor
            logger.warning(f"Preferred executor {job.preferred_executor} not available for job {job.id}")
        
        # Apply routing rules in order
        for rule in self._routing_rules:
            if self._evaluate_rule(rule, job):
                executor_type = rule['executor']
                if self._is_executor_available(executor_type):
                    job.routing_reason = rule.get('reason', f'Matched rule: {rule["condition"]}')
                    return executor_type
                    
        # Default fallback to docker
        if self._is_executor_available('docker'):
            job.routing_reason = 'Default fallback to docker'
            return 'docker'
            
        # No executors available
        available_executors = self.get_available_executors()
        raise ExecutorResourceError(
            f"No suitable executors available for job {job.id}. "
            f"Available: {available_executors}"
        )
    
    def get_executor(self, job: ContainerJob) -> ContainerExecutor:
        """
        Get executor instance for a job.
        
        Args:
            job: ContainerJob with executor_type set
            
        Returns:
            ContainerExecutor: Configured executor instance
        """
        executor_type = job.executor_type
        if not executor_type:
            raise ExecutorConfigurationError("Job must have executor_type set")
        
        # Check cache first
        cache_key = f"executor_{executor_type}_{job.docker_host.id if job.docker_host else 'default'}"
        
        if cache_key in self._executor_cache:
            return self._executor_cache[cache_key]
        
        # Create new executor instance
        executor = self._create_executor(executor_type, job)
        self._executor_cache[cache_key] = executor
        
        return executor
    
    def get_available_executors(self) -> List[str]:
        """Get list of currently available executor types"""
        available = []
        
        for executor_type in self._executor_configs.keys():
            if self._is_executor_available(executor_type):
                available.append(executor_type)
                
        return available
    
    def get_executor_capacity(self, executor_type: str) -> Dict[str, int]:
        """Get capacity information for executor type"""
        if executor_type == 'docker':
            hosts = DockerHost.objects.filter(
                executor_type='docker',
                is_active=True
            )
            
            total_capacity = sum(host.max_concurrent_jobs for host in hosts)
            current_usage = sum(host.current_job_count for host in hosts)
            
            return {
                'total_capacity': total_capacity,
                'current_usage': current_usage,
                'available_slots': total_capacity - current_usage,
            }
        
        # For cloud executors, capacity is typically unlimited or very high
        return {
            'total_capacity': 1000,  # Cloud services have high limits
            'current_usage': 0,      # We don't track cloud usage yet
            'available_slots': 1000,
        }
    
    def _create_executor(self, executor_type: str, job: ContainerJob) -> ContainerExecutor:
        """Create executor instance with appropriate configuration"""
        if executor_type not in self._executor_configs:
            raise ExecutorConfigurationError(f"Unknown executor type: {executor_type}")
        
        config = self._executor_configs[executor_type].copy()
        
        # Add job-specific configuration
        if job.docker_host:
            config['docker_host'] = job.docker_host
            
        # Import and instantiate executor
        if executor_type == 'docker':
            from .docker import DockerExecutor
            return DockerExecutor(config)
            
        if executor_type == 'cloudrun':
            from .cloudrun import CloudRunExecutor
            return CloudRunExecutor(config)
            
        if executor_type == 'mock':
            from .mock import MockExecutor
            return MockExecutor(config)
            
        raise ExecutorConfigurationError(f"Executor type {executor_type} not implemented")
    
    def _is_executor_available(self, executor_type: str) -> bool:
        """Check if executor type is available for new jobs"""
        if executor_type not in self._executor_configs:
            return False
            
        config = self._executor_configs[executor_type]
        if not config.get('enabled', True):
            return False
            
        if executor_type == 'docker':
            # Check Docker host availability
            available_hosts = DockerHost.objects.filter(
                executor_type='docker',
                is_active=True
            )
            
            for host in available_hosts:
                if host.is_available():
                    return True
            return False
            
        # For cloud executors, check configuration and credentials
        return self._check_cloud_executor_health(executor_type)
    
    def _check_cloud_executor_health(self, executor_type: str) -> bool:
        """Check if cloud executor is healthy and accessible"""
        # Use cache to avoid frequent health checks
        cache_key = f"executor_health_{executor_type}"
        health_status = cache.get(cache_key)
        
        if health_status is not None:
            return health_status
            
        # Perform actual health check
        try:
            executor = self._create_executor(executor_type, None)
            # TODO: Add health check method to executor interface
            health_status = True
        except Exception as e:
            logger.warning(f"Health check failed for {executor_type}: {e}")
            health_status = False
            
        # Cache result for 5 minutes
        cache.set(cache_key, health_status, 300)
        return health_status
    
    def _evaluate_rule(self, rule: Dict, job: ContainerJob) -> bool:
        """Evaluate if a routing rule matches a job"""
        condition = rule.get('condition', '')
        
        try:
            # Create evaluation context
            context = {
                'job': job,
                'template': job.template,
                'user': job.created_by,
                'memory_mb': job.template.memory_limit or 0,
                'cpu_cores': job.template.cpu_limit or 0,
                'timeout_seconds': job.template.timeout_seconds,
            }
            
            # Evaluate condition (simple string evaluation for now)
            # TODO: Consider using a safer expression evaluator
            return eval(condition, {"__builtins__": {}}, context)
            
        except Exception as e:
            logger.warning(f"Failed to evaluate routing rule '{condition}': {e}")
            return False
    
    def _load_routing_rules(self) -> List[Dict]:
        """Load routing rules from Django settings"""
        return getattr(settings, 'EXECUTOR_ROUTING_RULES', [
            {
                'condition': 'memory_mb > 8192',
                'executor': 'fargate',
                'reason': 'High memory requirement (>8GB)'
            },
            {
                'condition': 'timeout_seconds > 3600',
                'executor': 'fargate', 
                'reason': 'Long-running job (>1 hour)'
            },
            {
                'condition': 'template.name.startswith("batch-")',
                'executor': 'cloudrun',
                'reason': 'Batch processing template'
            },
            {
                'condition': 'user and user.groups.filter(name="premium").exists()',
                'executor': 'cloudrun',
                'reason': 'Premium user priority'
            }
        ])
    
    def _load_executor_configs(self) -> Dict[str, Dict]:
        """Load executor configurations from Django settings"""
        return getattr(settings, 'CONTAINER_EXECUTORS', {
            'docker': {
                'enabled': True,
                'default': True,
            },
            'cloudrun': {
                'enabled': False,
                'project': 'my-project',
                'region': 'us-central1',
            },
            'fargate': {
                'enabled': False,
                'cluster': 'default',
            },
            'mock': {
                'enabled': True,
            }
        })


# Global factory instance
executor_factory = ExecutorFactory()
```

### Routing Rules Configuration

#### Settings Example
```python
# settings.py
CONTAINER_EXECUTORS = {
    'docker': {
        'enabled': True,
        'default': True,
    },
    'cloudrun': {
        'enabled': True,
        'project': 'my-gcp-project',
        'region': 'us-central1',
        'service_account': 'container-runner@project.iam.gserviceaccount.com',
    },
    'fargate': {
        'enabled': False,  # Not implemented yet
        'cluster': 'container-jobs',
        'subnets': ['subnet-123', 'subnet-456'],
    },
    'mock': {
        'enabled': True,  # For testing
    }
}

EXECUTOR_ROUTING_RULES = [
    {
        'condition': 'memory_mb > 8192',
        'executor': 'fargate',
        'reason': 'High memory requirement (>8GB)',
        'priority': 1,
    },
    {
        'condition': 'cpu_cores > 4.0',
        'executor': 'fargate', 
        'reason': 'High CPU requirement (>4 cores)',
        'priority': 2,
    },
    {
        'condition': 'timeout_seconds > 3600',
        'executor': 'cloudrun',
        'reason': 'Long-running job (>1 hour)',
        'priority': 3,
    },
    {
        'condition': 'template.name.startswith("ml-")',
        'executor': 'fargate',
        'reason': 'Machine learning workload',
        'priority': 4,
    },
    {
        'condition': 'template.name.startswith("batch-")',
        'executor': 'cloudrun',
        'reason': 'Batch processing template',
        'priority': 5,
    },
    {
        'condition': 'user and user.groups.filter(name="premium").exists()',
        'executor': 'cloudrun',
        'reason': 'Premium user priority',
        'priority': 6,
    },
    {
        'condition': 'template.name.startswith("test-")',
        'executor': 'mock',
        'reason': 'Test template',
        'priority': 7,
    }
]
```

### Integration with Management Commands

#### Update Process Container Jobs
```python
# In process_container_jobs.py
from container_manager.executors.factory import executor_factory

def process_pending_jobs(self, host_filter: Optional[str] = None, max_jobs: int = 10) -> int:
    """Launch pending jobs using executor factory"""
    
    queryset = ContainerJob.objects.filter(status='pending').select_related(
        'template', 'docker_host', 'created_by'
    ).order_by('created_at')
    
    # Apply host filter if specified
    if host_filter:
        queryset = queryset.filter(docker_host__name=host_filter)
    
    pending_jobs = list(queryset[:max_jobs])
    if not pending_jobs:
        return 0
    
    launched = 0
    for job in pending_jobs:
        if self.should_stop:
            break
            
        try:
            # Route job to appropriate executor
            executor_type = executor_factory.route_job(job)
            job.executor_type = executor_type
            job.save()
            
            # Get executor and launch job
            executor = executor_factory.get_executor(job)
            success, execution_id = executor.launch_job(job)
            
            if success:
                job.set_execution_identifier(execution_id)
                job.save()
                launched += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Launched job {job.id} on {executor_type}: {execution_id}'
                    )
                )
            else:
                self.mark_job_failed(job, f'Launch failed: {execution_id}')
                
        except Exception as e:
            logger.error(f'Failed to launch job {job.id}: {e}')
            self.mark_job_failed(job, str(e))
    
    return launched
```

## Testing Criteria
- [ ] Factory routes jobs to correct executors based on rules
- [ ] Preferred executor takes precedence over routing rules
- [ ] Capacity checking prevents overloading executors
- [ ] Fallback mechanisms work when preferred executor unavailable
- [ ] Caching reduces executor instantiation overhead
- [ ] Configuration loading works with Django settings
- [ ] Health checks prevent routing to unhealthy executors

## Routing Rule Examples
```python
# Test cases for routing logic
test_cases = [
    {
        'job': 'high_memory_job',  # 16GB memory
        'expected_executor': 'fargate',
        'reason': 'High memory requirement'
    },
    {
        'job': 'premium_user_job',
        'expected_executor': 'cloudrun', 
        'reason': 'Premium user priority'
    },
    {
        'job': 'batch_processing_job',
        'expected_executor': 'cloudrun',
        'reason': 'Batch processing template'
    },
    {
        'job': 'regular_job',
        'expected_executor': 'docker',
        'reason': 'Default fallback'
    }
]
```

## Decision Points
- **Rule Evaluation**: Use `eval()` or build expression parser? → Start with `eval()` for simplicity, plan parser later
- **Health Checking**: How often to check cloud executor health? → Cache for 5 minutes, configurable
- **Executor Caching**: Per-job or global caching? → Per-host caching for isolation

## Success Criteria
- [ ] `ExecutorFactory` class routes jobs intelligently
- [ ] Configuration-driven routing rules work correctly
- [ ] Capacity management prevents resource exhaustion
- [ ] Fallback mechanisms handle executor failures gracefully
- [ ] Caching improves performance without breaking isolation
- [ ] Integration with management commands is seamless
- [ ] All routing decisions are logged for debugging
- [ ] Health checking prevents routing to failed executors

## Next Task Preparation
After completing this task, Task 005 will update the management commands to use the factory pattern. Key information to pass forward:

- `executor_factory.route_job()` determines executor type
- `executor_factory.get_executor()` creates configured instances
- Routing decisions are logged in `job.routing_reason`
- Capacity management prevents overloading
- Health checking ensures reliability