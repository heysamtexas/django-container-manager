# Troubleshooting Guide

This guide provides systematic diagnosis and resolution procedures for common issues in the Django Docker container management system. Follow the diagnostic framework below to identify and resolve problems efficiently.

## Quick Diagnostic Framework

When encountering issues, follow this systematic approach:

1. **Identify the problem**: What specific functionality is not working?
2. **Check system health**: Verify all components are running and accessible
3. **Review recent logs**: Look for error patterns and timing information
4. **Isolate the component**: Determine if this is Docker, Django, database, or network related
5. **Apply minimal fixes**: Start with the least invasive solution
6. **Verify resolution**: Confirm the fix resolves the issue without side effects

## Installation and Setup Issues

### Docker Configuration Problems

#### Permission Denied Accessing Docker Socket

**Symptoms**: `permission denied while trying to connect to the Docker daemon socket`

**Diagnosis**:
```bash
# Test Docker access
docker ps
# If permission denied, check socket permissions
ls -la /var/run/docker.sock
```

**Solutions**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify fix
docker ps
docker version
```

**Prevention**: Ensure Docker post-installation steps completed during initial setup.

#### Docker Daemon Not Running

**Symptoms**: Connection refused errors, `Cannot connect to the Docker daemon`

**Diagnosis**:
```bash
# Check Docker daemon status
docker version
systemctl status docker  # Linux
brew services list | grep docker  # macOS
```

**Solutions**:
```bash
# Start Docker service (Linux)
sudo systemctl start docker
sudo systemctl enable docker

# macOS - check Docker Desktop
open -a Docker

# Verify daemon is running
docker info
```

### Database Connection Issues

#### Database Connection Failures

**Symptoms**: `django.db.utils.OperationalError`, connection timeouts

**Diagnosis**:
```bash
# Check database connectivity
uv run python manage.py check --database default

# Test database shell access
uv run python manage.py dbshell

# Verify migration status
uv run python manage.py showmigrations
```

**Solutions**:
```bash
# Apply missing migrations
uv run python manage.py migrate

# Check database file permissions (SQLite)
ls -la db.sqlite3

# Verify database URL in settings
uv run python manage.py shell -c "
from django.conf import settings
print('Database:', settings.DATABASES['default'])
"
```

#### Migration Conflicts

**Symptoms**: `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Diagnosis**:
```bash
# Check migration status
uv run python manage.py showmigrations

# Look for conflicts
uv run python manage.py showmigrations --plan
```

**Solutions**:
```bash
# Reset migrations (development only)
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete
uv run python manage.py makemigrations
uv run python manage.py migrate

# For production, resolve specific conflicts
uv run python manage.py migrate --merge
```

### Python Environment Issues

#### uv sync Failures

**Symptoms**: Package installation errors, dependency conflicts

**Diagnosis**:
```bash
# Check uv version
uv --version

# Verify Python version
python --version

# Check for conflicting packages
uv lock --verbose
```

**Solutions**:
```bash
# Clean and rebuild environment
rm -rf .venv uv.lock
uv sync

# Update uv itself
pip install --upgrade uv

# Force reinstall if needed
uv sync --reinstall
```

#### Import Errors

**Symptoms**: `ModuleNotFoundError`, `ImportError`

**Diagnosis**:
```bash
# Check Python path
uv run python -c "import sys; print('\n'.join(sys.path))"

# Verify package installation
uv run python -c "import django; print(django.__version__)"

# Check for missing dependencies
uv run python manage.py check
```

**Solutions**:
```bash
# Install missing dependencies
uv add <package-name>

# Verify environment activation
source .venv/bin/activate  # Manual activation if needed

# Reinstall problematic packages
uv add --force-reinstall <package-name>
```

## Job Execution Problems

### Container Launch Failures

#### Image Pull Failures

**Symptoms**: `pull access denied for image`, `repository does not exist`

**Diagnosis**:
```bash
# Test direct image pull
docker pull <image-name>

# Check Docker Hub authentication
docker login

# Verify image name and tag
docker search <image-name>
```

