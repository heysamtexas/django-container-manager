# Production Deployment Guide

This guide covers deploying Django Docker Container Manager in production environments.

## Deployment Strategies

### Docker Compose Deployment

#### Complete Production Stack
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=False
      - DATABASE_URL=postgresql://django_user:${DB_PASSWORD}@db:5432/django_docker_manager
      - REDIS_URL=redis://redis:6379/0
      - ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
      - DOCKER_HOSTS=unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      - db
      - redis
    restart: unless-stopped
    networks:
      - app-network

  worker:
    build: .
    command: python manage.py process_container_jobs --poll-interval=3 --max-jobs=20
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=False
      - DATABASE_URL=postgresql://django_user:${DB_PASSWORD}@db:5432/django_docker_manager
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - db
    restart: unless-stopped
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/staticfiles:ro
      - media_volume:/app/media:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - web
    restart: unless-stopped
    networks:
      - app-network

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: django_docker_manager
      POSTGRES_USER: django_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backup:/backup
    restart: unless-stopped
    networks:
      - app-network

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - app-network

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:

networks:
  app-network:
    driver: bridge
```

#### Environment Configuration
```bash
# .env file for production
SECRET_KEY=your-complex-secret-key-here
DB_PASSWORD=secure-database-password
REDIS_PASSWORD=secure-redis-password
DOMAIN=yourdomain.com
```

### Kubernetes Deployment

#### Namespace and ConfigMap
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: django-docker-manager
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: django-docker-manager
data:
  DEBUG: "False"
  ALLOWED_HOSTS: "yourdomain.com,www.yourdomain.com"
  DATABASE_URL: "postgresql://django_user:password@postgres:5432/django_docker_manager"
  REDIS_URL: "redis://redis:6379/0"
```

#### Django Application Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-app
  namespace: django-docker-manager
spec:
  replicas: 3
  selector:
    matchLabels:
      app: django-app
  template:
    metadata:
      labels:
        app: django-app
    spec:
      containers:
      - name: django
        image: your-registry/django-docker-manager:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
        volumeMounts:
        - name: docker-socket
          mountPath: /var/run/docker.sock
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
---
apiVersion: v1
kind: Service
metadata:
  name: django-service
  namespace: django-docker-manager
spec:
  selector:
    app: django-app
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

#### Worker Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: container-worker
  namespace: django-docker-manager
spec:
  replicas: 2
  selector:
    matchLabels:
      app: container-worker
  template:
    metadata:
      labels:
        app: container-worker
    spec:
      containers:
      - name: worker
        image: your-registry/django-docker-manager:latest
        command: ["python", "manage.py", "process_container_jobs"]
        args: ["--poll-interval=5", "--max-jobs=10"]
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
        volumeMounts:
        - name: docker-socket
          mountPath: /var/run/docker.sock
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
      volumes:
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
```

## Database Setup

### PostgreSQL Configuration

#### Production Database Setup
```sql
-- Create database and user
CREATE DATABASE django_docker_manager;
CREATE USER django_user WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE django_docker_manager TO django_user;
ALTER USER django_user CREATEDB;

-- Set connection limits
ALTER USER django_user CONNECTION LIMIT 20;

-- Configure for Django
ALTER DATABASE django_docker_manager SET default_transaction_isolation TO 'read committed';
ALTER DATABASE django_docker_manager SET timezone TO 'UTC';
```

#### Database Optimization
```sql
-- PostgreSQL performance tuning
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- Reload configuration
SELECT pg_reload_conf();
```

### Database Backup Strategy

#### Automated Backups
```bash
#!/bin/bash
# backup.sh - Daily database backup script

BACKUP_DIR="/backup/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="django_docker_manager"

# Create backup directory
mkdir -p $BACKUP_DIR

# Perform backup
pg_dump -h localhost -U django_user -d $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 30 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

# Upload to cloud storage (optional)
# aws s3 cp $BACKUP_DIR/backup_$DATE.sql.gz s3://your-backup-bucket/
```

#### Backup Cron Job
```bash
# Add to crontab
0 2 * * * /path/to/backup.sh >> /var/log/backup.log 2>&1
```

## Security Configuration

### SSL/TLS Setup

#### Nginx SSL Configuration
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://django-app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Docker Socket Security

#### Socket Proxy Setup
```yaml
# docker-socket-proxy service
socket-proxy:
  image: tecnativa/docker-socket-proxy
  environment:
    CONTAINERS: 1
    IMAGES: 1
    AUTH: 1
    PING: 1
    VERSION: 1
    BUILD: 1
    COMMIT: 1
    EXEC: 1
    LOGS: 1
    NETWORKS: 1
    VOLUMES: 1
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  networks:
    - socket-proxy-network
  restart: unless-stopped
```

#### Firewall Configuration
```bash
# UFW firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Docker-specific rules
sudo ufw allow from 172.16.0.0/12 to any port 5432  # PostgreSQL
sudo ufw allow from 172.16.0.0/12 to any port 6379  # Redis
```

## Monitoring and Logging

### Application Monitoring

#### Health Check Endpoint
```python
# container_manager/views.py
from django.http import JsonResponse
from django.views import View
from django.db import connection
from .models import DockerHost

