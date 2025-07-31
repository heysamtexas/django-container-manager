# Coverage Task: Bulk Job Operations Manager

**Priority:** High
**Django Component:** Bulk Operations/Job Management
**Estimated Effort:** Large
**Current Coverage:** 80.2% (158/197 statements covered)

## Coverage Gap Summary
- Current coverage: 80.2%
- Target coverage: 85% (business logic standard)
- Missing lines: 149-150, 175-183, 234-241, 281, 289-292, 328, 336-339, 383-385, 407-414, 452-453
- Critical impact: Bulk job creation and management operations with gaps

## Uncovered Code Analysis
The `container_manager/bulk_operations.py` module provides efficient bulk operations for managing large numbers of container jobs. Major uncovered areas include:

### Bulk Job Creation Error Handling (lines 149-150, 175-183)
- Database transaction rollback on bulk creation failures
- Validation error handling for invalid job parameters
- Resource exhaustion handling during bulk operations
- Batch size optimization and splitting logic

### Job Migration and Host Transfer (lines 234-241, 289-292)
- Job migration between different executor hosts
- Host availability validation during migration
- Data consistency during job transfers
- Migration rollback on failure

### Advanced Bulk Operations (lines 328, 336-339, 383-414)
- Bulk job status updates and state transitions
- Conditional bulk operations based on job criteria
- Performance optimization for large job sets
- Bulk job deletion and cleanup operations

### Resource Management and Optimization (lines 452-453)
- Resource allocation across bulk job operations
- Performance monitoring and optimization
- Memory usage optimization for large datasets
- Batch processing efficiency improvements

## Suggested Tests

### Test 1: Bulk Job Creation with Error Handling
- **Purpose:** Test bulk job creation with various error scenarios
- **Django-specific considerations:** Database transactions, bulk_create operations
- **Test outline:**
  ```python
  def test_create_jobs_bulk_success(self):
      # Test successful bulk job creation
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      jobs, errors = manager.create_jobs_bulk(
          docker_image='alpine:latest',
          count=5,
          user=user,
          host=host,
          command='echo "bulk test"'
      )
      
      self.assertEqual(len(jobs), 5)
      self.assertEqual(len(errors), 0)
      
      # Verify jobs were created in database
      created_jobs = ContainerJob.objects.filter(docker_image='alpine:latest')
      self.assertEqual(created_jobs.count(), 5)
      
      for job in created_jobs:
          self.assertEqual(job.user, user)
          self.assertEqual(job.docker_host, host)

  def test_create_jobs_bulk_exceeds_limit(self):
      # Test bulk creation that exceeds maximum limit
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      with self.assertRaises(ValueError) as context:
          manager.create_jobs_bulk(
              docker_image='alpine:latest',
              count=MAX_BULK_CREATION_LIMIT + 1,
              user=user,
              host=host
          )
      
      self.assertIn('exceeds maximum', str(context.exception))

  def test_create_jobs_bulk_invalid_parameters(self):
      # Test bulk creation with invalid parameters
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      jobs, errors = manager.create_jobs_bulk(
          docker_image='',  # Invalid empty image
          count=3,
          user=user,
          host=host
      )
      
      self.assertEqual(len(jobs), 0)
      self.assertGreater(len(errors), 0)
      self.assertTrue(any('image' in error.lower() for error in errors))

  def test_create_jobs_bulk_database_error(self):
      # Test handling of database errors during bulk creation
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      with patch('container_manager.models.ContainerJob.objects.bulk_create') as mock_bulk_create:
          mock_bulk_create.side_effect = Exception("Database error")
          
          jobs, errors = manager.create_jobs_bulk(
              docker_image='alpine:latest',
              count=3,
              user=user,
              host=host
          )
          
          self.assertEqual(len(jobs), 0)
          self.assertGreater(len(errors), 0)
          self.assertTrue(any('database' in error.lower() for error in errors))

  def test_create_jobs_bulk_with_batching(self):
      # Test bulk creation with custom batch size
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      with patch('container_manager.models.ContainerJob.objects.bulk_create') as mock_bulk_create:
          mock_bulk_create.return_value = []
          
          jobs, errors = manager.create_jobs_bulk(
              docker_image='alpine:latest',
              count=250,
              user=user,
              host=host,
              batch_size=100
          )
          
          # Should be called 3 times: 100, 100, 50
          self.assertEqual(mock_bulk_create.call_count, 3)
  ```

