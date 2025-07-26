# Configuration Reference

This document covers all configuration options for Django Docker Container Manager.

## Django Settings

### Core Application Settings

```python
# settings.py

# Required applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',                # WebSocket support
    'container_manager',       # Core application
]

# ASGI application for WebSocket support
ASGI_APPLICATION = 'django_docker_manager.asgi.application'

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'django_docker_manager',
        'USER': 'django_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Redis channel layer for WebSockets
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

### Environment Variables

```bash
# Core Django settings
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,yourdomain.com

# Database configuration
DATABASE_URL=postgresql://user:pass@localhost/dbname

# Redis configuration
REDIS_URL=redis://localhost:6379/0

# Container management settings
DOCKER_HOSTS=unix:///var/run/docker.sock,tcp://docker-host:2376
CONTAINER_CLEANUP_HOURS=24
MAX_CONCURRENT_JOBS=10
JOB_POLL_INTERVAL=5

# Logging configuration
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security settings
SECURE_SSL_REDIRECT=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
```

## Docker Host Configuration

### Unix Socket Configuration
```python
# Local Docker daemon via Unix socket
{
    "name": "local-docker",
    "host_type": "unix",
    "connection_string": "unix:///var/run/docker.sock",
    "is_active": True,
    "tls_enabled": False,
    "tls_verify": False
}
```

### TCP Configuration
```python
# Remote Docker daemon via TCP
{
    "name": "remote-docker",
    "host_type": "tcp", 
    "connection_string": "tcp://192.168.1.100:2376",
    "is_active": True,
    "tls_enabled": True,
    "tls_verify": True
}
```

### TLS Configuration
For secure remote connections:

```bash
# Client certificate files should be placed in:
/etc/docker/certs/
├── ca.pem          # Certificate Authority
├── cert.pem        # Client certificate
└── key.pem         # Client private key
```

## Container Template Configuration

### Basic Template
```python
{
    "name": "basic-task",
    "description": "Basic container template for simple tasks",
    "docker_image": "ubuntu:22.04",
    "command": "echo 'Hello World'",
    "working_directory": "/app",
    "memory_limit": 256,      # MB
    "cpu_limit": 0.5,         # CPU cores
    "timeout_seconds": 3600,  # 1 hour
    "auto_remove": True
}
```

### Advanced Template with Environment Variables
```python
{
    "name": "django-task",
    "description": "Django application task runner",
    "docker_image": "myapp:latest",
    "command": "python manage.py process_data",
    "working_directory": "/app",
    "memory_limit": 1024,
    "cpu_limit": 2.0,
    "timeout_seconds": 7200,
    "auto_remove": True,
    "environment_variables": [
        {
            "key": "DATABASE_URL",
            "value": "postgresql://user:pass@db:5432/myapp",
            "is_secret": False
        },
        {
            "key": "SECRET_KEY", 
            "value": "your-secret-key",
            "is_secret": True
        },
        {
            "key": "REDIS_URL",
            "value": "redis://redis:6379/0",
            "is_secret": False
        }
    ],
    "network_assignments": [
        {
            "network_name": "app-network",
            "aliases": ["task-runner"]
        }
    ]
}
```

### GPU-Enabled Template
```python
{
    "name": "ml-training",
    "description": "Machine learning training with GPU support",
    "docker_image": "tensorflow/tensorflow:latest-gpu",
    "command": "python train_model.py",
    "memory_limit": 8192,     # 8GB
    "cpu_limit": 4.0,
    "timeout_seconds": 86400, # 24 hours
    "auto_remove": False,     # Keep for inspection
    "environment_variables": [
        {
            "key": "NVIDIA_VISIBLE_DEVICES",
            "value": "0",
            "is_secret": False
        },
        {
            "key": "CUDA_VISIBLE_DEVICES", 
            "value": "0",
            "is_secret": False
        }
    ]
}
```

## Resource Management

### Memory Limits
```python
# Memory limits in MB
"memory_limit": 512    # 512 MB
"memory_limit": 1024   # 1 GB  
"memory_limit": 4096   # 4 GB
"memory_limit": None   # No limit (not recommended)
```

### CPU Limits
```python
# CPU limits as decimal cores
"cpu_limit": 0.5       # Half a CPU core
"cpu_limit": 1.0       # One full CPU core
"cpu_limit": 2.5       # Two and a half CPU cores
"cpu_limit": None      # No limit (not recommended)
```

### Timeout Configuration
```python
# Timeout in seconds
"timeout_seconds": 300     # 5 minutes
"timeout_seconds": 3600    # 1 hour
"timeout_seconds": 86400   # 24 hours
```

## Network Configuration

### Docker Networks
```python
# Single network assignment
"network_assignments": [
    {
        "network_name": "default",
        "aliases": []
    }
]

