# Documentation Task: API Reference Creation

**Priority:** Medium-High
**Component:** API Documentation
**Estimated Effort:** High
**Current Status:** Missing - No API documentation exists

## Task Summary
Create comprehensive API.md documenting all models, views, and programmatic interfaces. Users need to understand how to interact with the system programmatically, but currently have no reference for the data models, API endpoints, or Python interfaces.

## Missing API Documentation
- No model documentation (fields, methods, relationships)
- No view/endpoint documentation (if REST API exists)
- No Python API usage examples
- No data structure explanations
- No integration patterns documented

## Specific Content Required

### 1. API Overview
- **System architecture**: Models, executors, management commands
- **Access methods**: Django admin, Python API, CLI commands, REST endpoints (if available)
- **Authentication**: Required permissions and access patterns
- **Data flow**: How data moves through the system
- **Key concepts**: Jobs, executions, hosts, environments

### 2. Core Models Documentation

#### ContainerJob Model
```python
class ContainerJob(models.Model):
    """
    Represents a containerized job execution request.
    
    Core model for managing Docker container jobs with full lifecycle tracking.
    """
```
- **Fields documentation**:
  - `image`: Docker image specification and format requirements
  - `command`: Command execution format (shell vs exec)
  - `status`: Job status lifecycle and valid transitions
  - `docker_host`: ExecutorHost relationship and selection
  - `environment_template`: Environment variable template usage
  - `memory_limit`: Resource limit specification
  - `cpu_limit`: CPU allocation and measurement
  - `created_at`, `started_at`, `finished_at`: Timestamp tracking
  - `exit_code`: Process exit code interpretation
- **Methods documentation**:
  - `launch()`: Job execution initiation
  - `get_status()`: Current job status retrieval
  - `get_logs()`: Log data access
  - `harvest()`: Final result collection
  - `get_all_environment_variables()`: Environment variable resolution
- **Properties documentation**:
  - `is_terminal_status`: Status completion checking
  - `runtime_duration`: Execution time calculation
  - `resource_utilization`: Resource usage metrics

#### ExecutorHost Model
```python
class ExecutorHost(models.Model):
    """
    Represents an execution environment (Docker daemon, Cloud Run, etc.).
    
    Manages connection details and capabilities for job execution hosts.
    """
```
- **Fields documentation**:
  - `name`: Human-readable identifier
  - `executor_type`: Executor backend selection
  - `connection_string`: Connection configuration format
  - `is_active`: Host availability status
  - `last_health_check`: Health monitoring timestamps
- **Methods documentation**:
  - `get_executor()`: Executor instance creation
  - `health_check()`: Host connectivity verification
  - `get_capacity()`: Resource availability checking
- **Executor types**: Docker, CloudRun, Mock configurations

#### EnvironmentVariableTemplate Model
```python
class EnvironmentVariableTemplate(models.Model):
    """
    Template for environment variable sets used across multiple jobs.
    
    Provides reusable environment configurations for consistent job execution.
    """
```
- **Fields documentation**:
  - `name`: Template identifier
  - `environment_variables_text`: Variable definition format
  - `description`: Template usage documentation
- **Methods documentation**:
  - `get_environment_variables_dict()`: Variable parsing and validation
  - `validate_format()`: Environment variable format checking

#### ContainerExecution Model
```python
class ContainerExecution(models.Model):
    """
    Tracks individual execution attempts for a ContainerJob.
    
    Maintains detailed execution history and debugging information.
    """
```
- **Fields documentation**:
  - `job`: Parent ContainerJob relationship
  - `container_id`: Docker container identifier
  - `status`: Execution-specific status tracking
  - `logs`: Captured container output
  - `started_at`, `finished_at`: Execution timing
- **Methods documentation**:
  - `get_container_info()`: Container metadata retrieval
  - `stream_logs()`: Real-time log streaming

### 3. Executor System Documentation
- **Executor interface**: Base executor contract and methods
- **Docker executor**: Docker-specific implementation details
- **Cloud Run executor**: Google Cloud Run integration
- **Mock executor**: Testing and development usage
- **Executor factory**: Dynamic executor selection and creation