**Solutions**:
```bash
# Authenticate with registry
docker login
# or for private registries:
docker login myregistry.com

# Verify image exists and is accessible
docker pull <image-name>

# Use public alternatives if available
# python:3.9 instead of private/python:3.9
```

#### Container Startup Failures

**Symptoms**: Containers start but immediately exit, invalid command errors

**Diagnosis**:
```python
# Check job configuration
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
job = ContainerJob.objects.get(id=<job_id>)
print('Image:', job.image)
print('Command:', job.command)
print('Status:', job.status)
print('Logs:', job.docker_log)
"
```

**Solutions**:
- **Invalid command syntax**: Ensure command is valid for the container image
- **Missing dependencies**: Use base images with required tools installed
- **Working directory issues**: Specify absolute paths in commands
- **Environment variables**: Verify required environment variables are set

### Job Status Issues

#### Jobs Stuck in Pending Status

**Symptoms**: Jobs remain in 'pending' status indefinitely

**Diagnosis**:
```python
# Check executor host availability
uv run python manage.py shell -c "
from container_manager.models import ExecutorHost, ContainerJob
print('Available hosts:', ExecutorHost.objects.filter(is_active=True).count())
print('Pending jobs:', ContainerJob.objects.filter(status='pending').count())
for host in ExecutorHost.objects.filter(is_active=True):
    print(f'Host: {host.name}, Type: {host.executor_type}')
"
```

**Solutions**:
```bash
# Start job processor
uv run python manage.py process_container_jobs --single-run

# Check host connectivity
uv run python manage.py shell -c "
from container_manager.models import ExecutorHost
from container_manager.executors.factory import ExecutorFactory
factory = ExecutorFactory()
for host in ExecutorHost.objects.filter(is_active=True):
    try:
        executor = factory.get_executor(host)
        print(f'{host.name}: Available')
    except Exception as e:
        print(f'{host.name}: Error - {e}')
"

# Verify job has required fields
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
for job in ContainerJob.objects.filter(status='pending')[:5]:
    print(f'Job {job.id}: docker_host={job.docker_host}, image={job.image}')
"
```

#### Jobs Failing Immediately

**Symptoms**: Jobs move from 'starting' to 'failed' within seconds

**Diagnosis**:
```python
# Check recent failed jobs
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
failed_jobs = ContainerJob.objects.filter(status='failed').order_by('-created_at')[:5]
for job in failed_jobs:
    print(f'Job {job.id}: {job.docker_log}')
"
```

**Common causes and solutions**:
- **Command execution errors**: Verify command syntax and executable paths
- **Missing files**: Ensure required files exist in container
- **Permission issues**: Check file permissions and user context
- **Resource limits**: Verify memory/CPU limits are sufficient

### Resource Management Problems

#### Memory Limit Exceeded

**Symptoms**: Containers killed due to memory limit, exit code 137

**Diagnosis**:
```python
# Check memory configuration
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
job = ContainerJob.objects.get(id=<job_id>)
print(f'Memory limit: {job.memory_limit}MB')
print(f'Exit code: {job.exit_code}')
print(f'Status: {job.status}')
"
```

**Solutions**:
```python
# Increase memory limit
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
job = ContainerJob.objects.get(id=<job_id>)
job.memory_limit = 2048  # Increase to 2GB
job.save()
print(f'Updated memory limit to {job.memory_limit}MB')
"

# Or optimize container memory usage
# - Use smaller base images
# - Optimize application memory footprint
# - Process data in smaller chunks
```

#### CPU Throttling Issues

**Symptoms**: Slow job execution, high CPU wait times

**Diagnosis**:
```bash
# Check host CPU usage
top -p $(pgrep -d, docker)

# Monitor container resource usage
docker stats

# Check Docker resource limits
docker system df
docker system info
```

**Solutions**:
- **Increase CPU limits**: Adjust `cpu_limit` field on jobs
- **Optimize CPU usage**: Review algorithm efficiency
- **Distribute load**: Use multiple smaller jobs instead of large ones
- **Host scaling**: Add more executor hosts for parallel processing

## Executor-Specific Issues

### Docker Executor Problems

#### Docker Daemon Connectivity

