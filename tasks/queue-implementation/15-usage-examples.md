# Task: Create Usage Examples and Patterns

## Objective
Create comprehensive usage examples, patterns, and best practices for queue management features.

## Success Criteria
- [ ] Common usage patterns documented
- [ ] Real-world examples provided
- [ ] Best practices guide created
- [ ] Integration examples with Django
- [ ] Deployment patterns shown
- [ ] Performance tuning guide included

## Implementation Details

### Usage Patterns Guide

```markdown
# Queue Management Usage Patterns

## Common Patterns

### 1. Admin-Driven Workflow Queue

Perfect for scenarios where admins create jobs through Django admin and a background process executes them.

```python
# In your Django admin or views
from container_manager.models import ContainerJob
from container_manager.queue import queue_manager

# Admin creates jobs
def create_analysis_job(request):
    if request.method == 'POST':
        # Get data from form
        document_path = request.POST['document_path']
        analysis_type = request.POST['analysis_type']
        
        # Create job
        job = ContainerJob.objects.create(
            name=f"analyze-{analysis_type}",
            command=f"python analyze.py --type={analysis_type} {document_path}",
            docker_image="analysis-engine:latest",
            priority=70 if analysis_type == 'urgent' else 50
        )
        
        # Queue for execution
        queue_manager.queue_job(job)
        
        messages.success(request, f"Analysis job {job.id} queued for execution")
        return redirect('admin:container_manager_containerjob_changelist')
```

**Background processor:**
```bash
# Start queue processor
python manage.py process_container_jobs --queue-mode --max-concurrent=3
```

### 2. Scheduled Batch Processing

Process large datasets during off-peak hours.

```python
# Schedule daily report generation
from django.utils import timezone
from datetime import timedelta

def schedule_daily_reports():
    """Schedule daily reports to run at 2 AM"""
    tomorrow_2am = timezone.now().replace(
        hour=2, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    
    report_types = ['sales', 'inventory', 'analytics', 'compliance']
    
    for report_type in report_types:
        job = ContainerJob.objects.create(
            name=f"daily-{report_type}-report",
            command=f"python generate_report.py --type={report_type} --date={tomorrow_2am.date()}",
            docker_image="report-generator:latest",
            priority=40,  # Lower priority for batch jobs
            max_retries=2  # Reports can be sensitive
        )
        
        queue_manager.queue_job(job, schedule_for=tomorrow_2am)
        print(f"Scheduled {report_type} report for {tomorrow_2am}")

# Run this from a management command or cron job
schedule_daily_reports()
```

### 3. Priority-Based Image Processing

Handle image processing requests with different priorities.

```python
# In your views or API endpoints
def process_image_upload(request):
    """Handle image upload with priority-based processing"""
    
    # Get user tier for priority assignment
    user_tier = request.user.profile.tier
    priority_map = {
        'premium': 90,
        'standard': 50, 
        'free': 20
    }
    
    uploaded_file = request.FILES['image']
    processing_type = request.POST.get('processing', 'standard')
    
    # Create processing job
    job = ContainerJob.objects.create(
        name=f"image-{processing_type}-{uploaded_file.name}",
        command=f"python process_image.py --input={uploaded_file.path} --type={processing_type}",
        docker_image="image-processor:latest",
        priority=priority_map.get(user_tier, 20),
        retry_strategy='aggressive' if user_tier == 'premium' else 'default'
    )
    
    # Queue immediately
    queue_manager.queue_job(job)
    
    return JsonResponse({
        'job_id': job.id,
        'status': 'queued',
        'priority': job.priority,
        'estimated_wait': estimate_wait_time(job.priority)
    })

def estimate_wait_time(priority):
    """Estimate wait time based on current queue and priority"""
    stats = queue_manager.get_queue_stats()
    
    # Higher priority jobs get processed faster
    if priority >= 80:
        return "1-2 minutes"
    elif priority >= 60:
        return "3-5 minutes"
    elif priority >= 40:
        return "5-10 minutes"
    else:
        return "10-30 minutes"
```

### 4. Resource-Aware Processing

Control resource usage with intelligent queuing.

```python
# Custom queue processor with resource awareness
from container_manager.queue import queue_manager
import psutil
import time

class ResourceAwareProcessor:
    def __init__(self, max_memory_percent=80, max_cpu_percent=70):
        self.max_memory_percent = max_memory_percent
        self.max_cpu_percent = max_cpu_percent
    
    def can_launch_more_jobs(self):
        """Check if system has resources to launch more jobs"""
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)
        
        return (memory_usage < self.max_memory_percent and 
                cpu_usage < self.max_cpu_percent)
    
    def process_with_resource_control(self):
        """Process queue with resource monitoring"""
        while True:
            try:
                if self.can_launch_more_jobs():
                    result = queue_manager.launch_next_batch(max_concurrent=5)
                    
                    if result['launched'] > 0:
                        print(f"Launched {result['launched']} jobs")
                    
                else:
                    print("System under load, waiting...")
                    time.sleep(30)  # Wait longer when resources are constrained
                    continue
                
                time.sleep(10)  # Normal polling interval
                
            except KeyboardInterrupt:
                print("Shutting down gracefully...")
                break

