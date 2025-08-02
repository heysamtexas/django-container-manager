# Documentation Task: Management Command Documentation Enhancement

**Priority:** Medium
**Component:** CLI Documentation
**Estimated Effort:** Low-Medium
**Current Status:** Limited help text in management commands

## Task Summary
Enhance management command help text and documentation to provide comprehensive guidance for CLI usage. Users interacting with the system via Django management commands need clear, actionable help that explains command purpose, options, and usage patterns.

## Current Documentation Gaps
- Basic help text in existing commands
- No usage examples in command help
- Missing explanation of command interactions
- Absent guidance on command sequencing
- No troubleshooting information in help text

## Management Commands to Document

### 1. process_jobs Command Enhancement
Current command likely handles job processing and execution. Needs comprehensive help text:

```python
class Command(BaseCommand):
    help = """
    Process pending container jobs and manage their execution lifecycle.
    
    This command handles the core job processing workflow:
    - Discovers pending jobs in the database
    - Launches jobs on available executor hosts
    - Monitors running jobs for completion
    - Harvests logs and results from completed jobs
    - Updates job status throughout the lifecycle
    
    Usage Examples:
        # Process all pending jobs once
        python manage.py process_jobs
        
        # Run in continuous mode (daemon-like)
        python manage.py process_jobs --daemon
        
        # Process only jobs for specific host
        python manage.py process_jobs --host production-docker
        
        # Limit concurrent jobs
        python manage.py process_jobs --max-jobs 5
        
        # Process with verbose output
        python manage.py process_jobs --verbosity 2
    
    Job Processing Flow:
        1. Query database for pending jobs
        2. Check executor host availability and capacity
        3. Launch jobs within resource limits
        4. Monitor running jobs for status changes
        5. Harvest completed jobs for logs and exit codes
        6. Update database with final results
    
    Monitoring and Logging:
        - Progress logged to console and Django logging system
        - Job execution details logged for debugging
        - Resource usage tracked and reported
        - Errors logged with context for troubleshooting
    
    Signal Handling:
        - SIGTERM: Graceful shutdown, finish current operations
        - SIGINT (Ctrl+C): Immediate shutdown with cleanup
        - SIGUSR1: Reload configuration without restart
    
    Exit Codes:
        0: Success, all jobs processed normally
        1: General error (configuration, database, etc.)
        2: Executor error (Docker daemon unavailable, etc.)
        3: Job processing error (job failures, resource limits)
    """
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--daemon',
            action='store_true',
            default=False,
            help=(
                'Run in daemon mode, continuously processing jobs. '
                'Use Ctrl+C or SIGTERM to stop gracefully.'
            )
        )
        
        parser.add_argument(
            '--host',
            type=str,
            help=(
                'Process jobs only for the specified executor host. '
                'Use host name as configured in ExecutorHost model.'
            )
        )
        
        parser.add_argument(
            '--max-jobs',
            type=int,
            default=10,
            help=(
                'Maximum number of concurrent jobs to run. '
                'Default: 10. Consider host resources when setting this value.'
            )
        )
        
        parser.add_argument(
            '--poll-interval',
            type=int,
            default=30,
            help=(
                'Seconds between polling cycles in daemon mode. '
                'Default: 30 seconds. Lower values increase responsiveness but CPU usage.'
            )
        )
        
        parser.add_argument(
            '--timeout',
            type=int,
            default=3600,
            help=(
                'Maximum job execution time in seconds before timeout. '
                'Default: 3600 (1 hour). Set to 0 for no timeout.'
            )
        )
```

### 2. manage_jobs Command Enhancement
Command for job lifecycle management operations:

