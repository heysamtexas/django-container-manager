# Docker Host Management Guide

This guide covers managing Docker hosts in Django Docker Container Manager.

## Overview

Docker hosts represent Docker daemon endpoints that the system can connect to for container management. The system supports both local Unix socket connections and remote TCP connections with optional TLS encryption.

## Host Types

### Unix Socket (Local)
- **Use case**: Local Docker daemon on the same machine
- **Connection**: `unix:///var/run/docker.sock`
- **Security**: File system permissions
- **Performance**: Fastest connection method

### TCP Socket (Remote)
- **Use case**: Remote Docker daemons across network
- **Connection**: `tcp://hostname:port`
- **Security**: Optional TLS with client certificates
- **Performance**: Network latency dependent

## Adding Docker Hosts

### Via Django Admin

1. Navigate to **Container Manager** → **Docker Hosts**
2. Click **Add Docker Host**
3. Fill in the configuration:
   - **Name**: Unique identifier (e.g., "production-docker")
   - **Host Type**: Select "Unix Socket" or "TCP"
   - **Connection String**: Full connection URL
   - **Is Active**: Enable/disable the host
   - **TLS Enabled**: For secure TCP connections
   - **TLS Verify**: Verify server certificates

### Via Django Shell

```python
from container_manager.models import DockerHost

# Local Unix socket
local_host = DockerHost.objects.create(
    name="local-docker",
    host_type="unix",
    connection_string="unix:///var/run/docker.sock",
    is_active=True,
    tls_enabled=False,
    tls_verify=False
)

# Remote TCP with TLS
remote_host = DockerHost.objects.create(
    name="production-docker",
    host_type="tcp",
    connection_string="tcp://docker.example.com:2376",
    is_active=True,
    tls_enabled=True,
    tls_verify=True,
    description="Production Docker swarm manager"
)
```

### Via Management Command

```bash
# Add local Docker host
uv run python manage.py shell -c "
from container_manager.models import DockerHost
DockerHost.objects.create(
    name='local-docker',
    host_type='unix',
    connection_string='unix:///var/run/docker.sock',
    is_active=True
)
"
```

## Configuration Examples

### Local Development Setup

```python
{
    "name": "local-dev",
    "host_type": "unix",
    "connection_string": "unix:///var/run/docker.sock",
    "is_active": True,
    "tls_enabled": False,
    "tls_verify": False,
    "description": "Local development Docker daemon"
}
```

### Remote Production Server

```python
{
    "name": "prod-server-01",
    "host_type": "tcp",
    "connection_string": "tcp://10.0.1.100:2376",
    "is_active": True,
    "tls_enabled": True,
    "tls_verify": True,
    "description": "Production server 01"
}
```

### Docker Swarm Manager

```python
{
    "name": "swarm-manager",
    "host_type": "tcp", 
    "connection_string": "tcp://swarm.example.com:2377",
    "is_active": True,
    "tls_enabled": True,
    "tls_verify": True,
    "description": "Docker Swarm cluster manager"
}
```

### Load Balancer Setup

```python
# Multiple hosts for load distribution
hosts = [
    {
        "name": "worker-01",
        "host_type": "tcp",
        "connection_string": "tcp://worker01.example.com:2376",
        "is_active": True,
        "tls_enabled": True,
        "tls_verify": True
    },
    {
        "name": "worker-02", 
        "host_type": "tcp",
        "connection_string": "tcp://worker02.example.com:2376",
        "is_active": True,
        "tls_enabled": True,
        "tls_verify": True
    }
]
```

## TLS Configuration

### Certificate Setup

For secure TCP connections, you need client certificates:

```bash
# Certificate directory structure
/etc/docker/certs/
├── ca.pem          # Certificate Authority
├── cert.pem        # Client certificate
└── key.pem         # Client private key
```

### Generating Certificates

```bash
# Generate CA private key
openssl genrsa -aes256 -out ca-key.pem 4096

# Generate CA certificate
openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem

# Generate server key
openssl genrsa -out server-key.pem 4096

# Generate server certificate signing request
openssl req -subj "/CN=docker.example.com" -sha256 -new -key server-key.pem -out server.csr

# Sign server certificate
openssl x509 -req -days 365 -sha256 -in server.csr -CA ca.pem -CAkey ca-key.pem -out server-cert.pem -CAcreateserial

# Generate client key
openssl genrsa -out key.pem 4096

# Generate client certificate signing request
openssl req -subj '/CN=client' -new -key key.pem -out client.csr

# Sign client certificate
openssl x509 -req -days 365 -sha256 -in client.csr -CA ca.pem -CAkey ca-key.pem -out cert.pem -CAcreateserial
```

