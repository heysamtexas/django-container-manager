# Contributing to Django Docker Container Manager

Thank you for your interest in contributing to Django Docker Container Manager! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project follows a standard code of conduct:

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain professionalism in all interactions

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.12 or later
- Docker and Docker Compose
- Git
- A GitHub account

### Initial Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/django-docker-manager.git
   cd django-docker-manager
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/heysamtexas/django-docker-manager.git
   ```

## Development Setup

### Environment Setup

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Create and activate virtual environment**:
   ```bash
   uv sync
   ```

3. **Set up database**:
   ```bash
   uv run python manage.py migrate
   ```

4. **Create superuser** (optional):
   ```bash
   uv run python manage.py createsuperuser
   ```

5. **Run tests** to verify setup:
   ```bash
   uv run python manage.py test
   ```

### Docker Setup

Ensure Docker is running and accessible:

```bash
# Test Docker access
docker ps

# For Unix socket (Linux/macOS)
ls -la /var/run/docker.sock

# For TCP access, ensure Docker daemon is listening
docker info
```

### IDE Configuration

#### VS Code
Recommended extensions:
- Python
- Django
- Docker
- GitLens

#### PyCharm
- Enable Django support
- Configure Python interpreter to use the virtual environment
- Set up Docker integration

## Making Changes

### Branching Strategy

1. **Create a feature branch** from main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```

2. **Use descriptive branch names**:
   - `feature/add-job-scheduling`
   - `fix/container-cleanup-bug` 
   - `docs/improve-installation-guide`
   - `refactor/docker-service-optimization`

### Development Workflow

1. **Make atomic commits** with clear messages
2. **Test your changes** thoroughly
3. **Update documentation** if needed
4. **Add tests** for new functionality
5. **Ensure code style compliance**

### Commit Messages

Use clear, descriptive commit messages:

```bash
# Good examples
git commit -m \"Add support for Docker Swarm hosts\"
git commit -m \"Fix memory leak in container monitoring\"
git commit -m \"Update installation documentation for Windows\"

# Avoid
git commit -m \"Fix bug\"
git commit -m \"Update stuff\"
```

## Testing

### Running Tests

```bash
# Run all tests
uv run python manage.py test

# Run specific test class
uv run python manage.py test container_manager.tests.DockerServiceTest

# Run with verbose output
uv run python manage.py test --verbosity=2

# Run specific test method
uv run python manage.py test container_manager.tests.DockerServiceTest.test_container_creation
```

### Test Coverage

We aim for high test coverage. Check coverage with:

```bash
# Install coverage tool
uv add --dev coverage

# Run tests with coverage
uv run coverage run --source='.' manage.py test
uv run coverage report
uv run coverage html  # Generate HTML report
```

### Writing Tests

#### Test Structure
```python
from django.test import TestCase
from unittest.mock import patch, MagicMock
from container_manager.models import ContainerJob, ContainerTemplate, DockerHost

class YourTestClass(TestCase):
    def setUp(self):
        \"\"\"Set up test fixtures\"\"\"
        self.host = DockerHost.objects.create(
            name=\"test-host\",
            host_type=\"unix\",
            connection_string=\"unix:///var/run/docker.sock\"
        )
        self.template = ContainerTemplate.objects.create(
            name=\"test-template\",
            docker_image=\"ubuntu:22.04\",
            command=\"echo 'test'\"
        )
    
    def test_your_functionality(self):
        \"\"\"Test description\"\"\"
        # Test implementation
        pass
```

#### Mocking Docker Operations
```python
@patch('container_manager.docker_service.docker.from_env')
def test_docker_operation(self, mock_docker):
    \"\"\"Test Docker operations with mocking\"\"\"
    mock_client = MagicMock()
    mock_docker.return_value = mock_client
    
    # Configure mock behavior
    mock_client.containers.create.return_value = MagicMock(id='test_container')
    
    # Test your code
    # Assertions
```

### Test Categories

#### Unit Tests
- Test individual functions and methods
- Mock external dependencies
- Fast execution

#### Integration Tests
- Test component interactions
- Use test database
- May use Docker test containers

#### Admin Tests
- Test Django admin functionality
- Verify UI components
- Test bulk actions

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications defined in `pyproject.toml`:

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Code Style Guidelines

#### General Principles
- Write clear, readable code
- Use descriptive variable and function names
- Add docstrings for classes and non-trivial functions
- Keep functions focused and small
- Follow Django conventions

