# Task: Implement Retry Logic with Exponential Backoff

## Objective
Implement sophisticated retry logic for failed job launches with exponential backoff, error classification, and proper retry limits.

## Success Criteria
- [ ] Exponential backoff for transient failures
- [ ] Error classification (transient vs permanent)
- [ ] Configurable retry strategies per job type
- [ ] Dead letter queue for permanently failed jobs
- [ ] Retry logic integrates with state machine

## Implementation Details

### Error Classification System

```python
# container_manager/retry.py
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"

class ErrorClassifier:
    """Classifies errors to determine retry strategy"""
    
    TRANSIENT_PATTERNS = [
        # Docker daemon issues
        r'connection.*refused',
        r'docker.*daemon.*not.*running',
        r'timeout.*connecting',
        
        # Resource constraints
        r'out of memory',
        r'no space left',
        r'resource temporarily unavailable',
        
        # Network issues
        r'network.*timeout',
        r'connection.*reset',
        r'temporary failure in name resolution',
        
        # System load
        r'system overloaded',
        r'too many open files',
        r'cannot allocate memory'
    ]
    
    PERMANENT_PATTERNS = [
        # Image issues
        r'image.*not found',
        r'no such image',
        r'repository.*not found',
        
        # Configuration errors
        r'invalid.*configuration',
        r'permission denied',
        r'access denied',
        r'authorization.*failed',
        
        # Command issues
        r'executable.*not found',
        r'command.*not found',
        r'invalid.*command'
    ]
    
    @classmethod
    def classify_error(cls, error_message):
        """
        Classify error as transient, permanent, or unknown.
        
        Args:
            error_message: Error message string
            
        Returns:
            ErrorType: Classification of the error
        """
        error_lower = error_message.lower()
        
        # Check for transient errors first
        for pattern in cls.TRANSIENT_PATTERNS:
            if re.search(pattern, error_lower):
                logger.debug(f"Classified as TRANSIENT: {pattern}")
                return ErrorType.TRANSIENT
        
        # Check for permanent errors
        for pattern in cls.PERMANENT_PATTERNS:
            if re.search(pattern, error_lower):
                logger.debug(f"Classified as PERMANENT: {pattern}")
                return ErrorType.PERMANENT
        
        # Default to unknown (treat as transient with caution)
        logger.debug("Classified as UNKNOWN")
        return ErrorType.UNKNOWN

class RetryStrategy:
    """Defines retry behavior for different error types"""
    
    def __init__(self, max_attempts=3, base_delay=1.0, max_delay=300.0, backoff_factor=2.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def should_retry(self, attempt_count, error_type):
        """
        Determine if job should be retried.
        
        Args:
            attempt_count: Current attempt number (1-based)
            error_type: ErrorType classification
            
        Returns:
            bool: True if should retry
        """
        if error_type == ErrorType.PERMANENT:
            return False
            
        return attempt_count < self.max_attempts
    
    def get_retry_delay(self, attempt_count):
        """
        Calculate delay before retry.
        
        Args:
            attempt_count: Current attempt number (1-based)
            
        Returns:
            float: Delay in seconds
        """
        if attempt_count <= 1:
            return 0  # First attempt has no delay
            
        delay = self.base_delay * (self.backoff_factor ** (attempt_count - 2))
        return min(delay, self.max_delay)

# Predefined strategies for different scenarios
RETRY_STRATEGIES = {
    'default': RetryStrategy(max_attempts=3, base_delay=2.0, max_delay=60.0),
    'aggressive': RetryStrategy(max_attempts=5, base_delay=1.0, max_delay=30.0),
    'conservative': RetryStrategy(max_attempts=2, base_delay=5.0, max_delay=300.0),
    'high_priority': RetryStrategy(max_attempts=5, base_delay=0.5, max_delay=15.0),
}
```

### Enhanced JobQueueManager with Retry Logic