# Usage
processor = ResourceAwareProcessor()
processor.process_with_resource_control()
```

### 5. Multi-Stage Workflow Pipeline

Chain jobs together for complex workflows.

```python
# Multi-stage document processing pipeline
class DocumentPipeline:
    def __init__(self, document_path):
        self.document_path = document_path
        self.jobs = []
    
    def create_pipeline(self):
        """Create a multi-stage processing pipeline"""
        
        # Stage 1: Text extraction
        extract_job = ContainerJob.objects.create(
            name=f"extract-{self.document_path}",
            command=f"python extract_text.py {self.document_path}",
            docker_image="text-extractor:latest",
            priority=60
        )
        self.jobs.append(extract_job)
        
        # Stage 2: Language detection (depends on extraction)
        detect_job = ContainerJob.objects.create(
            name=f"detect-lang-{self.document_path}",
            command=f"python detect_language.py {self.document_path}.txt",
            docker_image="lang-detector:latest",
            priority=60
        )
        self.jobs.append(detect_job)
        
        # Stage 3: Content analysis (depends on both previous stages)
        analyze_job = ContainerJob.objects.create(
            name=f"analyze-{self.document_path}",
            command=f"python analyze_content.py {self.document_path}.txt",
            docker_image="content-analyzer:latest", 
            priority=60
        )
        self.jobs.append(analyze_job)
        
        return self.jobs
    
    def start_pipeline(self):
        """Start the pipeline by queuing the first job"""
        jobs = self.create_pipeline()
        
        # Queue first job immediately
        queue_manager.queue_job(jobs[0])
        
        # Schedule subsequent jobs with delays to ensure order
        for i, job in enumerate(jobs[1:], 1):
            # Each stage starts 5 minutes after the previous
            schedule_time = timezone.now() + timedelta(minutes=5 * i)
            queue_manager.queue_job(job, schedule_for=schedule_time)
        
        return jobs

# Usage
pipeline = DocumentPipeline("contracts/contract-2023-001.pdf")
jobs = pipeline.start_pipeline()

print(f"Started pipeline with {len(jobs)} stages")
for job in jobs:
    print(f"- {job.name}: {job.queue_status}")
```

## Best Practices Guide

### Queue Design Patterns

#### 1. Priority Assignment Strategy

```python
# Good: Systematic priority assignment
PRIORITY_LEVELS = {
    'critical': 90,     # System maintenance, security updates
    'high': 80,         # Premium user requests, urgent processing
    'normal': 50,       # Standard operations
    'low': 30,          # Batch processing, reports
    'background': 10    # Cleanup, archival tasks
}

def assign_priority(job_type, user_tier=None, urgency=None):
    """Systematic priority assignment"""
    base_priority = PRIORITY_LEVELS.get(job_type, 50)
    
    # Adjust for user tier
    if user_tier == 'premium':
        base_priority += 20
    elif user_tier == 'enterprise':
        base_priority += 30
    
    # Adjust for urgency
    if urgency == 'urgent':
        base_priority += 10
    
    return min(base_priority, 100)  # Cap at 100
```

#### 2. Error Handling Strategy

```python
# Good: Comprehensive error handling
from container_manager.retry import ErrorClassifier, RETRY_STRATEGIES

