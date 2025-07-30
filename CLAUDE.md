# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django application for full lifecycle management of Docker containers. Instead of using traditional async task queues like Celery or RQ, this system executes Django commands inside Docker containers with complete tracking of logs, status, and resource usage.

## Development Commands

### Environment Setup
```bash
# Initialize virtual environment and install dependencies
uv sync

# Run database migrations
uv run python manage.py migrate

# Create superuser for admin access
uv run python manage.py createsuperuser

# Run development server
uv run python manage.py runserver
```

### Code Quality
```bash
# Format code with ruff
uv run ruff format .

# Lint code with ruff
uv run ruff check .

# Fix auto-fixable linting issues
uv run ruff check --fix .
```

### Testing
```bash
# Run all tests
uv run python manage.py test

# Run tests with verbose output
uv run python manage.py test --verbosity=2

# Run specific test file
uv run python manage.py test container_manager.tests.DockerServiceTest

# Run tests for specific app
uv run python manage.py test container_manager
```

## Code Quality Notes

### Testing Strategy (CRITICAL)
- **MANDATORY**: Run `uv run python manage.py test` before EVERY commit
- **No exceptions**: If any test fails, fix ALL failures before committing
- Use `--failfast` flag during development to tackle failures one by one
- **Test organization**: Always use `tests/` module structure, never single `tests.py` files
- **Admin interface**: Never write tests for Django admin interface functionality
- **Optional dependencies**: Use `@unittest.skipUnless()` for tests requiring optional packages
- **Strongly prefer writing tests for the Django suite rather than doing inlines or shells**

### Pre-Commit Checklist
**Required sequence before any commit:**
```bash
1. uv run python manage.py test          # ALL tests must pass
2. uv run ruff check .                   # Linting must pass  
3. uv run ruff format .                  # Code formatting
4. git add <files>                       # Stage changes
5. git commit -m "message"               # Only then commit
```

### Development Process
- **Test-driven approach**: Every feature change must have passing tests
- **Incremental commits**: Commit working states frequently, but only when tests pass
- **Failure handling**: When tests fail, treat it as highest priority to fix
- **No partial commits**: Don't commit "work in progress" with failing tests
- **Dependencies**: Mock optional dependencies in tests rather than requiring installation

### Test Development Guidelines
- When adding new functionality, write tests first or alongside implementation
- Fix test infrastructure issues immediately when discovered
- Mock external dependencies (cloud services, APIs) properly
- Test files should import from parent modules using `..` relative imports
- Remove obsolete tests when refactoring rather than trying to fix them
- **Testing is non-negotiable**: All code must have passing tests before commit
- **Test maintenance**: Keep tests current with code changes
- **Mock appropriately**: External services should be mocked, not stubbed
- **Test coverage**: Focus on core functionality, skip admin interface testing

### Code Coverage & Testing

**Django Coverage Subagent:**
This Django project uses a specialized `coverage-enforcer` subagent for all coverage analysis and enforcement. The subagent operates independently, analyzing Django test coverage and creating improvement tasks in the `tasks/` folder. You can invoke it explicitly with:

```
@coverage-enforcer analyze current Django coverage status
@coverage-enforcer check if this PR meets Django coverage requirements  
@coverage-enforcer create coverage tasks for [Django app/component]
```

**Django Coverage Standards:**
- **Overall Django codebase:** ≥75% statement coverage (enforced)
- **New Django features:** ≥90% coverage before merge
- **Management commands:** ≥80% coverage (Django user interfaces)
- **Core business logic:** ≥85% coverage (models, views, forms)
- **Django models:** ≥70% coverage (business logic focus)

**Coverage Task System:**
The coverage subagent creates detailed improvement tasks in `tasks/` folder using naming convention:
- `coverage-[short-description].md` (e.g., `coverage-user-model-methods.md`)
- Tasks include specific test suggestions and Django testing patterns
- Prioritized by Django component criticality and business impact

**Developer Workflow:**
1. Write Django tests first for new features (TDD approach)
2. Run coverage checks: `uv run coverage report --fail-under=75`
3. Review coverage tasks created by subagent in `tasks/` folder
4. Implement suggested tests following Django testing best practices