class HealthCheckView(View):
    def get(self, request):
        try:
            # Database check
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Docker hosts check
            active_hosts = DockerHost.objects.filter(is_active=True).count()
            
            return JsonResponse({
                'status': 'healthy',
                'database': 'connected',
                'active_docker_hosts': active_hosts,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            return JsonResponse({
                'status': 'unhealthy',
                'error': str(e)
            }, status=500)
```

#### Prometheus Metrics
```python
# Add to settings.py
INSTALLED_APPS += ['django_prometheus']
MIDDLEWARE.insert(0, 'django_prometheus.middleware.PrometheusBeforeMiddleware')
MIDDLEWARE.append('django_prometheus.middleware.PrometheusAfterMiddleware')

# Custom metrics
from prometheus_client import Counter, Histogram, Gauge

job_counter = Counter('container_jobs_total', 'Total container jobs', ['status'])
job_duration = Histogram('container_job_duration_seconds', 'Job duration')
active_containers = Gauge('active_containers', 'Number of active containers')
```

### Log Management

#### Structured Logging Configuration
```python
# Production logging settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "func": "%(funcName)s", "line": %(lineno)d}',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/django-docker-manager.log',
            'maxBytes': 50*1024*1024,  # 50MB
            'backupCount': 10,
            'formatter': 'json',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/django-docker-manager-error.log',
            'maxBytes': 50*1024*1024,  # 50MB
            'backupCount': 10,
            'formatter': 'json',
        },
    },
    'loggers': {
        'container_manager': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
```

#### Log Shipping with Fluentd
```yaml
# fluentd.conf
<source>
  @type tail
  path /var/log/django/*.log
  pos_file /var/log/fluentd/django.log.pos
  tag django.*
  format json
</source>

<match django.**>
  @type elasticsearch
  host elasticsearch
  port 9200
  index_name django-logs
  type_name _doc
</match>
```

## Performance Optimization

### Database Performance

#### Connection Pooling
```python
# Database configuration with connection pooling
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

#### Database Indexing
```sql
-- Add performance indexes
CREATE INDEX CONCURRENTLY idx_container_job_status ON container_manager_containerjob(status);
CREATE INDEX CONCURRENTLY idx_container_job_created ON container_manager_containerjob(created_at);
CREATE INDEX CONCURRENTLY idx_container_job_docker_host ON container_manager_containerjob(docker_host_id);
CREATE INDEX CONCURRENTLY idx_container_job_template ON container_manager_containerjob(template_id);
```

### Application Performance

#### Caching Configuration
```python
# Redis caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
            },
        },
        'TIMEOUT': 300,
        'KEY_PREFIX': 'django_docker_manager'
    }
}

# Session storage in Redis
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

## Scaling Strategies

### Horizontal Scaling

#### Load Balancer Configuration
```nginx
# nginx upstream configuration
upstream django_app {
    least_conn;
    server django-app-1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server django-app-2:8000 weight=1 max_fails=3 fail_timeout=30s;
    server django-app-3:8000 weight=1 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Connection keep-alive
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

#### Worker Scaling
```yaml
# Auto-scaling worker deployment
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: container-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: container-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Resource Management

#### Container Resource Limits
```python
# Production container limits
DEFAULT_CONTAINER_LIMITS = {
    'memory': '1g',
    'cpus': '1.0',
    'timeout': 3600,  # 1 hour
    'restart_policy': {'Name': 'on-failure', 'MaximumRetryCount': 3}
}

# Per-environment limits
ENVIRONMENT_LIMITS = {
    'development': {'memory': '256m', 'cpus': '0.5'},
    'staging': {'memory': '512m', 'cpus': '1.0'},
    'production': {'memory': '2g', 'cpus': '2.0'}
}
```

## Disaster Recovery

### Backup Strategy

#### Complete Backup Script
```bash
#!/bin/bash
# complete-backup.sh

BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h db -U django_user django_docker_manager | gzip > $BACKUP_DIR/database.sql.gz

# Redis backup
redis-cli --rdb $BACKUP_DIR/redis.rdb

# Static files backup
tar -czf $BACKUP_DIR/static.tar.gz /app/staticfiles

# Configuration backup
cp -r /app/config $BACKUP_DIR/

# Upload to cloud storage
aws s3 sync $BACKUP_DIR s3://your-backup-bucket/$(date +%Y%m%d)/

# Cleanup old backups
find /backup -type d -mtime +7 -exec rm -rf {} +
```

### Recovery Procedures

#### Database Recovery
```bash
# Stop application
docker-compose stop web worker

# Restore database
gunzip -c backup/database.sql.gz | psql -h db -U django_user django_docker_manager

# Restore Redis
redis-cli --rdb backup/redis.rdb

# Start application
docker-compose start web worker
```

## Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Database migrations applied
- [ ] Static files collected
- [ ] Docker images built and pushed
- [ ] Backup systems configured
- [ ] Monitoring setup complete

### Post-Deployment
- [ ] Health checks passing
- [ ] SSL certificates valid
- [ ] Database connectivity confirmed
- [ ] Docker host connections working
- [ ] Log shipping operational
- [ ] Metrics collection active
- [ ] Backup verification complete

### Security Checklist
- [ ] Docker socket secured
- [ ] Database credentials rotated
- [ ] Firewall rules applied
- [ ] SSL/TLS configured
- [ ] Security headers enabled
- [ ] Container resource limits set
- [ ] Network segmentation implemented

For ongoing maintenance, see the [Monitoring Guide](monitoring.md).