# Web Interface Requirements

## Overview

Simple, functional web interface for demonstrating and managing demo workflows. Focus on usability and clear demonstration of container manager capabilities rather than sophisticated UI/UX design.

## Interface Goals

### Primary Objectives
- **Workflow Submission** - Easy forms to start demo workflows
- **Status Monitoring** - Real-time view of workflow execution
- **Results Display** - Clear presentation of workflow outputs  
- **Admin Integration** - Leverage Django admin for settings management

### Design Principles
- **Functional over flashy** - Clear, working interface
- **Bootstrap simplicity** - Clean, responsive design
- **Minimal JavaScript** - Server-side rendering with basic interactivity
- **Admin integration** - Use Django admin for complex configuration

## Page Structure

### 1. Dashboard/Home Page (`/`)

**Purpose:** Landing page with overview and quick access to workflows

**Layout:**
```
┌─────────────────────────────────────────┐
│ Django Container Manager Demo           │
│ Navigation: Home | Workflows | Admin    │
├─────────────────────────────────────────┤
│ Welcome & Project Description           │
├─────────────────────────────────────────┤
│ Quick Start Workflow Cards             │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│ │ Web     │ │ Text    │ │ Document│    │
│ │ Crawler │ │ Rewriter│ │ Analyzer│    │
│ │ [Start] │ │ [Start] │ │ [Start] │    │
│ └─────────┘ └─────────┘ └─────────┘    │
├─────────────────────────────────────────┤
│ Recent Workflow Executions (last 5)    │
│ - Execution | Type | Status | Started  │
├─────────────────────────────────────────┤
│ System Status                           │
│ - Container Hosts Active: 2/3          │
│ - Jobs Running: 1                       │
│ - Jobs Completed Today: 12              │
└─────────────────────────────────────────┘
```

**Components:**
- Hero section explaining the demo purpose
- Three workflow cards with descriptions and "Start" buttons
- Recent executions table with basic status info
- System status widget showing container manager health

### 2. Workflow Listing Page (`/workflows/`)

**Purpose:** List all workflow executions with filtering and search

**Features:**
- **Filter by type** - Web crawler, text rewriter, document analyzer
- **Filter by status** - Pending, running, completed, failed
- **Search by name** - Basic text search
- **Pagination** - Standard Django pagination
- **Quick actions** - View details, cancel (if running)

**Table Columns:**
```
| ID (short) | Type | Status | Name/Description | Started | Duration | Actions |
|------------|------|--------|------------------|---------|----------|---------|
| abc123...  | Crawler | Completed | example.com | 2h ago | 00:45 | [View] |
| def456...  | Rewriter | Running | Shakespeare rewrite | 5m ago | - | [View] [Cancel] |
```

### 3. Workflow Detail Page (`/workflows/<id>/`)

**Purpose:** Detailed view of individual workflow execution

**Layout:**
```
┌─────────────────────────────────────────┐
│ Workflow Execution Details             │
│ Type: Web Page Crawler                 │
│ Status: [Completed] ✓                  │
├─────────────────────────────────────────┤
│ Execution Info                          │
│ - Created: 2024-01-15 10:30:00         │
│ - Started: 2024-01-15 10:30:15         │
│ - Completed: 2024-01-15 10:31:00       │
│ - Duration: 00:00:45                   │
├─────────────────────────────────────────┤
│ Input Parameters                        │
│ - URL: https://example.com              │
│ - Follow Links: No                      │
├─────────────────────────────────────────┤
│ Results                                 │
│ - Title: Example Domain                 │
│ - Word Count: 156                       │
│ - Links Found: 3                        │
│ [View Full Content] [Download JSON]     │
├─────────────────────────────────────────┤
│ Container Job Info                      │
│ - Job ID: job-abc123                    │
│ - Executor Host: docker-local           │
│ - Container ID: container-def456        │
│ [View Container Logs]                   │
└─────────────────────────────────────────┘
```

### 4. Workflow Creation Forms

#### Web Crawler Form (`/workflows/crawler/create/`)
```html
<form method="post">
    <div class="form-group">
        <label for="url">URL to Crawl *</label>
        <input type="url" name="url" required class="form-control" 
               placeholder="https://example.com">
    </div>
    
    <div class="form-check">
        <input type="checkbox" name="follow_links" class="form-check-input">
        <label class="form-check-label">Follow internal links</label>
    </div>
    
    <div class="form-group">
        <label for="max_depth">Maximum Depth</label>
        <input type="number" name="max_depth" value="1" min="1" max="3" 
               class="form-control">
    </div>
    
    <button type="submit" class="btn btn-primary">Start Crawling</button>
</form>
```