### Docker Daemon TLS Setup

```bash
# Start Docker daemon with TLS
dockerd \
    --tlsverify \
    --tlscacert=ca.pem \
    --tlscert=server-cert.pem \
    --tlskey=server-key.pem \
    -H=0.0.0.0:2376
```

### Environment Variables

```bash
# TLS certificate paths
DOCKER_TLS_CERTDIR=/etc/docker/certs
DOCKER_CERT_PATH=/etc/docker/certs
DOCKER_TLS_VERIFY=1
```

## Host Management Operations

### Testing Connectivity

```python
# Test host connection
from container_manager.docker_service import docker_service
from container_manager.models import DockerHost

host = DockerHost.objects.get(name="your-host")
try:
    client = docker_service.get_client(host)
    info = client.info()
    print(f"Connected to {host.name}: {info['ServerVersion']}")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Admin Interface Testing

The Django admin provides a "Test Connection" action:

1. Select Docker hosts in the admin list
2. Choose "Test connection to selected hosts" action
3. Execute to see connection results

### Bulk Operations

```python
# Enable multiple hosts
DockerHost.objects.filter(name__startswith="prod-").update(is_active=True)

# Disable hosts for maintenance
DockerHost.objects.filter(name__contains="staging").update(is_active=False)
```

## Host Selection and Load Balancing

### Automatic Host Selection

The system automatically selects active hosts for job execution:

```python
# container_manager/docker_service.py
def get_available_host(self):
    """Select best available host for job execution"""
    active_hosts = DockerHost.objects.filter(is_active=True)
    
    if not active_hosts.exists():
        raise ValueError("No active Docker hosts available")
    
    # Simple round-robin selection
    return active_hosts.order_by('last_used_at').first()
```

### Manual Host Selection

```python
# Create job on specific host
from container_manager.models import ContainerJob, DockerHost, ContainerTemplate

host = DockerHost.objects.get(name="specific-host")
template = ContainerTemplate.objects.get(name="my-template")

job = ContainerJob.objects.create(
    template=template,
    docker_host=host,
    command_override="custom command"
)
```

### Load Balancing Strategies

#### Round Robin
```python
def select_host_round_robin():
    hosts = DockerHost.objects.filter(is_active=True).order_by('last_used_at')
    if hosts.exists():
        selected = hosts.first()
        selected.last_used_at = timezone.now()
        selected.save()
        return selected
    return None
```

#### Resource-Based Selection
```python
def select_host_by_resources():
    """Select host with most available resources"""
    best_host = None
    best_score = -1
    
    for host in DockerHost.objects.filter(is_active=True):
        try:
            client = docker_service.get_client(host)
            info = client.info()
            
            # Calculate resource availability score
            mem_total = info.get('MemTotal', 0)
            mem_used = mem_total - info.get('MemAvailable', 0)
            cpu_count = info.get('NCPU', 1)
            
            # Simple scoring: available memory percentage + cpu count
            score = ((mem_total - mem_used) / mem_total * 100) + cpu_count
            
            if score > best_score:
                best_score = score
                best_host = host
                
        except Exception:
            continue  # Skip unavailable hosts
    
    return best_host
```

## Monitoring and Health Checks

### Host Health Monitoring

```python
# container_manager/health.py
def check_docker_host_health(host):
    """Check if Docker host is healthy"""
    try:
        client = docker_service.get_client(host)
        
        # Basic connectivity
        client.ping()
        
        # System info
        info = client.info()
        
        # Check disk space
        if info.get('Driver') == 'overlay2':
            # Check overlay storage
            pass
        
        return {
            'status': 'healthy',
            'version': info.get('ServerVersion'),
            'containers': info.get('Containers', 0),
            'images': info.get('Images', 0),
            'memory': info.get('MemTotal', 0),
            'cpus': info.get('NCPU', 0)
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
```

### Automated Health Checks

```python
# Management command for health monitoring
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Check Docker host health'
    
    def add_arguments(self, parser):
        parser.add_argument('--host', help='Specific host to check')
        parser.add_argument('--disable-unhealthy', action='store_true')
    
    def handle(self, *args, **options):
        hosts = DockerHost.objects.filter(is_active=True)
        
        if options['host']:
            hosts = hosts.filter(name=options['host'])
        
        for host in hosts:
            health = check_docker_host_health(host)
            
            if health['status'] == 'healthy':
                self.stdout.write(
                    self.style.SUCCESS(f'{host.name}: Healthy')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'{host.name}: {health["error"]}')
                )
                
                if options['disable_unhealthy']:
                    host.is_active = False
                    host.save()
                    self.stdout.write(f'Disabled {host.name}')