```python
class Command(BaseCommand):
    help = """
    Manage container job lifecycle operations and maintenance tasks.
    
    Provides administrative operations for job management including:
    - Cleanup of old completed jobs
    - Cancellation of running jobs
    - Status reporting and health checks
    - Resource usage analysis
    - Executor host management
    
    Usage Examples:
        # Clean up jobs older than 7 days
        python manage.py manage_jobs cleanup --days 7
        
        # Cancel specific job
        python manage.py manage_jobs cancel --job-id 123
        
        # Show job status summary
        python manage.py manage_jobs status
        
        # Health check all executor hosts
        python manage.py manage_jobs health-check
        
        # Show resource usage report
        python manage.py manage_jobs report --format table
    
    Subcommands:
        cleanup     Remove old completed jobs and associated data
        cancel      Cancel running or pending jobs
        status      Display job status summary and statistics
        health-check Verify executor host connectivity and health
        report      Generate resource usage and performance reports
        retry       Retry failed jobs with optional parameter changes
    
    Cleanup Operations:
        - Removes job records older than specified threshold
        - Cleans up associated container execution records
        - Removes log files and temporary data
        - Reports space reclaimed and records removed
        - Respects foreign key constraints and cascading deletes
    
    Safety Features:
        - Dry-run mode for all destructive operations
        - Confirmation prompts for bulk operations
        - Backup recommendations before major cleanups
        - Rollback guidance for recovery scenarios
    """
    
    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='subcommand', help='Available operations')
        
        # Cleanup subcommand
        cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old jobs and data')
        cleanup_parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Remove jobs older than this many days (default: 30)'
        )
        cleanup_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        cleanup_parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts (use with caution)'
        )
        
        # Cancel subcommand  
        cancel_parser = subparsers.add_parser('cancel', help='Cancel running jobs')
        cancel_parser.add_argument(
            '--job-id',
            type=int,
            help='Specific job ID to cancel'
        )
        cancel_parser.add_argument(
            '--host',
            type=str,
            help='Cancel all jobs on specified host'
        )
        cancel_parser.add_argument(
            '--reason',
            type=str,
            default='Manual cancellation',
            help='Reason for cancellation (recorded in job history)'
        )
        
        # Status subcommand
        status_parser = subparsers.add_parser('status', help='Show job status summary')
        status_parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed status including resource usage'
        )
        
        # Health check subcommand
        health_parser = subparsers.add_parser('health-check', help='Check executor host health')
        health_parser.add_argument(
            '--host',
            type=str,
            help='Check specific host only'
        )
        health_parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Health check timeout in seconds (default: 30)'
        )
```

### 3. Additional Management Commands
Document any other management commands discovered in the codebase:

#### Database Maintenance Commands
```python
# If migration-related commands exist
class Command(BaseCommand):
    help = """
    Perform database maintenance and migration operations.
    
    Handles database schema updates, data migrations, and consistency checks
    specific to the container management system.
    """
```

#### Development and Testing Commands
```python
# If development helper commands exist  
class Command(BaseCommand):
    help = """
    Development utilities for container job testing and debugging.
    
    Provides tools for developers to test job execution, validate
    configurations, and debug system behavior.
    """
```

## Command Documentation Standards

### 1. Help Text Structure
```python
help = """
[One-line summary of command purpose]

[Detailed description of what the command does]

Usage Examples:
    [3-5 practical examples with explanations]

[Operation Details - how the command works]

[Important Notes - warnings, performance considerations]

[Exit Codes - if applicable]
"""
```

### 2. Argument Documentation
```python
parser.add_argument(
    '--argument-name',
    type=str,
    default='default_value',
    help=(
        'Clear description of what this argument does. '
        'Include default values, valid ranges, and examples. '
        'Explain any important behavior or limitations.'
    )
)
```

### 3. Error Handling Documentation
Each command should document:
- Common error conditions and messages
- How to diagnose and resolve issues
- When to check logs for more information
- Recovery procedures if operations fail

### 4. Performance and Resource Considerations
Document:
- Expected execution time for operations
- Resource usage (CPU, memory, disk)
- Impact on running jobs or system performance
- Recommendations for production usage

## Implementation Requirements

### 1. Existing Command Analysis
First, analyze existing management commands to understand:
- Current command structure and functionality
- Existing argument patterns and naming
- Integration with the job processing system
- Dependencies on models and executors