### 4. Management Commands API
- **process_jobs**: Job execution management
  - Command syntax and options
  - Batch processing capabilities
  - Error handling and recovery
- **manage_jobs**: Job lifecycle management
  - Status monitoring and updates
  - Resource cleanup operations
- **Custom commands**: Extension patterns and development

### 5. Python API Usage Examples
- **Basic job creation**:
  ```python
  from container_manager.models import ContainerJob, ExecutorHost
  
  # Get or create executor host
  docker_host = ExecutorHost.objects.get(name='production-docker')
  
  # Create and launch job
  job = ContainerJob.objects.create(
      image='python:3.9',
      command='python -c "print(\'Hello World\')"',
      docker_host=docker_host
  )
  
  # Execute job
  job.launch()
  
  # Monitor status
  while not job.is_terminal_status:
      status = job.get_status()
      print(f"Job status: {status}")
      time.sleep(5)
  
  # Retrieve results
  logs = job.get_logs()
  exit_code = job.exit_code
  ```

- **Environment management**:
  ```python
  from container_manager.models import EnvironmentVariableTemplate
  
  # Create environment template
  env_template = EnvironmentVariableTemplate.objects.create(
      name='python-production',
      environment_variables_text='''
      PYTHONPATH=/app
      ENV=production
      DEBUG=False
      LOG_LEVEL=INFO
      '''
  )
  
  # Use template in job
  job = ContainerJob.objects.create(
      image='myapp:latest',
      command='python main.py',
      docker_host=docker_host,
      environment_template=env_template
  )
  ```

- **Resource management**:
  ```python
  # Job with resource limits
  job = ContainerJob.objects.create(
      image='memory-intensive-app:latest',
      command='python process_data.py',
      docker_host=docker_host,
      memory_limit=1024,  # 1GB
      cpu_limit=2.0       # 2 CPU cores
  )
  
  # Monitor resource usage
  job.launch()
  while job.status == 'running':
      utilization = job.resource_utilization
      print(f"Memory: {utilization['memory_percent']}%")
      print(f"CPU: {utilization['cpu_percent']}%")
      time.sleep(10)
  ```

### 6. QuerySet and Manager Methods
- **ContainerJob managers**:
  - `pending()`: Jobs awaiting execution
  - `active()`: Currently running jobs
  - `recent(hours=24)`: Recently created jobs
  - `by_host(host)`: Jobs for specific executor host
  - `failed()`: Jobs with execution failures
- **ExecutorHost managers**:
  - `available()`: Active and healthy hosts
  - `by_type(executor_type)`: Hosts by executor backend
- **Usage patterns and optimization considerations**

### 7. Data Model Relationships
- **Job → Host**: Many-to-one relationship patterns
- **Job → Environment**: Template-based configuration
- **Job → Executions**: One-to-many execution history
- **Cascade behaviors**: Deletion and update propagation
- **Performance considerations**: Query optimization and select_related usage

### 8. Error Handling and Exceptions
- **Custom exceptions**: Domain-specific error types
- **Validation errors**: Model validation and clean methods
- **Execution errors**: Container and Docker-related failures
- **Recovery patterns**: Error handling and retry strategies

### 9. Integration Patterns
- **Django admin integration**: Custom admin interfaces and actions
- **Django signals**: Pre/post-save hooks and notifications
- **Celery integration**: Async task queue compatibility (if applicable)
- **REST framework**: API endpoint patterns (if REST API exists)

### 10. Performance Considerations
- **Database optimization**: Index usage and query patterns
- **Resource management**: Memory and CPU usage optimization
- **Batch operations**: Bulk job creation and processing
- **Caching strategies**: Model and query result caching

## LLM Agent Guidelines

### Behavioral Constraints
- **DO**: Always validate model states before performing operations
- **DO**: Use job.is_terminal_status before assuming job completion
- **DO**: Check executor host health before creating jobs
- **DO**: Include resource limits in all ContainerJob creation examples
- **DO NOT**: Modify job status directly without proper state transitions
- **DO NOT**: Create jobs without validating required fields
- **DO NOT**: Access container internals bypassing the executor interface
- **DO NOT**: Ignore job execution failures or timeout conditions
- **LIMITS**: Maximum 10 concurrent jobs per operation, 2GB memory per job