```python
# container_manager/queue.py (additions to existing class)

from django.utils import timezone
from datetime import timedelta
from container_manager.retry import ErrorClassifier, RETRY_STRATEGIES, ErrorType

class JobQueueManager:
    # ... existing methods ...
    
    def launch_job_with_retry(self, job):
        """
        Launch job with sophisticated retry logic.
        
        Args:
            job: ContainerJob instance to launch
            
        Returns:
            dict: {'success': bool, 'error': str, 'retry_scheduled': bool}
        """
        try:
            with transaction.atomic():
                # Refresh job to check current state
                job.refresh_from_db()
                
                # Verify job is still ready to launch
                if not job.is_ready_to_launch:
                    return {
                        'success': False, 
                        'error': f"Job {job.id} no longer ready to launch",
                        'retry_scheduled': False
                    }
                
                # Get retry strategy for this job
                strategy = self._get_retry_strategy(job)
                
                # Import here to avoid circular imports
                from container_manager.services import job_service
                
                # Attempt to launch
                result = job_service.launch_job(job)
                
                if result.success:
                    # Launch successful
                    job.mark_as_running()
                    logger.info(f"Successfully launched job {job.id}")
                    return {'success': True, 'retry_scheduled': False}
                else:
                    # Launch failed - handle retry logic
                    return self._handle_launch_failure(job, result.error, strategy)
                    
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error launching job {job.id}: {str(e)}"
            logger.exception(error_msg)
            
            strategy = self._get_retry_strategy(job)
            return self._handle_launch_failure(job, error_msg, strategy)
    
    def _handle_launch_failure(self, job, error_message, strategy):
        """
        Handle job launch failure with retry logic.
        
        Args:
            job: Failed ContainerJob
            error_message: Error message from launch attempt
            strategy: RetryStrategy instance
            
        Returns:
            dict: Launch result with retry information
        """
        # Classify the error
        error_type = ErrorClassifier.classify_error(error_message)
        
        # Increment attempt count
        job.retry_count += 1
        
        # Store error information
        job.last_error = error_message
        job.last_error_at = timezone.now()
        
        # Determine if we should retry
        should_retry = strategy.should_retry(job.retry_count, error_type)
        
        if should_retry and error_type != ErrorType.PERMANENT:
            # Schedule retry
            retry_delay = strategy.get_retry_delay(job.retry_count)
            job.scheduled_for = timezone.now() + timedelta(seconds=retry_delay)
            job.transition_to(job.Status.RETRYING, save=False)
            
            job.save(update_fields=[
                'retry_count', 'last_error', 'last_error_at', 
                'scheduled_for', 'status'
            ])
            
            logger.warning(
                f"Job {job.id} failed (attempt {job.retry_count}): {error_message}. "
                f"Retrying in {retry_delay:.1f}s"
            )
            
            return {
                'success': False,
                'error': error_message,
                'retry_scheduled': True,
                'retry_in_seconds': retry_delay
            }
        else:
            # No more retries - mark as permanently failed
            job.transition_to(job.Status.FAILED, save=False)
            job.failed_at = timezone.now()
            
            # Remove from queue
            job.queued_at = None
            
            job.save(update_fields=[
                'retry_count', 'last_error', 'last_error_at', 
                'status', 'failed_at', 'queued_at'
            ])
            
            reason = "permanent error" if error_type == ErrorType.PERMANENT else "retry limit exceeded"
            logger.error(f"Job {job.id} permanently failed after {job.retry_count} attempts ({reason}): {error_message}")
            
            return {
                'success': False,
                'error': f"Permanently failed: {error_message}",
                'retry_scheduled': False
            }
    
    def _get_retry_strategy(self, job):
        """
        Get retry strategy for a job.
        
        Args:
            job: ContainerJob instance
            
        Returns:
            RetryStrategy: Strategy to use for this job
        """
        # Check if job specifies a strategy
        strategy_name = getattr(job, 'retry_strategy', None) or 'default'
        
        # Priority-based strategy selection
        if job.priority >= 80:
            strategy_name = 'high_priority'
        elif job.priority <= 20:
            strategy_name = 'conservative'
        
        return RETRY_STRATEGIES.get(strategy_name, RETRY_STRATEGIES['default'])
    
    def get_failed_jobs(self, include_retrying=False):
        """
        Get jobs that have failed permanently.
        
        Args:
            include_retrying: Include jobs in retry state
            
        Returns:
            QuerySet: Failed jobs
        """
        from container_manager.models import ContainerJob
        
        queryset = ContainerJob.objects.filter(status='failed')
        
        if include_retrying:
            queryset = queryset | ContainerJob.objects.filter(status='retrying')
            
        return queryset.order_by('-failed_at')
    
    def retry_failed_job(self, job, reset_count=False):
        """
        Manually retry a failed job.
        
        Args:
            job: ContainerJob to retry
            reset_count: Reset retry count to 0
            
        Returns:
            bool: True if job was queued for retry
        """
        if job.status not in ['failed', 'retrying']:
            raise ValueError(f"Cannot retry job in status: {job.status}")
        
        if reset_count:
            job.retry_count = 0
            
        job.queued_at = timezone.now()
        job.scheduled_for = None  # Retry immediately
        job.last_error = None
        job.last_error_at = None
        
        job.transition_to(job.Status.QUEUED, save=False)
        job.save(update_fields=[
            'status', 'queued_at', 'scheduled_for', 'retry_count',
            'last_error', 'last_error_at'
        ])
        
        logger.info(f"Manually retrying job {job.id} (retry_count={job.retry_count})")
        return True
```

