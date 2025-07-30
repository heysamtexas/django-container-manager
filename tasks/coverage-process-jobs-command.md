# Coverage Task: Process Container Jobs Management Command

**Priority:** High
**Django Component:** Management Commands/Job Processing
**Estimated Effort:** Large
**Current Coverage:** 56.8% (154/271 statements covered)

## Coverage Gap Summary
- Current coverage: 56.8%
- Target coverage: 80% (management command standard)
- Missing lines: 37-42, 163-164, 195-204, 268, 273, 303-352, 357-384, 391, 396, 401-404, 415, 425-426, 437-438, 443, 445-446, 448-449, 455-459, 468-474, 478-488, 492-525, 537, 542-543
- Critical impact: Core job processing workflow with significant gaps

## Uncovered Code Analysis
The `container_manager/management/commands/process_container_jobs.py` module implements the core job processing workflow. Major uncovered areas include:

### Job Processing Pipeline (lines 303-352)
- Batch job processing logic
- Job prioritization and queuing
- Concurrent job execution management
- Job failure recovery and retry logic

### Error Handling and Recovery (lines 357-404)
- Exception handling for job processing failures
- Dead letter queue management
- Job state consistency recovery
- Error notification and alerting

### Performance Monitoring (lines 415-488)
- Job processing metrics collection
- Performance bottleneck detection
- Resource utilization monitoring
- Processing rate optimization

### Advanced Job Management (lines 492-525)
- Job dependency management
- Scheduled job processing
- Job priority queue management
- Resource allocation optimization

## Suggested Tests

### Test 1: Batch Job Processing Pipeline
- **Purpose:** Test the core batch job processing workflow
- **Django-specific considerations:** ORM bulk operations, transaction management
- **Test outline:**
  ```python
  def test_process_pending_jobs_batch_success(self):
      # Test successful batch processing of multiple jobs
      command = Command()
      jobs = [
          ContainerJobFactory(status='pending') for _ in range(5)
      ]
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.return_value = True
          
          launched, errors = command.process_pending_jobs(batch_size=3)
          self.assertEqual(launched, 5)
          self.assertEqual(errors, 0)
          self.assertEqual(mock_launch.call_count, 5)

  def test_process_pending_jobs_with_failures(self):
      # Test batch processing with some job failures
      command = Command()
      jobs = [
          ContainerJobFactory(status='pending') for _ in range(3)
      ]
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          # First job succeeds, second fails, third succeeds
          mock_launch.side_effect = [True, False, True]
          
          launched, errors = command.process_pending_jobs()
          self.assertEqual(launched, 2)
          self.assertEqual(errors, 1)

  def test_process_pending_jobs_empty_queue(self):
      # Test processing when no pending jobs exist
      command = Command()
      
      launched, errors = command.process_pending_jobs()
      self.assertEqual(launched, 0)
      self.assertEqual(errors, 0)

  def test_process_pending_jobs_with_host_filter(self):
      # Test processing jobs filtered by specific host
      command = Command()
      host1 = ExecutorHostFactory(name='host1')
      host2 = ExecutorHostFactory(name='host2')
      
      job1 = ContainerJobFactory(status='pending', docker_host=host1)
      job2 = ContainerJobFactory(status='pending', docker_host=host2)
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.return_value = True
          
          launched, errors = command.process_pending_jobs(host_filter='host1')
          self.assertEqual(launched, 1)
          mock_launch.assert_called_once_with(job1, mock.ANY, mock.ANY)
  ```

