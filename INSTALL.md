# Installation Guide

Complete installation instructions for Django Docker Container Manager across all platforms and deployment scenarios.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Installation](#development-installation)
- [Production Installation](#production-installation)
- [Docker Configuration](#docker-configuration)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Upgrading](#upgrading)

## Prerequisites

### System Requirements

| Component | Minimum Version | Recommended | Notes |
|-----------|----------------|-------------|-------|
| **Python** | 3.8 | 3.11+ | Use pyenv for version management |
| **Docker** | 20.10 | 24.0+ | Docker Desktop or Docker Engine |
| **Django** | 4.2 | 5.2+ | Automatically installed |
| **Memory** | 2GB | 4GB+ | For container workloads |
| **Disk** | 5GB | 20GB+ | Docker images and logs |

### Required Software Installation

#### 1. Python Installation

```mermaid
flowchart TD
    A[Check Python Version] --> B{Python 3.8+?}
    B -->|Yes| C[✅ Python Ready]
    B -->|No| D[Install Python]
    D --> E{Platform?}
    E -->|macOS| F[brew install python@3.11]
    E -->|Ubuntu| G[sudo apt update && sudo apt install python3.11]
    E -->|Windows| H[Download from python.org]
    F --> C
    G --> C
    H --> C
```

**Check current Python version:**
```bash
python3 --version
# Should output: Python 3.8.0 or higher
```

**Install Python by platform:**

**macOS:**
```bash
# Using Homebrew (recommended)
brew install python@3.11
brew link python@3.11

# Verify installation
python3.11 --version
```

**Ubuntu/Debian:**
```bash
# Update package list
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev

# Verify installation
python3.11 --version
```

**Windows:**
1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run installer with "Add Python to PATH" checked
3. Verify in Command Prompt: `python --version`

#### 2. Docker Installation

**Verify Docker is installed:**
```bash
docker --version
docker-compose --version
```

**Install Docker by platform:**

**macOS:**
```bash
# Using Homebrew
brew install --cask docker

# Or download Docker Desktop from:
# https://desktop.docker.com/mac/main/amd64/Docker.dmg
```

**Ubuntu/Debian:**
```bash
# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Logout and login to refresh groups
```

**Windows:**
1. Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
2. Run installer and restart when prompted
3. Enable WSL 2 backend if prompted

**Start Docker daemon:**
```bash
# macOS/Windows (Docker Desktop)
# Start Docker Desktop application

# Linux
sudo systemctl start docker
sudo systemctl enable docker

# Verify Docker is running
docker ps
```

#### 3. uv Package Manager (Recommended)

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Verify installation
uv --version
```

### Optional but Recommended

#### Git (for development)
```bash
# macOS
brew install git

# Ubuntu/Debian
sudo apt install git

# Windows
# Download from: https://git-scm.com/download/win
```

#### PostgreSQL (for production)
```bash
# macOS
brew install postgresql
brew services start postgresql

# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Windows
# Download from: https://www.postgresql.org/download/windows/
```

## Development Installation

### Quick Development Setup (5 minutes)

1. **Clone the repository:**
```bash
git clone https://github.com/your-org/django-docker-container-manager.git
cd django-docker-container-manager
```

2. **Set up Python environment:**
```bash
# Using uv (recommended)
uv sync

# Or using venv + pip
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
pip install -e .
```

3. **Configure environment variables:**
```bash
# Create .env file
cat > .env << EOF
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=sqlite:///dev.db
DOCKER_HOST=unix:///var/run/docker.sock
LOG_LEVEL=INFO
EOF
```

4. **Set up database:**
```bash
# Run migrations
uv run python manage.py migrate

# Create superuser for admin access
uv run python manage.py createsuperuser
```

5. **Verify Docker integration:**
```bash
# Test Docker connection
docker ps

# If permission denied, add user to docker group:
sudo usermod -aG docker $USER
# Then logout and login again
```

6. **Start development server:**
```bash
# Terminal 1: Start Django development server
uv run python manage.py runserver

# Terminal 2: Start job processor (CRITICAL)
uv run python manage.py process_container_jobs

# Access admin at: http://localhost:8000/admin/
```

### Development Configuration

#### Settings for Development

Create `local_settings.py` (optional):
```python
# local_settings.py
from .settings import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'dev.db',
    }
}

# Container Manager settings
CONTAINER_MANAGER_SETTINGS = {
    'AUTO_PULL_IMAGES': True,
    'IMMEDIATE_CLEANUP': True,
    'DOCKER_TIMEOUT': 30,
    'MAX_CONCURRENT_JOBS': 5,
    'POLL_INTERVAL': 5,
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'container_manager': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

#### Docker Compose for Development

Create `docker-compose.dev.yml`:
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DEBUG=true
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/container_manager
    depends_on:
      - postgres
      - redis
    command: >
      sh -c "python manage.py migrate &&
             python manage.py runserver 0.0.0.0:8000"

  job-processor:
    build: .
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DEBUG=true
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/container_manager
    depends_on:
      - postgres
      - app
    command: python manage.py process_container_jobs

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=container_manager
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

Start development environment:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

## Production Installation

### Production Environment Preparation

#### 1. System Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    build-essential \
    libpq-dev \
    nginx \
    supervisor \
    curl \
    git
```

#### 2. Create Application User

```bash
# Create dedicated user for the application
sudo useradd --system --shell /bin/bash --home /opt/container-manager container-manager
sudo mkdir -p /opt/container-manager
sudo chown container-manager:container-manager /opt/container-manager
```

#### 3. Application Deployment

```bash
# Switch to application user
sudo -u container-manager -i

# Navigate to application directory
cd /opt/container-manager

# Clone application
git clone https://github.com/your-org/django-docker-container-manager.git app
cd app

# Set up Python environment
python3.11 -m venv venv
source venv/bin/activate

# Install application
pip install --upgrade pip
pip install -e .
```

#### 4. Production Configuration

Create production environment file:
```bash
# Create secure environment file
sudo -u container-manager cat > /opt/container-manager/app/.env << EOF
DEBUG=false
SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DATABASE_URL=postgresql://container_manager:secure_password@localhost:5432/container_manager
DOCKER_HOST=unix:///var/run/docker.sock
LOG_LEVEL=INFO

# Security settings
SECURE_SSL_REDIRECT=true
SECURE_BROWSER_XSS_FILTER=true
SECURE_CONTENT_TYPE_NOSNIFF=true
X_FRAME_OPTIONS=DENY

# Container Manager settings
CONTAINER_MANAGER_AUTO_PULL_IMAGES=true
CONTAINER_MANAGER_IMMEDIATE_CLEANUP=false
CONTAINER_MANAGER_MAX_CONCURRENT_JOBS=20
CONTAINER_MANAGER_DOCKER_TIMEOUT=60
EOF

# Secure the environment file
chmod 600 /opt/container-manager/app/.env
```

#### 5. Database Setup

```bash
# Create PostgreSQL database and user
sudo -u postgres psql << EOF
CREATE DATABASE container_manager;
CREATE USER container_manager WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE container_manager TO container_manager;
ALTER USER container_manager CREATEDB;  -- For running tests if needed
\q
EOF

# Run migrations
cd /opt/container-manager/app
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput

# Create admin user
python manage.py createsuperuser
```

#### 6. Web Server Configuration

**Nginx Configuration:**
```bash
# Create Nginx configuration
sudo cat > /etc/nginx/sites-available/container-manager << 'EOF'
upstream container_manager_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL Configuration (use certbot for Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    
    # Static files
    location /static/ {
        alias /opt/container-manager/app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Application
    location / {
        proxy_pass http://container_manager_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/container-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 7. Process Management

**Supervisor Configuration:**
```bash
# Create supervisor configuration for Django app
sudo cat > /etc/supervisor/conf.d/container-manager-app.conf << 'EOF'
[program:container-manager-app]
command=/opt/container-manager/app/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 container_manager.wsgi
directory=/opt/container-manager/app
user=container-manager
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/supervisor/container-manager-app.log
environment=PATH="/opt/container-manager/app/venv/bin"
EOF

# Create supervisor configuration for job processor
sudo cat > /etc/supervisor/conf.d/container-manager-jobs.conf << 'EOF'
[program:container-manager-jobs]
command=/opt/container-manager/app/venv/bin/python manage.py process_container_jobs
directory=/opt/container-manager/app
user=container-manager
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/supervisor/container-manager-jobs.log
environment=PATH="/opt/container-manager/app/venv/bin"
EOF

# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

#### 8. Docker Configuration for Production

```bash
# Add container-manager user to docker group
sudo usermod -aG docker container-manager

# Configure Docker daemon for production
sudo cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "userland-proxy": false,
  "live-restore": true,
  "default-ulimits": {
    "nofile": {
      "Hard": 64000,
      "Name": "nofile",
      "Soft": 64000
    }
  }
}
EOF

# Restart Docker daemon
sudo systemctl restart docker
```

## Docker Configuration

### Local Docker Setup

#### Docker Desktop (macOS/Windows)

1. **Configure Docker Desktop:**
   - **Memory**: Allocate at least 4GB RAM
   - **CPU**: Assign 2+ CPU cores
   - **Disk**: Reserve 20GB+ for images
   - **File Sharing**: Enable access to project directory

2. **Verify Docker access:**
```bash
# Test Docker connection
docker info

# Check user permissions
docker run hello-world

# If permission denied on Linux:
sudo usermod -aG docker $USER
# Logout and login again
```

#### Docker Engine (Linux)

1. **Configure Docker daemon:**
```bash
# Create daemon configuration
sudo mkdir -p /etc/docker
sudo cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-address-pools": [
    {"base": "172.17.0.0/16", "size": 24},
    {"base": "172.18.0.0/16", "size": 24}
  ]
}
EOF

# Restart Docker
sudo systemctl restart docker
```

2. **Configure user permissions:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker

# Test access
docker ps
```

### Remote Docker Configuration

#### Connecting to Remote Docker Host

1. **Set up remote Docker host:**
```bash
# On remote host: Enable Docker API
sudo cat > /etc/systemd/system/docker.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// -H tcp://0.0.0.0:2376 --tlsverify --tlscert=/etc/docker/server-cert.pem --tlskey=/etc/docker/server-key.pem --tlscacert=/etc/docker/ca.pem
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
```

2. **Create remote executor host:**
```python
from container_manager.models import ExecutorHost

remote_host = ExecutorHost.objects.create(
    name="production-docker",
    host_type="tcp",
    connection_string="tcp://docker.example.com:2376",
    tls_enabled=True,
    tls_verify=True,
    executor_type="docker",
    max_concurrent_jobs=10,
    weight=100,
    is_active=True
)
```

### Container Networking

#### Network Setup for Container Jobs

```bash
# Create custom networks for container isolation
docker network create --driver bridge app-network
docker network create --driver bridge data-network
docker network create --driver bridge monitoring-network

# List networks
docker network ls
```

#### Network Configuration in Jobs

```python
# Example: Multi-network container job
from container_manager.models import ContainerJob

job = ContainerJob.objects.create_job(
    image="nginx:alpine",
    command="nginx -g 'daemon off;'",
    network_configuration=[
        {"network_name": "app-network", "aliases": ["web"]},
        {"network_name": "monitoring-network", "aliases": ["nginx"]}
    ],
    memory_limit=256,
    cpu_limit=0.5
)
```

## Environment Configuration

### Environment Variables

#### Required Variables

```bash
# Core Django settings
SECRET_KEY=your-secret-key-here
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database configuration
DATABASE_URL=postgresql://user:password@host:5432/database

# Docker configuration
DOCKER_HOST=unix:///var/run/docker.sock

# Application settings
LOG_LEVEL=INFO
```

#### Optional Variables

```bash
# Container Manager specific
CONTAINER_MANAGER_AUTO_PULL_IMAGES=true
CONTAINER_MANAGER_IMMEDIATE_CLEANUP=false
CONTAINER_MANAGER_MAX_CONCURRENT_JOBS=10
CONTAINER_MANAGER_DOCKER_TIMEOUT=60
CONTAINER_MANAGER_POLL_INTERVAL=5

# Security settings
SECURE_SSL_REDIRECT=true
SECURE_BROWSER_XSS_FILTER=true
SECURE_CONTENT_TYPE_NOSNIFF=true
X_FRAME_OPTIONS=DENY

# Cache settings (optional)
CACHE_URL=redis://localhost:6379/0

# Email settings (optional)
EMAIL_URL=smtp://user:password@smtp.example.com:587

# Monitoring (optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
```

#### Environment File Management

**Development (.env):**
```bash
# .env (for development only)
DEBUG=true
SECRET_KEY=dev-secret-key
DATABASE_URL=sqlite:///dev.db
DOCKER_HOST=unix:///var/run/docker.sock
LOG_LEVEL=DEBUG
CONTAINER_MANAGER_AUTO_PULL_IMAGES=true
CONTAINER_MANAGER_IMMEDIATE_CLEANUP=true
```

**Production (secure environment):**
```bash
# Use proper secret management for production
# Examples: AWS Secrets Manager, HashiCorp Vault, etc.

# Environment variables via systemd
sudo systemctl edit container-manager-app
# Add:
# [Service]
# Environment="SECRET_KEY=production-secret"
# Environment="DATABASE_URL=postgresql://..."
```

### Django Settings Configuration

#### Base Settings Structure

```python
# settings/base.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables
from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')

# Security
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database
import dj_database_url
DATABASES = {
    'default': dj_database_url.parse(os.environ.get('DATABASE_URL'))
}

# Container Manager
CONTAINER_MANAGER_SETTINGS = {
    'AUTO_PULL_IMAGES': os.environ.get('CONTAINER_MANAGER_AUTO_PULL_IMAGES', 'true').lower() == 'true',
    'IMMEDIATE_CLEANUP': os.environ.get('CONTAINER_MANAGER_IMMEDIATE_CLEANUP', 'true').lower() == 'true',
    'MAX_CONCURRENT_JOBS': int(os.environ.get('CONTAINER_MANAGER_MAX_CONCURRENT_JOBS', '10')),
    'DOCKER_TIMEOUT': int(os.environ.get('CONTAINER_MANAGER_DOCKER_TIMEOUT', '30')),
    'POLL_INTERVAL': int(os.environ.get('CONTAINER_MANAGER_POLL_INTERVAL', '5')),
}
```

#### Environment-Specific Settings

```python
# settings/development.py
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Use SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'dev.db',
    }
}

# settings/production.py
from .base import *

DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/container-manager/app.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'container_manager': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Database Setup

### SQLite (Development)

SQLite is automatically configured for development and requires no additional setup:

```bash
# Database file will be created automatically
uv run python manage.py migrate

# Location: ./dev.db (or as specified in DATABASE_URL)
```

**SQLite Limitations:**
- Single writer (not suitable for high concurrency)
- No built-in backup/replication
- File-based (not suitable for distributed systems)
- Maximum database size: 281TB (practical limits much lower)

### PostgreSQL (Production)

#### PostgreSQL Installation

**Ubuntu/Debian:**
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**
```bash
# Install with Homebrew
brew install postgresql
brew services start postgresql

# Or with PostgreSQL.app
# Download from: https://postgresapp.com/
```

**Windows:**
```bash
# Download installer from:
# https://www.postgresql.org/download/windows/
```

#### Database and User Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE container_manager;
CREATE USER container_manager WITH PASSWORD 'secure_password_here';

# Grant permissions
GRANT ALL PRIVILEGES ON DATABASE container_manager TO container_manager;
ALTER USER container_manager CREATEDB;  -- For running tests

# Configure connection
ALTER USER container_manager SET client_encoding TO 'utf8';
ALTER USER container_manager SET default_transaction_isolation TO 'read committed';
ALTER USER container_manager SET timezone TO 'UTC';

# Exit psql
\q
```

#### Connection Configuration

**Database URL format:**
```bash
# Basic connection
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# With connection parameters
DATABASE_URL=postgresql://container_manager:password@localhost:5432/container_manager?sslmode=prefer&connect_timeout=10&application_name=django-container-manager
```

**Connection pooling (recommended for production):**
```bash
# Install pgbouncer
sudo apt install pgbouncer

# Configure pgbouncer (/etc/pgbouncer/pgbouncer.ini)
[databases]
container_manager = host=localhost port=5432 dbname=container_manager

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 100
default_pool_size = 25

# Update DATABASE_URL to use pgbouncer
DATABASE_URL=postgresql://container_manager:password@localhost:6432/container_manager
```

#### Database Migration

```bash
# Run initial migrations
python manage.py migrate

# Create database backup (production)
pg_dump container_manager > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup if needed
psql container_manager < backup_20241202_143000.sql
```

### Database Performance Tuning

#### PostgreSQL Configuration

```bash
# Edit postgresql.conf (location varies by installation)
sudo nano /etc/postgresql/15/main/postgresql.conf

# Key settings for container manager workload:
shared_buffers = 256MB                  # 1/4 of available RAM
effective_cache_size = 1GB              # 3/4 of available RAM
work_mem = 4MB                          # For sorting operations
maintenance_work_mem = 64MB             # For maintenance operations
checkpoint_completion_target = 0.9      # Smooth checkpoints
wal_buffers = 16MB                      # WAL buffer size
random_page_cost = 1.1                  # SSD storage
effective_io_concurrency = 200          # SSD concurrent I/O

# Connection settings
max_connections = 100                    # Adjust based on needs
```

#### Database Indexes

The application includes optimized indexes for common queries. Monitor query performance:

```sql
-- Check slow queries (enable log_statement = 'all' temporarily)
SELECT query, mean_time, calls, total_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE tablename LIKE 'container_manager_%';
```

## Verification

### Installation Verification Checklist

#### 1. System Dependencies

```bash
# Check Python version
python3 --version
# Expected: Python 3.8.0 or higher

# Check Docker version
docker --version
# Expected: Docker version 20.10.0 or higher

# Check Docker daemon
docker info
# Should show system information without errors

# Check uv installation
uv --version
# Expected: uv 0.1.0 or higher
```

#### 2. Application Setup

```bash
# Check Django installation
python manage.py --version
# Expected: 4.2.0 or higher

# Check database connectivity
python manage.py dbshell
# Should connect to database without errors
# Type \q to exit

# Check migrations
python manage.py showmigrations
# All migrations should show [X] (applied)

# Run Django system checks
python manage.py check
# Should show: System check identified no issues (0 silenced).
```

#### 3. Docker Integration Test

```bash
# Test basic Docker connectivity
docker run --rm hello-world

# Test Docker from Django shell
python manage.py shell
```

```python
# In Django shell
from container_manager.models import ExecutorHost
from container_manager.executors.factory import ExecutorFactory

# Create test executor host
host = ExecutorHost.objects.create(
    name="test-docker",
    executor_type="docker",
    connection_string="unix:///var/run/docker.sock",
    is_active=True
)

# Test executor creation
executor = ExecutorFactory.create_executor("docker", {"docker_host": host})

# Test Docker health
health = executor.get_health_status()
print(f"Docker healthy: {health['healthy']}")
# Expected: Docker healthy: True

# Clean up
host.delete()
exit()
```

#### 4. Job Execution Test

Create and execute a test container job:

```python
# In Django shell
from container_manager.models import ContainerJob, ExecutorHost

# Create executor host
docker_host = ExecutorHost.objects.create(
    name="verification-docker",
    executor_type="docker", 
    connection_string="unix:///var/run/docker.sock",
    is_active=True
)

# Create test job
test_job = ContainerJob.objects.create_job(
    image="hello-world",
    name="Installation Verification Test",
    memory_limit=128,
    cpu_limit=0.5,
    timeout_seconds=300
)

print(f"Created test job: {test_job.id}")
print(f"Job status: {test_job.status}")

# Job will be picked up by job processor automatically
# Check status after a few moments:
test_job.refresh_from_db()
print(f"Updated status: {test_job.status}")
print(f"Job output: {test_job.clean_output}")

# Clean up
test_job.delete()
docker_host.delete()
exit()
```

#### 5. Admin Interface Test

1. **Start development server:**
```bash
uv run python manage.py runserver
```

2. **Access admin interface:**
   - Open browser to: `http://localhost:8000/admin/`
   - Login with superuser credentials
   - Navigate to: Container Manager → Container Jobs
   - Verify you can see the test job created above

3. **Test job creation via admin:**
   - Click "Add Container Job"
   - Fill in basic job details
   - Save and verify job appears in list

#### 6. Job Processor Test

```bash
# Start job processor in verbose mode
uv run python manage.py process_container_jobs --verbosity=2

# Expected output should include:
# - Job processor starting
# - Polling for jobs every X seconds
# - Processing any pending jobs
# - No error messages

# Test with --once flag
uv run python manage.py process_container_jobs --once
# Should run once and exit cleanly
```

### Performance Verification

#### Resource Usage Test

```python
# Create resource-intensive test job
resource_job = ContainerJob.objects.create_job(
    image="python:3.11-slim",
    command="python -c 'import time; print(\"Starting\"); time.sleep(10); print(\"Completed\")'",
    name="Resource Test Job",
    memory_limit=256,
    cpu_limit=1.0,
    timeout_seconds=30
)

# Monitor the job
# - Check that it starts within 10 seconds
# - Verify resource limits are applied
# - Confirm logs are collected
# - Ensure cleanup happens after completion
```

#### Concurrent Job Test

```python
# Create multiple jobs to test concurrency
jobs = []
for i in range(3):
    job = ContainerJob.objects.create_job(
        image="alpine:latest",
        command=f"echo 'Job {i} running' && sleep 5 && echo 'Job {i} completed'",
        name=f"Concurrent Test Job {i}",
        memory_limit=64,
        cpu_limit=0.5
    )
    jobs.append(job)

# All jobs should execute concurrently (not sequentially)
# Total execution time should be ~5 seconds, not ~15 seconds
```

### Verification Troubleshooting

#### Common Verification Issues

**Django admin shows "Server Error (500)":**
```bash
# Check Django logs
python manage.py check --deploy

# Check database connectivity
python manage.py dbshell

# Verify static files
python manage.py collectstatic
```

**Docker permission denied:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Logout and login again, then test
docker ps
```

**Job processor not picking up jobs:**
```bash
# Check job processor is running
ps aux | grep "process_container_jobs"

# Check for errors in logs
python manage.py process_container_jobs --verbosity=2

# Verify database connectivity
python manage.py dbshell
```

**Container jobs failing to start:**
```bash
# Check Docker daemon
docker info

# Test manual container creation
docker run --rm hello-world

# Check job logs in admin interface
# Look for specific error messages
```

## Troubleshooting

### Common Installation Issues

#### Python and Package Issues

**Issue: `uv` command not found**
```bash
# Solution: Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Restart terminal or source shell config
source ~/.bashrc  # or ~/.zshrc
```

**Issue: Python version conflicts**
```bash
# Solution: Use pyenv for Python version management
curl https://pyenv.run | bash

# Install desired Python version
pyenv install 3.11.6
pyenv global 3.11.6

# Verify
python --version
```

**Issue: `pip install` failures with compilation errors**
```bash
# Solution: Install build dependencies
# Ubuntu/Debian:
sudo apt install build-essential python3-dev libpq-dev

# macOS:
xcode-select --install

# Or install from binary wheels
pip install --only-binary=all package-name
```

#### Docker Issues

**Issue: Docker daemon not running**
```bash
# Check Docker status
systemctl status docker

# Start Docker daemon
sudo systemctl start docker

# Enable automatic startup
sudo systemctl enable docker

# For Docker Desktop (macOS/Windows):
# Start Docker Desktop application
```

**Issue: Permission denied accessing Docker**
```bash
# Check current user groups
groups $USER

# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes (logout/login or use newgrp)
newgrp docker

# Test access
docker ps
```

**Issue: Docker socket permission denied**
```bash
# Check socket permissions
ls -la /var/run/docker.sock

# Fix permissions (temporary)
sudo chmod 666 /var/run/docker.sock

# Permanent fix: ensure user is in docker group
sudo usermod -aG docker $USER
```

**Issue: Docker out of disk space**
```bash
# Check disk usage
docker system df

# Clean up unused containers, images, networks
docker system prune -a

# Remove specific unused images
docker image prune -a

# Configure Docker to limit disk usage
# Edit /etc/docker/daemon.json:
{
  "data-root": "/path/to/docker/data",
  "storage-opts": ["size=50G"]
}
```

#### Database Issues

**Issue: PostgreSQL connection refused**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Start PostgreSQL if needed
sudo systemctl start postgresql

# Check if PostgreSQL is listening
sudo netstat -tlnp | grep 5432

# Check PostgreSQL configuration
sudo -u postgres psql -c "SHOW config_file;"

# Edit pg_hba.conf for authentication
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

**Issue: Database does not exist**
```bash
# Connect as postgres superuser
sudo -u postgres psql

# Create database
CREATE DATABASE container_manager;

# Create user with permissions
CREATE USER container_manager WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE container_manager TO container_manager;
```

**Issue: Migration conflicts**
```bash
# Check migration status
python manage.py showmigrations

# Reset migrations (development only!)
python manage.py migrate container_manager zero
python manage.py migrate

# For production, create custom migration to resolve conflicts
python manage.py makemigrations --merge
```

#### Application Issues

**Issue: `SECRET_KEY` not set**
```bash
# Generate a new secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Set in environment
export SECRET_KEY='generated-secret-key-here'

# Or add to .env file
echo "SECRET_KEY=generated-secret-key-here" >> .env
```

**Issue: Static files not loading**
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check static files settings
python manage.py check --deploy

# For development, ensure DEBUG=True
# For production, configure web server to serve static files
```

**Issue: Admin interface not accessible**
```bash
# Create superuser
python manage.py createsuperuser

# Check URL configuration
python manage.py show_urls | grep admin

# Verify ALLOWED_HOSTS setting
python manage.py check
```

#### Network and Connectivity Issues

**Issue: Containers cannot access external networks**
```bash
# Check Docker network configuration
docker network ls

# Test container network connectivity
docker run --rm alpine ping -c 3 8.8.8.8

# Check Docker daemon DNS settings
docker info | grep -A 5 "DNS"

# Configure custom DNS if needed
# Edit /etc/docker/daemon.json:
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}
```

**Issue: Container jobs timing out**
```bash
# Check container logs
docker logs <container_id>

# Increase timeout in job configuration
job.timeout_seconds = 1800  # 30 minutes

# Check Docker daemon logs
sudo journalctl -u docker.service -f

# Monitor container resource usage
docker stats <container_id>
```

#### Performance Issues

**Issue: Slow container startup**
```bash
# Pre-pull commonly used images
docker pull python:3.11-slim
docker pull alpine:latest
docker pull ubuntu:22.04

# Check available disk space
df -h

# Clean up unused Docker resources
docker system prune

# Monitor Docker daemon performance
docker info
```

**Issue: Job processor consuming high CPU**
```bash
# Increase poll interval to reduce CPU usage
python manage.py process_container_jobs --poll-interval=30

# Monitor job processor performance
top -p $(pgrep -f process_container_jobs)

# Check for stuck jobs
python manage.py shell
>>> from container_manager.models import ContainerJob
>>> ContainerJob.objects.filter(status='running').count()
```

### Platform-Specific Issues

#### macOS Specific

**Issue: Docker Desktop startup issues**
```bash
# Reset Docker Desktop
# Docker Desktop → Troubleshoot → Reset to factory defaults

# Check for conflicting virtualization software
# VirtualBox, VMware, etc. may conflict

# Ensure sufficient disk space (5GB+ free)
df -h

# Check macOS version compatibility
# Docker Desktop requires macOS 10.15 or later
```

**Issue: Homebrew permission issues**
```bash
# Fix Homebrew permissions
sudo chown -R $(whoami) /usr/local/var/homebrew

# Or reinstall Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### Ubuntu/Debian Specific

**Issue: `apt` package conflicts**
```bash
# Update package list
sudo apt update

# Fix broken packages
sudo apt --fix-broken install

# Clear apt cache
sudo apt clean
sudo apt autoclean

# Remove conflicting packages
sudo apt remove docker docker-engine docker.io containerd runc
```

**Issue: systemd service failures**
```bash
# Check service status
sudo systemctl status docker

# View service logs
sudo journalctl -u docker.service

# Reload systemd configuration
sudo systemctl daemon-reload

# Restart service
sudo systemctl restart docker
```

#### Windows Specific

**Issue: WSL 2 backend issues**
```bash
# Enable WSL 2 in Windows Features
# Control Panel → Programs → Turn Windows features on/off
# Check: Windows Subsystem for Linux, Virtual Machine Platform

# Update WSL kernel
wsl --update

# Set WSL 2 as default
wsl --set-default-version 2

# Restart Docker Desktop after enabling WSL 2
```

**Issue: Hyper-V conflicts**
```bash
# Disable other virtualization software
# VirtualBox, VMware Workstation may conflict with Hyper-V

# Check Windows version compatibility
# Docker Desktop requires Windows 10 Pro/Enterprise or Windows 11
```

### Debugging Tools and Techniques

#### Application Debugging

```bash
# Enable Django debug mode
export DEBUG=True

# Run with verbose logging
export LOG_LEVEL=DEBUG
python manage.py runserver --verbosity=2

# Use Django shell for debugging
python manage.py shell_plus  # If django-extensions installed

# Check Django configuration
python manage.py diffsettings
```

#### Docker Debugging

```bash
# Inspect running containers
docker ps -a

# View container logs
docker logs <container_id>

# Execute commands in running container
docker exec -it <container_id> /bin/bash

# Inspect container configuration
docker inspect <container_id>

# Monitor container resource usage
docker stats

# Check Docker daemon events
docker events --since '2024-12-02T10:00:00'
```

#### Database Debugging

```bash
# Connect to database directly
python manage.py dbshell

# Run database queries
psql -h localhost -U container_manager -d container_manager

# Check database connections
SELECT * FROM pg_stat_activity WHERE datname = 'container_manager';

# Monitor slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

### Recovery Procedures

#### Application Recovery

```bash
# Reset to clean state (development)
rm -f dev.db
python manage.py migrate
python manage.py createsuperuser

# Restore from backup (production)
sudo systemctl stop container-manager-app
sudo systemctl stop container-manager-jobs
pg_dump container_manager > backup_$(date +%Y%m%d_%H%M%S).sql
psql container_manager < backup_20241202_143000.sql
sudo systemctl start container-manager-app
sudo systemctl start container-manager-jobs
```

#### Docker Recovery

```bash
# Reset Docker to clean state
docker system prune -a --volumes

# Restart Docker daemon
sudo systemctl restart docker

# Rebuild base images
docker pull python:3.11-slim
docker pull alpine:latest
```

#### Emergency Contacts and Resources

- **Documentation**: [DOCKER.md](DOCKER.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Community Support**: GitHub Issues
- **Professional Support**: Contact your system administrator
- **Security Issues**: Report via responsible disclosure

## Upgrading

### Upgrading from Previous Versions

#### Pre-Upgrade Checklist

1. **Backup current installation:**
```bash
# Backup database
pg_dump container_manager > backup_before_upgrade_$(date +%Y%m%d).sql

# Backup configuration
cp -r /opt/container-manager/app/.env /opt/container-manager/app/.env.backup

# Note current version
pip show django-container-manager
```

2. **Check compatibility:**
```bash
# Review changelog for breaking changes
# Check Python version compatibility
# Check Docker version compatibility
# Review new configuration requirements
```

#### Standard Upgrade Process

1. **Stop services:**
```bash
sudo supervisorctl stop container-manager-app
sudo supervisorctl stop container-manager-jobs
```

2. **Upgrade application:**
```bash
# Switch to application user
sudo -u container-manager -i
cd /opt/container-manager/app

# Activate virtual environment
source venv/bin/activate

# Upgrade package
pip install --upgrade django-container-manager

# Or with uv
uv sync --upgrade
```

3. **Run migrations:**
```bash
# Check for new migrations
python manage.py showmigrations

# Apply migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput
```

4. **Restart services:**
```bash
sudo supervisorctl start container-manager-app
sudo supervisorctl start container-manager-jobs

# Verify services are running
sudo supervisorctl status
```

#### Rollback Procedure

If upgrade fails:

1. **Stop new services:**
```bash
sudo supervisorctl stop all
```

2. **Restore previous version:**
```bash
# Restore code
cd /opt/container-manager/app
git checkout previous-version-tag

# Restore virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

3. **Restore database:**
```bash
# Restore database backup
psql container_manager < backup_before_upgrade_20241202.sql
```

4. **Restart services:**
```bash
sudo supervisorctl start all
```

### Version-Specific Upgrade Notes

#### v1.0 to v2.0

- **Breaking change**: Executor configuration format updated
- **Action required**: Update ExecutorHost.executor_config format
- **Migration**: Automatic migration provided for existing hosts

#### v0.9 to v1.0

- **New feature**: Multi-cloud executor support
- **Configuration change**: New CONTAINER_MANAGER_SETTINGS format
- **Action required**: Update settings.py configuration

### Automated Upgrade Script

```bash
#!/bin/bash
# upgrade.sh - Automated upgrade script

set -e

echo "Starting Django Container Manager upgrade..."

# Backup
echo "Creating backup..."
sudo -u container-manager pg_dump container_manager > /opt/container-manager/backup_$(date +%Y%m%d_%H%M%S).sql

# Stop services
echo "Stopping services..."
sudo supervisorctl stop container-manager-app container-manager-jobs

# Upgrade
echo "Upgrading application..."
sudo -u container-manager bash << 'EOF'
cd /opt/container-manager/app
source venv/bin/activate
pip install --upgrade django-container-manager
python manage.py migrate
python manage.py collectstatic --noinput
EOF

# Start services
echo "Starting services..."
sudo supervisorctl start container-manager-app container-manager-jobs

# Verify
echo "Verifying upgrade..."
sleep 10
sudo supervisorctl status

echo "Upgrade completed successfully!"
```

### Monitoring Post-Upgrade

```bash
# Check application logs
sudo tail -f /var/log/supervisor/container-manager-app.log

# Check job processor logs
sudo tail -f /var/log/supervisor/container-manager-jobs.log

# Test basic functionality
python manage.py shell << 'EOF'
from container_manager.models import ContainerJob, ExecutorHost
print(f"Jobs in database: {ContainerJob.objects.count()}")
print(f"Active hosts: {ExecutorHost.objects.filter(is_active=True).count()}")
EOF

# Create test job to verify functionality
python manage.py shell << 'EOF'
from container_manager.models import ContainerJob, ExecutorHost
host = ExecutorHost.objects.filter(is_active=True).first()
if host:
    job = ContainerJob.objects.create_job(
        image="hello-world",
        name="Post-upgrade test",
        memory_limit=128
    )
    print(f"Created test job: {job.id}")
EOF
```

## LLM Agent Guidelines

### Behavioral Constraints

- **DO**: Test every installation command on clean systems before documenting
- **DO**: Provide exact version numbers and compatibility matrices
- **DO**: Include rollback procedures for each installation step
- **DO**: Document all prerequisites clearly and completely
- **DO NOT**: Assume any software is pre-installed (except OS)
- **DO NOT**: Include commands that could damage existing systems
- **DO NOT**: Skip security considerations in production sections
- **DO NOT**: Provide installation steps without verification procedures
- **LIMITS**: Each installation path should complete in under 30 minutes

### Security Requirements

- **Never include**: Real database credentials, API keys, or production URLs
- **Always emphasize**: Proper secret management and credential security
- **Validate all commands**: Ensure no commands run with unnecessary privileges
- **Production focus**: Highlight security implications of each configuration choice
- **Docker security**: Emphasize proper Docker daemon permissions and isolation

### Safe Operation Patterns

- **Command validation process**:
  1. Test each command on clean virtual machine
  2. Verify expected output matches documentation
  3. Test error scenarios and recovery procedures
  4. Document any system modifications made
- **Version verification**: Check software version compatibility before documenting
- **Rollback testing**: Ensure uninstall/rollback procedures actually work

### Error Handling

- **If commands fail**: Document the failure, don't skip or work around
- **If dependencies unavailable**: Provide alternative installation methods
- **If security risks identified**: Stop and request security review
- **When installation varies by platform**: Document all platform differences clearly

### Validation Requirements

- [ ] All installation commands tested on target platforms
- [ ] No privileged operations without explicit security warnings
- [ ] All configuration examples use placeholder values
- [ ] Rollback procedures tested and documented
- [ ] Security implications documented for production steps
- [ ] Docker daemon configuration verified safe and functional
- [ ] Database setup procedures tested with clean installations

### Installation Safety Boundaries

- **NEVER run**: Commands that could delete system files or data
- **NEVER skip**: Security warnings or credential protection measures
- **NEVER assume**: System state or existing software configurations
- **NEVER provide**: Installation steps that bypass security controls
- **NEVER ignore**: Platform differences or compatibility requirements
- **NEVER omit**: Verification steps to confirm successful installation
- **NEVER recommend**: Development practices for production environments

---

This comprehensive installation guide covers all scenarios from development setup to production deployment, with detailed troubleshooting and upgrade procedures.