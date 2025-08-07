# Task: Enhanced Admin Interface with Queue Status Display

## Objective
Enhance the Django admin interface for ContainerJob to display queue status, provide visual indicators, and improve usability for queue management.

## Success Criteria
- [ ] Queue status column with color-coded indicators
- [ ] Enhanced list display with queue-specific fields
- [ ] Proper filtering options for queue states
- [ ] Search functionality includes queue-related fields
- [ ] Readonly fields for queue timestamps
- [ ] Custom admin methods for queue status

## Implementation Details

### Enhanced ContainerJob Admin

```python
# container_manager/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.utils.safestring import mark_safe
from container_manager.models import ContainerJob
from container_manager.queue import queue_manager
import logging

logger = logging.getLogger(__name__)

@admin.register(ContainerJob)
class ContainerJobAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'name', 
        'queue_status_display', 
        'execution_status_display',
        'priority_display',
        'created_at_short',
        'queued_at_short', 
        'launched_at_short',
        'retry_count',
        'actions_column'
    ]
    
    list_filter = [
        'status',
        'priority',
        QueueStatusFilter,  # Custom filter
        'created_at',
        'queued_at',
        'launched_at',
        'retry_count'
    ]
    
    search_fields = [
        'name', 
        'command', 
        'docker_image',
        'id'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'launched_at',
        'queued_at',
        'last_error_at',
        'queue_status_detail',
        'execution_logs_link'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'command', 'docker_image', 'priority')
        }),
        ('Queue Information', {
            'fields': (
                'queue_status_detail',
                'queued_at',
                'scheduled_for', 
                'launched_at',
                'retry_count',
                'max_retries',
                'retry_strategy',
                'last_error',
                'last_error_at'
            ),
            'classes': ('collapse',)
        }),
        ('Execution Status', {
            'fields': (
                'status',
                'exit_code',
                'execution_logs_link',
                'started_at',
                'completed_at',
                'failed_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def queue_status_display(self, obj):
        """Display queue status with color coding"""
        status = obj.queue_status
        
        # Define colors and icons for different statuses
        status_config = {
            'not_queued': {'color': '#6c757d', 'icon': '○', 'label': 'Not Queued'},
            'queued': {'color': '#007bff', 'icon': '⏳', 'label': 'Queued'},
            'scheduled': {'color': '#fd7e14', 'icon': '📅', 'label': 'Scheduled'},
            'launched': {'color': '#28a745', 'icon': '🚀', 'label': 'Launched'},
            'launch_failed': {'color': '#dc3545', 'icon': '❌', 'label': 'Launch Failed'}
        }
        
        config = status_config.get(status, {'color': '#6c757d', 'icon': '?', 'label': status.title()})
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            config['color'],
            config['icon'],
            config['label']
        )
    queue_status_display.short_description = 'Queue Status'
    queue_status_display.admin_order_field = 'queued_at'
    
    def execution_status_display(self, obj):
        """Display container execution status"""
        status = obj.status or 'not_started'
        
        status_config = {
            'pending': {'color': '#6c757d', 'icon': '⏸'},
            'running': {'color': '#17a2b8', 'icon': '▶️'},
            'completed': {'color': '#28a745', 'icon': '✅'},
            'failed': {'color': '#dc3545', 'icon': '💥'},
            'cancelled': {'color': '#6f42c1', 'icon': '⏹'},
            'not_started': {'color': '#6c757d', 'icon': '○'}
        }
        
        config = status_config.get(status, {'color': '#6c757d', 'icon': '?'})
        
        return format_html(
            '<span style="color: {};">{} {}</span>',
            config['color'],
            config['icon'],
            status.replace('_', ' ').title()
        )
    execution_status_display.short_description = 'Execution Status'
    execution_status_display.admin_order_field = 'status'
    
    def priority_display(self, obj):
        """Display priority with visual indicator"""
        priority = obj.priority
        
        if priority >= 80:
            color = '#dc3545'  # High priority - red
            indicator = '🔥'
        elif priority >= 60:
            color = '#fd7e14'  # Medium-high priority - orange
            indicator = '⬆️'
        elif priority >= 40:
            color = '#28a745'  # Normal priority - green
            indicator = '➡️'
        else:
            color = '#6c757d'  # Low priority - gray
            indicator = '⬇️'
            
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            indicator,
            priority
        )
    priority_display.short_description = 'Priority'
    priority_display.admin_order_field = 'priority'
    
    def created_at_short(self, obj):
        """Short format for created timestamp"""
        if obj.created_at:
            if timezone.now().date() == obj.created_at.date():
                return obj.created_at.strftime('%H:%M:%S')
            else:
                return obj.created_at.strftime('%m/%d %H:%M')
        return '-'
    created_at_short.short_description = 'Created'
    created_at_short.admin_order_field = 'created_at'
    
    def queued_at_short(self, obj):
        """Short format for queued timestamp"""
        if obj.queued_at:
            if timezone.now().date() == obj.queued_at.date():
                return obj.queued_at.strftime('%H:%M:%S')
            else:
                return obj.queued_at.strftime('%m/%d %H:%M')
        return '-'
    queued_at_short.short_description = 'Queued'
    queued_at_short.admin_order_field = 'queued_at'
    
    def launched_at_short(self, obj):
        """Short format for launched timestamp"""
        if obj.launched_at:
            if timezone.now().date() == obj.launched_at.date():
                return obj.launched_at.strftime('%H:%M:%S')
            else:
                return obj.launched_at.strftime('%m/%d %H:%M')
        return '-'
    launched_at_short.short_description = 'Launched'
    launched_at_short.admin_order_field = 'launched_at'
    
    def queue_status_detail(self, obj):
        """Detailed queue status information"""
        if not obj.queued_at:
            return format_html('<em style="color: #6c757d;">Job is not queued</em>')
            
        details = []
        
        # Basic queue info
        details.append(f"<strong>Status:</strong> {obj.queue_status.replace('_', ' ').title()}")
        details.append(f"<strong>Priority:</strong> {obj.priority}")
        
        # Timing information
        if obj.queued_at:
            details.append(f"<strong>Queued:</strong> {obj.queued_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
        if obj.scheduled_for:
            if obj.scheduled_for > timezone.now():
                details.append(f"<strong>Scheduled for:</strong> {obj.scheduled_for.strftime('%Y-%m-%d %H:%M:%S')} (in {obj.scheduled_for - timezone.now()})")
            else:
                details.append(f"<strong>Was scheduled for:</strong> {obj.scheduled_for.strftime('%Y-%m-%d %H:%M:%S')} (overdue)")
                
        if obj.launched_at:
            details.append(f"<strong>Launched:</strong> {obj.launched_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
        # Retry information
        if obj.retry_count > 0:
            details.append(f"<strong>Retry attempts:</strong> {obj.retry_count}/{obj.max_retries}")
            
        if obj.last_error and obj.last_error_at:
            details.append(f"<strong>Last error:</strong> {obj.last_error_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
        return format_html('<br>'.join(details))
    queue_status_detail.short_description = 'Queue Details'
    
    def execution_logs_link(self, obj):
        """Link to execution logs if available"""
        if obj.logs:
            return format_html(
                '<a href="#" onclick="showLogs({}); return false;" style="color: #007bff;">📋 View Logs</a>',
                obj.id
            )
        return format_html('<em style="color: #6c757d;">No logs available</em>')
    execution_logs_link.short_description = 'Logs'
    
    def actions_column(self, obj):
        """Action buttons column"""
        actions = []
        
        # Queue management actions
        if obj.is_queued:
            actions.append(
                '<a href="#" onclick="dequeueJob({}); return false;" '
                'style="color: #dc3545; text-decoration: none;" title="Remove from queue">🗑️</a>'
                .format(obj.id)
            )
        elif obj.status in ['failed', 'cancelled'] and not obj.is_queued:
            actions.append(
                '<a href="#" onclick="requeueJob({}); return false;" '
                'style="color: #28a745; text-decoration: none;" title="Add to queue">➕</a>'
                .format(obj.id)
            )
            
        # Status actions
        if obj.status == 'running':
            actions.append(
                '<a href="#" onclick="cancelJob({}); return false;" '
                'style="color: #fd7e14; text-decoration: none;" title="Cancel job">⏹</a>'
                .format(obj.id)
            )
            
        return format_html(' '.join(actions)) if actions else '-'
    actions_column.short_description = 'Actions'
    
    def get_queryset(self, request):
        """Optimize queryset for admin list view"""
        return super().get_queryset(request).select_related().prefetch_related()
    
    class Media:
        js = ('admin/js/queue_admin.js',)  # Custom JavaScript for actions
        css = {
            'all': ('admin/css/queue_admin.css',)  # Custom CSS
        }

class QueueStatusFilter(admin.SimpleListFilter):
    """Custom filter for queue status"""
    title = 'Queue Status'
    parameter_name = 'queue_status'
    
    def lookups(self, request, model_admin):
        return [
            ('not_queued', 'Not Queued'),
            ('queued', 'Queued (Ready)'),
            ('scheduled', 'Scheduled (Future)'),
            ('launched', 'Launched'),
            ('launch_failed', 'Launch Failed'),
        ]
        
    def queryset(self, request, queryset):
        from django.db.models import Q, F
        
        if self.value() == 'not_queued':
            return queryset.filter(queued_at__isnull=True)
        elif self.value() == 'queued':
            return queryset.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__lt=F('max_retries')
            ).filter(
                Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now())
            )
        elif self.value() == 'scheduled':
            return queryset.filter(
                scheduled_for__isnull=False,
                scheduled_for__gt=timezone.now(),
                launched_at__isnull=True
            )
        elif self.value() == 'launched':
            return queryset.filter(launched_at__isnull=False)
        elif self.value() == 'launch_failed':
            return queryset.filter(
                queued_at__isnull=False,
                launched_at__isnull=True,
                retry_count__gte=F('max_retries')
            )
```