#### Example Code Style
```python
class ContainerService:
    \"\"\"Service for managing Docker containers.\"\"\"
    
    def create_container(self, job: ContainerJob) -> str:
        \"\"\"Create a Docker container for the given job.
        
        Args:
            job: The container job to create a container for
            
        Returns:
            Container ID string
            
        Raises:
            DockerConnectionError: If unable to connect to Docker daemon
            ContainerCreationError: If container creation fails
        \"\"\"
        try:
            client = self.get_docker_client(job.docker_host)
            container = client.containers.create(
                image=job.template.docker_image,
                command=job.get_effective_command(),
                mem_limit=f\"{job.get_effective_memory_limit()}m\",
                name=f\"job-{job.id}\"
            )
            return container.id
        except Exception as e:
            logger.error(f\"Failed to create container for job {job.id}: {e}\")
            raise
```

#### Django Specific Guidelines
- Use Django's built-in features when possible
- Follow Django model conventions
- Use Django's logging framework
- Prefer Django's testing tools
- Use Django's form validation

#### Documentation
- Add docstrings to all public classes and methods
- Include type hints where helpful
- Document complex algorithms
- Keep comments up to date

## Submitting Changes

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-branch
   git rebase main
   ```

2. **Run full test suite**:
   ```bash
   uv run python manage.py test
   ```

3. **Check code style**:
   ```bash
   uv run ruff check .
   uv run ruff format .
   ```

4. **Update documentation** if needed

### Pull Request Process

1. **Push your branch** to your fork:
   ```bash
   git push origin your-branch-name
   ```

2. **Create pull request** on GitHub with:
   - Clear title describing the change
   - Detailed description of what changed and why
   - Reference any related issues
   - Include screenshots for UI changes

3. **Pull request template**:
   ```markdown
   ## Summary
   Brief description of changes
   
   ## Changes Made
   - List of specific changes
   - New features added
   - Bugs fixed
   
   ## Testing
   - [ ] All tests pass
   - [ ] New tests added for new functionality
   - [ ] Manual testing completed
   
   ## Documentation
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated (if applicable)
   
   ## Related Issues
   Closes #123
   ```

### Review Process

- Pull requests require review before merging
- Address feedback promptly and professionally
- Make requested changes in new commits
- Squash commits before merge if requested

## Reporting Issues

### Bug Reports

Use the GitHub issue tracker with this information:

```markdown
**Bug Description**
Clear description of the bug

**Steps to Reproduce**
1. Step one
2. Step two
3. Step three

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.12.0]
- Django version: [e.g., 5.2.0]
- Docker version: [e.g., 24.0.0]

**Additional Context**
- Error messages
- Log output
- Screenshots
```

### Security Issues

For security vulnerabilities:
- **Do not** create public issues
- Email maintainers directly (when available)
- Provide detailed information privately
- Allow time for fix before disclosure

## Feature Requests

### Before Requesting

1. **Check existing issues** for similar requests
2. **Consider the scope** - does it fit the project goals?
3. **Think about implementation** - how would it work?

### Feature Request Format

```markdown
**Feature Summary**
Brief description of the feature

**Problem Statement**
What problem does this solve?

**Proposed Solution**
How should this work?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Use cases, examples, mockups
```

## Development Guidelines

### Architecture Principles

1. **Separation of Concerns**
   - Models handle data and business logic
   - Services handle external integrations
   - Views handle HTTP requests/responses
   - Templates handle presentation

2. **Error Handling**
   - Use specific exception types
   - Log errors with context
   - Provide meaningful error messages
   - Handle edge cases gracefully

3. **Performance**
   - Optimize database queries
   - Use appropriate caching
   - Consider resource usage
   - Profile when needed

### Adding New Features

#### Models
- Follow Django model conventions
- Add proper validation
- Include helpful methods
- Write comprehensive tests

#### Services  
- Keep services focused
- Handle errors appropriately
- Mock external dependencies in tests
- Document public interfaces

#### Admin Interface
- Provide useful admin actions
- Add appropriate filters
- Include helpful displays
- Test admin functionality

#### Management Commands
- Follow Django command conventions
- Add helpful arguments and options
- Include progress feedback
- Handle interruption gracefully

## Getting Help

### Resources

- **Documentation**: Check the `docs/` directory
- **Issues**: Search existing GitHub issues
- **Discussions**: Use GitHub Discussions for questions
- **Code Examples**: Look at existing code for patterns

### Community

- Be patient when asking for help
- Provide context and examples
- Search before asking
- Help others when you can

## Recognition

Contributors will be acknowledged in:
- Release notes
- Contributor lists
- Documentation credits

Thank you for contributing to Django Docker Container Manager!