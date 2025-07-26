# Django Package Conversion Specification

## Overview
Convert the existing `container_manager` Django app into a standalone, distributable Python package that users can `pip install` and add to any Django project for immediate container orchestration capabilities.

## Current State Analysis

### Isolation Status: 9/10 ✅
The `container_manager` app is exceptionally well-architected with minimal coupling to the parent project:

- ✅ **Complete Django app structure** with proper organization
- ✅ **Zero hardcoded project dependencies** 
- ✅ **Proper relative imports** throughout codebase
- ✅ **Self-contained templates and static files**
- ✅ **Standard Django patterns** everywhere
- ✅ **All migrations use `AUTH_USER_MODEL`** (not hardcoded User model)

### Dependencies Found (Minimal)
Only **4 settings references** that need fallback logic:
1. `CONTAINER_MANAGER` setting (used in 3 files)
2. `USE_EXECUTOR_FACTORY` setting (used in 1 file)

## Implementation Plan

### Phase 1: App Isolation (15 minutes)

#### 1.1 Create Default Settings Module
**File: `container_manager/defaults.py`**
```python
"""
Default settings for django-container-manager.
These can be overridden in Django settings.py
"""

DEFAULT_CONTAINER_MANAGER_SETTINGS = {
    "AUTO_PULL_IMAGES": True,
    "IMAGE_PULL_TIMEOUT": 300,
    "IMMEDIATE_CLEANUP": True, 
    "CLEANUP_ENABLED": True,
    "MAX_CONCURRENT_JOBS": 10,
    "POLL_INTERVAL": 5,
}

DEFAULT_USE_EXECUTOR_FACTORY = False
```

#### 1.2 Update Settings References
Replace hardcoded settings with fallback logic in these files:
- `container_manager/executors/docker.py`
- `container_manager/docker_service_original.py` 
- `container_manager/management/commands/cleanup_containers.py`
- `container_manager/management/commands/process_container_jobs.py`

**Pattern:**
```python
# Before:
container_settings = getattr(settings, "CONTAINER_MANAGER", {})

# After:
from .defaults import DEFAULT_CONTAINER_MANAGER_SETTINGS
container_settings = getattr(settings, "CONTAINER_MANAGER", DEFAULT_CONTAINER_MANAGER_SETTINGS)
```

#### 1.3 Verify App Independence
- Test app with minimal Django project
- Confirm no dependencies on `django_docker_manager`
- Validate all functionality works with defaults

### Phase 2: Package Structure (15 minutes)

#### 2.1 Update Package Configuration
**File: `pyproject.toml`**
```toml
[project]
name = "django-container-manager"
version = "1.0.0"
description = "Django app for container orchestration with multi-executor support"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
keywords = ["django", "containers", "docker", "orchestration", "cloud-run", "aws-fargate"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Framework :: Django",
    "Framework :: Django :: 4.2",
    "Framework :: Django :: 5.0",
    "Framework :: Django :: 5.1", 
    "Framework :: Django :: 5.2",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: System :: Distributed Computing",
]

dependencies = [
    "django>=4.2",
    "docker>=6.0.0",
    "psutil>=5.9.0",
]

[project.optional-dependencies]
cloud = [
    "google-cloud-run>=0.10.0",
    "boto3>=1.26.0",
]
dev = [
    "ruff>=0.1.0",
    "pytest>=7.0.0",
    "pytest-django>=4.5.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/django-container-manager"
Documentation = "https://django-container-manager.readthedocs.io/"
Repository = "https://github.com/yourusername/django-container-manager.git"
Issues = "https://github.com/yourusername/django-container-manager/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["container_manager"]

[tool.hatch.build.targets.sdist]
include = [
    "/container_manager",
    "/README.md",
    "/LICENSE",
]
```

#### 2.2 Add Distribution Files
**File: `MANIFEST.in`**
```
include README.md
include LICENSE
include CHANGELOG.md
recursive-include container_manager/templates *
recursive-include container_manager/static *
recursive-include container_manager/migrations *.py
```

**File: `LICENSE`**
```
MIT License

Copyright (c) 2024 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Phase 3: Documentation & Examples (10 minutes)

#### 3.1 Update README.md
**File: `README.md`**
```markdown
# Django Container Manager

A Django app for container orchestration with multi-executor support (Docker, Google Cloud Run, AWS Fargate).

## Features

- 🐳 **Multi-executor support**: Docker, Google Cloud Run, AWS Fargate, Mock
- ⚖️ **Weight-based routing**: Simple load distribution across hosts
- 📊 **Job tracking**: Complete lifecycle management with logs and metrics
- 🎛️ **Admin interface**: Django admin integration for easy management
- 🔧 **Management commands**: CLI tools for job and container management
- 📦 **Environment overrides**: Job-level customization of commands and variables

## Installation

```bash
pip install django-container-manager
```

## Quick Start