**Symptoms**: Connection timeouts, socket access errors

**Diagnosis**:
```bash
# Test Docker socket access
docker ps
docker version

# Check socket permissions
ls -la /var/run/docker.sock

# Test TCP connection (if using remote Docker)
telnet <docker-host> 2376
```

**Solutions**:
```bash
# Fix Unix socket permissions
sudo chmod 666 /var/run/docker.sock
# or better, add user to docker group:
sudo usermod -aG docker $USER

# For TCP connections, verify:
# - Host is reachable
# - Port 2376 is open
# - TLS certificates configured correctly
```

#### Container Networking Issues

**Symptoms**: Containers can't connect to external services, port binding failures

**Diagnosis**:
```bash
# Check Docker networks
docker network ls
docker network inspect bridge

# Test container networking
docker run --rm -it python:3.9 ping google.com

# Check port availability
netstat -tulpn | grep <port>
```

**Solutions**:
```bash
# Create custom networks if needed
docker network create --driver bridge custom-network

# For port conflicts, use different ports or docker-compose
# Check firewall settings
sudo ufw status  # Ubuntu
```

#### Volume Mounting Failures

**Symptoms**: File permission errors, missing files in containers

**Diagnosis**:
```bash
# Check mount points
docker inspect <container-id> | grep -A 10 "Mounts"

# Verify source paths exist
ls -la /path/to/source

# Check SELinux/AppArmor restrictions
getenforce  # SELinux
```

**Solutions**:
```bash
# Fix file permissions
chmod 755 /path/to/source
chown $USER:$USER /path/to/source

# For SELinux, add :Z or :z flag
# docker run -v /path:/container/path:Z image

# Create required directories
mkdir -p /path/to/source
```

### Cloud Run Executor Issues

#### Authentication Failures

**Symptoms**: GCP authentication errors, permission denied

**Diagnosis**:
```bash
# Check Google Cloud credentials
gcloud auth list
gcloud config list

# Verify service account permissions
gcloud projects get-iam-policy <project-id>

# Test Cloud Run access
gcloud run services list
```

**Solutions**:
```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Verify required permissions:
# - Cloud Run Developer
# - Service Account User
# - Cloud Build Editor (if building images)
```

#### Deployment Failures

**Symptoms**: Cloud Run deployment timeouts, image pull errors

**Diagnosis**:
```bash
# Check Cloud Run service status
gcloud run services describe <service-name> --region=<region>

# Verify image accessibility
gcloud container images list --repository=gcr.io/<project-id>

# Check Cloud Run quotas
gcloud run services list
```

**Solutions**:
- **Image registry access**: Ensure images are in accessible registry
- **Resource limits**: Verify Cloud Run resource allocations are sufficient
- **Region availability**: Check service is deployed in correct region
- **Timeout configuration**: Increase timeout limits for long-running jobs

## Environment Variable Issues

### Template Parsing Errors

**Symptoms**: Invalid environment variable format errors

**Common formatting issues**:
```bash
# ✗ Incorrect formats
KEY = value                  # Spaces around equals
KEY=value with spaces        # Unquoted spaces
MULTILINE_KEY=line1\nline2   # Improper newline handling

# ✓ Correct formats
KEY=value                    # Simple assignment
KEY="value with spaces"      # Quoted values
KEY='single quotes work'     # Single quotes OK
DATABASE_URL=postgresql://user:pass@host:5432/db  # Complex values
```

**Diagnosis**:
```python
# Test environment variable parsing
uv run python manage.py shell -c "
from container_manager.models import EnvironmentVariableTemplate
template = EnvironmentVariableTemplate.objects.get(name='<template-name>')
try:
    env_dict = template.get_environment_variables_dict()
    print('Parsed variables:', env_dict)
except Exception as e:
    print('Parse error:', e)
"
```

**Solutions**:
- **Quote values with spaces**: Use `KEY="value with spaces"`
- **Escape special characters**: Use proper escaping for quotes and backslashes
- **Validate format**: Test parsing before using in jobs
- **Use simple values**: Avoid complex multiline values in templates

### Variable Interpolation Problems