# Multiple networks with aliases
"network_assignments": [
    {
        "network_name": "app-network",
        "aliases": ["api-worker", "task-runner"]
    },
    {
        "network_name": "data-network", 
        "aliases": ["data-processor"]
    }
]
```

### Network Creation
```bash
# Create custom Docker networks
docker network create app-network
docker network create data-network --driver bridge
docker network create isolated-network --internal
```

## Job Processing Configuration

### Worker Settings
```python
# Management command options
CONTAINER_JOB_SETTINGS = {
    'POLL_INTERVAL': 5,           # Seconds between job polls
    'MAX_JOBS': 10,               # Maximum concurrent jobs
    'SINGLE_RUN': False,          # Run continuously
    'CLEANUP_ENABLED': True,      # Auto-cleanup old containers
    'CLEANUP_HOURS': 24,          # Hours to retain containers
}
```

### Job Queue Configuration
```python
# Database-based job queue settings
JOB_QUEUE_SETTINGS = {
    'MAX_RETRIES': 3,             # Maximum retry attempts
    'RETRY_DELAY': 300,           # Seconds between retries
    'BATCH_SIZE': 50,             # Jobs to process per batch
    'PRIORITY_ENABLED': True,     # Enable job priorities
}
```

## Logging Configuration

### Standard Logging
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"level": "{levelname}", "time": "{asctime}", "module": "{module}", "message": "{message}"}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'django_docker_manager.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'container_manager': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Container Logs
```python
# Container log collection settings
CONTAINER_LOG_SETTINGS = {
    'COLLECT_STDOUT': True,       # Collect stdout logs
    'COLLECT_STDERR': True,       # Collect stderr logs
    'MAX_LOG_SIZE': 1048576,      # 1MB max log size
    'LOG_ROTATION': True,         # Enable log rotation
    'RETENTION_DAYS': 7,          # Days to retain logs
}
```

## Security Configuration

### Docker Socket Security
```bash
# Restrict Docker socket access
sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock

# Use Docker socket proxy for additional security
docker run -d \
    --name docker-socket-proxy \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -p 2375:2375 \
    tecnativa/docker-socket-proxy
```

### TLS Configuration
```python
# TLS settings for remote Docker hosts
TLS_SETTINGS = {
    'CERT_PATH': '/etc/docker/certs/cert.pem',
    'KEY_PATH': '/etc/docker/certs/key.pem', 
    'CA_PATH': '/etc/docker/certs/ca.pem',
    'VERIFY': True,
    'VERSION': 'TLSv1.2'
}
```

### Secret Management
```python
# Environment variable encryption
SECRET_SETTINGS = {
    'ENCRYPTION_KEY': 'your-encryption-key',
    'HASH_ALGORITHM': 'SHA256',
    'MASK_SECRETS': True,         # Mask secrets in logs
    'SECRET_KEYWORDS': [          # Keywords to identify secrets
        'password', 'key', 'token', 'secret', 'credential'
    ]
}
```

## Monitoring Configuration

### Health Checks
```python
# Health check endpoints
HEALTH_CHECK_SETTINGS = {
    'ENABLED': True,
    'DOCKER_HOST_CHECK': True,    # Check Docker host connectivity
    'DATABASE_CHECK': True,       # Check database connectivity
    'REDIS_CHECK': True,          # Check Redis connectivity
    'DISK_SPACE_CHECK': True,     # Check available disk space
    'MEMORY_CHECK': True,         # Check available memory
}
```

### Metrics Collection
```python
# Metrics collection settings
METRICS_SETTINGS = {
    'ENABLED': True,
    'COLLECTION_INTERVAL': 60,    # Seconds
    'RETENTION_DAYS': 30,         # Days to retain metrics
    'EXPORT_PROMETHEUS': True,    # Export Prometheus metrics
    'EXPORT_GRAFANA': True,       # Export Grafana dashboard
}
```

## Performance Tuning

### Database Optimization
```python
# Database connection pooling
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'django_docker_manager',
        'USER': 'django_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        },
        'CONN_MAX_AGE': 300,
    }
}
```

### Caching Configuration
```python
# Redis caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 300,
        'KEY_PREFIX': 'django_docker_manager'
    }
}
```

## Example Configuration Files

### Production settings.py
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes', 
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'container_manager',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'django_docker_manager'),
        'USER': os.environ.get('DB_USER', 'django_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.environ.get('REDIS_HOST', '127.0.0.1'), 6379)],
        },
    },
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://user:pass@db:5432/django_docker_manager
      - REDIS_URL=redis://redis:6379/0
      - ALLOWED_HOSTS=localhost,yourdomain.com
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - db
      - redis
    restart: unless-stopped

  worker:
    build: .
    command: python manage.py process_container_jobs --poll-interval=5 --max-jobs=10
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://user:pass@db:5432/django_docker_manager
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: django_docker_manager
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

## Validation

### Configuration Testing
```bash
# Test configuration
uv run python manage.py check

# Test database connectivity
uv run python manage.py dbshell

# Test Docker connectivity
uv run python manage.py shell -c "
from container_manager.docker_service import docker_service
from container_manager.models import DockerHost
for host in DockerHost.objects.filter(is_active=True):
    try:
        client = docker_service.get_client(host)
        print(f'{host.name}: Connected')
    except Exception as e:
        print(f'{host.name}: Failed - {e}')
"
```

For deployment-specific configuration, see the [Deployment Guide](deployment.md).