### Test 2: Job Prioritization and Queuing
- **Purpose:** Test job priority handling and queue management
- **Django-specific considerations:** ORM ordering, priority queues
- **Test outline:**
  ```python
  def test_get_pending_jobs_priority_order(self):
      # Test that jobs are retrieved in priority order
      command = Command()
      
      # Create jobs with different priorities
      low_priority = ContainerJobFactory(status='pending', priority=1)
      high_priority = ContainerJobFactory(status='pending', priority=10)
      medium_priority = ContainerJobFactory(status='pending', priority=5)
      
      jobs = command.get_pending_jobs()
      job_ids = [job.id for job in jobs]
      
      # Should be ordered by priority (highest first)
      self.assertEqual(job_ids[0], high_priority.id)
      self.assertEqual(job_ids[1], medium_priority.id)
      self.assertEqual(job_ids[2], low_priority.id)

  def test_get_pending_jobs_with_created_time_tiebreaker(self):
      # Test priority tiebreaker using creation time
      command = Command()
      
      # Create jobs with same priority but different creation times
      earlier_job = ContainerJobFactory(status='pending', priority=5)
      later_job = ContainerJobFactory(status='pending', priority=5)
      
      jobs = command.get_pending_jobs()
      
      # Earlier job should come first when priorities are equal
      self.assertEqual(jobs[0].id, earlier_job.id)
      self.assertEqual(jobs[1].id, later_job.id)

  def test_concurrent_job_limit_enforcement(self):
      # Test that concurrent job limits are enforced
      command = Command()
      
      # Create multiple running jobs
      running_jobs = [
          ContainerJobFactory(status='running') for _ in range(3)
      ]
      pending_jobs = [
          ContainerJobFactory(status='pending') for _ in range(5)
      ]
      
      with patch.object(command, 'get_max_concurrent_jobs') as mock_max:
          mock_max.return_value = 3  # Already at limit
          
          with patch.object(command, 'launch_single_job') as mock_launch:
              launched, errors = command.process_pending_jobs()
              # Should not launch any new jobs due to limit
              self.assertEqual(launched, 0)
              mock_launch.assert_not_called()
  ```

### Test 3: Error Handling and Recovery
- **Purpose:** Test comprehensive error handling in job processing
- **Django-specific considerations:** Transaction rollback, error logging
- **Test outline:**
  ```python
  def test_handle_job_processing_exception(self):
      # Test handling of unexpected exceptions during processing
      command = Command()
      job = ContainerJobFactory(status='pending')
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.side_effect = Exception("Unexpected error")
          
          # Should handle exception gracefully
          launched, errors = command.process_pending_jobs()
          self.assertEqual(launched, 0)
          self.assertEqual(errors, 1)
          
          # Job should remain in pending state for retry
          job.refresh_from_db()
          self.assertEqual(job.status, 'pending')

  def test_job_retry_logic_on_failure(self):
      # Test retry logic for failed jobs
      command = Command()
      job = ContainerJobFactory(status='pending', retry_count=0)
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.return_value = False  # Launch failure
          
          launched, errors = command.process_pending_jobs()
          
          job.refresh_from_db()
          # Should increment retry count
          self.assertEqual(job.retry_count, 1)
          self.assertEqual(job.status, 'pending')  # Ready for retry

  def test_job_max_retries_exceeded(self):
      # Test handling when job exceeds max retry attempts
      command = Command()
      job = ContainerJobFactory(status='pending', retry_count=5)
      
      with patch.object(command, 'get_max_retries') as mock_max_retries:
          mock_max_retries.return_value = 3
          
          with patch.object(command, 'launch_single_job') as mock_launch:
              mock_launch.return_value = False
              
              launched, errors = command.process_pending_jobs()
              
              job.refresh_from_db()
              # Should mark as failed after exceeding retries
              self.assertEqual(job.status, 'failed')
              self.assertIn('Max retries exceeded', job.error_message or '')

  def test_dead_letter_queue_processing(self):
      # Test handling of jobs in dead letter queue
      command = Command()
      dead_job = ContainerJobFactory(
          status='failed',
          retry_count=5,
          error_message='Max retries exceeded'
      )
      
      # Dead letter jobs should not be processed
      with patch.object(command, 'launch_single_job') as mock_launch:
          launched, errors = command.process_pending_jobs()
          
          self.assertEqual(launched, 0)
          mock_launch.assert_not_called()
  ```