#### Text Rewriter Form (`/workflows/rewriter/create/`)
```html
<form method="post">
    <div class="form-group">
        <label for="text">Text to Rewrite *</label>
        <textarea name="text" required class="form-control" rows="5" 
                  placeholder="Enter text to rewrite in historical style..."></textarea>
    </div>
    
    <div class="form-group">
        <label for="figure">Historical Figure *</label>
        <select name="figure" required class="form-control">
            <option value="shakespeare">William Shakespeare</option>
            <option value="churchill">Winston Churchill</option>
            <option value="lincoln">Abraham Lincoln</option>
            <option value="einstein">Albert Einstein</option>
            <option value="twain">Mark Twain</option>
            <option value="wilde">Oscar Wilde</option>
            <option value="hemingway">Ernest Hemingway</option>
            <option value="roosevelt">Theodore Roosevelt</option>
        </select>
    </div>
    
    <button type="submit" class="btn btn-primary">Rewrite Text</button>
</form>
```

#### Document Analyzer Form (`/workflows/analyzer/create/`)
```html
<form method="post" enctype="multipart/form-data">
    <div class="form-group">
        <label for="document">Document File *</label>
        <input type="file" name="document" required class="form-control-file"
               accept=".pdf,.txt,.md">
        <small class="form-text text-muted">
            Supported formats: PDF, TXT, MD (max 10MB)
        </small>
    </div>
    
    <div class="form-group">
        <label for="analysis_type">Analysis Type</label>
        <div class="form-check">
            <input type="checkbox" name="sentiment" checked class="form-check-input">
            <label class="form-check-label">Sentiment Analysis</label>
        </div>
        <div class="form-check">
            <input type="checkbox" name="topics" checked class="form-check-input">
            <label class="form-check-label">Topic Extraction</label>
        </div>
        <div class="form-check">
            <input type="checkbox" name="entities" checked class="form-check-input">
            <label class="form-check-label">Entity Recognition</label>
        </div>
    </div>
    
    <button type="submit" class="btn btn-primary">Analyze Document</button>
</form>
```

## Django Views Structure

### Class-Based Views

```python
# demo_workflows/views.py
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.shortcuts import redirect
from django.contrib import messages
from .models import WorkflowExecution
from .forms import CrawlerForm, RewriterForm, AnalyzerForm

class DashboardView(TemplateView):
    template_name = 'demo_workflows/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_executions'] = WorkflowExecution.objects.all()[:5]
        context['system_status'] = self.get_system_status()
        return context
    
    def get_system_status(self):
        from container_manager.models import ExecutorHost, ContainerJob
        return {
            'active_hosts': ExecutorHost.objects.filter(is_active=True).count(),
            'total_hosts': ExecutorHost.objects.count(),
            'running_jobs': ContainerJob.objects.filter(status='running').count(),
            'completed_today': WorkflowExecution.objects.filter(
                completed_at__date=timezone.now().date()
            ).count(),
        }

class WorkflowListView(ListView):
    model = WorkflowExecution
    template_name = 'demo_workflows/workflow_list.html'
    context_object_name = 'executions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by type
        workflow_type = self.request.GET.get('type')
        if workflow_type:
            queryset = queryset.filter(workflow_type=workflow_type)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search by name/description
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(id__icontains=search) |
                Q(crawl_data__url__icontains=search) |
                Q(rewrite_data__original_text__icontains=search) |
                Q(analysis_data__document_name__icontains=search)
            )
        
        return queryset.order_by('-created_at')

class WorkflowDetailView(DetailView):
    model = WorkflowExecution
    template_name = 'demo_workflows/workflow_detail.html'
    context_object_name = 'execution'

class CrawlerCreateView(FormView):
    form_class = CrawlerForm
    template_name = 'demo_workflows/crawler_form.html'
    
    def form_valid(self, form):
        execution = form.save(self.request.user)
        messages.success(self.request, f'Web crawler started: {execution.id}')
        return redirect('workflow_detail', pk=execution.id)

# Similar views for RewriterCreateView and AnalyzerCreateView
```

### URL Configuration

```python
# demo_workflows/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('workflows/', views.WorkflowListView.as_view(), name='workflow_list'),
    path('workflows/<uuid:pk>/', views.WorkflowDetailView.as_view(), name='workflow_detail'),
    
    # Workflow creation
    path('workflows/crawler/create/', views.CrawlerCreateView.as_view(), name='create_crawler'),
    path('workflows/rewriter/create/', views.RewriterCreateView.as_view(), name='create_rewriter'),
    path('workflows/analyzer/create/', views.AnalyzerCreateView.as_view(), name='create_analyzer'),
    
    # AJAX endpoints for status updates
    path('api/workflow/<uuid:pk>/status/', views.WorkflowStatusView.as_view(), name='workflow_status'),
    path('api/workflow/<uuid:pk>/cancel/', views.CancelWorkflowView.as_view(), name='cancel_workflow'),
]
```

## Templates Structure

### Base Template