**Symptoms**: Variables not resolved, circular reference errors

**Diagnosis**:
```python
# Check for circular references
uv run python manage.py shell -c "
from container_manager.models import EnvironmentVariableTemplate
template = EnvironmentVariableTemplate.objects.get(name='<template-name>')
env_vars = template.get_environment_variables_dict()
for key, value in env_vars.items():
    if key in value:
        print(f'Potential circular reference: {key}={value}')
"
```

**Solutions**:
- **Avoid circular references**: Don't reference a variable within its own definition
- **Use absolute values**: Prefer absolute paths and values over relative references
- **Test interpolation**: Verify variable resolution before deployment

## Logging and Monitoring Issues

### Log Collection Problems

#### Missing Container Logs

**Symptoms**: Jobs complete but no logs available

**Diagnosis**:
```python
# Check log collection
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
job = ContainerJob.objects.get(id=<job_id>)
print('Job status:', job.status)
print('Logs length:', len(job.docker_log or ''))
print('Log preview:', (job.docker_log or '')[:200])
"

# Check Docker logging configuration
docker info | grep -i logging
```

**Solutions**:
```bash
# Verify Docker logging driver
# Add to daemon.json if needed:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Restart Docker daemon after changes
sudo systemctl restart docker
```

#### Log Parsing Failures

**Symptoms**: Garbled logs, encoding errors

**Diagnosis**:
```bash
# Check log encoding
file db.sqlite3
locale

# Test direct Docker logs
docker logs <container-id> | head -20
```

**Solutions**:
- **Set UTF-8 encoding**: Ensure system locale supports UTF-8
- **Handle binary output**: Filter or encode binary data in container output
- **Log size limits**: Implement log rotation to prevent oversized logs

### Health Check Failures

#### Executor Host Health Checks

**Symptoms**: Hosts marked inactive, health check timeouts

**Diagnosis**:
```python
# Manual health check
uv run python manage.py shell -c "
from container_manager.models import ExecutorHost
from container_manager.executors.factory import ExecutorFactory
factory = ExecutorFactory()

for host in ExecutorHost.objects.all():
    try:
        executor = factory.get_executor(host)
        # Attempt basic operation
        print(f'{host.name}: Healthy')
    except Exception as e:
        print(f'{host.name}: Health check failed - {e}')
"
```

**Solutions**:
```bash
# Check network connectivity
ping <host-address>
telnet <host> <port>

# Verify service availability
# For Docker: docker ps
# For Cloud Run: gcloud run services list

# Update host configuration if needed
# Verify connection strings and credentials
```

## Performance Issues

### Slow Job Execution

#### Image Pull Optimization

**Symptoms**: Long delays before job execution starts

**Diagnosis**:
```bash
# Test image pull speed
time docker pull <image-name>

# Check available disk space
df -h

# Monitor network during pull
iftop  # or similar network monitor
```

**Solutions**:
```bash
# Use image caching
docker pull <base-image>  # Pre-pull common base images

# Optimize Dockerfile
# - Use smaller base images (alpine variants)
# - Combine RUN statements
# - Order layers by change frequency

# Use local registry for frequently used images
# Set up Docker registry cache
```

#### Container Startup Delays

**Symptoms**: Long time between container creation and job execution

**Diagnosis**:
```python
# Check job timing
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
job = ContainerJob.objects.get(id=<job_id>)
if job.started_at and job.created_at:
    startup_time = job.started_at - job.created_at
    print(f'Startup time: {startup_time.total_seconds()} seconds')
"
```

**Solutions**:
- **Optimize base images**: Use minimal base images with required tools pre-installed
- **Reduce initialization**: Minimize application startup time
- **Pre-warm containers**: Consider container reuse strategies
- **Resource allocation**: Ensure sufficient CPU/memory for startup

### Resource Contention

#### Host Resource Exhaustion

**Symptoms**: Jobs fail due to resource unavailability

**Diagnosis**:
```bash
# Check system resources
free -h     # Memory usage
df -h       # Disk usage
top         # CPU usage
iostat 1 5  # I/O statistics

# Check Docker resource usage
docker stats
docker system df
```

