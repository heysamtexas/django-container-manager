# Demo Project Setup Specification

## Repository Structure

```
django-container-manager-demo/
├── README.md                    # Setup and usage instructions
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project metadata and tools config
├── .env.example                # Environment variables template
├── Dockerfile                  # Single production-ready image
├── docker-compose.yml          # Development environment
├── manage.py                   # Django management script
├── data/                       # SQLite database and uploads (bind-mounted)
│   ├── db.sqlite3             # Database file
│   └── uploads/               # File uploads directory
├── demo_project/              # Django project configuration
│   ├── __init__.py
│   ├── settings.py            # Environment-based settings
│   ├── urls.py                # URL routing
│   └── wsgi.py                # WSGI application
└── demo_workflows/            # Demo workflows Django app
    ├── __init__.py
    ├── models.py              # Workflow data models
    ├── admin.py               # Django admin integration
    ├── views.py               # Web interface views
    ├── urls.py                # App URL patterns
    ├── forms.py               # Workflow submission forms
    ├── management/commands/   # Django management commands
    │   ├── crawl_webpage.py
    │   ├── rewrite_text.py
    │   └── analyze_document.py
    ├── templates/demo_workflows/
    │   ├── base.html
    │   ├── dashboard.html
    │   └── workflow_detail.html
    └── static/demo_workflows/
        └── style.css
```

## Environment Configuration

### Environment Variables with django-environ

**`.env.example`** (to be copied to `.env`):
```bash
# Django Core Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=sqlite:///data/db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1

# Docker Socket Configuration (platform-specific)
# Linux/WSL
DOCKER_SOCKET_PATH=/var/run/docker.sock
# macOS with Docker Desktop
# DOCKER_SOCKET_PATH=/var/run/docker.sock
# macOS with Colima
# DOCKER_SOCKET_PATH=${HOME}/.colima/default/docker.sock

# Demo Workflows - API Keys (optional for demo)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Demo Workflows - Configuration
CRAWL_USER_AGENT=Django Container Manager Demo Bot 1.0
CRAWL_TIMEOUT=30
TEXT_REWRITE_MODEL=gpt-3.5-turbo
DOCUMENT_ANALYSIS_MAX_SIZE_MB=10
```

### settings.py Configuration

```python
import environ
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, []),
    CRAWL_TIMEOUT=(int, 30),
    DOCUMENT_ANALYSIS_MAX_SIZE_MB=(int, 10),
)

# Read .env file
environ.Env.read_env(BASE_DIR / '.env')

# Django Core Settings
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Database configuration using DATABASE_URL
DATABASES = {
    'default': env.db()
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'container_manager',          # The package being demonstrated
    'demo_workflows',            # Our demo app
    'solo',                     # For single-instance settings
]

# ... standard Django settings ...

# Demo Workflows Configuration
DEMO_WORKFLOWS = {
    'OPENAI_API_KEY': env('OPENAI_API_KEY', default=''),
    'ANTHROPIC_API_KEY': env('ANTHROPIC_API_KEY', default=''),
    'CRAWL_USER_AGENT': env('CRAWL_USER_AGENT'),
    'CRAWL_TIMEOUT': env('CRAWL_TIMEOUT'),
    'TEXT_REWRITE_MODEL': env('TEXT_REWRITE_MODEL', default='gpt-3.5-turbo'),
    'DOCUMENT_ANALYSIS_MAX_SIZE_MB': env('DOCUMENT_ANALYSIS_MAX_SIZE_MB'),
}

# Media files (for document uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'data' / 'uploads'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

## Database Configuration

### SQLite with Bind Mount Strategy

**Benefits:**
- **Simple setup** - No external database required
- **Data persistence** - Database survives container restarts
- **Easy backup** - Simple file copy
- **Development friendly** - Can inspect with DB browser

**Configuration:**
```yaml
# docker-compose.yml volumes section
volumes:
  - ./data:/app/data  # Bind mount for database and uploads
```

**Database URL Pattern:**
```bash
DATABASE_URL=sqlite:///data/db.sqlite3
```

### Migration Strategy

```python
# Initial setup commands
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## Settings Management with django-solo

### Single-Instance Configuration Model

