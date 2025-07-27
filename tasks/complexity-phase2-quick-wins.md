# Complexity Phase 2: Quick Wins (Priority 1)

## Overview
Target the 5 remaining functions with complexity 9-12 for immediate improvement. These have manageable complexity levels and can be refactored with focused method extraction.

## Current Status
- **Total remaining:** 9 C901 complexity errors
- **Quick wins target:** 5 functions (complexity 9-12)
- **Expected outcome:** Reduce remaining errors from 9 to 4

## Target Functions

### 1. `manage_container_job.py:handle_run` (Complexity: 9)
**Location:** `container_manager/management/commands/manage_container_job.py:148`
**Issue:** Job validation and execution logic mixed together

**Refactoring Strategy:**
```python
# Extract validation logic
def _validate_job_for_run(self, job_id):
    # Job lookup and validation logic
    
def _execute_job_run(self, job):
    # Actual execution logic
    
def handle_run(self, options):
    job = self._validate_job_for_run(options["job_id"])
    if job:
        self._execute_job_run(job)
```

**Expected Complexity:** 5-6

---

### 2. `docker.py:_create_container` (Complexity: 12)
**Location:** `container_manager/executors/docker.py:325`
**Issue:** Container creation, environment setup, and volume mounting mixed

**Refactoring Strategy:**
```python
def _prepare_container_environment(self, job):
    # Environment variable preparation
    
def _prepare_container_config(self, job):
    # Container configuration setup
    
def _create_container(self, job):
    env = self._prepare_container_environment(job)
    config = self._prepare_container_config(job)
    # Simple container creation
```

**Expected Complexity:** 6-7

---

### 3. `cloudrun.py:harvest_job` (Complexity: 12)  
**Location:** `container_manager/executors/cloudrun.py:301`
**Issue:** Result processing, log collection, and status updates mixed

**Refactoring Strategy:**
```python
def _collect_job_logs(self, job_name, project):
    # Log collection logic
    
def _process_job_results(self, job, execution_data):
    # Result processing logic
    
def harvest_job(self, job):
    logs = self._collect_job_logs(job_name, project)
    return self._process_job_results(job, execution_data)
```

**Expected Complexity:** 6-8

---

### 4. `process_container_jobs.py:handle` (Complexity: 12)
**Location:** `container_manager/management/commands/process_container_jobs.py:92`
**Issue:** Option processing, setup, and main loop logic mixed

**Refactoring Strategy:**
```python
def _process_command_options(self, options):
    # Option validation and processing
    
def _setup_worker_environment(self, options):
    # Environment setup logic
    
def _run_main_worker_loop(self, config):
    # Main processing loop
    
def handle(self, *args, **options):
    config = self._process_command_options(options)
    self._setup_worker_environment(config)
    self._run_main_worker_loop(config)
```

**Expected Complexity:** 5-6

---

### 5. `process_container_jobs.py:monitor_running_jobs` (Complexity: 12)
**Location:** `container_manager/management/commands/process_container_jobs.py:337`
**Issue:** Job monitoring, status checking, and harvesting mixed

**Refactoring Strategy:**
```python
def _get_monitorable_jobs(self, host_filter):
    # Job filtering and selection
    
def _check_job_status(self, job):
    # Status checking logic
    
def _harvest_completed_job(self, job):
    # Job completion handling
    
def monitor_running_jobs(self, host_filter=None):
    jobs = self._get_monitorable_jobs(host_filter)
    # Simple monitoring loop
```

**Expected Complexity:** 6-7

## Implementation Plan

### Phase 1: Management Commands (Lower Risk)
1. Refactor `handle_run` (complexity 9)
2. Refactor `handle` (complexity 12)  
3. Refactor `monitor_running_jobs` (complexity 12)

### Phase 2: Executor Functions (Higher Risk)
4. Refactor `_create_container` (complexity 12)
5. Refactor `harvest_job` (complexity 12)

## Testing Strategy
- Run full test suite after each function refactor
- Ensure no functionality changes, only code organization
- Test both success and error paths
- Verify logging still works correctly

## Success Criteria
- ✅ All 5 functions have complexity ≤ 8
- ✅ All tests pass after refactoring
- ✅ No functionality changes
- ✅ Code is more readable and maintainable

## Timeline Estimate
- **Management commands:** 2-3 hours
- **Executor functions:** 3-4 hours  
- **Testing and validation:** 1-2 hours
- **Total:** 6-9 hours