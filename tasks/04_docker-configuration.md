# Docker Configuration Specification

## Overview

Single production-ready Docker image that can run the Django web server or execute management commands. The container must be platform-agnostic and configurable for different Docker socket locations (Linux, macOS Docker Desktop, macOS Colima).

## Dockerfile Specification

### Single Multi-Purpose Image

```dockerfile
# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=demo_project.settings

# Set work directory
WORKDIR /app

# Install system dependencies for common use cases
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install UV for fast Python package management
RUN pip install --no-cache-dir uv

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies using UV
RUN uv pip install --system --no-cache -r requirements.txt

# Copy project files
COPY . .

# Create data directory for SQLite and uploads
RUN mkdir -p /app/data/uploads

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port 8000 for Django development server
EXPOSE 8000

# Default command runs Django development server
# Can be overridden to run management commands
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## Docker Compose Configuration

### Development Environment

```yaml
# docker-compose.yml
version: '3.8'

services:
  demo:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      # Data persistence (SQLite database and uploads)
      - ./data:/app/data
      
      # Docker socket (configurable for different platforms)
      - ${DOCKER_SOCKET_PATH:-/var/run/docker.sock}:/var/run/docker.sock
      
      # Source code volume for development (optional)
      # - .:/app
      
    environment:
      # Override environment variables
      - DEBUG=True
      - SECRET_KEY=${SECRET_KEY:-demo-secret-key-change-in-production}
      - DATABASE_URL=sqlite:///data/db.sqlite3
      - DOCKER_SOCKET_PATH=/var/run/docker.sock
      
      # Demo workflow configuration
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - CRAWL_USER_AGENT=${CRAWL_USER_AGENT:-Django Container Manager Demo Bot 1.0}
      
    depends_on:
      - demo-init
    
    # Restart policy for development
    restart: unless-stopped

  # Initialization service to set up database
  demo-init:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=sqlite:///data/db.sqlite3
    command: |
      sh -c "
        python manage.py migrate --noinput &&
        python manage.py collectstatic --noinput
      "
    restart: "no"

  # Optional: Worker service for processing jobs
  demo-worker:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ./data:/app/data
      - ${DOCKER_SOCKET_PATH:-/var/run/docker.sock}:/var/run/docker.sock
    environment:
      - DATABASE_URL=sqlite:///data/db.sqlite3
      - DOCKER_SOCKET_PATH=/var/run/docker.sock
    command: python manage.py process_container_jobs --poll-interval=10
    depends_on:
      - demo-init
    restart: unless-stopped
```

### Override for Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  demo:
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}  # Must be provided
    command: |
      sh -c "
        python manage.py migrate --noinput &&
        python manage.py collectstatic --noinput &&
        gunicorn demo_project.wsgi:application --bind 0.0.0.0:8000
      "
```

## Platform-Specific Configuration

### Environment Variable Configuration

**`.env.example`:**
```bash
# Django Core
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=sqlite:///data/db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1

# Docker Socket Configuration
# Choose ONE based on your platform:

# Linux/WSL2
DOCKER_SOCKET_PATH=/var/run/docker.sock

# macOS with Docker Desktop
# DOCKER_SOCKET_PATH=/var/run/docker.sock

# macOS with Colima
# DOCKER_SOCKET_PATH=${HOME}/.colima/default/docker.sock

# Windows with Docker Desktop (WSL2)
# DOCKER_SOCKET_PATH=/var/run/docker.sock

# API Keys (optional)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
CRAWL_USER_AGENT=Django Container Manager Demo Bot 1.0
```

### Platform Detection Script

```bash
#!/bin/bash
# scripts/detect-docker-socket.sh
# Automatically detect and set appropriate Docker socket path

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Linux detected"
    export DOCKER_SOCKET_PATH="/var/run/docker.sock"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS detected"
    if command -v colima &> /dev/null && colima status &> /dev/null; then
        echo "Colima is running"
        export DOCKER_SOCKET_PATH="$HOME/.colima/default/docker.sock"
    else
        echo "Using Docker Desktop"
        export DOCKER_SOCKET_PATH="/var/run/docker.sock"
    fi
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "Windows detected"
    export DOCKER_SOCKET_PATH="/var/run/docker.sock"
else
    echo "Unknown OS, defaulting to standard socket"
    export DOCKER_SOCKET_PATH="/var/run/docker.sock"
fi

echo "Docker socket path: $DOCKER_SOCKET_PATH"
```

## Volume Strategy

### Data Persistence

```yaml
volumes:
  # SQLite database and uploads
  - ./data:/app/data
  
  # Structure:
  # ./data/
  # ├── db.sqlite3          # SQLite database
  # ├── uploads/            # Document uploads
  # │   ├── documents/      # Original uploaded files
  # │   └── results/        # Analysis results
  # └── logs/              # Application logs (optional)
```