```python
# demo_workflows/models.py
from solo.models import SingletonModel
from django.db import models

class DemoSettings(SingletonModel):
    """Single-instance configuration for demo workflows"""
    
    # Container Manager Settings
    container_manager_auto_pull = models.BooleanField(
        default=True,
        help_text="Automatically pull Docker images if not available locally"
    )
    container_manager_cleanup = models.BooleanField(
        default=True,
        help_text="Automatically clean up containers after job completion"
    )
    
    # API Integration Settings
    openai_api_key = models.CharField(
        max_length=200, 
        blank=True,
        help_text="OpenAI API key for text rewriting workflows"
    )
    anthropic_api_key = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Anthropic API key for text rewriting workflows"
    )
    
    # Crawler Settings
    crawl_user_agent = models.CharField(
        max_length=200,
        default="Django Container Manager Demo Bot 1.0",
        help_text="User agent string for web crawling"
    )
    
    class Meta:
        verbose_name = "Demo Settings"
        verbose_name_plural = "Demo Settings"
    
    def __str__(self):
        return "Demo Workflows Settings"
```

### Admin Integration

```python
# demo_workflows/admin.py
from django.contrib import admin
from solo.admin import SingletonModelAdmin
from .models import DemoSettings

@admin.register(DemoSettings)
class DemoSettingsAdmin(SingletonModelAdmin):
    fieldsets = (
        ('Container Manager', {
            'fields': ('container_manager_auto_pull', 'container_manager_cleanup')
        }),
        ('API Keys', {
            'fields': ('openai_api_key', 'anthropic_api_key'),
            'description': 'API keys for external services (optional for demo)'
        }),
        ('Crawler Configuration', {
            'fields': ('crawl_user_agent',)
        }),
    )
```

### Runtime Access

```python
# In management commands or views
from demo_workflows.models import DemoSettings

def some_workflow_function():
    settings = DemoSettings.get_solo()
    
    if settings.openai_api_key:
        # Use OpenAI API
        pass
    elif settings.anthropic_api_key:
        # Use Anthropic API
        pass
    else:
        # Return mock/example response
        pass
```

## Dependency Management

### requirements.txt

```
# Core Django and package
django>=5.2,<6.0
django-container-manager>=1.0.0

# Configuration management
django-environ>=0.11.0
django-solo>=2.1.0

# Web crawling
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# AI/ML integration
openai>=1.0.0
anthropic>=0.7.0

# Document processing
pypdf2>=3.0.0
python-magic>=0.4.27

# Web interface
django-bootstrap4>=23.0

# Development tools
django-extensions>=3.2.0
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-container-manager-demo"
version = "1.0.0"
description = "Demonstration project for django-container-manager package"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}

dependencies = [
    "django>=5.2,<6.0",
    "django-container-manager>=1.0.0",
    "django-environ>=0.11.0",
    "django-solo>=2.1.0",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
    "openai>=1.0.0",
    "anthropic>=0.7.0",
    "pypdf2>=3.0.0",
    "django-bootstrap4>=23.0",
]

[project.optional-dependencies]
dev = [
    "django-extensions>=3.2.0",
    "ipython>=8.0.0",
]

# Tool configurations
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "SIM", "B", "C4", "DJ"]
ignore = ["E501", "DJ001", "T201"]
```

## Data Directory Structure

### Bind-Mounted Data Directory

```
data/                          # Bind-mounted to /app/data in container
├── db.sqlite3                # SQLite database file
├── uploads/                  # File uploads for document analysis
│   ├── documents/           # Uploaded documents
│   └── results/             # Generated analysis results
└── logs/                    # Application logs (optional)
    ├── django.log
    └── workflows.log
```

### Volume Configuration

**docker-compose.yml:**
```yaml
services:
  demo:
    volumes:
      # Database and uploads persistence
      - ./data:/app/data
      
      # Docker socket (configurable for different platforms)
      - ${DOCKER_SOCKET_PATH:-/var/run/docker.sock}:/var/run/docker.sock
```

## Platform Compatibility

### Docker Socket Configuration

**Linux/WSL2:**
```bash
DOCKER_SOCKET_PATH=/var/run/docker.sock
```

**macOS with Docker Desktop:**
```bash
DOCKER_SOCKET_PATH=/var/run/docker.sock
```

**macOS with Colima:**
```bash
DOCKER_SOCKET_PATH=${HOME}/.colima/default/docker.sock
```

### Setup Instructions

1. **Clone repository**
2. **Copy environment file:** `cp .env.example .env`
3. **Edit `.env`** for your platform (especially `DOCKER_SOCKET_PATH`)
4. **Build and run:** `docker-compose up --build`
5. **Initialize database:** `docker-compose exec demo python manage.py migrate`
6. **Create admin user:** `docker-compose exec demo python manage.py createsuperuser`
7. **Access application:** http://localhost:8000

This setup provides a clean, environment-driven configuration that works across platforms while maintaining simplicity and focusing on demonstrating the container manager package.