# Task: Extend Management Command with Queue Mode

## Objective
Enhance the existing `process_container_jobs` management command to support queue processing mode while maintaining backward compatibility.

## Success Criteria
- [ ] `--queue-mode` flag for queue processing
- [ ] Configurable concurrency and polling parameters
- [ ] Graceful shutdown handling
- [ ] Backward compatibility with existing command usage
- [ ] Comprehensive help documentation

## Implementation Details

### Enhanced Management Command

```python
# container_manager/management/commands/process_container_jobs.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from container_manager.queue import queue_manager
import logging
import sys
import signal
import threading

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process container jobs - either existing jobs or queue mode'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shutdown_event = threading.Event()

    def add_arguments(self, parser):
        # Queue mode arguments
        parser.add_argument(
            '--queue-mode',
            action='store_true',
            help='Run in queue processing mode (launches queued jobs continuously)'
        )
        
        parser.add_argument(
            '--max-concurrent',
            type=int,
            default=5,
            help='Maximum concurrent jobs when in queue mode (default: 5)'
        )
        
        parser.add_argument(
            '--poll-interval',
            type=int,
            default=10,
            help='Polling interval in seconds for queue mode (default: 10)'
        )
        
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process queue once and exit (don\'t run continuously)'
        )
        
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout in seconds for job acquisition (default: 30)'
        )
        
        # Legacy arguments (for backward compatibility)
        parser.add_argument(
            '--job-id',
            type=int,
            help='Process specific job by ID (legacy mode)'
        )
        
        parser.add_argument(
            '--status',
            choices=['pending', 'running', 'failed'],
            help='Process jobs with specific status (legacy mode)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually doing it'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )

    def handle(self, *args, **options):
        # Set up logging level
        if options['verbose']:
            logging.getLogger('container_manager').setLevel(logging.DEBUG)
            
        # Validate arguments
        if options['queue_mode'] and (options['job_id'] or options['status']):
            raise CommandError("Cannot use --queue-mode with --job-id or --status")
            
        if options['max_concurrent'] < 1:
            raise CommandError("--max-concurrent must be at least 1")
            
        if options['poll_interval'] < 1:
            raise CommandError("--poll-interval must be at least 1")

        try:
            if options['queue_mode']:
                return self._handle_queue_mode(options)
            else:
                return self._handle_legacy_mode(options)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted by user"))
            return
        except Exception as e:
            logger.exception(f"Command failed: {e}")
            raise CommandError(f"Command failed: {e}")

    def _handle_queue_mode(self, options):
        """Handle queue processing mode"""
        max_concurrent = options['max_concurrent']
        poll_interval = options['poll_interval']
        once = options['once']
        dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting queue processor (max_concurrent={max_concurrent}, "
                f"poll_interval={poll_interval}s, once={once})"
            )
        )
        
        if dry_run:
            return self._dry_run_queue_mode(options)
            
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        if once:
            # Single queue processing run
            result = queue_manager.launch_next_batch(
                max_concurrent=max_concurrent,
                timeout=options['timeout']
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed queue: launched {result['launched']} jobs"
                )
            )
            
            if result['errors']:
                self.stdout.write(
                    self.style.WARNING(
                        f"Encountered {len(result['errors'])} errors:"
                    )
                )
                for error in result['errors']:
                    self.stdout.write(f"  - {error}")
                    
            return result
        else:
            # Continuous queue processing
            try:
                stats = queue_manager.process_queue_continuous(
                    max_concurrent=max_concurrent,
                    poll_interval=poll_interval,
                    shutdown_event=self.shutdown_event
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Queue processor finished. "
                        f"Processed {stats['iterations']} iterations, "
                        f"launched {stats['jobs_launched']} jobs"
                    )
                )
                
                if stats['errors']:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Encountered {len(stats['errors'])} errors during processing"
                        )
                    )
                    
                return stats
                
            except Exception as e:
                logger.exception("Error in continuous queue processing")
                raise CommandError(f"Queue processing failed: {e}")

    def _handle_legacy_mode(self, options):
        """Handle legacy job processing mode"""
        from container_manager.models import ContainerJob
        from container_manager.services import job_service
        
        job_id = options['job_id']
        status = options['status']
        dry_run = options['dry_run']
        
        # Build queryset
        if job_id:
            queryset = ContainerJob.objects.filter(id=job_id)
        elif status:
            queryset = ContainerJob.objects.filter(status=status)
        else:
            # Default: process running jobs (original behavior)
            queryset = ContainerJob.objects.filter(status='running')
        
        jobs = list(queryset)
        
        if not jobs:
            self.stdout.write("No jobs found to process")
            return
            
        self.stdout.write(f"Found {len(jobs)} job(s) to process")
        
        if dry_run:
            for job in jobs:
                self.stdout.write(f"Would process: Job {job.id} ({job.status}) - {job.name}")
            return
            
        # Process jobs
        processed = 0
        errors = 0
        
        for job in jobs:
            try:
                if options['verbose']:
                    self.stdout.write(f"Processing job {job.id} ({job.status})")
                    
                # Use existing job service logic
                result = job_service.process_job(job)
                
                if result.success:
                    processed += 1
                    if options['verbose']:
                        self.stdout.write(
                            self.style.SUCCESS(f"Successfully processed job {job.id}")
                        )
                else:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f"Failed to process job {job.id}: {result.error}")
                    )
                    
            except Exception as e:
                errors += 1
                logger.exception(f"Error processing job {job.id}")
                self.stdout.write(
                    self.style.ERROR(f"Error processing job {job.id}: {e}")
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(f"Processed: {processed} jobs, Errors: {errors}")
        )

    def _dry_run_queue_mode(self, options):
        """Show what would be processed in queue mode without actually doing it"""
        metrics = queue_manager.get_worker_metrics()
        
        self.stdout.write("Queue Status (dry run):")
        self.stdout.write(f"  Ready to launch now: {metrics['ready_now']}")
        self.stdout.write(f"  Scheduled for future: {metrics['scheduled_future']}")
        self.stdout.write(f"  Currently running: {metrics['running']}")
        self.stdout.write(f"  Launch failed: {metrics['launch_failed']}")
        
        # Show next jobs that would be processed
        ready_jobs = queue_manager.get_ready_jobs(limit=options['max_concurrent'])
        
        if ready_jobs:
            self.stdout.write(f"\nNext {len(ready_jobs)} job(s) that would be launched:")
            for job in ready_jobs:
                self.stdout.write(
                    f"  - Job {job.id}: {job.name} (priority={job.priority}, "
                    f"queued={job.queued_at.strftime('%H:%M:%S')})"
                )
        else:
            self.stdout.write("\nNo jobs ready for launch")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.stdout.write(
                self.style.WARNING(f"Received {signal_name}, shutting down gracefully...")
            )
            self.shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Handle SIGUSR1 for status reporting
        def status_handler(signum, frame):
            metrics = queue_manager.get_worker_metrics()
            self.stdout.write(f"Queue status: {metrics}")
            
        signal.signal(signal.SIGUSR1, status_handler)
```