**Django Coverage Focus:**
- Models: Custom methods, validators, business logic
- Views: Business logic, permissions, form handling  
- Management commands: All options and error conditions
- Forms: Validation logic and custom clean methods
- Excludes: Django migrations, admin configs, settings files


### Common Issues and Fixes

**Test Import Conflicts:**
- Use `tests/` directory structure, not `tests.py` files
- Update `tests/__init__.py` to import all test modules
- Use relative imports: `from ..models import MyModel`

**Missing Model Fields in Tests:**
- Check test failures for field expectations
- Add missing fields with appropriate defaults and migrations
- Don't ignore "field does not exist" errors

**Cloud Service Testing:**
- Mock cloud APIs at the import level: `@patch("google.cloud.service")`
- Use `@unittest.skipUnless()` for optional dependency tests
- Never require actual cloud credentials for basic test runs

### Code Complexity and Design Guidelines

**Complexity Management:**
- Keep cyclomatic complexity ≤ 8 per function (enforced by ruff C901)
- Extract helper methods when functions exceed 8 branches/conditions
- Prefer early returns over deep nesting of if statements
- Break complex functions into smaller, focused methods
- Use guard clauses to reduce indentation levels

**Exception Handling Patterns:**
- Use `logger.exception()` in except blocks for full tracebacks
- Avoid nested try/except blocks - extract to separate methods instead
- Keep exception handling focused and specific
- Don't silence exceptions without logging

**Code Organization:**
- **Avoid magic numbers**: Use named constants for numeric values
- **Single Responsibility**: Each function should do one thing well
- **Extract Methods**: When complexity grows, extract logical sections
- **Reduce Nesting**: Use early returns and guard clauses
- **Named Constants**: Replace magic numbers with descriptive constants

**Refactoring Patterns:**
```python
# ❌ Complex nested function
def complex_function(data):
    if data:
        if data.is_valid():
            try:
                if data.type == "special":
                    # ... many lines of logic
                else:
                    # ... more complex logic
            except Exception as e:
                logger.error(f"Error: {e}")
                return None
    return result

# ✅ Refactored with early returns and extracted methods
def simple_function(data):
    if not data or not data.is_valid():
        return None
    
    try:
        return self._process_data_by_type(data)
    except Exception as e:
        logger.exception(f"Error processing data: {e}")
        return None

def _process_data_by_type(self, data):
    if data.type == "special":
        return self._handle_special_data(data)
    return self._handle_regular_data(data)
```

**Specific Complexity Rules:**
- **McCabe Complexity ≤ 8**: Functions exceeding this should be refactored
- **Function Length**: Aim for <50 lines per function
- **Parameter Count**: Limit to 6 parameters maximum (PLR0913)
- **Nested Levels**: Avoid more than 3 levels of indentation
- **Magic Numbers**: Extract to named constants (PLR2004)

**When Refactoring:**
1. **Identify complexity hotspots** using `ruff check --select C901`
2. **Extract methods** for logical sections (5+ lines doing one thing)
3. **Use early returns** to reduce nesting
4. **Extract constants** for magic numbers
5. **Split large functions** into focused helpers
6. **Test thoroughly** after each refactoring step

## Advanced Testing & Development Guidelines

### Testing Strategy Framework (MANDATORY)

**Required Test Development Sequence:**
1. **Start Simple, Always**: Begin with basic success/failure cases
2. **Validate Early**: Run tests after every 2-3 test methods added  
3. **Build Incrementally**: Add complexity only after simple tests pass
4. **Stop on Buffer Bloat**: If test output exceeds ~1000 lines, rethink approach

**Coverage Priority Framework:**
- **Priority 1**: Core business logic (models, executors, job processing)
- **Priority 2**: Utility functions (helpers, validators, formatters)
- **Priority 3**: Compatibility layers (backward compatibility, legacy APIs) 
- **Priority 4**: Framework integrations (admin, signals) - DEFER UNLESS EXPLICIT

### External API Testing Framework

**Non-Deterministic Testing Approach:**
When testing external APIs (Docker, Cloud services, databases):

1. **Isolation First**: Mock at module import level
2. **Behavior Focus**: Test your logic, not the external API
3. **Error Scenarios**: Test what happens when external service fails
4. **Timeout Awareness**: Use reasonable timeouts in tests
5. **Dependency Gates**: Use `@skipUnless` for optional dependencies

