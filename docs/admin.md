# Admin Interface Guide

This guide covers using the Django admin interface for managing Docker containers and jobs in Django Docker Container Manager.

## Overview

The Django admin interface is the primary management tool for the system, providing comprehensive control over Docker hosts, container templates, jobs, and executions. It features enhanced functionality with real-time updates, bulk operations, and intuitive status indicators.

## Accessing the Admin Interface

### Setup
```bash
# Create superuser account
uv run python manage.py createsuperuser

# Start development server
uv run python manage.py runserver

# Access admin at http://localhost:8000/admin/
```

### Login
1. Navigate to `/admin/`
2. Enter superuser credentials
3. Access the Container Manager section

## Docker Hosts Management

### Adding Docker Hosts

1. Navigate to **Container Manager** → **Docker Hosts**
2. Click **Add Docker Host**
3. Configure host settings:
   - **Name**: Unique identifier (e.g., "production-docker")
   - **Host Type**: Select "Unix Socket" or "TCP"
   - **Connection String**: Docker daemon URL
   - **Is Active**: Enable/disable the host
   - **TLS Settings**: For secure TCP connections

### Docker Host Features

#### Connection Testing
- **Bulk Action**: "Test connection to selected hosts"
- **Usage**: Select hosts and apply action to verify connectivity
- **Output**: Success/failure status with error details

#### Status Indicators
- **Active hosts**: Green checkmark indicator
- **Inactive hosts**: Red X indicator  
- **Connection status**: Visual feedback in list view

#### Host Configuration
```python
# Example Unix socket configuration
Name: local-docker
Host Type: unix
Connection String: unix:///var/run/docker.sock
Is Active: ✓
TLS Enabled: ✗

# Example TCP configuration  
Name: production-docker
Host Type: tcp
Connection String: tcp://docker.example.com:2376
Is Active: ✓
TLS Enabled: ✓
TLS Verify: ✓
```

## Container Templates Management

### Creating Templates

1. Navigate to **Container Manager** → **Container Templates**
2. Click **Add Container Template**
3. Configure template:
   - **Name**: Template identifier
   - **Description**: Human-readable description
   - **Docker Image**: Image name and tag
   - **Command**: Default command to execute
   - **Resource Limits**: Memory and CPU constraints
   - **Timeout**: Maximum execution time

### Template Features

#### Inline Environment Variables
- **Add variables**: Click "Add another Environment Variable"
- **Variable configuration**:
  - **Key**: Environment variable name
  - **Value**: Variable value
  - **Is Secret**: Mark sensitive values (hidden in logs)

#### Inline Network Assignments
- **Add networks**: Click "Add another Network Assignment"
- **Network configuration**:
  - **Network Name**: Docker network to join
  - **Aliases**: Container aliases in network

#### Template Validation
- **Image format**: Validates Docker image references
- **Resource limits**: Ensures reasonable memory/CPU values
- **Command syntax**: Basic command validation

### Template List Features

#### Filtering and Search
- **Search**: Template name and description
- **Filters**: 
  - Docker image
  - Is active status
  - Creation date

#### Bulk Operations
- **Activate templates**: Enable multiple templates
- **Deactivate templates**: Disable multiple templates
- **Export configuration**: Download template configurations

## Container Jobs Management

### Job Creation

#### Manual Job Creation
1. Navigate to **Container Manager** → **Container Jobs**
2. Click **Add Container Job**
3. Select:
   - **Template**: Container template to use
   - **Docker Host**: Host for execution
   - **Priority**: Execution priority (1-5)
4. Optional overrides:
   - **Command Override**: Custom command
   - **Memory/CPU Limits**: Resource overrides
   - **Timeout Override**: Execution timeout

#### Quick Job Actions
- **Create and Run**: Immediately start job after creation
- **Duplicate Job**: Copy existing job configuration
- **Bulk Create**: Create multiple jobs from template

### Job Status Monitoring

#### Status Indicators
Jobs display color-coded status indicators:
- **Green (Completed)**: Successful execution (exit code 0)
- **Blue (Running)**: Currently executing
- **Yellow (Pending)**: Waiting for execution
- **Red (Failed)**: Execution failed (non-zero exit code)
- **Gray (Cancelled)**: Manually cancelled