### Test 2: Job Migration and Host Transfer
- **Purpose:** Test job migration between different executor hosts
- **Django-specific considerations:** Database updates, foreign key changes
- **Test outline:**
  ```python
  def test_migrate_jobs_to_host_success(self):
      # Test successful job migration to different host
      manager = BulkJobManager()
      source_host = ExecutorHostFactory(name='source-host')
      target_host = ExecutorHostFactory(name='target-host')
      
      jobs = [
          ContainerJobFactory(docker_host=source_host, status='pending')
          for _ in range(3)
      ]
      
      migrated_count, errors = manager.migrate_jobs_to_host(
          jobs=[job.id for job in jobs],
          target_host=target_host
      )
      
      self.assertEqual(migrated_count, 3)
      self.assertEqual(len(errors), 0)
      
      # Verify jobs were migrated
      for job in jobs:
          job.refresh_from_db()
          self.assertEqual(job.docker_host, target_host)

  def test_migrate_jobs_to_host_invalid_status(self):
      # Test migration rejection for jobs with invalid status
      manager = BulkJobManager()
      source_host = ExecutorHostFactory()
      target_host = ExecutorHostFactory()
      
      running_job = ContainerJobFactory(docker_host=source_host, status='running')
      pending_job = ContainerJobFactory(docker_host=source_host, status='pending')
      
      migrated_count, errors = manager.migrate_jobs_to_host(
          jobs=[running_job.id, pending_job.id],
          target_host=target_host
      )
      
      self.assertEqual(migrated_count, 1)  # Only pending job migrated
      self.assertEqual(len(errors), 1)
      
      # Verify only pending job was migrated
      running_job.refresh_from_db()
      pending_job.refresh_from_db()
      self.assertEqual(running_job.docker_host, source_host)  # Unchanged
      self.assertEqual(pending_job.docker_host, target_host)  # Migrated

  def test_migrate_jobs_host_unavailable(self):
      # Test migration when target host is unavailable
      manager = BulkJobManager()
      source_host = ExecutorHostFactory()
      target_host = ExecutorHostFactory(is_active=False)
      
      jobs = [ContainerJobFactory(docker_host=source_host, status='pending')]
      
      migrated_count, errors = manager.migrate_jobs_to_host(
          jobs=[job.id for job in jobs],
          target_host=target_host
      )
      
      self.assertEqual(migrated_count, 0)
      self.assertGreater(len(errors), 0)
      self.assertTrue(any('unavailable' in error.lower() for error in errors))

  def test_migrate_jobs_with_validation_errors(self):
      # Test migration with validation errors
      manager = BulkJobManager()
      source_host = ExecutorHostFactory(executor_type='docker')
      target_host = ExecutorHostFactory(executor_type='cloudrun')
      
      # Job that's incompatible with CloudRun
      incompatible_job = ContainerJobFactory(
          docker_host=source_host,
          status='pending',
          docker_image='localhost:5000/private-image'  # Won't work on CloudRun
      )
      
      migrated_count, errors = manager.migrate_jobs_to_host(
          jobs=[incompatible_job.id],
          target_host=target_host
      )
      
      self.assertEqual(migrated_count, 0)
      self.assertGreater(len(errors), 0)
  ```

### Test 3: Bulk Status Updates and State Management
- **Purpose:** Test bulk job status updates and state transitions
- **Django-specific considerations:** Bulk update operations, state validation
- **Test outline:**
  ```python
  def test_bulk_update_job_status_success(self):
      # Test successful bulk status updates
      manager = BulkJobManager()
      jobs = [
          ContainerJobFactory(status='pending') for _ in range(5)
      ]
      
      updated_count, errors = manager.bulk_update_job_status(
          job_ids=[job.id for job in jobs],
          new_status='cancelled',
          reason='Bulk cancellation'
      )
      
      self.assertEqual(updated_count, 5)
      self.assertEqual(len(errors), 0)
      
      # Verify status updates
      for job in jobs:
          job.refresh_from_db()
          self.assertEqual(job.status, 'cancelled')
          self.assertIn('Bulk cancellation', job.status_message or '')

  def test_bulk_update_invalid_status_transition(self):
      # Test bulk update with invalid status transitions
      manager = BulkJobManager()
      completed_job = ContainerJobFactory(status='completed')
      pending_job = ContainerJobFactory(status='pending')
      
      updated_count, errors = manager.bulk_update_job_status(
          job_ids=[completed_job.id, pending_job.id],
          new_status='running'  # Invalid transition from completed
      )
      
      self.assertEqual(updated_count, 1)  # Only pending job updated
      self.assertEqual(len(errors), 1)
      
      # Verify only valid transition occurred
      completed_job.refresh_from_db()
      pending_job.refresh_from_db()
      self.assertEqual(completed_job.status, 'completed')  # Unchanged
      self.assertEqual(pending_job.status, 'running')  # Updated

  def test_bulk_delete_jobs_success(self):
      # Test successful bulk job deletion
      manager = BulkJobManager()
      jobs = [
          ContainerJobFactory(status='completed') for _ in range(3)
      ]
      job_ids = [job.id for job in jobs]
      
      deleted_count, errors = manager.bulk_delete_jobs(
          job_ids=job_ids,
          force=False
      )
      
      self.assertEqual(deleted_count, 3)
      self.assertEqual(len(errors), 0)
      
      # Verify jobs were deleted
      remaining_jobs = ContainerJob.objects.filter(id__in=job_ids)
      self.assertEqual(remaining_jobs.count(), 0)

  def test_bulk_delete_jobs_with_active_jobs(self):
      # Test bulk deletion with active jobs (should be rejected)
      manager = BulkJobManager()
      running_job = ContainerJobFactory(status='running')
      completed_job = ContainerJobFactory(status='completed')
      
      deleted_count, errors = manager.bulk_delete_jobs(
          job_ids=[running_job.id, completed_job.id],
          force=False
      )
      
      self.assertEqual(deleted_count, 1)  # Only completed job deleted
      self.assertEqual(len(errors), 1)
      
      # Verify only completed job was deleted
      self.assertFalse(ContainerJob.objects.filter(id=running_job.id).exists())
      self.assertTrue(ContainerJob.objects.filter(id=completed_job.id).exists())

  def test_bulk_cleanup_old_jobs(self):
      # Test bulk cleanup of old completed jobs
      manager = BulkJobManager()
      
      # Create old completed jobs
      old_time = timezone.now() - timedelta(days=30)
      old_jobs = []
      for _ in range(3):
          job = ContainerJobFactory(status='completed')
          job.finished_at = old_time
          job.save()
          old_jobs.append(job)
      
      # Create recent job (should not be cleaned up)
      recent_job = ContainerJobFactory(status='completed')
      
      cleaned_count = manager.bulk_cleanup_old_jobs(days_old=7)
      
      self.assertEqual(cleaned_count, 3)
      
      # Verify old jobs were cleaned up but recent job remains
      for job in old_jobs:
          self.assertFalse(ContainerJob.objects.filter(id=job.id).exists())
      self.assertTrue(ContainerJob.objects.filter(id=recent_job.id).exists())
  ```

