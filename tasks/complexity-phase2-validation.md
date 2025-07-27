# Complexity Phase 2: Validation & Testing Strategy

## Overview
Comprehensive testing and validation approach for complexity refactoring to ensure no functionality is broken while improving code maintainability.

## Testing Philosophy
**Zero Tolerance for Functional Changes**
- Refactoring should only change code organization, never behavior
- All existing tests must pass without modification
- Output/logging should remain identical
- Error handling must preserve exact same behavior

## Pre-Refactoring Validation

### 1. Baseline Test Suite
```bash
# Establish baseline before any changes
uv run python manage.py test --verbosity=2
# Expected: 105 tests passing, 19 skipped

# Establish complexity baseline
uv run ruff check . --select C901
# Expected: 9 errors (complexity 9-18)
```

### 2. Behavior Documentation
For each target function, document:
- **Input parameters and types**
- **Return values and types** 
- **Side effects** (database changes, logging, file I/O)
- **Exception scenarios** and expected error messages
- **Integration points** with other functions

### 3. Output Capture
For display functions (`show_job_details`):
- Capture exact output for various job states
- Document formatting expectations
- Test with edge cases (missing data, long strings)

## During Refactoring: Incremental Validation

### Function-by-Function Approach
1. **Refactor ONE function at a time**
2. **Run tests after each function**
3. **Commit working state before moving to next**
4. **Document any test changes needed**

### Validation Checklist Per Function
```bash
# After refactoring each function:

# 1. Complexity check
uv run ruff check [file] --select C901
# Verify target function complexity ≤ 8

# 2. Full linting
uv run ruff check [file]
# No new linting errors introduced

# 3. Function-specific tests
uv run python manage.py test [app.tests.TestClass.test_specific_function]

# 4. Full test suite
uv run python manage.py test
# All 105 tests still passing

# 5. Manual smoke test (for management commands)
uv run python manage.py [command] --help
```

## Function-Specific Validation

### Management Commands
**Files:** `manage_container_job.py`, `process_container_jobs.py`

**Test Strategy:**
```bash
# Command help still works
uv run python manage.py manage_container_job --help
uv run python manage.py process_container_jobs --help

# Basic command functionality  
uv run python manage.py manage_container_job list
uv run python manage.py manage_container_job create [args]

# Output format validation (capture and compare)
uv run python manage.py manage_container_job show [job_id] > before.txt
# [refactor]
uv run python manage.py manage_container_job show [job_id] > after.txt
diff before.txt after.txt  # Should be empty
```

### Docker Executor
**File:** `executors/docker.py`

**Test Strategy:**
```python
# Unit tests for extracted methods
class TestDockerExecutorRefactor(TestCase):
    def test_prepare_container_environment_preserves_behavior(self):
        # Test that environment preparation logic unchanged
        
    def test_create_container_still_creates_same_container(self):
        # Mock Docker API, verify same API calls made
```

### Cloud Run Executor  
**File:** `executors/cloudrun.py`

**Critical Test Areas:**
```python
# Status mapping validation
def test_status_mapping_unchanged(self):
    # Test all Cloud Run status -> our status mappings
    original_statuses = [
        "SUCCEEDED", "FAILED", "RUNNING", "PENDING", "CANCELLED"
    ]
    # Verify refactored code produces identical mappings

# Configuration validation
def test_config_processing_unchanged(self):
    # Test various config combinations still work
    
# Job spec creation
def test_job_spec_identical(self):
    # Mock job, verify generated spec is byte-for-byte identical
```

## Error Handling Validation

### Exception Scenarios
Test that refactored code handles errors identically:

```python
# Original behavior: what exceptions are raised?
# Refactored behavior: same exceptions raised?

test_cases = [
    ("invalid_job_id", ExpectedExceptionType),
    ("missing_credentials", ExpectedExceptionType),
    ("network_failure", ExpectedExceptionType),
    ("permission_denied", ExpectedExceptionType),
]
```

### Logging Validation
```python
# Capture logs before and after refactoring
with self.assertLogs('container_manager', level='INFO') as logs:
    result = function_call()
    
# Verify log messages unchanged (content, not just count)
```

## Performance Validation

### No Performance Regression
```python
import time

# Benchmark before refactoring
start = time.time()
for i in range(100):
    function_call()
original_time = time.time() - start

# Benchmark after refactoring  
start = time.time()
for i in range(100):
    function_call()
refactored_time = time.time() - start

# Should be similar (within 20% acceptable)
assert refactored_time < original_time * 1.2
```

## Integration Testing

### End-to-End Workflows
Test complete workflows still work:

```bash
# 1. Create sample data
uv run python manage.py create_sample_data

# 2. Process jobs
uv run python manage.py process_container_jobs --max-jobs=1

# 3. Check results
uv run python manage.py manage_container_job list
uv run python manage.py manage_container_job show [job_id] --logs
```

### API Integration
For Cloud Run executor refactoring:
```python
# Test with real Cloud Run (if credentials available)
# Or comprehensive mocking of all API scenarios
```

## Rollback Procedures

### Git Strategy
```bash
# Before starting each function refactor:
git checkout -b refactor-[function-name]
git commit -m "Pre-refactor checkpoint for [function]"

# If refactor fails:
git checkout main  # Return to known good state
git branch -D refactor-[function-name]  # Clean up failed attempt
```

### Test Failure Response
```bash
# If tests fail after refactoring:
1. Check if test expectations need updating (RARE - investigate first)
2. Check if refactoring introduced subtle behavior change
3. Rollback to previous commit if unfixable quickly
4. Document issue and try different refactoring approach
```

## Success Metrics

### Quantitative Goals
- ✅ **Complexity:** All functions ≤ 8 complexity
- ✅ **Tests:** 105 tests passing (same as before)
- ✅ **Coverage:** No reduction in test coverage
- ✅ **Performance:** No >20% performance regression

### Qualitative Goals  
- ✅ **Readability:** Functions are easier to understand
- ✅ **Maintainability:** Changes would be easier to make
- ✅ **Testability:** Individual components can be tested in isolation
- ✅ **Documentation:** New methods have clear purposes

## Final Validation Checklist

```bash
# Complete validation before declaring success:

# 1. Full test suite
uv run python manage.py test
# Expected: 105 tests passing, 19 skipped

# 2. No complexity violations
uv run ruff check . --select C901
# Expected: 0 errors (down from 9)

# 3. No new linting issues
uv run ruff check .
# Expected: No new errors introduced

# 4. Integration tests
uv run python manage.py create_sample_data
uv run python manage.py process_container_jobs --max-jobs=1
uv run python manage.py manage_container_job list

# 5. Performance spot check
# Run a few key operations, verify reasonable performance

# 6. Documentation updated
# CLAUDE.md reflects new complexity standards
```

## Timeline
- **Per-function validation:** 30-60 minutes
- **Integration testing:** 2-3 hours
- **Final validation:** 1-2 hours
- **Total validation effort:** 30-40% of development time