# Code Coverage: Executor Testing (Priority 2)

## Executive Summary

**Impact:** HIGH - Executors contain core business logic for job execution across different platforms
**Current Coverage:**
- `cloudrun.py` - **29%** (360 statements) - Cloud Run executor
- `docker.py` - **37%** (323 statements) - Docker executor  
- `base.py` - **39%** (67 statements) - Base executor interface
- `executors/__init__.py` - **24%** (17 statements) - Executor factory

**Target:** Achieve **≥85%** coverage on core executors (business-critical logic)

## Critical Coverage Analysis

### 1. `cloudrun.py` - 29% Coverage 🔴
**File:** `container_manager/executors/cloudrun.py`
**Current Coverage:** 105/360 statements covered
**Missing Coverage:** 255 statements (71% uncovered)

**High-Impact Uncovered Functions:**
- `check_status()` - Job status monitoring (complexity 13)
- `__init__()` - Executor initialization (complexity 11)  
- `_create_job_spec()` - Job specification creation (complexity 11)
- `harvest_job()` - Result collection (complexity 12)
- `submit_job()` - Job submission to Cloud Run
- `cancel_job()` - Job cancellation
- `get_logs()` - Log retrieval from Cloud Run

**Testing Strategy:**
```python
class CloudRunExecutorTest(TestCase):
    def setUp(self):
        # Mock Google Cloud Run client consistently
        self.mock_client = Mock()
        self.executor = CloudRunExecutor({
            'project_id': 'test-project',
            'region': 'us-central1'
        })
        self.executor.client = self.mock_client

    def test_check_status_maps_cloud_run_states_correctly(self):
        # Test all Cloud Run status → our status mappings
        test_cases = [
            ('SUCCEEDED', 'completed'),
            ('FAILED', 'failed'),
            ('RUNNING', 'running'),
            ('PENDING', 'pending'),
            ('CANCELLED', 'cancelled')
        ]
        for cloud_status, expected_status in test_cases:
            # Test status mapping logic
            
    def test_submit_job_creates_correct_job_spec(self):
        # Test job specification generation
        job = self.create_test_job()
        self.executor.submit_job(job)
        # Verify API call with correct parameters
        
    def test_harvest_job_collects_logs_and_results(self):
        # Test result collection and log retrieval
        
    def test_cancel_job_terminates_cloud_run_execution(self):
        # Test job cancellation
```

**Complex Function Testing:**

**`check_status()` (Complexity 13):**
```python
def test_check_status_handles_all_execution_phases(self):
    # Test: job creation → execution → completion/failure
    phases = ['PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED']
    for phase in phases:
        mock_execution = self.create_mock_execution(phase)
        status = self.executor.check_status('execution-123')
        # Verify correct status mapping and error handling

def test_check_status_handles_api_errors_gracefully(self):
    # Test Google Cloud API error scenarios
    api_errors = [
        google.api_core.exceptions.NotFound,
        google.api_core.exceptions.PermissionDenied,
        google.api_core.exceptions.DeadlineExceeded
    ]
    for error_type in api_errors:
        self.mock_client.get_execution.side_effect = error_type
        # Test error handling and status reporting
```

**`_create_job_spec()` (Complexity 11):**
```python
def test_create_job_spec_builds_complete_specification(self):
    # Test comprehensive job spec creation
    job = self.create_complex_test_job()
    spec = self.executor._create_job_spec(job, 'test-job-name')
    
    # Verify all spec components:
    self.assertIn('container', spec)
    self.assertIn('resources', spec)
    self.assertIn('environment', spec)
    self.assertIn('volumes', spec)
    
def test_create_job_spec_handles_resource_limits(self):
    # Test resource specification (CPU, memory, disk)
    
def test_create_job_spec_configures_environment_correctly(self):
    # Test environment variable configuration
```

### 2. `docker.py` - 37% Coverage 🔴
**File:** `container_manager/executors/docker.py`
**Current Coverage:** 119/323 statements covered
**Missing Coverage:** 204 statements (63% uncovered)

**High-Impact Uncovered Functions:**
- `_create_container()` - Container creation (complexity 12)
- `submit_job()` - Job submission to Docker
- `check_status()` - Container status monitoring
- `harvest_job()` - Container result collection
- `cancel_job()` - Container termination
- `get_logs()` - Docker container log retrieval

