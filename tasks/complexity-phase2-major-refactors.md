# Complexity Phase 2: Major Refactors (Priority 2)

## Overview
Target the 4 remaining functions with complexity 11-18 that require more substantial architectural changes. These functions have deeply nested logic and multiple responsibilities.

## Current Status
- **Remaining after quick wins:** 4 C901 complexity errors
- **Major refactor target:** 4 functions (complexity 11-18)
- **Expected outcome:** Achieve 0 remaining complexity errors

## Target Functions

### 1. `manage_container_job.py:show_job_details` (Complexity: 18) 🔥
**Location:** `container_manager/management/commands/manage_container_job.py:333`
**Issue:** Massive display function handling all job detail formatting

**Current Problems:**
- 18 complexity (highest in codebase)
- Handles job info, execution details, logs, metadata formatting
- Multiple nested conditionals for different display modes
- Mixed concerns: data retrieval and display formatting

**Refactoring Strategy:**
```python
class JobDetailFormatter:
    def format_basic_info(self, job):
        # Job ID, name, template, status
        
    def format_execution_details(self, job):
        # Runtime, duration, exit codes
        
    def format_resource_usage(self, job):
        # Memory, CPU usage stats
        
    def format_logs(self, job, show_logs):
        # Log output formatting
        
    def format_metadata(self, job):
        # Created by, timestamps, etc.

def show_job_details(self, job, show_logs=False):
    formatter = JobDetailFormatter()
    # Simple orchestration of formatters
```

**Expected Complexity:** 4-5 (95% reduction!)

---

### 2. `cloudrun.py:check_status` (Complexity: 13)
**Location:** `container_manager/executors/cloudrun.py:231`
**Issue:** Complex status mapping and error handling for Cloud Run jobs

**Current Problems:**
- Multiple Cloud Run API status states to map
- Complex error handling for different failure modes
- Nested conditionals for different execution phases
- Mixed concerns: API calls and status interpretation

**Refactoring Strategy:**
```python
class CloudRunStatusMapper:
    STATUS_MAP = {
        # Clear mapping of Cloud Run states to our states
    }
    
    def map_execution_status(self, cloud_run_status):
        # Pure status mapping logic
        
    def handle_execution_errors(self, error_info):
        # Error interpretation logic

def _get_cloud_run_execution(self, execution_id):
    # API call logic only
    
def check_status(self, execution_id):
    execution = self._get_cloud_run_execution(execution_id)
    mapper = CloudRunStatusMapper()
    return mapper.map_execution_status(execution)
```

**Expected Complexity:** 6-7

---

### 3. `cloudrun.py:__init__` (Complexity: 11)
**Location:** `container_manager/executors/cloudrun.py:43`
**Issue:** Complex configuration setup and validation

**Current Problems:**
- Multiple configuration sources (config dict, environment, defaults)
- Complex validation logic for different auth methods
- Nested conditionals for different setup modes
- Mixed concerns: config parsing and client initialization

**Refactoring Strategy:**
```python
class CloudRunConfigValidator:
    def validate_auth_config(self, config):
        # Authentication validation
        
    def validate_resource_config(self, config):
        # Resource limit validation
        
    def resolve_region(self, config):
        # Region resolution logic

def _initialize_config(self, config):
    validator = CloudRunConfigValidator()
    # Clean config setup
    
def _initialize_client(self, validated_config):
    # Client creation only
    
def __init__(self, config):
    self.config = self._initialize_config(config)
    self.client = self._initialize_client(self.config)
```

**Expected Complexity:** 5-6

---

### 4. `cloudrun.py:_create_job_spec` (Complexity: 11)
**Location:** `container_manager/executors/cloudrun.py:500`
**Issue:** Complex job specification building

**Current Problems:**
- Multiple specification sections (container, resources, environment)
- Complex conditional logic for different job types
- Nested dictionaries and configuration building
- Mixed concerns: validation and specification creation

**Refactoring Strategy:**
```python
class CloudRunJobSpecBuilder:
    def build_container_spec(self, job):
        # Container configuration
        
    def build_resource_spec(self, job):
        # Resource requirements
        
    def build_environment_spec(self, job):
        # Environment variables
        
    def build_execution_spec(self, job):
        # Execution configuration

def _create_job_spec(self, job, job_name):
    builder = CloudRunJobSpecBuilder()
    # Simple orchestration
```

**Expected Complexity:** 5-6

## Implementation Strategy

### Phase 1: Display Logic (Lowest Risk)
1. **`show_job_details`** - Extract formatters, biggest complexity win
   - Create `JobDetailFormatter` class
   - Extract 5-6 focused formatting methods
   - Test display output matches exactly

### Phase 2: Cloud Run Configuration (Medium Risk)  
2. **`__init__`** - Extract config validation
3. **`_create_job_spec`** - Extract spec builders

### Phase 3: Cloud Run Runtime (Higher Risk)
4. **`check_status`** - Extract status mapping logic
   - Most critical for runtime behavior
   - Requires careful testing of all status paths

## Risk Mitigation

### High-Risk Considerations:
- **Cloud Run functions** affect actual job execution
- **Status mapping** errors could cause job state corruption
- **Configuration changes** could break authentication

### Mitigation Strategies:
- Comprehensive test coverage for all status combinations
- Mock all Cloud Run API calls in tests
- Verify configuration parsing with real Cloud Run config examples
- Test display formatters with various job states

## Testing Requirements

### Unit Tests:
- Test all new formatter/mapper classes independently
- Mock Cloud Run API responses for all status scenarios
- Test configuration validation edge cases

### Integration Tests:
- Full job lifecycle with refactored functions
- Error handling paths
- Display output verification

### Manual Testing:
- Run against real Cloud Run jobs if possible
- Verify display output readability
- Test with various job configurations

## Success Criteria
- ✅ All 4 functions have complexity ≤ 8
- ✅ Zero remaining C901 complexity errors in codebase
- ✅ All existing tests pass
- ✅ No functional behavior changes
- ✅ Code is significantly more maintainable

## Timeline Estimate
- **Display formatter:** 3-4 hours
- **Cloud Run config:** 2-3 hours  
- **Cloud Run spec builder:** 2-3 hours
- **Cloud Run status mapper:** 3-4 hours
- **Testing and validation:** 4-6 hours
- **Total:** 14-20 hours

## Dependencies
- Should complete **Quick Wins** first to reduce scope
- May benefit from Cloud Run integration testing setup