### Custom JavaScript for Admin Actions

```javascript
// static/admin/js/queue_admin.js

function showLogs(jobId) {
    // Show job logs in a modal or popup
    const url = `/admin/container_manager/containerjob/${jobId}/logs/`;
    window.open(url, '_blank', 'width=800,height=600,scrollbars=yes');
}

function dequeueJob(jobId) {
    if (confirm('Remove this job from the queue?')) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/admin/container_manager/containerjob/${jobId}/dequeue/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(`Error: ${data.error}`);
            }
        })
        .catch(error => {
            alert(`Error: ${error}`);
        });
    }
}

function requeueJob(jobId) {
    if (confirm('Add this job to the queue?')) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/admin/container_manager/containerjob/${jobId}/requeue/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(`Error: ${data.error}`);
            }
        })
        .catch(error => {
            alert(`Error: ${error}`);
        });
    }
}

function cancelJob(jobId) {
    if (confirm('Cancel this running job?')) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/admin/container_manager/containerjob/${jobId}/cancel/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(`Error: ${data.error}`);
            }
        })
        .catch(error => {
            alert(`Error: ${error}`);
        });
    }
}
```

### Custom CSS for Queue Admin

```css
/* static/admin/css/queue_admin.css */

/* Queue status indicators */
.queue-status {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
}

.queue-status.queued {
    background-color: #e3f2fd;
    color: #0277bd;
}

.queue-status.scheduled {
    background-color: #fff3e0;
    color: #ef6c00;
}

.queue-status.launched {
    background-color: #e8f5e8;
    color: #2e7d32;
}

.queue-status.launch-failed {
    background-color: #ffebee;
    color: #c62828;
}

/* Priority indicators */
.priority-high {
    color: #d32f2f !important;
    font-weight: bold;
}

.priority-normal {
    color: #388e3c !important;
}

.priority-low {
    color: #616161 !important;
}

/* Action buttons */
.action-buttons a {
    margin-right: 8px;
    text-decoration: none;
    font-size: 16px;
}

.action-buttons a:hover {
    opacity: 0.7;
}

/* Queue details section */
.queue-details {
    background-color: #f8f9fa;
    padding: 10px;
    border-radius: 4px;
    margin: 10px 0;
    border-left: 4px solid #007bff;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .queue-status {
        display: block;
        margin-bottom: 4px;
    }
    
    .action-buttons a {
        display: block;
        margin-bottom: 4px;
    }
}
```

## Files to Create/Modify
- `container_manager/admin.py` - Enhanced admin interface
- `static/admin/js/queue_admin.js` - Custom JavaScript
- `static/admin/css/queue_admin.css` - Custom CSS

## Testing Requirements
- [ ] Test admin interface displays queue status correctly
- [ ] Test filtering by queue status works
- [ ] Test search includes queue-related fields
- [ ] Test color coding is applied correctly
- [ ] Test responsive design on mobile
- [ ] Test readonly fields are properly protected

## Dependencies
- Depends on: `01-queue-model-fields.md` (queue fields and properties)
- Depends on: `02-state-machine-validation.md` (queue status property)

## Notes
- Visual indicators make queue status immediately apparent
- Custom filters help administrators find specific job states
- Readonly fields prevent accidental modification of queue state
- Responsive design works on mobile devices
- JavaScript actions provide quick queue management
- Custom CSS maintains consistent Django admin styling