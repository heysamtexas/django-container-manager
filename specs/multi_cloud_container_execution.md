# Multi-Cloud Container Execution Abstraction

## Vision Statement

Transform the Django container management system from Docker-specific to cloud-agnostic, enabling job execution across local Docker, Google Cloud Run, AWS Fargate, Scaleway Container Instances, and other container platforms through a unified interface.

## Architecture Overview

### Core Abstraction Layer

**Container Executor Interface**: Abstract base class defining the contract for all execution backends:

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

class ContainerExecutor(ABC):
    """Abstract interface for container execution backends"""
    
    @abstractmethod
    def launch_job(self, job: ContainerJob) -> Tuple[bool, str]:
        """Launch job, return (success, execution_id)"""
        
    @abstractmethod
    def check_status(self, execution_id: str) -> str:
        """Return: 'running', 'exited', 'failed', 'not-found'"""
        
    @abstractmethod
    def get_logs(self, execution_id: str) -> Tuple[str, str]:
        """Return (stdout, stderr) logs"""
        
    @abstractmethod
    def harvest_job(self, job: ContainerJob) -> bool:
        """Collect final results and cleanup"""
        
    @abstractmethod
    def cleanup(self, execution_id: str) -> bool:
        """Force cleanup of execution resources"""
```

### Implementation Strategy

**Design Principles:**
- Low cyclomatic complexity with early returns
- No nested try/except blocks
- Cloud provider failures degrade gracefully
- Each executor is completely independent
- Configuration-driven routing decisions

**Error Handling Pattern:**
```python
def operation(self):
    if not precondition:
        return False, "precondition failed"
    
    try:
        result = api_call()
    except SpecificError:
        return False, "specific error message"
    except Exception as e:
        return False, f"unexpected error: {e}"
    
    return True, result
```

## Concrete Executor Implementations

### 1. DockerExecutor (Refactored Current Implementation)

**Responsibilities:**
- Wrap existing DockerService functionality
- Handle local and remote Docker daemon connections
- Maintain backward compatibility

**Key Refactoring:**
- Extract Docker-specific logic from current `docker_service.py`
- Implement ContainerExecutor interface
- Preserve all existing Docker labels and functionality

### 2. CloudRunExecutor

**Responsibilities:**
- Google Cloud Run job execution via REST API
- Handle authentication (service account, ADC)
- Map Django job parameters to Cloud Run job specs

**Cloud Run Specifics:**
- Uses Cloud Run Jobs API (not Services)
- Supports environment variables, resource limits
- Automatic cleanup via TTL
- Logs accessible via Cloud Logging API

### 3. FargateExecutor (Future)

**Responsibilities:**
- AWS Fargate task execution via boto3
- ECS task definition management
- CloudWatch logs integration

### 4. ScalewayExecutor (Future)

**Responsibilities:**
- Scaleway Container Instances API
- Cost-effective execution option
- European data residency

### 5. MockExecutor (Testing)

**Responsibilities:**
- In-memory job simulation
- Deterministic behavior for tests
- No external dependencies

## Data Model Enhancements

### Enhanced ContainerJob Model

**New Fields:**
```python
class ContainerJob(models.Model):
    # Existing fields...
    
    # Multi-cloud execution tracking
    executor_type = models.CharField(
        max_length=50,
        default='docker',
        choices=[
            ('docker', 'Docker'),
            ('cloudrun', 'Google Cloud Run'),
            ('fargate', 'AWS Fargate'),
            ('scaleway', 'Scaleway Containers'),
            ('mock', 'Mock (Testing)'),
        ]
    )
    
    external_execution_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="Cloud provider's execution/job ID"
    )
    
    executor_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific data (regions, URLs, etc.)"
    )
    
    # Routing preferences
    preferred_executor = models.CharField(
        max_length=50,
        blank=True,
        help_text="Preferred executor for this job"
    )
```

### Enhanced DockerHost Model

**Purpose Evolution:**
- Rename to `ExecutionHost` or keep `DockerHost` for backward compatibility
- Support multiple executor types per host entry
- Add cloud provider credentials/configuration

**New Fields:**
```python
class DockerHost(models.Model):
    # Existing fields...
    
    # Multi-executor support
    executor_type = models.CharField(max_length=50, default='docker')
    executor_config = models.JSONField(
        default=dict,
        help_text="Executor-specific configuration (credentials, regions, etc.)"
    )
    
    # Resource and cost management
    cost_per_hour = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Cost tracking for cloud providers"
    )
    
    max_concurrent_jobs = models.PositiveIntegerField(
        default=10,
        help_text="Maximum concurrent jobs for this executor"
    )
```

## Job Routing and Execution Logic

### Executor Factory Pattern

**Central Routing:**
```python
class ExecutorFactory:
    def get_executor(self, job: ContainerJob) -> ContainerExecutor:
        # 1. Check job.preferred_executor
        # 2. Apply routing rules based on template, user, resource needs
        # 3. Check executor availability and capacity
        # 4. Return appropriate executor instance
        
    def get_available_executors(self) -> List[str]:
        # Return list of currently available executor types
        
    def route_job(self, job: ContainerJob) -> str:
        # Determine best executor for job without creating instance