**Solutions**:
```bash
# Clean up unused resources
docker system prune -f
docker volume prune -f
docker image prune -f

# Adjust job concurrency
# Reduce --max-jobs in process_container_jobs command

# Add resource monitoring
# Implement resource-aware job scheduling
```

## Security and Permissions

### Container Security Issues

#### User Namespace Problems

**Symptoms**: File permission conflicts, UID/GID mapping errors

**Diagnosis**:
```bash
# Check Docker user namespace configuration
docker info | grep -i userns

# Test file permissions in container
docker run --rm -v /tmp:/tmp:Z python:3.9 ls -la /tmp
```

**Solutions**:
```bash
# Configure user namespace remapping
# Edit /etc/docker/daemon.json:
{
  "userns-remap": "default"
}

# Or use specific user mapping
docker run --user $(id -u):$(id -g) image command
```

#### Network Security

**Symptoms**: Container isolation concerns, unexpected network access

**Diagnosis**:
```bash
# Check container network configuration
docker network ls
docker inspect <container-id> | grep -A 20 "NetworkSettings"

# Test network isolation
docker run --rm --network none python:3.9 ping google.com
```

**Solutions**:
```bash
# Use custom networks for isolation
docker network create --driver bridge isolated-network

# Implement network policies
# Use Docker security profiles
# Configure firewall rules appropriately
```

### Access Control Problems

#### Django Admin Access

**Symptoms**: Authentication failures, permission denied in admin interface

**Diagnosis**:
```python
# Check user permissions
uv run python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(username='<username>')
print('Is superuser:', user.is_superuser)
print('Is staff:', user.is_staff)
print('Groups:', list(user.groups.all()))
"
```

**Solutions**:
```bash
# Create superuser
uv run python manage.py createsuperuser

# Or grant permissions to existing user
uv run python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(username='<username>')
user.is_staff = True
user.is_superuser = True
user.save()
print('Permissions updated')
"
```

## Diagnostic Tools and Commands

### System Information Collection

Use this script to collect comprehensive system information for troubleshooting:

```bash
#!/bin/bash
echo "=== Django Docker Manager Diagnostic Information ==="
echo "Generated at: $(date)"
echo

echo "=== System Information ==="
uname -a
echo "Python version: $(python --version 2>&1)"
echo "Docker version:"
docker --version 2>&1 || echo "Docker not available"
echo "uv version:"
uv --version 2>&1 || echo "uv not available"
echo

echo "=== Docker Status ==="
docker info 2>&1 | head -20 || echo "Docker daemon not accessible"
echo
echo "Running containers:"
docker ps 2>&1 || echo "Cannot list containers"
echo

echo "=== Django Application Status ==="
cd /path/to/django-docker 2>/dev/null || echo "Project path not found"
echo "Django check:"
uv run python manage.py check 2>&1 | head -10
echo
echo "Migration status:"
uv run python manage.py showmigrations 2>&1 | tail -10
echo

echo "=== Database Status ==="
echo "Database connectivity:"
uv run python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print('Database: Connected')
except Exception as e:
    print(f'Database: Error - {e}')
" 2>&1
echo

echo "=== Job Status Summary ==="
uv run python manage.py shell -c "
from container_manager.models import ContainerJob, ExecutorHost
try:
    total_jobs = ContainerJob.objects.count()
    pending_jobs = ContainerJob.objects.filter(status='pending').count()
    running_jobs = ContainerJob.objects.filter(status='running').count()
    failed_jobs = ContainerJob.objects.filter(status='failed').count()
    
    print(f'Total jobs: {total_jobs}')
    print(f'Pending: {pending_jobs}')
    print(f'Running: {running_jobs}')
    print(f'Failed: {failed_jobs}')
    
    active_hosts = ExecutorHost.objects.filter(is_active=True).count()
    total_hosts = ExecutorHost.objects.count()
    print(f'Executor hosts: {active_hosts}/{total_hosts} active')
    
except Exception as e:
    print(f'Job status error: {e}')
" 2>&1
echo

echo "=== Recent Error Logs ==="
echo "Recent failed jobs:"
uv run python manage.py shell -c "
from container_manager.models import ContainerJob
failed_jobs = ContainerJob.objects.filter(status='failed').order_by('-created_at')[:3]
for job in failed_jobs:
    print(f'Job {job.id}: {(job.docker_log or \"\")[:100]}...')
" 2>&1
echo

echo "=== Resource Usage ==="
echo "Memory usage:"
free -h 2>&1 || echo "free command not available"
echo
echo "Disk usage:"
df -h 2>&1 | head -10 || echo "df command not available"
echo

echo "=== End Diagnostic Information ==="
```