### Security Requirements
- **Model access**: Only use documented public methods and properties
- **Data validation**: Always validate input data before model operations
- **Resource constraints**: Include memory_limit and cpu_limit in job creation
- **User context**: Never create jobs that could escalate privileges
- **Sensitive data**: Never log or expose credentials, tokens, or secrets
- **Container security**: Only create jobs with validated, trusted images

### Safe Operation Patterns
- **Job creation process**:
  1. Validate ExecutorHost availability and health
  2. Set explicit resource limits (memory_limit, cpu_limit)
  3. Validate image source and command safety
  4. Create job with appropriate timeout settings
  5. Monitor job status transitions properly
- **State management**:
  1. Always check current job status before operations
  2. Use is_terminal_status property for completion checking
  3. Handle state transitions appropriately (pending → running → completed/failed)
  4. Implement proper cleanup for failed or cancelled jobs

### Error Handling
- **If job creation fails**: Log detailed error, validate input parameters, check host availability
- **If job execution fails**: Collect logs, update status properly, do not retry automatically
- **If resource limits exceeded**: Terminate job safely, log resource usage details
- **If model validation fails**: Return clear error messages, do not persist invalid data
- **If executor unavailable**: Mark host unhealthy, redirect to available hosts

### Validation Requirements
- [ ] All job creation examples include resource limits
- [ ] Model state checking implemented before all operations
- [ ] Error handling examples cover common failure scenarios
- [ ] No direct database manipulation bypassing model methods
- [ ] All container jobs specify non-root user execution where possible
- [ ] Timeout settings appropriate for operation types
- [ ] Job cleanup procedures documented for all scenarios
- [ ] Resource monitoring patterns included in examples

### API Safety Boundaries
- **NEVER directly modify**: job.status field without proper state validation
- **NEVER bypass**: executor interface for container operations
- **NEVER create**: jobs without memory and CPU limits in production
- **NEVER ignore**: job execution timeouts or resource exhaustion
- **NEVER expose**: internal container details or credentials in logs
- **NEVER allow**: unlimited job creation or resource allocation
- **NEVER skip**: job completion verification before accessing results

## Success Criteria
- [ ] All models comprehensively documented with examples
- [ ] Python API usage patterns clearly explained
- [ ] Management command interfaces documented
- [ ] Relationship patterns and data flow explained
- [ ] Error handling and exception patterns covered
- [ ] Performance optimization guidance provided
- [ ] Integration examples for common use cases
- [ ] Code examples tested and verified working

## File Location
- **Create**: `/Users/samtexas/src/playground/django-docker/API.md`
- **Reference**: `container_manager/models.py`, `container_manager/executors/`
- **Link from**: README.md, DOCKER.md

## Content Structure
```markdown
# API Reference

## Overview
[System architecture and API access methods]

## Core Models
[Detailed model documentation with examples]

## Executor System
[Executor interface and implementations]

## Management Commands
[CLI command interface documentation]

## Python API
[Programmatic usage examples and patterns]

## Data Relationships
[Model relationships and data flow]

## Error Handling
[Exception handling and recovery patterns]

## Integration Patterns
[Common integration scenarios]

## Performance Guide
[Optimization and best practices]

## Reference
[Complete method and field reference]
```

## Style Guidelines
- **Code-first documentation**: Start with working examples
- **Progressive complexity**: Simple examples first, advanced patterns later
- **Type annotations**: Include Python type hints where helpful
- **Real-world scenarios**: Practical usage patterns over theoretical examples
- **Cross-references**: Link between related concepts and models
- **Version compatibility**: Note any version-specific behaviors
- **Testing integration**: Show how to test API usage

## Technical References
- **Model implementations**: `container_manager/models.py`
- **Executor code**: `container_manager/executors/`
- **Management commands**: `management/commands/`
- **Admin interfaces**: `container_manager/admin.py`

## Definition of Done
- [ ] API.md provides complete model reference
- [ ] Python API usage thoroughly documented
- [ ] All code examples tested and working
- [ ] Integration patterns explained with examples
- [ ] Error handling comprehensively covered
- [ ] Performance considerations addressed
- [ ] Cross-references to other documentation included
- [ ] Serves as definitive API reference for developers