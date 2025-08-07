# Task: Admin Actions for Queue Management

## Objective
Implement Django admin actions for bulk queue operations and individual job management with proper error handling and user feedback.

## Success Criteria
- [ ] Bulk admin actions for queue operations
- [ ] Individual job action endpoints
- [ ] Proper error handling and user feedback
- [ ] Permission checking for queue operations
- [ ] Comprehensive logging of admin actions
- [ ] AJAX endpoints for seamless UX

## Implementation Details

### Admin Actions for Bulk Operations

```python
# container_manager/admin.py (additions to existing ContainerJobAdmin)

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied

class ContainerJobAdmin(admin.ModelAdmin):
    # ... existing configuration ...
    
    actions = [
        'queue_selected_jobs',
        'dequeue_selected_jobs', 
        'cancel_selected_jobs',
        'retry_failed_jobs',
        'set_high_priority',
        'set_normal_priority',
        'set_low_priority'
    ]
    
    def queue_selected_jobs(self, request, queryset):
        """Queue selected jobs for execution"""
        if not request.user.has_perm('container_manager.change_containerjob'):
            raise PermissionDenied
            
        queued_count = 0
        error_count = 0
        errors = []
        
        for job in queryset:
            try:
                if job.is_queued:
                    continue  # Skip already queued jobs
                    
                if job.status in ['completed', 'cancelled']:
                    errors.append(f"Job {job.id} ({job.name}): Cannot queue {job.status} job")
                    error_count += 1
                    continue
                    
                queue_manager.queue_job(job)
                queued_count += 1
                
                logger.info(f"Admin user {request.user.username} queued job {job.id}")
                
            except Exception as e:
                errors.append(f"Job {job.id} ({job.name}): {str(e)}")
                error_count += 1
                logger.error(f"Error queuing job {job.id}: {e}")
        
        # Provide user feedback
        if queued_count > 0:
            messages.success(request, f'Successfully queued {queued_count} job(s)')
            
        if error_count > 0:
            messages.warning(request, f'{error_count} job(s) could not be queued')
            for error in errors[:5]:  # Show max 5 errors
                messages.error(request, error)
            if len(errors) > 5:
                messages.error(request, f'... and {len(errors) - 5} more errors')
                
    queue_selected_jobs.short_description = '📤 Queue selected jobs for execution'
    
    def dequeue_selected_jobs(self, request, queryset):
        """Remove selected jobs from queue"""
        if not request.user.has_perm('container_manager.change_containerjob'):
            raise PermissionDenied
            
        dequeued_count = 0
        error_count = 0
        errors = []
        
        for job in queryset.filter(queued_at__isnull=False, launched_at__isnull=True):
            try:
                queue_manager.dequeue_job(job)
                dequeued_count += 1
                
                logger.info(f"Admin user {request.user.username} dequeued job {job.id}")
                
            except Exception as e:
                errors.append(f"Job {job.id} ({job.name}): {str(e)}")
                error_count += 1
                logger.error(f"Error dequeuing job {job.id}: {e}")
        
        if dequeued_count > 0:
            messages.success(request, f'Successfully removed {dequeued_count} job(s) from queue')
        else:
            messages.info(request, 'No queued jobs found in selection')
            
        if error_count > 0:
            messages.warning(request, f'{error_count} job(s) could not be dequeued')
            for error in errors[:3]:
                messages.error(request, error)
                
    dequeue_selected_jobs.short_description = '📥 Remove selected jobs from queue'
    
    def cancel_selected_jobs(self, request, queryset):
        """Cancel selected running jobs"""
        if not request.user.has_perm('container_manager.change_containerjob'):
            raise PermissionDenied
            
        cancelled_count = 0
        error_count = 0
        
        for job in queryset.filter(status='running'):
            try:
                from container_manager.services import job_service
                result = job_service.cancel_job(job)
                
                if result.success:
                    cancelled_count += 1
                    logger.info(f"Admin user {request.user.username} cancelled job {job.id}")
                else:
                    error_count += 1
                    messages.error(request, f"Job {job.id}: {result.error}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error cancelling job {job.id}: {e}")
                messages.error(request, f"Job {job.id}: {str(e)}")
        
        if cancelled_count > 0:
            messages.success(request, f'Successfully cancelled {cancelled_count} job(s)')
        else:
            messages.info(request, 'No running jobs found in selection')
            
        if error_count > 0:
            messages.warning(request, f'{error_count} job(s) could not be cancelled')
            
    cancel_selected_jobs.short_description = '⏹ Cancel selected running jobs'
    
    def retry_failed_jobs(self, request, queryset):
        """Retry selected failed jobs"""
        if not request.user.has_perm('container_manager.change_containerjob'):
            raise PermissionDenied
            
        retried_count = 0
        
        for job in queryset.filter(status__in=['failed', 'retrying']):
            try:
                queue_manager.retry_failed_job(job, reset_count=True)
                retried_count += 1
                
                logger.info(f"Admin user {request.user.username} retried job {job.id}")
                
            except Exception as e:
                logger.error(f"Error retrying job {job.id}: {e}")
                messages.error(request, f"Job {job.id}: {str(e)}")
        
        if retried_count > 0:
            messages.success(request, f'Successfully queued {retried_count} job(s) for retry')
        else:
            messages.info(request, 'No failed jobs found in selection')
            
    retry_failed_jobs.short_description = '🔄 Retry selected failed jobs'
    
    def set_high_priority(self, request, queryset):
        """Set selected jobs to high priority"""
        updated = queryset.update(priority=80)
        messages.success(request, f'Set {updated} job(s) to high priority')
        logger.info(f"Admin user {request.user.username} set {updated} jobs to high priority")
        
    set_high_priority.short_description = '🔥 Set high priority (80)'
    
    def set_normal_priority(self, request, queryset):
        """Set selected jobs to normal priority"""
        updated = queryset.update(priority=50)
        messages.success(request, f'Set {updated} job(s) to normal priority')
        logger.info(f"Admin user {request.user.username} set {updated} jobs to normal priority")
        
    set_normal_priority.short_description = '➡️ Set normal priority (50)'
    
    def set_low_priority(self, request, queryset):
        """Set selected jobs to low priority"""
        updated = queryset.update(priority=20)
        messages.success(request, f'Set {updated} job(s) to low priority')
        logger.info(f"Admin user {request.user.username} set {updated} jobs to low priority")
        
    set_low_priority.short_description = '⬇️ Set low priority (20)'
    
    def get_urls(self):
        """Add custom URLs for AJAX actions"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:job_id>/dequeue/',
                self.admin_site.admin_view(self.dequeue_job_view),
                name='containerjob-dequeue'
            ),
            path(
                '<int:job_id>/requeue/',
                self.admin_site.admin_view(self.requeue_job_view),
                name='containerjob-requeue'
            ),
            path(
                '<int:job_id>/cancel/',
                self.admin_site.admin_view(self.cancel_job_view),
                name='containerjob-cancel'
            ),
            path(
                '<int:job_id>/logs/',
                self.admin_site.admin_view(self.job_logs_view),
                name='containerjob-logs'
            ),
            path(
                'queue-stats/',
                self.admin_site.admin_view(self.queue_stats_view),
                name='containerjob-queue-stats'
            ),
        ]
        return custom_urls + urls
    
    @method_decorator(require_POST)
    @method_decorator(csrf_protect)
    def dequeue_job_view(self, request, job_id):
        """AJAX endpoint to dequeue a single job"""
        try:
            if not request.user.has_perm('container_manager.change_containerjob'):
                return JsonResponse({'success': False, 'error': 'Permission denied'})
                
            job = get_object_or_404(ContainerJob, id=job_id)
            
            if not job.is_queued:
                return JsonResponse({'success': False, 'error': 'Job is not queued'})
                
            queue_manager.dequeue_job(job)
            
            logger.info(f"Admin user {request.user.username} dequeued job {job.id} via AJAX")
            
            return JsonResponse({
                'success': True,
                'message': f'Job {job.id} removed from queue'
            })
            
        except Exception as e:
            logger.error(f"Error dequeuing job {job_id}: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    @method_decorator(require_POST)
    @method_decorator(csrf_protect)
    def requeue_job_view(self, request, job_id):
        """AJAX endpoint to requeue a single job"""
        try:
            if not request.user.has_perm('container_manager.change_containerjob'):
                return JsonResponse({'success': False, 'error': 'Permission denied'})
                
            job = get_object_or_404(ContainerJob, id=job_id)
            
            if job.is_queued:
                return JsonResponse({'success': False, 'error': 'Job is already queued'})
                
            if job.status in ['completed', 'cancelled']:
                return JsonResponse({'success': False, 'error': f'Cannot queue {job.status} job'})
                
            queue_manager.queue_job(job)
            
            logger.info(f"Admin user {request.user.username} requeued job {job.id} via AJAX")
            
            return JsonResponse({
                'success': True,
                'message': f'Job {job.id} added to queue'
            })
            
        except Exception as e:
            logger.error(f"Error requeuing job {job_id}: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    @method_decorator(require_POST)
    @method_decorator(csrf_protect)
    def cancel_job_view(self, request, job_id):
        """AJAX endpoint to cancel a single job"""
        try:
            if not request.user.has_perm('container_manager.change_containerjob'):
                return JsonResponse({'success': False, 'error': 'Permission denied'})
                
            job = get_object_or_404(ContainerJob, id=job_id)
            
            if job.status != 'running':
                return JsonResponse({'success': False, 'error': 'Job is not running'})
                
            from container_manager.services import job_service
            result = job_service.cancel_job(job)
            
            if result.success:
                logger.info(f"Admin user {request.user.username} cancelled job {job.id} via AJAX")
                return JsonResponse({
                    'success': True,
                    'message': f'Job {job.id} cancelled'
                })
            else:
                return JsonResponse({'success': False, 'error': result.error})
                
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    def job_logs_view(self, request, job_id):
        """View job execution logs"""
        job = get_object_or_404(ContainerJob, id=job_id)
        
        if not request.user.has_perm('container_manager.view_containerjob'):
            raise PermissionDenied
            
        context = {
            'job': job,
            'logs': job.logs or 'No logs available',
            'title': f'Job {job.id} Logs'
        }
        
        return render(request, 'admin/container_manager/job_logs.html', context)
    
    def queue_stats_view(self, request):
        """View queue statistics"""
        if not request.user.has_perm('container_manager.view_containerjob'):
            raise PermissionDenied
            
        try:
            stats = queue_manager.get_worker_metrics()
            
            # Add additional statistics
            from container_manager.models import ContainerJob
            
            stats.update({
                'total_jobs': ContainerJob.objects.count(),
                'completed_today': ContainerJob.objects.filter(
                    status='completed',
                    completed_at__date=timezone.now().date()
                ).count(),
                'failed_today': ContainerJob.objects.filter(
                    status='failed',
                    failed_at__date=timezone.now().date()
                ).count(),
                'high_priority_queued': ContainerJob.objects.filter(
                    queued_at__isnull=False,
                    launched_at__isnull=True,
                    priority__gte=70
                ).count()
            })
            
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse(stats)
                
            context = {
                'stats': stats,
                'title': 'Queue Statistics'
            }
            
            return render(request, 'admin/container_manager/queue_stats.html', context)
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'error': str(e)}, status=500)
            else:
                messages.error(request, f'Error loading queue statistics: {e}')
                return HttpResponseRedirect(reverse('admin:container_manager_containerjob_changelist'))
```