**Testing Strategy:**
```python
class DockerExecutorTest(TestCase):
    def setUp(self):
        # Mock Docker client
        self.mock_docker = Mock()
        self.executor = DockerExecutor({
            'host': 'tcp://localhost:2376',
            'tls_verify': False
        })
        self.executor.client = self.mock_docker

    def test_create_container_configures_all_options(self):
        # Test container configuration creation
        job = self.create_test_job()
        container_config = self.executor._create_container(job)
        
        # Verify configuration completeness
        self.assertIn('image', container_config)
        self.assertIn('command', container_config)
        self.assertIn('environment', container_config)
        self.assertIn('volumes', container_config)
        
    def test_submit_job_creates_and_starts_container(self):
        # Test full job submission workflow
        
    def test_check_status_maps_docker_states(self):
        # Test Docker container state → our status mapping
        docker_states = ['created', 'running', 'exited', 'dead']
        for state in docker_states:
            # Test status mapping
            
    def test_harvest_job_collects_exit_code_and_logs(self):
        # Test result collection from completed container
```

**Complex Function Testing:**

**`_create_container()` (Complexity 12):**
```python
def test_create_container_handles_volume_mounting(self):
    # Test volume configuration and mounting
    
def test_create_container_configures_networking(self):
    # Test network configuration
    
def test_create_container_sets_resource_limits(self):
    # Test CPU and memory limits
    
def test_create_container_handles_environment_variables(self):
    # Test environment variable configuration
```

### 3. `base.py` - 39% Coverage 🟡
**File:** `container_manager/executors/base.py`
**Current Coverage:** 26/67 statements covered
**Missing Coverage:** 41 statements (61% uncovered)

**Key Uncovered Areas:**
- Abstract method validation
- Common utility methods
- Error handling patterns
- Base class initialization

**Testing Strategy:**
```python
class BaseExecutorTest(TestCase):
    def test_abstract_methods_enforce_implementation(self):
        # Test that abstract methods raise NotImplementedError
        
    def test_common_utilities_work_correctly(self):
        # Test shared utility methods
        
    def test_error_handling_patterns(self):
        # Test base error handling
```

### 4. `executors/__init__.py` - 24% Coverage 🔴
**File:** `container_manager/executors/__init__.py`
**Current Coverage:** 4/17 statements covered
**Missing Coverage:** 13 statements (76% uncovered)

**Key Functions:**
- Executor factory functions
- Dynamic executor loading
- Configuration validation

**Testing Strategy:**
```python
class ExecutorFactoryTest(TestCase):
    def test_factory_creates_correct_executor_types(self):
        # Test factory method executor creation
        
    def test_factory_handles_invalid_executor_types(self):
        # Test error handling for unknown types
        
    def test_dynamic_loading_works_correctly(self):
        # Test dynamic executor class loading
```

## Advanced Testing Scenarios

### 1. API Integration Testing
```python
# Mock external APIs comprehensively
@patch('google.cloud.run_v2.JobsClient')
@patch('docker.from_env')
class ExecutorIntegrationTest(TestCase):
    def test_cloud_run_api_error_handling(self):
        # Test various Google Cloud API error scenarios
        
    def test_docker_api_connectivity_issues(self):
        # Test Docker daemon connectivity problems
        
    def test_executor_failover_scenarios(self):
        # Test executor switching on failures
```

### 2. Performance and Resource Testing
```python
class ExecutorPerformanceTest(TestCase):
    def test_concurrent_job_execution(self):
        # Test multiple jobs running simultaneously
        
    def test_resource_limit_enforcement(self):
        # Test CPU and memory limit enforcement
        
    def test_long_running_job_monitoring(self):
        # Test status monitoring for extended periods
```

### 3. Error Recovery Testing
```python
class ExecutorErrorRecoveryTest(TestCase):
    def test_network_failure_recovery(self):
        # Test recovery from network interruptions
        
    def test_api_timeout_handling(self):
        # Test timeout and retry logic
        
    def test_resource_exhaustion_handling(self):
        # Test behavior when resources are exhausted
```

## Mock Strategy & Test Infrastructure

### Google Cloud Run Mocking
```python
class MockCloudRunClient:
    """Comprehensive mock for Google Cloud Run client"""
    
    def __init__(self):
        self.jobs = {}
        self.executions = {}
        
    def create_job(self, parent, job):
        # Mock job creation
        
    def run_job(self, name):
        # Mock job execution
        
    def get_execution(self, name):
        # Mock execution status retrieval
        
    def list_executions(self, parent):
        # Mock execution listing
```