### Model Fields for Retry Information

```python
# Add to ContainerJob model (container_manager/models.py)

class ContainerJob(models.Model):
    # ... existing fields ...
    
    # Retry information fields
    last_error = models.TextField(
        blank=True, null=True,
        help_text="Last error message from failed launch attempt"
    )
    
    last_error_at = models.DateTimeField(
        blank=True, null=True,
        help_text="When the last error occurred"
    )
    
    retry_strategy = models.CharField(
        max_length=50, blank=True, null=True,
        choices=[
            ('default', 'Default'),
            ('aggressive', 'Aggressive'),
            ('conservative', 'Conservative'),
            ('high_priority', 'High Priority'),
        ],
        help_text="Retry strategy to use for this job"
    )
```

## Files to Create/Modify
- `container_manager/retry.py` - New file with retry logic
- `container_manager/queue.py` - Add retry methods to JobQueueManager
- `container_manager/models.py` - Add retry information fields
- New migration for retry fields

## Testing Requirements
- [ ] Test error classification for different error types
- [ ] Test exponential backoff calculation
- [ ] Test transient errors are retried
- [ ] Test permanent errors are not retried
- [ ] Test retry limit enforcement
- [ ] Test retry scheduling with delays
- [ ] Test manual retry functionality

### Critical Retry Tests

```python
def test_transient_error_retry(self):
    """Test transient errors trigger retry with backoff"""
    job = self.create_test_job()
    queue_manager.queue_job(job)
    
    # Mock transient failure
    with patch('container_manager.services.job_service.launch_job') as mock_launch:
        mock_launch.return_value.success = False
        mock_launch.return_value.error = "Connection refused"
        
        result = queue_manager.launch_job_with_retry(job)
        
        self.assertFalse(result['success'])
        self.assertTrue(result['retry_scheduled'])
        
        job.refresh_from_db()
        self.assertEqual(job.status, 'retrying')
        self.assertEqual(job.retry_count, 1)
        self.assertIsNotNone(job.scheduled_for)

def test_permanent_error_no_retry(self):
    """Test permanent errors don't trigger retry"""
    job = self.create_test_job()
    queue_manager.queue_job(job)
    
    # Mock permanent failure
    with patch('container_manager.services.job_service.launch_job') as mock_launch:
        mock_launch.return_value.success = False
        mock_launch.return_value.error = "Image not found"
        
        result = queue_manager.launch_job_with_retry(job)
        
        self.assertFalse(result['success'])
        self.assertFalse(result['retry_scheduled'])
        
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIsNone(job.queued_at)  # Removed from queue
```

## Dependencies
- Depends on: `04-queue-manager-basic.md` (basic queue manager)
- Depends on: `02-state-machine-validation.md` (state transitions)

## Notes
- Error classification uses regex patterns for flexibility
- Exponential backoff prevents overwhelming failing services
- Different retry strategies for different job priorities
- Dead letter queue pattern for permanently failed jobs
- Manual retry capability for administrative intervention
- Comprehensive error information stored for debugging