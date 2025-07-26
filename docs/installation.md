# Installation Guide

This guide provides detailed instructions for installing Django Docker Container Manager in various environments.

## Prerequisites

### Required Software
- **Python 3.12+**: The application requires Python 3.12 or higher
- **Docker Engine 20.10+**: For container management functionality
- **Git**: For cloning the repository

### Optional Components
- **Redis 6.0+**: Required for production WebSocket support and real-time features
- **PostgreSQL 12+**: Recommended for production databases (SQLite is used by default)

## Development Installation

### Quick Start
```bash
# Clone the repository
git clone https://github.com/heysamtexas/django-docker-manager.git
cd django-docker-manager

# Install dependencies using uv
uv sync

# Apply database migrations
uv run python manage.py migrate

# Create a superuser account
uv run python manage.py createsuperuser

# Start the development server
uv run python manage.py runserver
```

### Using pip/venv (Alternative)
If you prefer traditional Python tooling:

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Apply migrations and create superuser
python manage.py migrate
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

## Docker Socket Configuration

### Unix Socket (Local Development)
For local development, ensure Docker socket is accessible:

```bash
# Check Docker socket permissions
ls -la /var/run/docker.sock

# If needed, add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Test Docker access
docker ps
```

### TCP Socket (Remote Docker)
For remote Docker hosts, configure TLS certificates:

```bash
# Generate client certificates (if needed)
openssl genrsa -out client-key.pem 2048
openssl req -new -key client-key.pem -out client.csr
# ... follow Docker TLS setup guide
```

## Database Configuration

### SQLite (Default)
No additional configuration required. Database file will be created automatically.

### PostgreSQL (Recommended for Production)
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres createdb django_docker_manager
sudo -u postgres createuser -P django_user

# Grant permissions
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE django_docker_manager TO django_user;"

# Update Django settings
export DATABASE_URL="postgresql://django_user:password@localhost/django_docker_manager"
```

### MySQL/MariaDB (Alternative)
```bash
# Install MySQL client
pip install mysqlclient

# Create database
mysql -u root -p -e "CREATE DATABASE django_docker_manager;"
mysql -u root -p -e "CREATE USER 'django_user'@'localhost' IDENTIFIED BY 'password';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON django_docker_manager.* TO 'django_user'@'localhost';"

# Update Django settings
export DATABASE_URL="mysql://django_user:password@localhost/django_docker_manager"
```

## Redis Configuration

### Local Redis Installation
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS (with Homebrew)
brew install redis

# Start Redis service
sudo systemctl start redis-server  # Linux
brew services start redis          # macOS

# Test Redis connection
redis-cli ping
```

### Docker Redis (Development)
```bash
# Run Redis in Docker
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Update Django settings
export REDIS_URL="redis://localhost:6379/0"
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Django configuration
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# Redis (optional for development)
REDIS_URL=redis://localhost:6379/0

# Docker hosts
DOCKER_HOSTS=unix:///var/run/docker.sock
```

## Verification

### Test Installation
```bash
# Run system checks
uv run python manage.py check

# Run tests
uv run python manage.py test

# Create test Docker host
uv run python manage.py shell -c "
from container_manager.models import DockerHost
host = DockerHost.objects.create(
    name='local-docker',
    host_type='unix',
    connection_string='unix:///var/run/docker.sock',
    is_active=True
)
print(f'Created Docker host: {host.name}')
"
```

### Test Docker Integration
```bash
# Test Docker connectivity
uv run python manage.py shell -c "
from container_manager.docker_service import docker_service
from container_manager.models import DockerHost
host = DockerHost.objects.first()
try:
    client = docker_service.get_client(host)
    print('Docker connection successful!')
    print(f'Docker version: {client.version()}')
except Exception as e:
    print(f'Docker connection failed: {e}')
"
```

## Troubleshooting

### Common Issues

#### Permission Denied - Docker Socket
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or temporarily change socket permissions (not recommended for production)
sudo chmod 666 /var/run/docker.sock
```

#### Python Version Issues
```bash
# Check Python version
python --version
python3.12 --version

# Install Python 3.12 on Ubuntu
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

#### Dependencies Installation Failures
```bash
# Install system dependencies
sudo apt-get install build-essential python3.12-dev libpq-dev

# On macOS
xcode-select --install
brew install postgresql
```

#### Database Connection Issues
```bash
# Test database connection
uv run python manage.py dbshell

# Check database settings
uv run python manage.py shell -c "
from django.conf import settings
print(f'Database: {settings.DATABASES}')
"
```

#### Redis Connection Issues
```bash
# Test Redis connection
redis-cli ping

# Check Redis logs
sudo journalctl -u redis-server -f  # Linux
brew services info redis             # macOS
```

## Next Steps

After successful installation:

1. **Configure Docker Hosts**: Add your Docker daemon endpoints in the admin interface
2. **Create Container Templates**: Define reusable container configurations  
3. **Start Job Processor**: Run the worker daemon to process jobs
4. **Review Security**: Follow the security guidelines for production deployment

For detailed usage instructions, see the [Configuration Guide](configuration.md).