def setup_job_for_reliability(job, job_type):
    """Configure job for maximum reliability"""
    
    if job_type == 'user_facing':
        # User-facing jobs get aggressive retry
        job.retry_strategy = 'aggressive'
        job.max_retries = 5
        
    elif job_type == 'batch_processing':
        # Batch jobs can be more conservative
        job.retry_strategy = 'conservative' 
        job.max_retries = 2
        
    elif job_type == 'critical_system':
        # Critical jobs get custom strategy
        job.retry_strategy = 'custom_critical'
        job.max_retries = 7
        
        # Define custom strategy if not exists
        if 'custom_critical' not in RETRY_STRATEGIES:
            RETRY_STRATEGIES['custom_critical'] = RetryStrategy(
                max_attempts=7,
                base_delay=0.5,
                max_delay=60.0,
                backoff_factor=2.0
            )
    
    job.save()
```

#### 3. Queue Monitoring and Alerting

```python
# Queue health monitoring
import logging
from django.core.mail import send_mail

logger = logging.getLogger('queue_monitor')

class QueueHealthMonitor:
    def __init__(self):
        self.alert_thresholds = {
            'queue_depth': 100,
            'launch_failed': 10,
            'avg_wait_time': 300  # 5 minutes
        }
    
    def check_queue_health(self):
        """Monitor queue health and send alerts"""
        stats = queue_manager.get_queue_stats()
        alerts = []
        
        # Check queue depth
        if stats['queued'] > self.alert_thresholds['queue_depth']:
            alerts.append(f"Queue depth high: {stats['queued']} jobs waiting")
        
        # Check failed launches
        if stats['launch_failed'] > self.alert_thresholds['launch_failed']:
            alerts.append(f"High launch failure rate: {stats['launch_failed']} failed jobs")
        
        # Check for stuck running jobs
        stuck_jobs = ContainerJob.objects.filter(
            status='running',
            launched_at__lt=timezone.now() - timedelta(hours=2)
        )
        
        if stuck_jobs.exists():
            alerts.append(f"Possible stuck jobs: {stuck_jobs.count()} running > 2 hours")
        
        if alerts:
            self.send_alerts(alerts)
            
    def send_alerts(self, alerts):
        """Send queue health alerts"""
        message = "Queue Health Alerts:\n\n" + "\n".join(f"- {alert}" for alert in alerts)
        
        send_mail(
            subject="Queue Health Alert",
            message=message,
            from_email="system@yourapp.com",
            recipient_list=["devops@yourapp.com"]
        )
        
        logger.warning("Queue health alerts sent: %s", alerts)