```

**Routing Rules Examples:**
```python
# Route by resource requirements
if job.template.memory_limit > 8192:  # > 8GB
    return 'fargate'  # Better for high-memory workloads

# Route by user preferences  
if job.created_by.groups.filter(name='premium').exists():
    return 'cloudrun'  # Faster cold starts

# Route by template characteristics
if job.template.name.startswith('batch-'):
    return 'scaleway'  # Cost-effective for batch jobs
    
# Default fallback
return 'docker'
```

### Execution Flow Enhancement

**Updated Process Container Jobs Logic:**
```python
def process_jobs_with_routing():
    for job in pending_jobs:
        if should_stop:
            break
            
        executor_type = factory.route_job(job)
        if not executor_type:
            mark_job_failed(job, "No available executors")
            continue
            
        job.executor_type = executor_type
        job.save()
        
        executor = factory.get_executor(job)
        success, execution_id = executor.launch_job(job)
        
        if success:
            job.external_execution_id = execution_id
            job.save()
        else:
            mark_job_failed(job, f"Launch failed: {execution_id}")
```

## Configuration Schema

### Settings Structure

```python
# settings.py
CONTAINER_EXECUTORS = {
    'docker': {
        'class': 'container_manager.executors.DockerExecutor',
        'hosts': ['local-docker', 'remote-docker-1'],
        'default': True,
    },
    'cloudrun': {
        'class': 'container_manager.executors.CloudRunExecutor',
        'project': 'my-gcp-project',
        'region': 'us-central1',
        'service_account': 'container-runner@project.iam.gserviceaccount.com',
        'enabled': True,
    },
    'fargate': {
        'class': 'container_manager.executors.FargateExecutor',
        'cluster': 'container-jobs',
        'subnets': ['subnet-123', 'subnet-456'],
        'security_groups': ['sg-789'],
        'enabled': False,  # Not implemented yet
    },
    'mock': {
        'class': 'container_manager.executors.MockExecutor',
        'enabled': True,  # For testing
    }
}

# Routing rules
EXECUTOR_ROUTING_RULES = [
    {
        'condition': 'template.memory_limit > 8192',
        'executor': 'fargate',
        'reason': 'High memory requirement'
    },
    {
        'condition': 'user.groups.filter(name="premium").exists()',
        'executor': 'cloudrun', 
        'reason': 'Premium user'
    },
    {
        'condition': 'template.name.startswith("batch-")',
        'executor': 'scaleway',
        'reason': 'Batch processing'
    }
]
```

## Task-Driven Development Plan

### Task Structure

Each task is a discrete, implementable unit with clear success criteria:

**File Naming:** `tasks/NNN_description.md` (e.g., `tasks/001_create_executor_interface.md`)

**Task Template:**
```markdown
# Task: [Description]

## Objective
Clear, testable goal statement

## Git Strategy  
- Branch: `task-NNN-description`
- Commit pattern: "Add [component]: [what it does]"

## Prerequisites
- List of completed tasks
- Required setup/configuration

## Implementation Steps
1. [ ] Step with early return pattern example
2. [ ] Step with specific ruff compliance requirement  
3. [ ] Step with test addition requirement

## Code Quality Requirements
- Cyclomatic complexity < 10 per function
- No nested try/except blocks
- Use early returns vs deep nesting
- Run ruff format/check before commits

## Testing Criteria
- [ ] Unit tests pass
- [ ] Integration tests added
- [ ] Mock usage documented

## Decision Points
- **Point 1:** When to ask user about API design choice
- **Point 2:** When to confirm cloud provider priorities