```

### Periodic Health Checks

```bash
# Cron job for regular health checks
*/5 * * * * /path/to/venv/bin/python /path/to/manage.py check_docker_health --disable-unhealthy
```

## Security Considerations

### Network Security

```bash
# Firewall rules for Docker daemon
sudo ufw allow from 10.0.0.0/8 to any port 2376  # Internal network only
sudo ufw deny 2376  # Block external access
```

### Access Control

```python
# Restrict host access by user groups
class DockerHost(models.Model):
    # ... existing fields ...
    allowed_groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        help_text="Groups allowed to use this host"
    )
    
    def can_user_access(self, user):
        if not self.allowed_groups.exists():
            return True  # No restrictions
        return self.allowed_groups.filter(user=user).exists()
```

### Audit Logging

```python
# Log host access
import logging

logger = logging.getLogger('container_manager.security')

def log_host_access(host, user, action):
    logger.info(
        "Docker host access",
        extra={
            'host': host.name,
            'user': user.username,
            'action': action,
            'timestamp': timezone.now()
        }
    )
```

## Troubleshooting

### Common Connection Issues

#### Permission Denied - Unix Socket
```bash
# Check socket permissions
ls -la /var/run/docker.sock

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Test access
docker ps
```

#### TCP Connection Refused
```bash
# Check Docker daemon is listening
sudo netstat -tlnp | grep :2376

# Check firewall rules
sudo ufw status

# Test connection
telnet docker.example.com 2376
```

#### TLS Certificate Issues
```bash
# Verify certificate files
ls -la /etc/docker/certs/

# Test TLS connection
openssl s_client -connect docker.example.com:2376 -cert cert.pem -key key.pem -CAfile ca.pem
```

### Host Performance Issues

#### High Resource Usage
```python
# Monitor host resources
def monitor_host_resources(host):
    client = docker_service.get_client(host)
    info = client.info()
    
    print(f"Memory: {info['MemTotal'] // (1024**3)}GB total")
    print(f"CPUs: {info['NCPU']}")
    print(f"Containers: {info['ContainersRunning']}/{info['Containers']}")
    print(f"Images: {info['Images']}")
```

#### Container Cleanup
```bash
# Clean up stopped containers
docker container prune -f

# Clean up unused images
docker image prune -a -f

# Clean up unused networks
docker network prune -f

# Clean up volumes
docker volume prune -f
```

### Debugging Connection Issues

```python
# Debug Docker client connection
import docker
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

try:
    client = docker.DockerClient(
        base_url='tcp://docker.example.com:2376',
        tls=docker.tls.TLSConfig(
            client_cert=('/etc/docker/certs/cert.pem', '/etc/docker/certs/key.pem'),
            ca_cert='/etc/docker/certs/ca.pem',
            verify=True
        )
    )
    print(client.info())
except Exception as e:
    print(f"Connection failed: {e}")
```

## Best Practices

### Host Configuration
1. **Use descriptive names** - Clear host identification
2. **Enable TLS for remote hosts** - Always use encryption
3. **Regular health checks** - Monitor host availability
4. **Resource monitoring** - Track usage patterns
5. **Access control** - Limit host access by groups

### Performance Optimization
1. **Local hosts for development** - Use Unix sockets when possible
2. **Network optimization** - Minimize latency for remote hosts
3. **Connection pooling** - Reuse Docker client connections
4. **Load balancing** - Distribute jobs across hosts
5. **Resource management** - Monitor and manage host resources

### Security Guidelines
1. **Certificate management** - Regularly rotate TLS certificates
2. **Network isolation** - Use private networks for Docker communication
3. **Firewall rules** - Restrict Docker daemon access
4. **Audit logging** - Log all host access attempts
5. **Regular updates** - Keep Docker daemon updated

For job management on configured hosts, see the [Job Management Guide](jobs.md).