# Run from management command or cron
monitor = QueueHealthMonitor()
monitor.check_queue_health()
```

## Integration Examples

### 1. Django REST API Integration

```python
# API views with queue integration
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class JobQueueAPIView(APIView):
    """API endpoint for job queue operations"""
    
    def post(self, request):
        """Create and queue a new job"""
        try:
            job_data = request.data
            
            job = ContainerJob.objects.create(
                name=job_data['name'],
                command=job_data['command'],
                docker_image=job_data.get('image', 'default:latest'),
                priority=job_data.get('priority', 50)
            )
            
            # Queue with optional scheduling
            schedule_for = job_data.get('schedule_for')
            if schedule_for:
                schedule_for = timezone.datetime.fromisoformat(schedule_for)
            
            queue_manager.queue_job(job, schedule_for=schedule_for)
            
            return Response({
                'job_id': job.id,
                'status': job.queue_status,
                'queued_at': job.queued_at,
                'scheduled_for': job.scheduled_for
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, job_id=None):
        """Get job status or queue statistics"""
        if job_id:
            try:
                job = ContainerJob.objects.get(id=job_id)
                return Response({
                    'job_id': job.id,
                    'name': job.name,
                    'status': job.status,
                    'queue_status': job.queue_status,
                    'priority': job.priority,
                    'queued_at': job.queued_at,
                    'launched_at': job.launched_at,
                    'completed_at': job.completed_at,
                    'retry_count': job.retry_count
                })
            except ContainerJob.DoesNotExist:
                return Response({
                    'error': 'Job not found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Return queue statistics
            stats = queue_manager.get_queue_stats()
            return Response(stats)
```

### 2. Celery Integration Pattern

```python
# Use queue system alongside Celery for container-specific tasks
from celery import shared_task
from container_manager.queue import queue_manager

@shared_task
def create_analysis_job(data_path, analysis_type):
    """Celery task that creates container jobs"""
    
    job = ContainerJob.objects.create(
        name=f"analysis-{analysis_type}",
        command=f"python analyze.py --data={data_path} --type={analysis_type}",
        docker_image="analytics:latest"
    )
    
    # Queue the container job
    queue_manager.queue_job(job)
    
    return job.id

@shared_task
def monitor_job_completion(job_id):
    """Monitor job until completion"""
    job = ContainerJob.objects.get(id=job_id)
    
    # Wait for completion
    timeout = 300  # 5 minutes
    start_time = time.time()
    
    while job.status not in ['completed', 'failed', 'cancelled']:
        if time.time() - start_time > timeout:
            break
            
        time.sleep(10)
        job.refresh_from_db()
    
    return {
        'job_id': job.id,
        'final_status': job.status,
        'exit_code': job.exit_code
    }
```

## Performance Tuning Guide

### Database Optimization

```python
# Optimize queue queries with proper indexing and query patterns

# Good: Use select_related for admin queries
def get_jobs_for_admin():
    return ContainerJob.objects.select_related().filter(
        queued_at__isnull=False
    ).order_by('-priority', 'queued_at')

# Good: Use database-level filtering
def get_high_priority_ready_jobs():
    return ContainerJob.objects.filter(
        queued_at__isnull=False,
        launched_at__isnull=True,
        priority__gte=70,
        retry_count__lt=models.F('max_retries')
    ).filter(
        models.Q(scheduled_for__isnull=True) |
        models.Q(scheduled_for__lte=timezone.now())
    )

# Database connection optimization
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'conn_max_age': 600,  # Connection pooling
        }
    }
}
```

### Deployment Patterns

#### Docker Compose Example

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
      - queue-processor
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/django_db
  
  queue-processor:
    build: .
    command: python manage.py process_container_jobs --queue-mode --max-concurrent=10
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/django_db
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # Access to Docker daemon
    restart: unless-stopped
  
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: django_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

#### Kubernetes Example

```yaml
# kubernetes/queue-processor-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: queue-processor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: queue-processor
  template:
    metadata:
      labels:
        app: queue-processor
    spec:
      containers:
      - name: queue-processor
        image: myapp:latest
        command: ["python", "manage.py", "process_container_jobs", "--queue-mode", "--max-concurrent=5"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        volumeMounts:
        - name: docker-sock
          mountPath: /var/run/docker.sock
      volumes:
      - name: docker-sock
        hostPath:
          path: /var/run/docker.sock
```
```

## Files to Create
- `docs/usage-patterns.md` - Usage patterns and examples
- `docs/best-practices.md` - Best practices guide
- `docs/integration-examples.md` - Integration examples
- `docs/deployment-patterns.md` - Deployment configurations
- `examples/` directory with working code examples

## Example Files Structure

```
examples/
├── admin_workflow/
│   ├── models.py           # Extended models
│   ├── admin.py           # Admin customizations
│   └── views.py           # Admin views
├── api_integration/
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # API views
│   └── urls.py            # URL patterns
├── batch_processing/
│   ├── management/
│   │   └── commands/
│   │       └── schedule_reports.py
│   └── processors.py     # Batch processors
└── deployment/
    ├── docker-compose.yml
    ├── kubernetes/
    │   ├── deployment.yaml
    │   └── service.yaml
    └── systemd/
        └── queue-processor.service
```

## Dependencies
- Depends on: `14-api-documentation.md` (API documentation)
- Requires: Complete queue implementation

## Testing Examples

```bash
# Validate all examples work
python manage.py test examples.tests

# Run example workflows
python manage.py shell < examples/batch_processing/demo.py
```

## Notes
- Examples should be production-ready
- Include error handling in all examples
- Show both simple and complex scenarios
- Cover common integration patterns
- Provide deployment guidance
- Include monitoring and alerting patterns