### Templates for Custom Views

```html
<!-- templates/admin/container_manager/job_logs.html -->
{% extends "admin/base_site.html" %}
{% load i18n %}

{% block title %}{{ title }} | {{ site_title|default:_('Django site admin') }}{% endblock %}

{% block breadcrumbs %}
<div class="breadcrumbs">
    <a href="{% url 'admin:index' %}">{% trans 'Home' %}</a>
    &rsaquo; <a href="{% url 'admin:container_manager_containerjob_changelist' %}">Container Jobs</a>
    &rsaquo; <a href="{% url 'admin:container_manager_containerjob_change' job.id %}">Job {{ job.id }}</a>
    &rsaquo; Logs
</div>
{% endblock %}

{% block content %}
<h1>{{ title }}</h1>

<div class="job-info">
    <h2>Job Information</h2>
    <p><strong>ID:</strong> {{ job.id }}</p>
    <p><strong>Name:</strong> {{ job.name }}</p>
    <p><strong>Status:</strong> {{ job.status }}</p>
    <p><strong>Command:</strong> <code>{{ job.command }}</code></p>
    {% if job.launched_at %}
    <p><strong>Launched:</strong> {{ job.launched_at }}</p>
    {% endif %}
    {% if job.completed_at %}
    <p><strong>Completed:</strong> {{ job.completed_at }}</p>
    {% endif %}
</div>

<div class="job-logs">
    <h2>Execution Logs</h2>
    <pre style="background: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; border-radius: 4px; max-height: 500px; overflow-y: auto; font-family: 'Courier New', monospace;">{{ logs }}</pre>
</div>

<div class="submit-row">
    <a href="{% url 'admin:container_manager_containerjob_change' job.id %}" class="default">Back to Job</a>
    <button onclick="window.print()" class="default">Print Logs</button>
</div>
{% endblock %}
```