### Usage Documentation

```python
# Add to command help text
EXAMPLES = """
Examples:

Queue Mode (new):
  %(prog)s --queue-mode                    # Continuous queue processing
  %(prog)s --queue-mode --once            # Process queue once and exit
  %(prog)s --queue-mode --max-concurrent=10 --poll-interval=5
  %(prog)s --queue-mode --dry-run         # See what would be processed

Legacy Mode (existing):
  %(prog)s                                # Process running jobs (default)
  %(prog)s --job-id=123                   # Process specific job
  %(prog)s --status=pending               # Process jobs with status
  %(prog)s --dry-run                      # Show what would be processed

Operational:
  kill -USR1 <pid>                        # Get queue status
  kill -TERM <pid>                        # Graceful shutdown
"""

class Command(BaseCommand):
    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.epilog = EXAMPLES % {'prog': f'{prog_name} {subcommand}'}
        return parser
```

## Files to Modify
- `container_manager/management/commands/process_container_jobs.py`

## Testing Requirements
- [ ] Test queue mode launches jobs correctly
- [ ] Test --once mode processes queue and exits
- [ ] Test --dry-run shows correct information
- [ ] Test backward compatibility with existing usage
- [ ] Test signal handling for graceful shutdown
- [ ] Test argument validation
- [ ] Test error handling and logging

### Command Testing Examples

```bash
# Test queue mode
python manage.py process_container_jobs --queue-mode --once --verbose

# Test dry run
python manage.py process_container_jobs --queue-mode --dry-run

# Test continuous processing (interrupt with Ctrl+C)
python manage.py process_container_jobs --queue-mode --max-concurrent=3

# Test legacy mode (backward compatibility)
python manage.py process_container_jobs --status=pending

# Test help
python manage.py process_container_jobs --help
```

## Dependencies
- Depends on: `04-queue-manager-basic.md` (queue_manager implementation)
- Depends on: `05-concurrency-control.md` (process_queue_continuous method)

## Deployment Considerations

### Systemd Service Example

```ini
# /etc/systemd/system/django-queue-processor.service
[Unit]
Description=Django Container Manager Queue Processor
After=network.target postgresql.service

[Service]
Type=exec
User=django
Group=django
WorkingDirectory=/path/to/django/project
Environment=DJANGO_SETTINGS_MODULE=myproject.settings
ExecStart=/path/to/venv/bin/python manage.py process_container_jobs --queue-mode --max-concurrent=5
ExecReload=/bin/kill -USR1 $MAINPID
KillMode=process
KillSignal=SIGTERM
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker Compose Example

```yaml
# docker-compose.yml
services:
  queue-processor:
    build: .
    command: python manage.py process_container_jobs --queue-mode --max-concurrent=10
    environment:
      - DJANGO_SETTINGS_MODULE=myproject.settings
    depends_on:
      - db
    restart: unless-stopped
```

## Notes
- Maintains full backward compatibility with existing command usage
- Supports both one-shot and continuous queue processing
- Graceful shutdown prevents job corruption
- Dry-run mode helps with operational debugging
- Signal handling provides operational control
- Comprehensive help and examples for users