### Benefits of Bind Mounts

1. **Data Persistence** - Database survives container recreation
2. **Easy Backup** - Simple file copy of `./data` directory
3. **Development Friendly** - Direct access to database file
4. **Platform Agnostic** - Works on all Docker platforms
5. **No Volume Management** - No need for Docker volume commands

## Multi-Purpose Container Usage

### Web Server Mode

```bash
# Run Django development server
docker-compose up

# Or directly with docker run
docker run -p 8000:8000 \
  -v ./data:/app/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  demo-project:latest
```

### Management Command Mode

```bash
# Run Django management commands
docker-compose exec demo python manage.py migrate
docker-compose exec demo python manage.py createsuperuser
docker-compose exec demo python manage.py shell

# Run workflow commands
docker-compose exec demo python manage.py crawl_webpage <execution-id> --url https://example.com
docker-compose exec demo python manage.py rewrite_text <execution-id> --text "Hello world" --figure shakespeare
docker-compose exec demo python manage.py analyze_document <execution-id> --file-path /app/data/uploads/document.pdf
```

### Worker Mode

```bash
# Run container job processor
docker-compose exec demo python manage.py process_container_jobs

# Or as separate service
docker-compose up demo-worker
```

## Build and Deployment Scripts

### Build Script

```bash
#!/bin/bash
# scripts/build.sh
set -e

echo "Building Django Container Manager Demo..."

# Build Docker image
docker build -t django-container-manager-demo:latest .

# Tag with version if provided
if [ ! -z "$1" ]; then
    docker tag django-container-manager-demo:latest django-container-manager-demo:$1
    echo "Tagged as version: $1"
fi

echo "Build complete!"
```

### Setup Script

```bash
#!/bin/bash
# scripts/setup.sh
set -e

echo "Setting up Django Container Manager Demo..."

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file from .env.example"
    echo "Please edit .env file with your configuration"
fi

# Detect Docker socket path
source scripts/detect-docker-socket.sh

# Create data directory
mkdir -p data/uploads/documents
mkdir -p data/uploads/results

# Build and start services
docker-compose build
docker-compose up -d demo-init

# Wait for init to complete
echo "Waiting for database initialization..."
docker-compose wait demo-init

# Start main services
docker-compose up -d demo

echo "Setup complete!"
echo "Web interface available at: http://localhost:8000"
echo "Admin interface at: http://localhost:8000/admin"
echo ""
echo "Create admin user with:"
echo "docker-compose exec demo python manage.py createsuperuser"
```

### Development Script

```bash
#!/bin/bash
# scripts/dev.sh
# Development helper script

case "$1" in
    "start")
        docker-compose up
        ;;
    "stop")
        docker-compose down
        ;;
    "logs")
        docker-compose logs -f demo
        ;;
    "shell")
        docker-compose exec demo python manage.py shell
        ;;
    "admin")
        docker-compose exec demo python manage.py createsuperuser
        ;;
    "migrate")
        docker-compose exec demo python manage.py migrate
        ;;
    "worker")
        docker-compose exec demo python manage.py process_container_jobs
        ;;
    *)
        echo "Usage: $0 {start|stop|logs|shell|admin|migrate|worker}"
        echo ""
        echo "  start   - Start all services"
        echo "  stop    - Stop all services"
        echo "  logs    - Follow container logs"
        echo "  shell   - Open Django shell"
        echo "  admin   - Create admin user"
        echo "  migrate - Run database migrations"
        echo "  worker  - Run job processor"
        ;;
esac
```

## Docker Socket Security

### Security Considerations

1. **Docker Socket Access** - Container has full Docker API access
2. **User Permissions** - Run as non-root user when possible
3. **Image Security** - Use official base images and minimal installs
4. **Network Isolation** - Consider Docker networks for production

### Production Recommendations

```yaml
# For production, consider:
services:
  demo:
    # Read-only root filesystem
    read_only: true
    
    # Temporary filesystems for writable areas
    tmpfs:
      - /tmp
      - /app/tmp
    
    # Security options
    security_opt:
      - no-new-privileges:true
    
    # Limit resources
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

## Testing Docker Configuration

### Smoke Tests

```bash
#!/bin/bash
# scripts/test-docker.sh
# Test Docker configuration

echo "Testing Docker configuration..."

# Test build
docker build -t test-demo .

# Test basic run
docker run --rm test-demo python manage.py check

# Test with socket mount
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  test-demo python manage.py check

# Test with data volume
mkdir -p test-data
docker run --rm \
  -v ./test-data:/app/data \
  test-demo python manage.py migrate --noinput

echo "Docker configuration tests passed!"
rm -rf test-data
```

This Docker configuration provides a flexible, platform-agnostic setup that can run as both a web server and command executor while maintaining data persistence and proper Docker socket access across different platforms.