#### Real-time Updates
- **Auto-refresh**: Status updates automatically via HTMX
- **Live monitoring**: Running job progress without page reload
- **Execution time**: Live duration counter for running jobs

### Job List Features

#### Advanced Filtering
```python
# Available filters
Status: pending, running, completed, failed, cancelled
Template: Filter by container template
Docker Host: Filter by execution host
Date Range: Created date filtering
Priority: Job priority level
Exit Code: Filter by exit code value
```

#### Bulk Operations
- **Start Jobs**: Execute selected pending jobs
- **Cancel Jobs**: Stop selected running jobs
- **Retry Failed**: Restart selected failed jobs
- **Delete Jobs**: Remove selected jobs and logs
- **Export Data**: Download job data as CSV

#### Search Functionality
- **Job ID**: Search by exact job UUID
- **Template Name**: Search by template
- **Command**: Search in executed commands
- **Error Messages**: Search in stderr logs

### Job Detail View

#### Execution Information
```python
# Displayed information
Job ID: abc123-def4-5678-9abc-def123456789
Template: data-processing-template
Docker Host: production-docker
Status: completed
Priority: 3
Created: 2024-01-15 10:30:15
Started: 2024-01-15 10:30:16
Finished: 2024-01-15 10:30:45
Duration: 0:00:29
Exit Code: 0
Container ID: container_abc123
```

#### Command and Environment
- **Effective Command**: Final command executed (with overrides)
- **Environment Variables**: All variables passed to container
- **Resource Limits**: Memory/CPU limits applied
- **Network Configuration**: Networks and aliases used

#### Log Viewing
- **Stdout Logs**: Complete standard output
- **Stderr Logs**: Complete error output  
- **Log Download**: Export logs as text files
- **Log Search**: Find text within logs

## Container Executions

### Execution Records

Each job automatically creates a ContainerExecution record containing:
- **Complete Logs**: Stdout and stderr output
- **Resource Usage**: Memory and CPU statistics (if available)
- **Container Metadata**: Docker container information
- **Execution Timeline**: Detailed timing information

### Log Management

#### Log Viewing
- **Inline Display**: View logs directly in admin
- **Syntax Highlighting**: Basic highlighting for common log formats
- **Scrollable Output**: Long logs in scrollable containers
- **Copy/Download**: Export logs for external analysis

#### Log Search
- **Text Search**: Find specific content in logs
- **Error Pattern**: Quick filters for common error patterns
- **Timestamp Navigation**: Jump to specific time periods

## Environment Variables Management

### Variable Configuration

#### Template-Level Variables
- **Default Values**: Set at template level
- **Secret Marking**: Mark sensitive variables
- **Variable Inheritance**: Override behavior configuration

#### Job-Level Overrides
- **Override Environment**: JSON field for job-specific variables
- **Merge Behavior**: How overrides combine with template variables
- **Secret Handling**: Automatic masking in logs and displays

### Security Features

#### Secret Management
- **Secret Marking**: Mark variables as sensitive
- **Log Masking**: Automatic hiding in log output
- **Admin Display**: Masked values in admin interface
- **Export Control**: Exclude secrets from exports

## Network Assignments

### Network Configuration

#### Template Networks
- **Default Networks**: Networks assigned at template level
- **Alias Configuration**: Container aliases in networks
- **Network Validation**: Verify network existence

#### Job Networks
- **Network Override**: Job-specific network assignments
- **Dynamic Networks**: Runtime network creation
- **Connectivity Testing**: Network reachability validation

## Admin Customizations

### Enhanced UI Features

#### Bootstrap5 Integration
- **Modern Styling**: Clean, responsive interface
- **Status Badges**: Color-coded status indicators
- **Progress Bars**: Visual progress for running jobs
- **Alert Messages**: User-friendly notifications

#### HTMX Integration
- **Real-time Updates**: Live status changes without refresh
- **Dynamic Forms**: Interactive form elements
- **Partial Updates**: Update specific page sections
- **Background Operations**: Non-blocking admin actions

