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

### Version Control Best Practices
- Remember to commit often as a means of checkpointing your progress. Do not be shy to rollback, branch, or use git to its fullest potential.
- **Always run a full suite of tests before committing any changes. Use the standard Django test runner to do that.**

[Rest of the file remains the same...]