### Log Analysis Commands

```bash
# Container log analysis
docker logs <container-id> --tail=100 --follow

# Django application logs (if configured)
tail -f logs/django.log

# System resource monitoring
htop  # Interactive process viewer
iostat 1 5  # I/O statistics
vmstat 1 5  # Virtual memory statistics

# Network connectivity tests
ping google.com
nslookup <hostname>
telnet <host> <port>
```

### Database Inspection

```python
# Django shell database inspection
uv run python manage.py shell

# Inside Django shell:
from container_manager.models import *
from django.db import connection

# Check recent jobs
recent_jobs = ContainerJob.objects.order_by('-created_at')[:10]
for job in recent_jobs:
    print(f"{job.id}: {job.status} - {job.image}")

# Check executor hosts
hosts = ExecutorHost.objects.all()
for host in hosts:
    print(f"{host.name}: {host.executor_type} - Active: {host.is_active}")

# Database table inspection
with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", [table[0] for table in tables])
```

## Getting Help and Reporting Issues

### Information to Collect Before Seeking Help

Before reporting issues or asking for help, collect this information:

1. **System Environment**:
   - Operating system and version
   - Docker version (`docker --version`)
   - Python version (`python --version`)
   - uv version (`uv --version`)

2. **Error Details**:
   - Complete error messages (not truncated)
   - Stack traces (full output)
   - Steps that led to the error
   - Expected vs. actual behavior

3. **Configuration Information** (sanitized):
   - ExecutorHost configurations (remove sensitive connection details)
   - Job configurations that fail
   - Environment variable templates (remove secrets)

4. **Logs and Timing**:
   - Recent application logs
   - Container logs if available
   - Timestamps when issues occur
   - Pattern of occurrence (intermittent vs. consistent)

5. **System State**:
   - Output of diagnostic script above
   - Resource usage during issues
   - Any recent changes to system or configuration

### Issue Reporting Template

Use this template when reporting issues:

```markdown
## Problem Description
[Clear, concise description of what's not working]

## Environment
- **OS**: [Operating System and version]
- **Docker**: [Docker version output]
- **Python**: [Python version]
- **uv**: [uv version]
- **Project**: [Git commit hash or release version]

## Steps to Reproduce
1. [First step - be specific]
2. [Second step - include commands run]
3. [Third step - include any configuration]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens - include error messages]

## Error Messages
```
[Complete error text with stack traces]
```

## Configuration
[Relevant model configurations, environment variables, settings - remove secrets]

## Logs
```
[Relevant log excerpts with timestamps]
```

## Additional Context
[System resource usage, recent changes, related issues, attempted solutions]
```

### Self-Help Resources

Before seeking external help:

1. **Search existing documentation**: Check README.md, INSTALL.md, API.md
2. **Review logs systematically**: Look for patterns in error messages
3. **Test in isolation**: Try reproducing with minimal configuration
4. **Check recent changes**: Consider what changed before issues started
5. **Verify basic functionality**: Ensure core components work independently

### Escalation Guidelines

**Level 1 - Self-Service** (5-15 minutes):
- Follow diagnostic framework
- Check documentation
- Run diagnostic commands
- Try obvious solutions

**Level 2 - Community Help** (30-60 minutes):
- Search existing issues
- Prepare detailed issue report
- Include diagnostic information
- Engage with community

**Level 3 - Expert Assistance** (1+ hours of investigation):
- Complex system integration issues
- Performance optimization needs
- Security configuration questions
- Custom deployment scenarios