```html
<!-- templates/admin/container_manager/queue_stats.html -->
{% extends "admin/base_site.html" %}
{% load i18n %}

{% block title %}{{ title }} | {{ site_title|default:_('Django site admin') }}{% endblock %}

{% block breadcrumbs %}
<div class="breadcrumbs">
    <a href="{% url 'admin:index' %}">{% trans 'Home' %}</a>
    &rsaquo; <a href="{% url 'admin:container_manager_containerjob_changelist' %}">Container Jobs</a>
    &rsaquo; Queue Statistics
</div>
{% endblock %}

{% block content %}
<h1>{{ title }}</h1>

<div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0;">
    
    <div class="stat-card" style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007bff;">
        <h3>Queue Status</h3>
        <p><strong>Ready to Launch:</strong> {{ stats.ready_now }}</p>
        <p><strong>Scheduled:</strong> {{ stats.scheduled_future }}</p>
        <p><strong>High Priority:</strong> {{ stats.high_priority_queued }}</p>
        <p><strong>Launch Failed:</strong> {{ stats.launch_failed }}</p>
    </div>
    
    <div class="stat-card" style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #28a745;">
        <h3>Execution Status</h3>
        <p><strong>Currently Running:</strong> {{ stats.running }}</p>
        <p><strong>Completed Today:</strong> {{ stats.completed_today }}</p>
        <p><strong>Failed Today:</strong> {{ stats.failed_today }}</p>
    </div>
    
    <div class="stat-card" style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #17a2b8;">
        <h3>Total Metrics</h3>
        <p><strong>Total Jobs:</strong> {{ stats.total_jobs }}</p>
        <p><strong>Queue Depth:</strong> {{ stats.queue_depth }}</p>
    </div>
    
</div>

<div class="submit-row">
    <a href="{% url 'admin:container_manager_containerjob_changelist' %}" class="default">Back to Jobs</a>
    <button onclick="location.reload()" class="default">Refresh Stats</button>
</div>

<script>
// Auto-refresh every 30 seconds
setTimeout(() => {
    location.reload();
}, 30000);
</script>
{% endblock %}
```

## Files to Create/Modify
- `container_manager/admin.py` - Add bulk actions and AJAX endpoints
- `templates/admin/container_manager/job_logs.html` - Job logs template
- `templates/admin/container_manager/queue_stats.html` - Queue statistics template

## Testing Requirements
- [ ] Test bulk queue operations work correctly
- [ ] Test individual AJAX actions respond properly
- [ ] Test permission checking prevents unauthorized access
- [ ] Test error handling provides meaningful feedback
- [ ] Test logging captures admin actions
- [ ] Test templates render correctly

## Dependencies
- Depends on: `09-admin-queue-display.md` (enhanced admin interface)
- Depends on: `04-queue-manager-basic.md` (queue_manager methods)

## Notes
- Bulk actions provide efficient queue management
- AJAX endpoints enable seamless user experience
- Proper permission checking ensures security
- Comprehensive logging provides audit trail
- Error handling prevents admin interface corruption
- Custom templates provide detailed information views