```html
<!-- demo_workflows/templates/demo_workflows/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Django Container Manager Demo{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Custom CSS -->
    <link href="{% static 'demo_workflows/style.css' %}" rel="stylesheet">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{% url 'dashboard' %}">
                Django Container Manager Demo
            </a>
            
            <div class="navbar-nav">
                <a class="nav-link" href="{% url 'dashboard' %}">Home</a>
                <a class="nav-link" href="{% url 'workflow_list' %}">Workflows</a>
                <a class="nav-link" href="/admin/">Admin</a>
            </div>
        </div>
    </nav>
    
    <!-- Main content -->
    <div class="container mt-4">
        <!-- Messages -->
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible fade show">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
        
        {% block content %}{% endblock %}
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Custom JS -->
    <script src="{% static 'demo_workflows/script.js' %}"></script>
</body>
</html>
```

## Status Updates and Interactivity

### Real-Time Status Updates (Simple Polling)

```javascript
// demo_workflows/static/demo_workflows/script.js
class WorkflowStatusUpdater {
    constructor(executionId) {
        this.executionId = executionId;
        this.pollInterval = 5000; // 5 seconds
        this.maxRetries = 60; // 5 minutes max
        this.retries = 0;
        
        this.startPolling();
    }
    
    startPolling() {
        if (this.retries >= this.maxRetries) {
            console.log('Max retries reached, stopping updates');
            return;
        }
        
        fetch(`/api/workflow/${this.executionId}/status/`)
            .then(response => response.json())
            .then(data => {
                this.updateStatus(data);
                
                if (data.status === 'running' || data.status === 'pending') {
                    setTimeout(() => this.startPolling(), this.pollInterval);
                }
            })
            .catch(error => {
                console.error('Status update failed:', error);
                this.retries++;
                setTimeout(() => this.startPolling(), this.pollInterval);
            });
    }
    
    updateStatus(data) {
        // Update status badge
        const statusBadge = document.getElementById('status-badge');
        if (statusBadge) {
            statusBadge.textContent = data.status;
            statusBadge.className = `badge bg-${this.getStatusColor(data.status)}`;
        }
        
        // Update duration if completed
        if (data.duration) {
            const durationEl = document.getElementById('duration');
            if (durationEl) {
                durationEl.textContent = data.duration;
            }
        }
        
        // Show results if completed
        if (data.status === 'completed' && data.results) {
            this.showResults(data.results);
        }
    }
    
    getStatusColor(status) {
        const colors = {
            'pending': 'secondary',
            'running': 'primary',
            'completed': 'success',
            'failed': 'danger',
            'cancelled': 'warning'
        };
        return colors[status] || 'secondary';
    }
    
    showResults(results) {
        const resultsContainer = document.getElementById('results-container');
        if (resultsContainer) {
            resultsContainer.innerHTML = this.formatResults(results);
            resultsContainer.style.display = 'block';
        }
    }
    
    formatResults(results) {
        // Format results based on workflow type
        return `<pre>${JSON.stringify(results, null, 2)}</pre>`;
    }
}

// Initialize status updater if on workflow detail page
document.addEventListener('DOMContentLoaded', function() {
    const executionId = document.body.dataset.executionId;
    if (executionId) {
        new WorkflowStatusUpdater(executionId);
    }
});
```

## Admin Integration

### Django Admin Configuration

```python
# demo_workflows/admin.py
from django.contrib import admin
from .models import WorkflowExecution, WebPageCrawl, TextRewrite, DocumentAnalysis

@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'workflow_type', 'status', 'created_at', 'duration']
    list_filter = ['workflow_type', 'status', 'created_at']
    search_fields = ['id']
    readonly_fields = ['id', 'created_at', 'started_at', 'completed_at', 'duration']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'workflow_type', 'status')
        }),
        ('Timing', {
            'fields': ('created_at', 'started_at', 'completed_at', 'duration')
        }),
        ('Execution', {
            'fields': ('container_job', 'created_by')
        }),
        ('Results', {
            'fields': ('result_data', 'error_message'),
            'classes': ('collapse',)
        }),
    )

# Inline admin for related workflow data
class WebPageCrawlInline(admin.StackedInline):
    model = WebPageCrawl
    extra = 0

class TextRewriteInline(admin.StackedInline):
    model = TextRewrite
    extra = 0

class DocumentAnalysisInline(admin.StackedInline):
    model = DocumentAnalysis
    extra = 0
```

## Responsive Design

### Mobile-Friendly Layout

```css
/* demo_workflows/static/demo_workflows/style.css */
.workflow-card {
    transition: transform 0.2s;
    cursor: pointer;
}

.workflow-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.status-badge {
    font-size: 0.875rem;
}

.execution-table {
    font-size: 0.875rem;
}

@media (max-width: 768px) {
    .workflow-cards {
        flex-direction: column;
    }
    
    .execution-table {
        font-size: 0.75rem;
    }
    
    .table-responsive {
        border: none;
    }
}

.results-container {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 0.375rem;
    padding: 1rem;
    margin-top: 1rem;
}

.error-message {
    color: #dc3545;
    font-family: monospace;
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    border-radius: 0.375rem;
    padding: 0.75rem;
}
```

This web interface provides a clean, functional demonstration platform that focuses on showcasing the container manager's capabilities while maintaining simplicity and usability.