### Test 4: Performance Monitoring and Metrics
- **Purpose:** Test job processing performance monitoring
- **Django-specific considerations:** Metrics collection, performance logging
- **Test outline:**
  ```python
  def test_job_processing_metrics_collection(self):
      # Test collection of job processing metrics
      command = Command()
      jobs = [ContainerJobFactory(status='pending') for _ in range(3)]
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.return_value = True
          
          start_time = time.time()
          launched, errors = command.process_pending_jobs()
          end_time = time.time()
          
          # Should collect timing metrics
          processing_time = end_time - start_time
          self.assertGreater(processing_time, 0)

  def test_resource_utilization_monitoring(self):
      # Test monitoring of system resource utilization
      command = Command()
      
      with patch('psutil.cpu_percent') as mock_cpu:
          with patch('psutil.virtual_memory') as mock_memory:
              mock_cpu.return_value = 75.0
              mock_memory.return_value.percent = 60.0
              
              metrics = command.get_system_metrics()
              self.assertEqual(metrics['cpu_percent'], 75.0)
              self.assertEqual(metrics['memory_percent'], 60.0)

  def test_processing_rate_calculation(self):
      # Test calculation of job processing rate
      command = Command()
      jobs = [ContainerJobFactory(status='pending') for _ in range(10)]
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.return_value = True
          
          start_time = time.time()
          launched, errors = command.process_pending_jobs()
          end_time = time.time()
          
          processing_time = end_time - start_time
          rate = launched / processing_time if processing_time > 0 else 0
          
          self.assertGreater(rate, 0)
          self.assertEqual(launched, 10)

  def test_bottleneck_detection(self):
      # Test detection of processing bottlenecks
      command = Command()
      
      # Simulate slow job processing
      with patch.object(command, 'launch_single_job') as mock_launch:
          def slow_launch(*args):
              time.sleep(0.1)  # Simulate slow processing
              return True
          
          mock_launch.side_effect = slow_launch
          
          job = ContainerJobFactory(status='pending')
          start_time = time.time()
          launched, errors = command.process_pending_jobs()
          end_time = time.time()
          
          # Should detect slow processing
          processing_time = end_time - start_time
          self.assertGreater(processing_time, 0.05)  # At least 50ms for one job
  ```

### Test 5: Advanced Job Management Features
- **Purpose:** Test advanced job management functionality
- **Django-specific considerations:** Complex queries, job relationships
- **Test outline:**
  ```python
  def test_job_dependency_management(self):
      # Test handling of job dependencies
      command = Command()
      
      parent_job = ContainerJobFactory(status='completed')
      dependent_job = ContainerJobFactory(
          status='pending',
          depends_on=parent_job
      )
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          mock_launch.return_value = True
          
          launched, errors = command.process_pending_jobs()
          
          # Dependent job should be processed since parent is completed
          self.assertEqual(launched, 1)
          mock_launch.assert_called_once_with(dependent_job, mock.ANY, mock.ANY)

  def test_job_dependency_blocking(self):
      # Test that jobs are blocked by incomplete dependencies
      command = Command()
      
      parent_job = ContainerJobFactory(status='running')  # Still running
      dependent_job = ContainerJobFactory(
          status='pending',
          depends_on=parent_job
      )
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          launched, errors = command.process_pending_jobs()
          
          # Dependent job should not be processed
          self.assertEqual(launched, 0)
          mock_launch.assert_not_called()

  def test_scheduled_job_processing(self):
      # Test processing of scheduled jobs
      command = Command()
      
      # Create job scheduled for the future
      future_time = django_timezone.now() + timedelta(hours=1)
      scheduled_job = ContainerJobFactory(
          status='pending',
          scheduled_time=future_time
      )
      
      with patch.object(command, 'launch_single_job') as mock_launch:
          launched, errors = command.process_pending_jobs()
          
          # Future job should not be processed yet
          self.assertEqual(launched, 0)
          mock_launch.assert_not_called()

  def test_resource_allocation_optimization(self):
      # Test resource allocation across multiple jobs
      command = Command()
      
      # Create jobs with different resource requirements
      high_resource_job = ContainerJobFactory(
          status='pending',
          memory_limit=1024,
          cpu_limit=2.0
      )
      low_resource_job = ContainerJobFactory(
          status='pending',
          memory_limit=256,
          cpu_limit=0.5
      )
      
      with patch.object(command, 'get_available_resources') as mock_resources:
          mock_resources.return_value = {'memory': 1280, 'cpu': 2.5}
          
          with patch.object(command, 'launch_single_job') as mock_launch:
              mock_launch.return_value = True
              
              launched, errors = command.process_pending_jobs()
              
              # Should launch both jobs as resources allow
              self.assertEqual(launched, 2)
  ```

## Django Testing Patterns
- **Management Command Testing:** Test command functionality with Django's call_command
- **Batch Processing:** Test ORM bulk operations and transaction management
- **Performance Testing:** Mock time and resource monitoring functions
- **Error Recovery:** Test transaction rollback and job state consistency
- **Concurrency:** Test job processing limits and resource allocation

## Definition of Done
- [ ] All uncovered job processing pipeline functionality tested
- [ ] Error handling and recovery mechanisms comprehensively covered
- [ ] Performance monitoring and metrics collection tested
- [ ] Advanced job management features (dependencies, scheduling) covered
- [ ] Batch processing and concurrent job limits tested
- [ ] Coverage target of 80% achieved for management command
- [ ] Django testing best practices followed
- [ ] Resource allocation and optimization logic tested