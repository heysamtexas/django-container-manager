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

### Container Job Management
```bash
# Process container jobs (main worker command)
uv run python manage.py process_container_jobs

# Process jobs with custom settings
uv run python manage.py process_container_jobs --poll-interval=10 --max-jobs=5

# Process jobs for specific Docker host
uv run python manage.py process_container_jobs --host=production-host

# Run cleanup of old containers
uv run python manage.py process_container_jobs --cleanup --cleanup-hours=48

# Create a container job manually
uv run python manage.py manage_container_job create template-name host-name --name="My Job"

# List container jobs
uv run python manage.py manage_container_job list --status=running

# Show job details with logs
uv run python manage.py manage_container_job show JOB-UUID --logs

# Cancel a running job
uv run python manage.py manage_container_job cancel JOB-UUID
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

### Version Control Best Practices
- Remember to commit often as a means of checkpointing your progress. Do not be shy to rollback, branch, or use git to its fullest potential.
- **Testing discipline must be as rigorous as code quality standards**