**Key Principle**: Think "How does my code behave when X happens?" not "Does X work?"

### Test Complexity Self-Check Framework

**Before Writing Complex Tests, Ask:**
- **Method Length**: >20 lines? Extract helpers
- **Mock Complexity**: >5 mocks in one test? Split scenarios  
- **Assertion Count**: >10 assertions? Multiple test methods needed
- **Setup Lines**: >15 lines of setup? Extract to helper method
- **Nested Logic**: >2 levels of if/for? Simplify test logic
- **Output Volume**: Will this generate >100 lines output? Redesign approach

**Red Flags for Test Complexity:**
🚨 **STOP** if you're creating:
- Tests that test multiple unrelated scenarios
- Complex mock hierarchies spanning >3 objects deep  
- Tests requiring extensive setup/teardown
- Tests that generate massive output logs
- Tests with unclear pass/fail criteria

### Output and Context Management

**Buffer Management Guidelines:**
- **Test Output Limit**: Stop if single test command outputs >500 lines
- **Batch Size Awareness**: Run tests in small batches during development
- **Context Conservation**: Large outputs eat context - prefer focused tests
- **Early Termination**: Use timeouts and `--failfast` liberally

### Recovery Patterns

**When Things Go Wrong:**
1. **Infinite Loops**: Kill immediately, examine mock return values
2. **Massive Output**: Ctrl+C, rethink test approach  
3. **Complex Failures**: Step back to simpler version
4. **Mock Confusion**: Start with one mock, add incrementally
5. **Parameter Errors**: Verify actual method signatures first

### Quality Gates Integration

**Automated Complexity Checks:**
Beyond ruff C901 (cyclomatic complexity ≤ 8):

**Test Method Complexity Indicators:**
- Line count per test method (<20 lines ideal)
- Number of mocks per test (<5 mocks preferred)
- Assertion density (max 5-7 assertions per test)
- Setup/teardown ratio (setup should be <50% of test)
- Exception handling coverage (test error paths explicitly)

**Self-Check Questions:**
- Can I explain this test in one sentence?
- Would a junior developer understand this test?
- Does this test only fail for one specific reason?
- Can this test run in isolation?

### External Dependency Mocking Patterns

**Google Cloud Services Example:**
```python
def setUp(self):
    # Mock at module level
    mock_run_v2 = MagicMock()
    mock_jobs_client = MagicMock()
    mock_run_v2.JobsClient = Mock(return_value=mock_jobs_client)
    
    sys.modules['google.cloud.run_v2'] = mock_run_v2
    
def tearDown(self):
    # Clean up mocked modules
    for module in ['google.cloud.run_v2', 'google.auth']:
        if module in sys.modules:
            del sys.modules[module]
```

**Docker Services Example:**
```python
@patch('container_manager.docker_service.DockerExecutor')
def test_service_method(self, mock_executor_class):
    mock_executor = Mock()
    mock_executor.method.return_value = expected_result
    mock_executor_class.return_value = mock_executor
    
    # Test your logic, not Docker's
```

### Test Organization Best Practices

**File Structure:**
```
tests/
├── __init__.py
├── test_models.py              # Core business logic
├── test_executors/             # Priority 1
│   ├── test_docker.py
│   ├── test_cloudrun.py
│   └── test_base.py
├── test_management/            # Priority 2  
│   ├── test_process_jobs.py
│   └── test_manage_jobs.py
├── test_services/              # Priority 3
│   └── test_docker_service.py  # Backward compatibility
└── test_admin.py               # Priority 4 (defer)
```

**Test Method Naming:**
```python
def test_method_scenario_expectedOutcome(self):
    """Test method_name with scenario produces expected_outcome"""
    pass

# Examples:
def test_launch_job_with_valid_config_returns_success(self):
def test_check_status_when_job_not_found_returns_not_found(self):
def test_harvest_job_with_failed_execution_updates_exit_code(self):
```

### Version Control Best Practices
- Remember to commit often as a means of checkpointing your progress. Do not be shy to rollback, branch, or use git to its fullest potential.
- **Testing discipline must be as rigorous as code quality standards**
