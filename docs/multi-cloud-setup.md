# Multi-Cloud Setup Guide

Complete guide for configuring Django Multi-Executor Container Manager across multiple cloud providers with intelligent routing, cost optimization, and zero-downtime migration capabilities.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Core Setup](#core-setup)
- [Docker Executor Configuration](#docker-executor-configuration)
- [Google Cloud Run Setup](#google-cloud-run-setup)
- [AWS Fargate Setup](#aws-fargate-setup-coming-soon)
- [Azure Container Instances Setup](#azure-container-instances-setup-coming-soon)
- [Routing Configuration](#routing-configuration)
- [Cost Tracking Setup](#cost-tracking-setup)
- [Performance Monitoring](#performance-monitoring)
- [Migration Planning](#migration-planning)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- **Python 3.12+** with uv package manager
- **Django 5.2+** (automatically installed)
- **PostgreSQL 13+** (recommended for production)
- **Redis 6+** (for real-time features)
- **Docker 20.10+** (for local execution)

### Cloud Provider Accounts
- **Google Cloud Platform** account with billing enabled
- **AWS** account with appropriate permissions (future)
- **Microsoft Azure** account with subscription (future)

### Required Permissions

#### Google Cloud Platform
```json
{
  "bindings": [
    {
      "role": "roles/run.admin",
      "members": ["serviceAccount:your-service@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/logging.viewer",
      "members": ["serviceAccount:your-service@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/monitoring.viewer", 
      "members": ["serviceAccount:your-service@project.iam.gserviceaccount.com"]
    }
  ]
}
```

## Core Setup

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/heysamtexas/django-docker-manager.git
cd django-docker-manager

# Create virtual environment and install dependencies
uv sync

# Configure environment variables
cp .env.example .env
```

### 2. Environment Configuration

Create `.env` file with the following variables:

```bash
# Core Django Configuration
DJANGO_SETTINGS_MODULE=django_docker_manager.settings
SECRET_KEY=your-super-secret-key-here-change-this-in-production
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database Configuration (PostgreSQL recommended)
DATABASE_URL=postgresql://username:password@localhost:5432/django_docker_manager

# Redis Configuration (for real-time features)
REDIS_URL=redis://localhost:6379/0

# Google Cloud Platform
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# AWS Configuration (when available)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_DEFAULT_REGION=us-east-1

# Azure Configuration (when available)
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id

# Security & Monitoring
AUDIT_LOG_LEVEL=INFO
PERFORMANCE_TRACKING_ENABLED=True
COST_TRACKING_ENABLED=True
```

### 3. Database Setup

```bash
# Run database migrations
uv run python manage.py migrate

# Create superuser for admin access
uv run python manage.py createsuperuser

# Load sample data (optional)
uv run python manage.py loaddata fixtures/sample_executors.json
```

### 4. Verify Installation

```bash
# Start development server
uv run python manage.py runserver

# Access admin interface
open http://localhost:8000/admin/

# Run health check
uv run python manage.py check --deploy
```

## Docker Executor Configuration

### Local Docker Setup

#### 1. Configure Docker Host

In Django Admin (`/admin/container_manager/dockerhost/`):

```
Name: local-docker
Host Type: Unix Socket
Connection String: unix:///var/run/docker.sock
Executor Type: docker
TLS Enabled: False (for local development)
Is Active: True
Max Concurrent Jobs: 10
Cost Per Hour: $0.00 (free for local)
```

#### 2. Test Docker Connection

```bash
# Test Docker connectivity
uv run python manage.py manage_container_job test-connection local-docker

# Expected output:
# ✅ Connection successful to local-docker
# Docker version: 20.10.21
# Available resources: 8 CPUs, 16GB RAM
```

### Remote Docker Setup

#### 1. Configure TLS Connection

```bash
# Generate client certificates (if not using existing ones)
cd /path/to/docker-certs/
openssl genrsa -out client-key.pem 4096
openssl req -subj '/CN=client' -new -key client-key.pem -out client.csr
openssl x509 -req -days 365 -in client.csr -CA ca.pem -CAkey ca-key.pem -out client-cert.pem
```

#### 2. Add Remote Docker Host

```
Name: remote-docker-prod
Host Type: TCP
Connection String: tcp://docker-host.example.com:2376
Executor Type: docker
TLS Enabled: True
TLS Verify: True
TLS CA Cert: /path/to/ca.pem
TLS Client Cert: /path/to/client-cert.pem
TLS Client Key: /path/to/client-key.pem
Is Active: True
Max Concurrent Jobs: 50
Cost Per Hour: $5.00
```

## Google Cloud Run Setup

### 1. Prerequisites

```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable monitoring.googleapis.com
```

### 2. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create container-manager \
    --display-name="Container Manager Service Account" \
    --description="Service account for Django Container Manager"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:container-manager@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:container-manager@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.viewer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:container-manager@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/monitoring.viewer"

# Create and download key
gcloud iam service-accounts keys create key.json \
    --iam-account=container-manager@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Configure Cloud Run Executor

In Django Admin (`/admin/container_manager/dockerhost/`):

```json
{
  "name": "gcp-cloudrun-us-central1",
  "host_type": "tcp",
  "connection_string": "https://run.googleapis.com",
  "executor_type": "cloudrun",
  "executor_config": {
    "project_id": "your-project-id",
    "region": "us-central1",
    "service_account": "container-manager@your-project-id.iam.gserviceaccount.com",
    "vpc_connector": "projects/your-project-id/locations/us-central1/connectors/default",
    "memory_limit": 2048,
    "cpu_limit": 2.0,
    "timeout_seconds": 3600,
    "max_instances": 100
  },
  "is_active": true,
  "max_concurrent_jobs": 1000,
  "cost_per_hour": 0.00002400,
  "average_startup_time": 5
}
```

### 4. Test Cloud Run Connection

```bash
# Test Cloud Run connectivity
uv run python manage.py manage_container_job test-connection gcp-cloudrun-us-central1

# Expected output:
# ✅ Connection successful to gcp-cloudrun-us-central1
# Region: us-central1
# Available quotas: 1000 concurrent executions
# Service account: container-manager@project.iam.gserviceaccount.com
```

### 5. Regional Cloud Run Setup

For global deployment, configure multiple regions:

```bash
# Configure additional regions
regions=("us-east1" "europe-west1" "asia-southeast1")

for region in "${regions[@]}"; do
  # Add region-specific executor in Django Admin
  echo "Add executor: gcp-cloudrun-${region}"
done
```

## AWS Fargate Setup (Coming Soon)

### Prerequisites (Future Implementation)

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure credentials
aws configure
```

### Configuration Template (Future)

```json
{
  "name": "aws-fargate-us-east-1",
  "executor_type": "fargate",
  "executor_config": {
    "region": "us-east-1",
    "cluster_name": "container-manager",
    "subnet_ids": ["subnet-12345", "subnet-67890"],
    "security_group_ids": ["sg-abcdef"],
    "task_role_arn": "arn:aws:iam::123456789012:role/TaskRole",
    "cpu": 256,
    "memory": 512,
    "platform_version": "LATEST"
  }
}
```

## Azure Container Instances Setup (Coming Soon)

### Prerequisites (Future Implementation)

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login
```

### Configuration Template (Future)

```json
{
  "name": "azure-aci-east-us",
  "executor_type": "azure",
  "executor_config": {
    "subscription_id": "your-subscription-id",
    "resource_group": "container-manager-rg",
    "location": "eastus",
    "cpu": 1.0,
    "memory": 1.5,
    "os_type": "Linux",
    "restart_policy": "Never"
  }
}
```

## Routing Configuration

### 1. Create Routing Rule Sets

```bash
# Access Django Admin
open http://localhost:8000/admin/container_manager/routingruleset/
```

#### Basic Routing Rules

```python
# Rule Set: Production Routing
rules = [
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
```

#### Advanced Cost-Aware Routing

```python
# Rule Set: Cost Optimization
cost_rules = [
    {
        "name": "budget-conscious",
        "condition": "estimated_cost < 0.05 and not job_name.startswith('urgent_')",
        "target_executor": "docker",
        "priority": 15,
        "description": "Use Docker for jobs under 5 cents"
    },
    {
        "name": "performance-over-cost",
        "condition": "timeout_seconds > 1800 and estimated_cost < 2.00",
        "target_executor": "cloudrun",
        "priority": 25,
        "description": "Use Cloud Run for long jobs under $2"
    }
]
```

#### Geographic Routing

```python
# Rule Set: Geographic Distribution
geo_rules = [
    {
        "name": "us-traffic",
        "condition": "'region=us' in override_environment or 'datacenter=us' in job_name",
        "target_executor": "gcp-cloudrun-us-central1",
        "priority": 8
    },
    {
        "name": "eu-traffic", 
        "condition": "'region=eu' in override_environment or 'datacenter=eu' in job_name",
        "target_executor": "gcp-cloudrun-europe-west1",
        "priority": 8
    }
]
```

### 2. Test Routing Rules

```bash
# Test routing for a specific job template
uv run python manage.py test_routing web-scraper --show-evaluation

# Expected output:
# 🎯 Routing Evaluation for Template: web-scraper
# Memory: 512 MB, CPU: 1.0, Timeout: 300s
# 
# Evaluated Rules:
# ✅ small-jobs-docker (priority: 10) - MATCH
# ❌ large-jobs-cloudrun (priority: 20) - condition failed
# ❌ urgent-jobs-fastest (priority: 5) - condition failed
# 
# 🏆 Selected Executor: local-docker
# 📊 Estimated Cost: $0.001
```

## Cost Tracking Setup

### 1. Configure Cost Profiles

Create cost profiles for each executor type:

#### Docker Cost Profile

```json
{
  "name": "docker-local-costs",
  "executor_type": "docker",
  "region": "local",
  "cpu_cost_per_core_hour": 0.000000,
  "memory_cost_per_gb_hour": 0.000000,
  "storage_cost_per_gb_hour": 0.000000,
  "network_cost_per_gb": 0.000000,
  "request_cost": 0.000000,
  "startup_cost": 0.000000,
  "currency": "USD",
  "is_active": true
}
```

#### Google Cloud Run Cost Profile

```json
{
  "name": "cloudrun-us-central1-costs",
  "executor_type": "cloudrun", 
  "region": "us-central1",
  "cpu_cost_per_core_hour": 0.000024,
  "memory_cost_per_gb_hour": 0.0000025,
  "storage_cost_per_gb_hour": 0.000000,
  "network_cost_per_gb": 0.12,
  "request_cost": 0.0000004,
  "startup_cost": 0.000000,
  "currency": "USD", 
  "is_active": true
}
```

### 2. Enable Cost Tracking

```bash
# Enable cost tracking in settings
export COST_TRACKING_ENABLED=True

# Set up cost budgets and alerts
uv run python manage.py setup_cost_budgets \
  --daily-budget=100.00 \
  --weekly-budget=500.00 \
  --monthly-budget=2000.00
```

### 3. Cost Monitoring

```bash
# View cost analysis
uv run python manage.py cost_analysis --last-30-days

# Cost breakdown by executor
uv run python manage.py cost_breakdown --group-by=executor_type

# Generate cost report
uv run python manage.py cost_report --format=csv --output=cost_report.csv
```

## Performance Monitoring

### 1. Enable Performance Tracking

```python
# In Django settings
PERFORMANCE_TRACKING_ENABLED = True
PERFORMANCE_METRICS_RETENTION_DAYS = 90
PERFORMANCE_ALERT_THRESHOLDS = {
    'slow_launch_threshold_ms': 10000,
    'high_cpu_threshold_percent': 80,
    'high_memory_threshold_mb': 1024,
    'high_failure_rate_percent': 10
}
```

### 2. Performance Metrics Collection

Performance metrics are automatically collected for:

- **Job Launch Time**: Time from creation to container start
- **Execution Duration**: Total job execution time  
- **Resource Usage**: CPU and memory utilization
- **Network Transfer**: Data in/out during execution
- **Success/Failure Rates**: Reliability metrics per executor

### 3. Performance Analysis

```bash
# Generate performance report
uv run python manage.py performance_report \
  --executor-type=cloudrun \
  --last-7-days \
  --format=json

# Performance recommendations
uv run python manage.py performance_recommendations \
  --analyze-all-executors \
  --include-cost-analysis
```

### 4. Performance Alerts

Configure automated alerts for performance issues:

```python
# Performance alert rules
PERFORMANCE_ALERTS = {
    'high_latency': {
        'condition': 'avg_launch_time_ms > 15000',
        'severity': 'warning',
        'notification_channels': ['email', 'slack']
    },
    'high_failure_rate': {
        'condition': 'failure_rate_percent > 5',
        'severity': 'critical', 
        'notification_channels': ['email', 'slack', 'pagerduty']
    },
    'cost_spike': {
        'condition': 'hourly_cost_usd > 50',
        'severity': 'warning',
        'notification_channels': ['email']
    }
}
```

## Migration Planning

### 1. Plan a Migration

```bash
# Create a gradual migration plan
uv run python manage.py migrate_jobs create \
  "docker-to-cloudrun-migration" \
  docker cloudrun \
  --strategy=gradual \
  --batch-size=20 \
  --batch-interval=120 \
  --max-failure-rate=5.0 \
  --filter-status=pending \
  --description="Migrate pending jobs from Docker to Cloud Run for better scalability"
```

### 2. Validate Migration Plan

```bash
# Validate the migration plan
uv run python manage.py migrate_jobs validate <migration-plan-id>

# Expected output:
# ✅ Migration plan validation passed
# Source executor: docker (20 available hosts)
# Target executor: cloudrun (5 available hosts) 
# Jobs selected: 150
# Estimated duration: 25 minutes
# Estimated cost impact: +$2.50 per batch
```

### 3. Execute Migration

```bash
# Execute the migration with monitoring
uv run python manage.py migrate_jobs execute <migration-plan-id> --confirm

# Monitor migration progress
uv run python manage.py migrate_jobs monitor <migration-plan-id> --refresh-interval=10
```

### 4. Migration Rollback

```bash
# Rollback if needed (if rollback was enabled)
uv run python manage.py migrate_jobs rollback <migration-plan-id> --confirm

# Check rollback status
uv run python manage.py migrate_jobs show <migration-plan-id>
```

## Production Deployment

### 1. Docker Compose for Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.prod
    ports:
      - "80:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=False
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./secrets/gcp-key.json:/app/gcp-key.json:ro
      - static_volume:/app/staticfiles
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build:
      context: .
      dockerfile: Dockerfile.prod
    command: >
      sh -c "python manage.py process_container_jobs 
             --poll-interval=5 
             --max-jobs=50 
             --host-filter=all"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./secrets/gcp-key.json:/app/gcp-key.json:ro
    depends_on:
      - db
      - redis
    restart: unless-stopped
    deploy:
      replicas: 3

  migration-worker:
    build:
      context: .
      dockerfile: Dockerfile.prod
    command: python manage.py migrate_jobs monitor --all-plans --refresh-interval=30
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/staticfiles:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - web
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    restart: unless-stopped
    command: postgres -c 'max_connections=200'

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  static_volume:
  prometheus_data:
  grafana_data:
```

### 2. Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: container-manager-web
  namespace: container-manager
spec:
  replicas: 3
  selector:
    matchLabels:
      app: container-manager-web
  template:
    metadata:
      labels:
        app: container-manager-web
    spec:
      serviceAccountName: container-manager
      containers:
      - name: web
        image: your-registry/container-manager:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: "/app/gcp-key.json"
        volumeMounts:
        - name: gcp-service-account
          mountPath: "/app/gcp-key.json"
          subPath: "key.json"
          readOnly: true
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: gcp-service-account
        secret:
          secretName: gcp-service-account
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: container-manager-worker
  namespace: container-manager
spec:
  replicas: 5
  selector:
    matchLabels:
      app: container-manager-worker
  template:
    metadata:
      labels:
        app: container-manager-worker
    spec:
      serviceAccountName: container-manager
      containers:
      - name: worker
        image: your-registry/container-manager:latest
        command: 
        - python
        - manage.py 
        - process_container_jobs
        - --poll-interval=5
        - --max-jobs=20
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: "/app/gcp-key.json"
        volumeMounts:
        - name: gcp-service-account
          mountPath: "/app/gcp-key.json"
          subPath: "key.json"
          readOnly: true
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
      volumes:
      - name: gcp-service-account
        secret:
          secretName: gcp-service-account
```

### 3. Production Monitoring

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'container-manager'
    static_configs:
      - targets: ['web:8000']
    metrics_path: '/metrics/'
    scrape_interval: 30s

rule_files:
  - "container_manager.rules"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

## Troubleshooting

### Common Issues

#### 1. Docker Connection Problems

```bash
# Check Docker daemon status
sudo systemctl status docker

# Test Docker socket permissions
ls -la /var/run/docker.sock

# Test connection manually
docker ps

# Fix permission issues
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. Google Cloud Run Authentication Issues

```bash
# Verify service account
gcloud auth list

# Test service account permissions
gcloud run services list --project=YOUR_PROJECT_ID

# Check key file
cat /path/to/service-account-key.json | jq .

# Re-authenticate if needed
gcloud auth activate-service-account --key-file=/path/to/service-account-key.json
```

#### 3. Job Stuck in Pending Status

```bash
# Check worker process
ps aux | grep process_container_jobs

# Check executor availability
uv run python manage.py list_executors --show-capacity

# Check routing rules
uv run python manage.py test_routing template-name --debug

# Force job to specific executor
uv run python manage.py manage_container_job create template-name executor-name --force
```

#### 4. High Costs or Performance Issues

```bash
# Check cost breakdown
uv run python manage.py cost_analysis --last-24-hours --detailed

# Analyze performance metrics
uv run python manage.py performance_analysis --last-7-days

# Review routing decisions
uv run python manage.py routing_analysis --show-decisions --last-1000-jobs

# Get optimization recommendations
uv run python manage.py optimize_routing --dry-run
```

### Debug Commands

```bash
# Check system health
uv run python manage.py health_check --all-components

# Validate configuration
uv run python manage.py check --deploy

# Test all executor connections
uv run python manage.py test_all_connections

# Debug routing for specific job
uv run python manage.py debug_routing job-id --verbose

# Show performance metrics
uv run python manage.py show_metrics --last-24-hours

# Export configuration
uv run python manage.py export_config --format=yaml --output=config.yaml
```

### Support Resources

- 📖 **Documentation**: [Full documentation](../README.md)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/heysamtexas/django-docker-manager/issues)
- 💬 **Community**: [GitHub Discussions](https://github.com/heysamtexas/django-docker-manager/discussions)
- 📧 **Security Issues**: security@django-docker-manager.com

---

## Next Steps

1. **Configure additional cloud providers** as they become available
2. **Set up monitoring and alerting** for production environments
3. **Implement advanced routing strategies** based on your specific needs
4. **Create migration plans** for transitioning between executor types
5. **Optimize costs** using performance and cost analytics

For more advanced configuration options, see:
- [Advanced Configuration Guide](configuration.md)
- [Migration Strategies](migration-guide.md)
- [Performance Tuning](performance-tuning.md)
- [Security Best Practices](security.md)