### Custom Actions

#### System-Wide Actions
```python
# Available bulk actions
Test Docker Host Connections
Start Selected Jobs
Cancel Selected Jobs
Retry Failed Jobs
Clean Up Old Jobs
Export Configuration
Validate Templates
```

#### Administrative Tools
- **Health Check**: System status overview
- **Resource Monitor**: Current resource usage
- **Queue Status**: Job queue depth and processing rate
- **Log Analysis**: Error pattern detection

## User Permissions

### Admin Groups

#### Administrator
- **Full Access**: All models and operations
- **System Configuration**: Docker hosts and global settings
- **User Management**: Create/modify admin users

#### Operator
- **Job Management**: Create, monitor, and control jobs
- **Template Usage**: Use existing templates
- **Limited Configuration**: Basic template modifications

#### Viewer
- **Read-Only Access**: View jobs and status
- **Log Access**: View execution logs
- **Monitoring**: Access to status dashboards

### Permission Configuration
```python
# Example permission setup
from django.contrib.auth.models import Group, Permission

# Create operator group
operators = Group.objects.create(name='Operators')
operators.permissions.add(
    Permission.objects.get(codename='add_containerjob'),
    Permission.objects.get(codename='change_containerjob'),
    Permission.objects.get(codename='view_containerjob'),
    Permission.objects.get(codename='view_containertemplate'),
)
```

## Performance Optimization

### List View Performance

#### Pagination
- **Default**: 25 items per page
- **Configurable**: Adjust via admin settings
- **Large Datasets**: Efficient handling of thousands of jobs

#### Query Optimization
- **Select Related**: Optimized database queries
- **Prefetch**: Reduced query count for related objects
- **Indexing**: Database indexes on frequently filtered fields

#### Caching
- **Template Data**: Cache template configurations
- **Status Counts**: Cache job status statistics
- **Host Information**: Cache Docker host metadata

### Memory Management

#### Log Display
- **Truncation**: Large logs truncated for display
- **Streaming**: Stream large log files
- **Lazy Loading**: Load logs on demand

#### Data Retention
- **Automatic Cleanup**: Old job records removed
- **Configurable Retention**: Set retention periods
- **Archive Options**: Export before deletion

## Troubleshooting

### Common Admin Issues

#### Performance Problems
- **Slow List Views**: Check database indexing
- **Large Log Files**: Configure log truncation
- **Memory Usage**: Monitor admin process memory

#### Connection Issues
- **Docker Host Unreachable**: Verify network connectivity
- **Permission Denied**: Check Docker socket permissions
- **TLS Configuration**: Validate certificate setup

#### Data Issues
- **Missing Jobs**: Check database constraints
- **Orphaned Containers**: Run cleanup operations
- **Status Inconsistency**: Verify job processor status

### Debug Features

#### Admin Debug Toolbar
```python
# Enable in development
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

#### Logging Configuration
```python
# Enhanced admin logging
LOGGING = {
    'loggers': {
        'container_manager.admin': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}
```

## Best Practices

### Daily Operations
1. **Monitor Queue**: Check pending job count regularly
2. **Review Failures**: Investigate failed jobs promptly
3. **Host Health**: Verify Docker host connectivity
4. **Resource Usage**: Monitor system resource consumption
5. **Clean Up**: Remove old completed jobs periodically

### Security Guidelines
1. **User Permissions**: Apply principle of least privilege
2. **Secret Management**: Mark sensitive variables appropriately
3. **Access Logging**: Monitor admin access patterns
4. **Regular Updates**: Keep Django and dependencies updated
5. **Backup Strategy**: Regular database backups

### Performance Tips
1. **Efficient Filtering**: Use appropriate filters for large datasets
2. **Batch Operations**: Use bulk actions for multiple items
3. **Log Management**: Configure appropriate log retention
4. **Database Maintenance**: Regular optimization and cleanup
5. **Monitoring**: Track admin performance metrics

For advanced monitoring capabilities, see the [Monitoring Guide](monitoring.md).