## Success Criteria
Measurable definition of completion
```

### Development Task Sequence

**Phase 1: Foundation (Tasks 001-005)**
1. `001_create_executor_interface.md` - Abstract base class
2. `002_refactor_docker_service.md` - Extract into DockerExecutor
3. `003_enhance_data_models.md` - Add multi-cloud fields
4. `004_create_executor_factory.md` - Central routing logic
5. `005_update_management_commands.md` - Use factory pattern

**Phase 2: Cloud Executors (Tasks 006-010)**  
6. `006_implement_mock_executor.md` - Testing implementation
7. `007_implement_cloudrun_executor.md` - Google Cloud Run
8. `008_add_routing_rules.md` - Configuration-driven routing
9. `009_add_cost_tracking.md` - Resource usage monitoring
10. `010_enhance_admin_interface.md` - Multi-cloud visibility

**Phase 3: Advanced Features (Tasks 011-015)**
11. `011_add_fallback_logic.md` - Executor failure handling
12. `012_implement_bulk_operations.md` - Cross-executor job management
13. `013_add_performance_monitoring.md` - Executor performance tracking
14. `014_create_migration_tools.md` - Move jobs between executors
15. `015_add_integration_tests.md` - End-to-end testing

**Phase 4: Documentation & Polish (Tasks 016-020)**
16. `016_update_documentation.md` - User guide for multi-cloud
17. `017_create_deployment_guide.md` - Production setup
18. `018_add_troubleshooting_guide.md` - Common issues
19. `019_performance_optimization.md` - Bottleneck analysis
20. `020_prepare_library_extraction.md` - Standalone package prep

### Self-Direction Protocol

**Autonomous Development Guidelines:**

1. **Start Each Task:**
   - Create feature branch: `git checkout -b task-NNN-description`
   - Read task file completely before coding
   - Understand success criteria and decision points

2. **During Implementation:**
   - Follow early return patterns religiously
   - Commit after each logical unit (every 30-60 mins)
   - Run `uv run ruff format . && uv run ruff check --fix .` before commits
   - Use descriptive commit messages: `"Add CloudRunExecutor.launch_job method"`

3. **Code Quality Enforcement:**
   - Keep functions under 10 lines when possible
   - Prefer guard clauses to nested conditions
   - No method should handle more than one concern
   - Extract complex logic into helper methods

4. **Testing Requirements:**
   - Add tests for each new public method
   - Use mocks for external APIs (Cloud Run, etc.)
   - Run `uv run python manage.py test` before task completion
   - Add docstring examples for complex methods

5. **Decision Points:**
   - Stop and ask user when task specifies decision point
   - Document assumptions made when proceeding autonomously
   - Create checkpoint commits before exploring alternatives

6. **Task Completion:**
   - Verify all success criteria met
   - Run full test suite: `uv run python manage.py test`
   - Merge to main: `git checkout main && git merge task-NNN-description`
   - Update progress in next task file

**Git Strategy Throughout:**
- Use `git stash` liberally when exploring alternatives
- Create checkpoint commits before risky refactoring
- Tag major milestones: `git tag milestone-phase1-complete`
- Use descriptive branch names that match task numbers

**Error Recovery:**
- `git checkout .` to discard changes and restart step
- `git reset --hard HEAD~1` to undo last commit
- `git checkout main && git branch -D task-NNN` to abandon task
- Always communicate blockers rather than forcing bad solutions

## Integration with Existing System

### Backward Compatibility Strategy

**Phase 1: Parallel Implementation**
- Keep existing `docker_service.py` functional
- Add new executor system alongside
- Gradual migration of functionality

**Phase 2: Feature Flag Migration**
- Add setting: `USE_MULTI_CLOUD_EXECUTORS = False`
- Allow incremental adoption
- Test new system in development first

**Phase 3: Complete Migration**
- Remove old Docker-specific code
- Update all management commands
- Ensure admin interface supports all executors

### Testing Strategy

**Unit Testing:**
- Mock all external APIs (Docker, Cloud Run, etc.)
- Test each executor independently
- Verify routing logic with various job configurations

**Integration Testing:**
- End-to-end job execution with MockExecutor
- Cross-executor job migration
- Failure recovery scenarios

**Performance Testing:**
- Executor selection overhead
- Concurrent job handling across multiple executors
- Resource usage monitoring

## Success Metrics

### Technical Metrics
- Zero downtime migration from Docker-only to multi-cloud
- <100ms overhead for executor selection per job
- 99.9% success rate for job routing decisions
- All existing functionality preserved

### Business Metrics  
- Ability to leverage multiple cloud providers simultaneously
- Cost optimization through intelligent executor routing
- Improved job throughput via cloud auto-scaling
- Reduced operational complexity despite multi-cloud setup

### Developer Experience Metrics
- Django admin interface works seamlessly with all executors
- Management commands support all executor types
- Troubleshooting complexity remains low
- Documentation clarity for multi-cloud setup

## Future Extensions

### Additional Executors
- **Azure Container Instances**: Microsoft cloud option
- **DigitalOcean App Platform**: Developer-friendly option
- **Kubernetes Jobs**: Enterprise container orchestration
- **Lambda/Functions**: For lightweight, short-running tasks

### Advanced Features
- **Cross-cloud job migration**: Move running jobs between executors
- **Cost optimization**: Automatic executor selection based on pricing
- **Geographic routing**: Route jobs based on data locality
- **Hybrid execution**: Split large jobs across multiple clouds

### Library Extraction
- Package as standalone Django app: `django-multi-cloud-containers`
- Plugin architecture for custom executors
- Configuration management tools
- Monitoring and observability integrations

## Risk Mitigation

### Technical Risks
- **Cloud API changes**: Version pin and test against API updates
- **Authentication complexity**: Centralized credential management
- **Network failures**: Robust retry and fallback mechanisms
- **Cost overruns**: Spending limits and monitoring alerts

### Operational Risks
- **Vendor lock-in**: Maintain local Docker as always-available fallback
- **Complexity growth**: Keep configuration simple, avoid over-engineering
- **Debugging difficulty**: Centralized logging across all executors
- **Team knowledge**: Document operational procedures thoroughly

### Migration Risks
- **Data loss**: Comprehensive backup strategy before migrations
- **Downtime**: Blue-green deployment with rollback capability
- **Compatibility issues**: Extensive testing with existing templates
- **Performance regression**: Benchmark before and after migration

This specification provides a comprehensive roadmap for transforming the Django container management system into a cloud-agnostic, multi-executor platform while maintaining the simplicity and Django integration that makes it valuable.