### Docker Client Mocking
```python
class MockDockerClient:
    """Comprehensive mock for Docker client"""
    
    def __init__(self):
        self.containers = MockContainerManager()
        
    class MockContainerManager:
        def create(self, **kwargs):
            # Mock container creation
            
        def get(self, container_id):
            # Mock container retrieval
            
        def list(self, **kwargs):
            # Mock container listing
```

### Shared Test Utilities
```python
class ExecutorTestMixin:
    """Common utilities for executor testing"""
    
    def create_test_job(self, **kwargs):
        # Create standardized test job objects
        
    def assert_job_spec_valid(self, spec):
        # Validate job specification structure
        
    def mock_successful_execution(self, executor):
        # Set up mocks for successful job execution
        
    def mock_failed_execution(self, executor, error_type):
        # Set up mocks for failed job execution
```

## Implementation Plan

### Phase 1: Cloud Run Executor (Highest Business Impact)
1. **`cloudrun.py`** - 29% → 85% coverage
   - Focus on status mapping and job lifecycle
   - Mock Google Cloud Run API comprehensively
   - Test complex functions: `check_status`, `_create_job_spec`, `harvest_job`
   - **Estimated effort:** 14-18 hours

### Phase 2: Docker Executor (High Impact)
2. **`docker.py`** - 37% → 85% coverage
   - Focus on container management and lifecycle
   - Mock Docker API thoroughly
   - Test complex functions: `_create_container`, `submit_job`, `check_status`
   - **Estimated effort:** 12-16 hours

### Phase 3: Base Classes and Infrastructure
3. **`base.py`** - 39% → 85% coverage
4. **`executors/__init__.py`** - 24% → 85% coverage
   - **Estimated effort:** 4-6 hours combined

## Testing Challenges & Solutions

### Challenge 1: External API Dependencies
**Problem:** Executors depend on Google Cloud Run and Docker APIs
**Solution:**
- Comprehensive mocking at the client level
- Use dependency injection for testability
- Create realistic mock responses based on actual API behavior

### Challenge 2: Asynchronous Operations
**Problem:** Job execution is asynchronous with status polling
**Solution:**
- Mock time-dependent operations
- Test state transitions explicitly
- Use deterministic mock sequences

### Challenge 3: Complex Configuration
**Problem:** Executors have many configuration options
**Solution:**
- Test configuration permutations systematically
- Use parameterized tests for multiple scenarios
- Validate configuration parsing edge cases

### Challenge 4: Error Condition Coverage
**Problem:** Many error paths are hard to trigger
**Solution:**
- Use mock side effects to simulate errors
- Test all documented error scenarios
- Include timeout and resource exhaustion cases

## Success Metrics

### Coverage Targets
- `cloudrun.py`: 29% → **≥85%** (306+ statements covered)
- `docker.py`: 37% → **≥85%** (275+ statements covered)
- `base.py`: 39% → **≥85%** (57+ statements covered)
- `executors/__init__.py`: 24% → **≥85%** (14+ statements covered)

### Quality Metrics
- **All executor functions tested** including complex ones
- **Error handling coverage** for all failure modes
- **API integration mocking** comprehensive and realistic
- **State transition testing** complete and deterministic
- **Configuration validation** thorough and edge-case aware

### Functional Coverage
- **Job lifecycle operations** (submit, monitor, harvest, cancel)
- **Status mapping accuracy** for all external service states
- **Resource management** (CPU, memory, disk, network)
- **Error recovery patterns** and retry logic
- **Configuration parsing** and validation

## Risk Mitigation

### High-Risk Areas
- **Status mapping logic** - Critical for job state accuracy
- **Resource limit enforcement** - Important for system stability
- **API error handling** - Must handle all external service failures

### Mitigation Strategies
- **Comprehensive status testing** - Test all state combinations
- **Resource validation** - Test limits and enforcement
- **Error injection testing** - Simulate all API failure modes
- **Integration testing** - Test real workflow scenarios

## Timeline Estimate

### Conservative Estimate: 34-46 hours
- **Cloud Run executor:** 18 hours
- **Docker executor:** 16 hours
- **Base classes:** 6 hours
- **Integration testing:** 4-6 hours

### Optimistic Estimate: 26-34 hours
- **Cloud Run executor:** 14 hours
- **Docker executor:** 12 hours
- **Base classes:** 4 hours
- **Integration testing:** 2-4 hours

## Dependencies

### Prerequisites
- Mock infrastructure established
- External API documentation reviewed
- Test database with proper isolation
- Coverage reporting configured

### Coordination
- Benefits from management command testing patterns
- Requires shared mock utilities
- Needs consistent error handling patterns
- May inform service layer testing approach