## LLM Agent Guidelines

### Behavioral Constraints
- **DO**: Follow diagnostic procedures step-by-step without skipping steps
- **DO**: Document all findings and attempted solutions
- **DO**: Stop troubleshooting when safety boundaries are approached
- **DO**: Verify system state before and after troubleshooting actions
- **DO NOT**: Modify production data during troubleshooting
- **DO NOT**: Restart services without understanding impact
- **DO NOT**: Delete logs or system files during diagnostics
- **DO NOT**: Continue troubleshooting if system stability is at risk
- **LIMITS**: Maximum 30 minutes per troubleshooting session before escalation

### Security Requirements
- **Access control**: Only use read-only operations for diagnostics unless explicitly authorized
- **Data protection**: Never expose sensitive information in troubleshooting logs
- **System integrity**: Avoid operations that could compromise system security
- **Privilege boundaries**: Do not escalate privileges beyond necessary scope
- **Evidence preservation**: Maintain audit trail of all troubleshooting actions

### Safe Operation Patterns
- **Diagnostic workflow**:
  1. Identify and document the problem symptoms
  2. Check system health and resource availability
  3. Review recent logs for error patterns
  4. Verify configuration settings are correct
  5. Test connectivity and permissions
  6. Apply minimal, reversible fixes first
- **Recovery procedures**:
  1. Create backups before making changes
  2. Test fixes in non-production environment first
  3. Document all changes made during troubleshooting
  4. Verify fix resolves issue without side effects
  5. Monitor system stability after applying fixes

### Error Handling
- **If diagnostic commands fail**: Document failure, try alternative approaches, escalate if needed
- **If system becomes unstable**: Stop troubleshooting, revert changes, escalate immediately
- **If data corruption suspected**: Stop all operations, preserve evidence, escalate to data recovery
- **If security breach indicated**: Follow security incident procedures, do not continue troubleshooting
- **If unclear on procedure**: Request guidance rather than guessing

### Validation Requirements
- [ ] All diagnostic commands are read-only or have minimal system impact
- [ ] Troubleshooting procedures tested in safe environments
- [ ] No sensitive information exposed in diagnostic outputs
- [ ] Clear escalation criteria defined for each problem category
- [ ] Recovery procedures include rollback steps
- [ ] Documentation includes expected diagnostic outputs
- [ ] Safety boundaries clearly marked for dangerous operations

### Troubleshooting Safety Boundaries
- **NEVER delete**: System logs, database files, or configuration without explicit authorization
- **NEVER modify**: Production database data during troubleshooting
- **NEVER restart**: Critical services without understanding dependencies and impact
- **NEVER bypass**: Security controls or authentication mechanisms
- **NEVER ignore**: System stability warnings or resource exhaustion alerts
- **NEVER continue**: If troubleshooting actions could cause data loss
- **NEVER escalate**: Privileges beyond minimum required for diagnostics

## Frequently Asked Questions

### Q: Jobs are stuck in pending status and never start
**A**: Check executor host availability and ensure the job processor is running:
```bash
uv run python manage.py process_container_jobs --single-run
```

### Q: Container images fail to pull
**A**: Verify image names and authentication:
```bash
docker pull <image-name>
docker login  # if authentication required
```

### Q: Jobs complete but no logs are captured
**A**: Check Docker logging configuration and ensure containers produce output to stdout/stderr.

### Q: High memory usage causing system slowdown
**A**: Monitor resource usage and adjust job concurrency:
```bash
docker stats
# Reduce --max-jobs parameter
```

### Q: Permission denied errors with Docker
**A**: Add user to docker group:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Q: Database migration conflicts during setup
**A**: Reset migrations in development environment:
```bash
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
uv run python manage.py makemigrations
uv run python manage.py migrate
```

### Q: Cloud Run executor authentication failures
**A**: Set up Google Cloud authentication:
```bash
gcloud auth application-default login
# or set GOOGLE_APPLICATION_CREDENTIALS environment variable
```

### Q: Containers start but immediately exit
**A**: Check command syntax and container logs:
```bash
docker logs <container-id>
# Verify command is valid for the image
```