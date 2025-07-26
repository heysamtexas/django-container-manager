# Configuration Reference

Complete configuration reference for Django Multi-Executor Container Manager, covering all configuration options for multi-cloud deployment, routing, cost tracking, and performance monitoring.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Django Settings](#django-settings)
- [Docker Host Configuration](#docker-host-configuration)
- [Cloud Provider Configuration](#cloud-provider-configuration)
- [Routing Rules](#routing-rules)
- [Cost Profiles](#cost-profiles)
- [Performance Settings](#performance-settings)
- [Security Configuration](#security-configuration)

## Environment Variables

### Core Django Settings

```bash
# Required
DJANGO_SETTINGS_MODULE=django_docker_manager.settings
SECRET_KEY=your-super-secret-key-here

# Database
DATABASE_URL=postgresql://user:password@host:port/dbname
# Alternative SQLite for development
# DATABASE_URL=sqlite:///db.sqlite3

# Debug and Environment
DEBUG=False  # Never True in production
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Time Zone
TIME_ZONE=UTC
USE_TZ=True
```

### Multi-Cloud Provider Configuration

#### Google Cloud Platform

```bash
# Required for Cloud Run executor
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Optional: Custom Cloud Run settings
GCP_DEFAULT_REGION=us-central1
GCP_MAX_INSTANCES=1000
GCP_MIN_INSTANCES=0
GCP_CONCURRENCY=80
GCP_TIMEOUT=3600
```

#### AWS (Future Support)

```bash
# AWS Fargate configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
AWS_SESSION_TOKEN=optional-session-token

# ECS/Fargate specific
AWS_ECS_CLUSTER_NAME=container-manager
AWS_ECS_TASK_DEFINITION_FAMILY=container-jobs
AWS_VPC_SUBNET_IDS=subnet-12345,subnet-67890
AWS_SECURITY_GROUP_IDS=sg-abcdef
```

#### Microsoft Azure (Future Support)

```bash
# Azure Container Instances configuration
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id

# ACI specific
AZURE_RESOURCE_GROUP=container-manager-rg
AZURE_LOCATION=eastus
AZURE_DNS_NAME_LABEL=container-manager
```

### Feature Toggles

```bash
# Performance tracking
PERFORMANCE_TRACKING_ENABLED=True
PERFORMANCE_METRICS_RETENTION_DAYS=90

# Cost tracking
COST_TRACKING_ENABLED=True
COST_CALCULATION_METHOD=profile_based  # profile_based, api_metered, estimated

# Migration tools
MIGRATION_ENABLED=True
MIGRATION_MAX_CONCURRENT=5
MIGRATION_DEFAULT_STRATEGY=gradual

# Security features
AUDIT_LOGGING_ENABLED=True
AUDIT_LOG_LEVEL=INFO
EXECUTOR_HEALTH_CHECK_ENABLED=True
HEALTH_CHECK_INTERVAL_SECONDS=30
```

### Redis Configuration

```bash
# For real-time features and channels
REDIS_URL=redis://localhost:6379/0
REDIS_SSL_CERT_REQS=none  # For SSL connections

# Channel layer settings
CHANNEL_LAYER_HOST=localhost
CHANNEL_LAYER_PORT=6379
CHANNEL_LAYER_PREFIX=container_manager
```

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
    'container_manager.cost',
    'container_manager.performance',
    'container_manager.migration',
]

# Container Manager specific settings
CONTAINER_MANAGER = {
    # Executor settings
    'EXECUTOR_TIMEOUT_SECONDS': 3600,
    'MAX_CONCURRENT_JOBS_PER_HOST': 50,
    'DEFAULT_MEMORY_LIMIT_MB': 512,
    'DEFAULT_CPU_LIMIT': 1.0,
    
    # Job processing
    'JOB_POLL_INTERVAL_SECONDS': 5,
    'JOB_CLEANUP_RETENTION_HOURS': 72,
    'MAX_LOG_SIZE_MB': 100,
    
    # Routing
    'ROUTING_ENABLED': True,
    'ROUTING_FALLBACK_EXECUTOR': 'docker',
    'ROUTING_CACHE_TTL_SECONDS': 300,
    
    # Performance
    'PERFORMANCE_TRACKING_ENABLED': True,
    'PERFORMANCE_METRICS_BATCH_SIZE': 100,
    'PERFORMANCE_ALERT_THRESHOLDS': {
        'slow_launch_threshold_ms': 10000,
        'high_cpu_threshold_percent': 80,
        'high_memory_threshold_mb': 1024,
        'high_failure_rate_percent': 10,
    },
    
    # Cost tracking
    'COST_TRACKING_ENABLED': True,
    'COST_UPDATE_INTERVAL_SECONDS': 60,
    'COST_RETENTION_DAYS': 90,
    'DEFAULT_CURRENCY': 'USD',
    
    # Migration
    'MIGRATION_BATCH_SIZE': 10,
    'MIGRATION_BATCH_INTERVAL_SECONDS': 60,
    'MIGRATION_MAX_FAILURE_RATE': 5.0,
    'MIGRATION_ROLLBACK_ENABLED': True,
}

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

## Cloud Provider Configuration

### Google Cloud Run

```python
{
    "name": "gcp-cloudrun-us-central1",
    "host_type": "tcp",
    "connection_string": "https://run.googleapis.com",
    "executor_type": "cloudrun",
    "is_active": True,
    "max_concurrent_jobs": 1000,
    "executor_config": {
        "project_id": "your-project-id",
        "region": "us-central1",
        "service_account": "container-manager@your-project.iam.gserviceaccount.com",
        
        # Resource limits
        "memory_limit": 2048,  # MB
        "cpu_limit": 2.0,      # cores
        "timeout_seconds": 3600,
        
        # Scaling
        "min_instances": 0,
        "max_instances": 100,
        "concurrency": 80,
        
        # Networking
        "vpc_connector": "projects/your-project/locations/us-central1/connectors/default",
        "ingress": "internal",
        
        # Environment
        "env_vars": {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "INFO"
        },
        
        # Security
        "allow_unauthenticated": False,
        "execution_environment": "gen2"
    }
}
```

### AWS Fargate (Future)

```python
{
    "name": "aws-fargate-us-east-1",
    "host_type": "tcp", 
    "connection_string": "https://ecs.us-east-1.amazonaws.com",
    "executor_type": "fargate",
    "is_active": True,
    "max_concurrent_jobs": 500,
    "executor_config": {
        "region": "us-east-1",
        "cluster_name": "container-manager",
        "task_definition_family": "container-jobs",
        
        # Network configuration
        "subnet_ids": ["subnet-12345", "subnet-67890"],
        "security_group_ids": ["sg-abcdef"],
        "assign_public_ip": "ENABLED",
        
        # Resources
        "cpu": 256,        # CPU units (256 = 0.25 vCPU)
        "memory": 512,     # MB
        "platform_version": "LATEST",
        
        # IAM
        "task_role_arn": "arn:aws:iam::123456789012:role/TaskRole",
        "execution_role_arn": "arn:aws:iam::123456789012:role/ExecutionRole",
        
        # Logging
        "log_driver": "awslogs",
        "log_options": {
            "awslogs-group": "/ecs/container-jobs",
            "awslogs-region": "us-east-1",
            "awslogs-stream-prefix": "ecs"
        }
    }
}
```

### Azure Container Instances (Future)

```python
{
    "name": "azure-aci-east-us",
    "host_type": "tcp",
    "connection_string": "https://management.azure.com",
    "executor_type": "azure",
    "is_active": True,
    "max_concurrent_jobs": 200,
    "executor_config": {
        "subscription_id": "your-subscription-id",
        "resource_group": "container-manager-rg",
        "location": "eastus",
        
        # Resources
        "cpu": 1.0,
        "memory": 1.5,  # GB
        "os_type": "Linux",
        "restart_policy": "Never",
        
        # Networking
        "dns_name_label": "container-manager",
        "ip_address_type": "Public",
        "ports": [{"port": 80, "protocol": "TCP"}],
        
        # Environment
        "environment_variables": {
            "ENVIRONMENT": "production"
        },
        
        # Security
        "identity": {
            "type": "SystemAssigned"
        }
    }
}
```

## Routing Rules

### Basic Routing Configuration

```python
# Create routing ruleset
{
    "name": "production-routing",
    "description": "Production routing rules for optimal performance and cost",
    "is_active": True,
    "rules": [
        {
            "name": "small-jobs-docker",
            "condition": "memory_mb <= 512 and timeout_seconds <= 300",
            "target_executor": "docker",
            "priority": 10,
            "description": "Route small, quick jobs to Docker for cost efficiency"
        },
        {
            "name": "large-jobs-cloudrun",
            "condition": "memory_mb > 512 or timeout_seconds > 300",
            "target_executor": "cloudrun", 
            "priority": 20,
            "description": "Route large or long-running jobs to Cloud Run for auto-scaling"
        },
        {
            "name": "urgent-jobs-fastest",
            "condition": "job_name.startswith('urgent_') or job_name.startswith('priority_')",
            "target_executor": "cloudrun",
            "priority": 5,
            "description": "Route urgent jobs to fastest available executor"
        }
    ]
}
```

### Advanced Routing Rules

#### Cost-Aware Routing

```python
{
    "name": "cost-optimization",
    "condition": "estimated_cost < 0.05 and not job_name.startswith('urgent_')",
    "target_executor": "docker",
    "priority": 15,
    "description": "Use Docker for jobs under 5 cents"
}
```

#### Geographic Routing

```python
{
    "name": "us-traffic",
    "condition": "'region=us' in override_environment or 'datacenter=us' in job_name",
    "target_executor": "gcp-cloudrun-us-central1",
    "priority": 8
}
```

### Routing Condition Syntax

Available variables in routing conditions:

```python
# Job properties
memory_mb          # Memory limit in MB
cpu_cores          # CPU core limit
timeout_seconds    # Timeout in seconds
estimated_cost     # Estimated job cost
job_name          # Job name
template_name     # Template name

# Environment variables
override_environment  # JSON string of environment overrides

# Time-based
hour_of_day       # 0-23
day_of_week       # 0-6 (Monday=0)
is_weekend        # Boolean

# Host properties  
available_hosts   # List of available host names
host_load         # Current load percentage

# String operations
startswith(), endswith(), contains(), in

# Comparison operators
==, !=, <, <=, >, >=, and, or, not, in

# Examples
"memory_mb > 1024 and timeout_seconds < 3600"
"'gpu=true' in override_environment"
"hour_of_day >= 9 and hour_of_day <= 17"  # Business hours
"estimated_cost < 0.10 and not is_weekend"
```

## Cost Profiles

### Docker Cost Profile

```python
{
    "name": "docker-local-free",
    "executor_type": "docker",
    "region": "local",
    "cpu_cost_per_core_hour": 0.000000,
    "memory_cost_per_gb_hour": 0.000000,
    "storage_cost_per_gb_hour": 0.000000,
    "network_cost_per_gb": 0.000000,
    "request_cost": 0.000000,
    "startup_cost": 0.000000,
    "currency": "USD",
    "is_active": True
}
```

### Cloud Run Cost Profile

```python
{
    "name": "cloudrun-us-central1-standard",
    "executor_type": "cloudrun",
    "region": "us-central1", 
    "cpu_cost_per_core_hour": 0.000024,   # $0.000024 per vCPU/hour
    "memory_cost_per_gb_hour": 0.0000025, # $0.0000025 per GB/hour
    "storage_cost_per_gb_hour": 0.000000, # No persistent storage cost
    "network_cost_per_gb": 0.12,          # $0.12 per GB egress
    "request_cost": 0.0000004,             # $0.0000004 per request
    "startup_cost": 0.000000,              # No startup cost
    "currency": "USD",
    "is_active": True
}
```

## Performance Settings

### Performance Tracking Configuration

```python
PERFORMANCE_SETTINGS = {
    'TRACKING_ENABLED': True,
    'METRICS_RETENTION_DAYS': 90,
    'BATCH_SIZE': 100,
    'UPDATE_INTERVAL_SECONDS': 60,
    
    # Alert thresholds
    'ALERT_THRESHOLDS': {
        'slow_launch_threshold_ms': 10000,
        'high_cpu_threshold_percent': 80,
        'high_memory_threshold_mb': 1024,
        'high_failure_rate_percent': 10,
        'high_cost_threshold_usd': 1.00,
    },
    
    # Metrics to collect
    'COLLECT_METRICS': [
        'launch_time',
        'execution_duration', 
        'memory_usage',
        'cpu_usage',
        'network_io',
        'cost_breakdown',
    ],
    
    # Performance optimization
    'AUTO_OPTIMIZATION_ENABLED': True,
    'OPTIMIZATION_RULES': {
        'prefer_faster_executor_if_cost_similar': True,
        'suggest_resource_adjustments': True,
        'detect_resource_waste': True,
    }
}
```

### Executor Health Check Settings

```python
HEALTH_CHECK_SETTINGS = {
    'ENABLED': True,
    'INTERVAL_SECONDS': 30,
    'TIMEOUT_SECONDS': 10,
    'MAX_FAILURES': 3,
    'FAILURE_RESET_HOURS': 1,
    
    # Health check methods per executor type
    'METHODS': {
        'docker': 'docker_ping',
        'cloudrun': 'gcp_api_check',
        'fargate': 'aws_api_check',
        'azure': 'azure_api_check',
    },
    
    # Actions on health check failure
    'FAILURE_ACTIONS': {
        'disable_executor': True,
        'send_alert': True,
        'trigger_failover': True,
    }
}
```

## Security Configuration

### Authentication and Authorization

```python
# Service account configurations per cloud provider

# Google Cloud
GCP_SERVICE_ACCOUNT = {
    'type': 'service_account',
    'project_id': 'your-project-id',
    'private_key_id': 'key-id',
    'private_key': '-----BEGIN PRIVATE KEY-----\n...',
    'client_email': 'container-manager@your-project.iam.gserviceaccount.com',
    'client_id': 'client-id',
    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
    'token_uri': 'https://oauth2.googleapis.com/token',
}

# Required IAM roles for GCP service account:
# - roles/run.admin
# - roles/logging.viewer
# - roles/monitoring.viewer
```

### Network Security

```python
NETWORK_SECURITY = {
    # Container networking
    'DOCKER_NETWORK_ISOLATION': True,
    'CUSTOM_NETWORKS_ONLY': True,
    'BRIDGE_ACCESS_RESTRICTED': True,
    
    # Cloud provider network settings
    'VPC_CONNECTOR_REQUIRED': True,
    'PRIVATE_IP_ONLY': False,
    'INGRESS_CONTROL': 'internal',
    
    # Firewall rules
    'ALLOWED_PORTS': [80, 443, 8080],
    'EGRESS_RESTRICTIONS': {
        'block_private_ips': False,
        'allowed_domains': ['*.googleapis.com', '*.docker.io'],
    }
}
```

### Secret Management

```python
SECRET_MANAGEMENT = {
    'ENVIRONMENT_VARIABLE_ENCRYPTION': True,
    'SECRET_MASKING_IN_LOGS': True,
    'SECRET_PATTERNS': [
        r'.*_SECRET.*',
        r'.*_PASSWORD.*', 
        r'.*_KEY.*',
        r'.*_TOKEN.*',
    ],
    
    # External secret stores
    'SECRET_PROVIDERS': {
        'hashicorp_vault': {
            'enabled': False,
            'url': 'https://vault.example.com',
            'auth_method': 'kubernetes',
        },
        'aws_secrets_manager': {
            'enabled': False,
            'region': 'us-east-1',
        },
        'azure_key_vault': {
            'enabled': False,
            'vault_url': 'https://vault.vault.azure.net/',
        },
        'gcp_secret_manager': {
            'enabled': False,
            'project_id': 'your-project-id',
        }
    }
}
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

## Configuration Validation

### Validation Commands

```bash
# Validate complete configuration
uv run python manage.py validate_config

# Validate specific components
uv run python manage.py validate_config --component=executors
uv run python manage.py validate_config --component=routing
uv run python manage.py validate_config --component=cost_profiles

# Test all executor connections
uv run python manage.py test_connections --all

# Validate routing rules
uv run python manage.py validate_routing --verbose

# Check performance settings
uv run python manage.py check_performance_config
```

### Configuration Export/Import

```bash
# Export current configuration
uv run python manage.py export_config --format=yaml --output=config.yaml

# Import configuration
uv run python manage.py import_config --file=config.yaml --validate

# Backup configuration
uv run python manage.py backup_config --include-secrets --output=backup.json
```

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

This comprehensive configuration reference covers all major aspects of the Django Multi-Executor Container Manager. Refer to specific sections for detailed setup instructions for your environment.

For deployment-specific configuration, see the [Deployment Guide](deployment.md).