### Test 4: Performance Optimization and Resource Management
- **Purpose:** Test performance optimization for bulk operations
- **Django-specific considerations:** Query optimization, memory usage
- **Test outline:**
  ```python
  def test_bulk_operations_memory_efficiency(self):
      # Test memory efficiency of bulk operations
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      # Create large number of jobs to test memory usage
      with patch('container_manager.bulk_operations.MAX_BULK_CREATION_LIMIT', 1000):
          jobs, errors = manager.create_jobs_bulk(
              docker_image='alpine:latest',
              count=1000,
              user=user,
              host=host,
              batch_size=100  # Small batch size for memory efficiency
          )
          
          self.assertEqual(len(jobs), 1000)
          self.assertEqual(len(errors), 0)

  def test_bulk_operations_query_optimization(self):
      # Test that bulk operations use optimized queries
      manager = BulkJobManager()
      jobs = [ContainerJobFactory(status='pending') for _ in range(10)]
      
      with self.assertNumQueries(2):  # Should use minimal queries
          updated_count, errors = manager.bulk_update_job_status(
              job_ids=[job.id for job in jobs],
              new_status='cancelled'
          )
          
          self.assertEqual(updated_count, 10)

  def test_bulk_operations_transaction_integrity(self):
      # Test transaction integrity during bulk operations
      manager = BulkJobManager()
      user = UserFactory()
      host = ExecutorHostFactory()
      
      # Simulate partial failure during bulk creation
      with patch('container_manager.models.ContainerJob.objects.bulk_create') as mock_bulk_create:
          # First batch succeeds, second batch fails
          mock_bulk_create.side_effect = [
              [Mock(id=1), Mock(id=2)],  # First batch success
              Exception("Database error")  # Second batch fails
          ]
          
          jobs, errors = manager.create_jobs_bulk(
              docker_image='alpine:latest',
              count=4,
              user=user,
              host=host,
              batch_size=2
          )
          
          # Should have partial results and errors
          self.assertEqual(len(jobs), 2)  # First batch succeeded
          self.assertGreater(len(errors), 0)

  def test_bulk_operations_resource_monitoring(self):
      # Test resource usage monitoring during bulk operations
      manager = BulkJobManager()
      
      # Mock resource monitoring
      with patch('psutil.virtual_memory') as mock_memory:
          mock_memory.return_value.percent = 80.0  # High memory usage
          
          # Should handle high resource usage gracefully
          metrics = manager.get_bulk_operation_metrics()
          self.assertIn('memory_usage', metrics)
          self.assertEqual(metrics['memory_usage'], 80.0)
  ```

## Django Testing Patterns
- **Bulk Operations Testing:** Test Django bulk_create and bulk_update operations
- **Transaction Testing:** Test database transaction integrity and rollback
- **Performance Testing:** Test query optimization and memory efficiency
- **Error Recovery:** Test partial failure handling and cleanup
- **Resource Monitoring:** Test system resource usage during bulk operations

## Definition of Done
- [ ] All uncovered bulk job creation and management functionality tested
- [ ] Job migration and host transfer operations comprehensively covered
- [ ] Bulk status updates and state management tested
- [ ] Performance optimization and resource management covered
- [ ] Error handling and transaction integrity tested
- [ ] Coverage target of 85% achieved for business logic
- [ ] Django testing best practices followed
- [ ] Memory efficiency and query optimization verified