### 2. Help Text Enhancement
For each command:
- Expand basic help to comprehensive documentation
- Add practical usage examples
- Explain command interactions and workflows
- Document all arguments and options
- Include troubleshooting guidance

### 3. Consistency Improvements
Ensure:
- Consistent argument naming across commands
- Standard help text formatting
- Common patterns for similar operations
- Unified error handling and reporting

### 4. User Experience Improvements
- Clear progress reporting for long operations
- Confirmation prompts for destructive operations
- Helpful error messages with suggested solutions
- Dry-run options for testing commands

## LLM Agent Guidelines

### Behavioral Constraints
- **DO**: Test all command examples before documenting them
- **DO**: Validate parameter combinations and edge cases
- **DO**: Document expected output formats clearly
- **DO**: Include error handling examples for common failures
- **DO NOT**: Document command options that don't exist
- **DO NOT**: Create examples that could harm production systems
- **DO NOT**: Include commands that require privileged access without warnings
- **DO NOT**: Ignore potential security implications of command usage
- **LIMITS**: Document only existing functionality, no feature additions

### Security Requirements
- **Command validation**: Verify all command examples are safe to run
- **Parameter safety**: Ensure documented parameters don't expose sensitive data
- **Access control**: Document required permissions for command execution
- **Production safety**: Mark commands that should not be run in production
- **Resource limits**: Document commands that consume significant system resources

### Safe Operation Patterns
- **Command documentation workflow**:
  1. Read command source code to understand full functionality
  2. Test command with all documented parameter combinations
  3. Verify help text accuracy against actual implementation
  4. Test error scenarios and document expected behavior
  5. Validate examples in clean test environment
- **Help text enhancement**:
  1. Provide clear, actionable descriptions
  2. Include complete parameter documentation
  3. Add practical usage examples
  4. Document common error scenarios
  5. Specify expected output formats

### Error Handling
- **If command behavior unclear**: Study source code, don't guess functionality
- **If examples fail**: Fix examples to match actual behavior, don't ignore failures
- **If parameter validation fails**: Document correct parameter formats and constraints
- **If command has security implications**: Add appropriate warnings and usage guidance

### Validation Requirements
- [ ] All command examples tested in isolated environment
- [ ] Parameter descriptions match actual command behavior
- [ ] Error scenarios documented with expected error messages
- [ ] Security implications noted for potentially dangerous commands
- [ ] Resource usage implications documented for heavy operations
- [ ] Help text improvements tested with actual command execution
- [ ] Cross-references to related documentation included

### Management Command Safety Boundaries
- **NEVER document**: Commands that don't exist in the codebase
- **NEVER ignore**: Security implications of documented commands
- **NEVER provide**: Examples that could damage production systems
- **NEVER skip**: Testing documented command examples
- **NEVER omit**: Required parameters or important warnings
- **NEVER encourage**: Unsafe command usage patterns
- **NEVER assume**: Command behavior without testing

## Success Criteria
- [ ] All management commands have comprehensive help text
- [ ] Usage examples provided for common scenarios
- [ ] Command arguments clearly documented
- [ ] Error conditions and troubleshooting guidance included
- [ ] Performance and resource considerations documented
- [ ] Consistent help formatting across all commands
- [ ] Commands tested to verify help text accuracy

## File Locations
- **Edit**: `/Users/samtexas/src/playground/django-docker/container_manager/management/commands/*.py`
- **Reference**: CLAUDE.md for command usage patterns

## Testing Requirements
- [ ] All help text examples tested and verified working
- [ ] Command arguments validated against actual implementation
- [ ] Error conditions tested to ensure accurate documentation
- [ ] Help formatting consistent and readable

## Definition of Done
- [ ] Enhanced help text for all existing management commands
- [ ] Usage examples tested and verified
- [ ] Argument documentation complete and accurate
- [ ] Error handling and troubleshooting guidance provided
- [ ] Consistent documentation style across commands
- [ ] Commands serve as self-documenting CLI interface