1. Add to your Django project:

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    # ... your other apps
    'container_manager',  # Add this
]
```

2. Run migrations:

```bash
python manage.py migrate
```

3. Create a superuser and access admin:

```bash
python manage.py createsuperuser
python manage.py runserver
# Visit http://localhost:8000/admin/
```

4. Start the job processor:

```bash
python manage.py process_container_jobs
```

## Configuration (Optional)

```python
# settings.py
CONTAINER_MANAGER = {
    "AUTO_PULL_IMAGES": True,
    "CLEANUP_ENABLED": True,
    "MAX_CONCURRENT_JOBS": 10,
    "POLL_INTERVAL": 5,
}
```

## Usage

1. **Create Docker Host** in admin interface
2. **Create Container Template** with image and settings  
3. **Create Container Job** from template
4. **Monitor execution** in admin or via management commands

See full documentation at [django-container-manager.readthedocs.io](https://django-container-manager.readthedocs.io/)
```

#### 3.2 Create Quick Start Guide
**File: `QUICKSTART.md`**
```markdown
# Quick Start Guide

## Basic Setup

### 1. Installation
```bash
pip install django-container-manager
```

### 2. Django Configuration
```python
# settings.py
INSTALLED_APPS = [
    # ... existing apps
    'container_manager',
]

# Optional settings
CONTAINER_MANAGER = {
    "AUTO_PULL_IMAGES": True,
    "CLEANUP_ENABLED": True,
}
```

### 3. Database Setup
```bash
python manage.py migrate
```

## First Container Job

### 1. Create Docker Host
```python
from container_manager.models import DockerHost

host = DockerHost.objects.create(
    name="local-docker",
    executor_type="docker",
    connection_string="unix:///var/run/docker.sock",
    weight=100
)
```

### 2. Create Template
```python
from container_manager.models import ContainerTemplate

template = ContainerTemplate.objects.create(
    name="hello-world",
    docker_image="hello-world",
    timeout_seconds=60
)
```

### 3. Create and Run Job
```python
from container_manager.models import ContainerJob

job = ContainerJob.objects.create(
    template=template,
    docker_host=host,
    name="My First Job"
)
```

### 4. Start Job Processor
```bash
python manage.py process_container_jobs
```
```

### Phase 4: Testing & Validation (10 minutes)

#### 4.1 Create Test Installation Script
**File: `test_installation.py`**
```python
#!/usr/bin/env python3
"""
Test script to validate django-container-manager package installation
"""
import subprocess
import sys
import tempfile
import os

def test_package_installation():
    """Test installing and using the package in a fresh Django project"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        
        # Create minimal Django project
        subprocess.run([sys.executable, "-m", "django", "startproject", "testproject"], check=True)
        os.chdir("testproject")
        
        # Install our package (assuming built locally)
        subprocess.run([sys.executable, "-m", "pip", "install", "../path/to/built/package"], check=True)
        
        # Add to settings
        settings_content = '''
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth', 
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'container_manager',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

SECRET_KEY = 'test-key-not-for-production'
'''
        
        with open('testproject/settings.py', 'w') as f:
            f.write(settings_content)
        
        # Test migrations
        subprocess.run([sys.executable, "manage.py", "migrate"], check=True)
        
        # Test management commands
        result = subprocess.run([sys.executable, "manage.py", "help"], 
                              capture_output=True, text=True)
        assert "process_container_jobs" in result.stdout
        
        print("✅ Package installation test passed!")

if __name__ == "__main__":
    test_package_installation()
```

#### 4.2 Build and Test Package
```bash
# Build package
python -m build

# Test installation locally
pip install dist/django_container_manager-1.0.0-py3-none-any.whl

# Run tests
python test_installation.py
```

## Expected User Experience

### Installation
```bash
pip install django-container-manager
```

### Configuration  
```python
# settings.py - Minimal required
INSTALLED_APPS = [
    # ... existing apps
    'container_manager',
]

# Optional customization
CONTAINER_MANAGER = {
    "AUTO_PULL_IMAGES": True,
    "MAX_CONCURRENT_JOBS": 5,
}
```

### Usage
```bash
python manage.py migrate
python manage.py process_container_jobs  # Start job processor
```

**Result: Full container orchestration system ready to use!**

## Success Criteria

- ✅ Package installs via `pip install django-container-manager`
- ✅ Works with zero required configuration (sensible defaults)
- ✅ All functionality preserved from original app
- ✅ Admin interface accessible immediately after migration
- ✅ Management commands available and functional
- ✅ Can be added to any Django project without conflicts

## Time Estimate: ~50 minutes

The app is already exceptionally well-architected for this conversion, following Django best practices with minimal coupling to the parent project.

## Migration Path for Existing Users

Existing users can migrate by:
1. Uninstalling old app
2. Installing package: `pip install django-container-manager`
3. No settings changes required (backwards compatible)
4. Existing data preserved (same migration history)