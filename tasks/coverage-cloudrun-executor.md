# Coverage Task: Cloud Run Executor Implementation

**Priority:** High
**Django Component:** Executors/Cloud Integration  
**Estimated Effort:** Large
**Current Coverage:** 30.7% (117/381 statements covered)

## Coverage Gap Summary
- Current coverage: 30.7%
- Target coverage: 75% (minimum standard)
- Missing lines: 73, 105, 118, 151-165, 169-183, 195-269, 281-295, 299, 303-314, 318-328, 333-342, 346-353, 357, 361-362, 374-396, 400-404, 408-415, 419-430, 434-447, 453-456, 463-481, 485-488, 492-493, 505-537, 549-555, 573, 581-589, 593-610, 614-622, 628-646, 650-654, 674-680, 684-736, 774-792, 812-815, 820
- Critical impact: Google Cloud Run integration with extensive uncovered functionality

## Uncovered Code Analysis
The `container_manager/executors/cloudrun.py` module implements Google Cloud Run integration. Major uncovered areas include:

### Core Cloud Run Operations (lines 151-269)
- Job creation and configuration for Cloud Run
- Service account and IAM handling
- Resource allocation and scaling configuration
- Environment variable management for Cloud Run jobs

### Job Lifecycle Management (lines 281-430)
- Job execution and monitoring
- Status polling and completion detection
- Log retrieval from Cloud Logging
- Job cleanup and resource management

### Error Handling and Retry Logic (lines 434-537)
- Cloud API error handling and retry mechanisms
- Authentication and permission error handling
- Rate limiting and quota management
- Network connectivity error handling

### Configuration and Validation (lines 549-736)
- Cloud Run configuration validation
- Resource limits and constraints checking
- Region and project configuration
- Service account permissions validation

## Suggested Tests

### Test 1: Cloud Run Job Creation and Configuration
- **Purpose:** Test Google Cloud Run job creation with various configurations
- **Django-specific considerations:** Model integration, configuration validation
- **Test outline:**
  ```python
  @unittest.skipUnless(False, "Cloud Run tests require optional dependencies")
  def test_create_cloudrun_job_success(self):
      # Test successful Cloud Run job creation
      config = {
          'project_id': 'test-project',
          'region': 'us-central1',
          'service_account': 'test@project.iam.gserviceaccount.com'
      }
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory(
          image='gcr.io/test-project/test-image:latest',
          command='echo "Hello Cloud Run"'
      )
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.create_job.return_value.name = 'test-job-123'
          result = executor.create_job(job)
          self.assertIsNotNone(result)
          mock_client.return_value.create_job.assert_called_once()

  def test_create_cloudrun_job_with_environment_variables(self):
      # Test job creation with environment variables
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory(
          environment_variables='ENV_VAR1=value1\nENV_VAR2=value2'
      )
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          executor.create_job(job)
          # Verify environment variables are properly configured
          call_args = mock_client.return_value.create_job.call_args
          self.assertIsNotNone(call_args)

  def test_create_cloudrun_job_authentication_error(self):
      # Test job creation with authentication failure
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory()
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.create_job.side_effect = Exception("Authentication failed")
          with self.assertRaises(ExecutorError):
              executor.create_job(job)
  ```

### Test 2: Job Execution and Monitoring
- **Purpose:** Test Cloud Run job execution and status monitoring
- **Django-specific considerations:** Job state management, async operations
- **Test outline:**
  ```python
  def test_execute_cloudrun_job_success(self):
      # Test successful job execution
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory()
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_execution = Mock()
          mock_execution.name = 'test-execution-123'
          mock_client.return_value.run_job.return_value = mock_execution
          
          result = executor.execute(job)
          self.assertEqual(result, 'test-execution-123')

  def test_check_cloudrun_job_status_running(self):
      # Test status checking for running job
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.run_v2.ExecutionsClient') as mock_client:
          mock_execution = Mock()
          mock_execution.status.state = 'RUNNING'
          mock_client.return_value.get_execution.return_value = mock_execution
          
          status = executor.check_status('test-execution-123')
          self.assertEqual(status, 'running')

  def test_check_cloudrun_job_status_completed(self):
      # Test status checking for completed job
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.run_v2.ExecutionsClient') as mock_client:
          mock_execution = Mock()
          mock_execution.status.state = 'SUCCEEDED'
          mock_execution.status.completion_time = Mock()
          mock_client.return_value.get_execution.return_value = mock_execution
          
          status = executor.check_status('test-execution-123')
          self.assertEqual(status, 'completed')

  def test_check_cloudrun_job_status_failed(self):
      # Test status checking for failed job
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.run_v2.ExecutionsClient') as mock_client:
          mock_execution = Mock()
          mock_execution.status.state = 'FAILED'
          mock_execution.status.failure_message = 'Job failed'
          mock_client.return_value.get_execution.return_value = mock_execution
          
          status = executor.check_status('test-execution-123')
          self.assertEqual(status, 'failed')
  ```

### Test 3: Log Retrieval and Management
- **Purpose:** Test Cloud Logging integration for job logs
- **Django-specific considerations:** Log formatting, large log handling
- **Test outline:**
  ```python
  def test_get_cloudrun_logs_success(self):
      # Test successful log retrieval
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.logging.Client') as mock_logging_client:
          mock_entries = [
              Mock(payload='Log line 1', timestamp=Mock()),
              Mock(payload='Log line 2', timestamp=Mock())
          ]
          mock_logging_client.return_value.list_entries.return_value = mock_entries
          
          logs = executor.get_logs('test-execution-123')
          self.assertIn('Log line 1', logs)
          self.assertIn('Log line 2', logs)

  def test_get_cloudrun_logs_no_logs(self):
      # Test log retrieval when no logs available
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.logging.Client') as mock_logging_client:
          mock_logging_client.return_value.list_entries.return_value = []
          
          logs = executor.get_logs('test-execution-123')
          self.assertEqual(logs, '')

  def test_get_cloudrun_logs_api_error(self):
      # Test log retrieval with API error
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.logging.Client') as mock_logging_client:
          mock_logging_client.return_value.list_entries.side_effect = Exception("Logging API error")
          
          logs = executor.get_logs('test-execution-123')
          self.assertIn('Error retrieving logs', logs)
  ```

### Test 4: Configuration Validation and Setup
- **Purpose:** Test Cloud Run configuration validation
- **Django-specific considerations:** Settings integration, validation logic
- **Test outline:**
  ```python
  def test_validate_cloudrun_config_valid(self):
      # Test validation of valid configuration
      config = {
          'project_id': 'test-project',
          'region': 'us-central1',
          'service_account': 'test@project.iam.gserviceaccount.com'
      }
      executor = CloudRunExecutor(config)
      
      errors = executor.validate_configuration()
      self.assertEqual(len(errors), 0)

  def test_validate_cloudrun_config_missing_project(self):
      # Test validation with missing project ID
      config = {'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      errors = executor.validate_configuration()
      self.assertGreater(len(errors), 0)
      self.assertTrue(any('project_id' in error for error in errors))

  def test_validate_cloudrun_config_invalid_region(self):
      # Test validation with invalid region
      config = {
          'project_id': 'test-project',
          'region': 'invalid-region'
      }
      executor = CloudRunExecutor(config)
      
      errors = executor.validate_configuration()
      self.assertGreater(len(errors), 0)
      self.assertTrue(any('region' in error for error in errors))

  def test_validate_job_for_cloudrun_execution(self):
      # Test job validation for Cloud Run execution
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory(
          image='gcr.io/test-project/test-image:latest',
          command='echo "test"'
      )
      
      errors = executor.validate_job_for_execution(job)
      self.assertEqual(len(errors), 0)
  ```

### Test 5: Error Handling and Retry Logic
- **Purpose:** Test comprehensive error handling for Cloud Run operations
- **Django-specific considerations:** Exception logging, graceful degradation
- **Test outline:**
  ```python
  def test_cloudrun_api_rate_limiting(self):
      # Test handling of API rate limiting
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory()
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.create_job.side_effect = Exception("Rate limit exceeded")
          
          with self.assertRaises(ExecutorError):
              executor.create_job(job)

  def test_cloudrun_permission_denied(self):
      # Test handling of permission denied errors
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      job = ContainerJobFactory()
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.create_job.side_effect = Exception("Permission denied")
          
          with self.assertRaises(ExecutorError):
              executor.create_job(job)

  def test_cloudrun_network_connectivity_error(self):
      # Test handling of network connectivity issues
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.get_job.side_effect = Exception("Network timeout")
          
          with self.assertRaises(ExecutorConnectionError):
              executor.health_check()
  ```

### Test 6: Resource Management and Cleanup
- **Purpose:** Test Cloud Run resource cleanup and management
- **Django-specific considerations:** Resource lifecycle, cost management
- **Test outline:**
  ```python
  def test_cleanup_cloudrun_job_success(self):
      # Test successful job cleanup
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.delete_job.return_value = Mock()
          
          result = executor.cleanup('test-job-123')
          self.assertTrue(result)
          mock_client.return_value.delete_job.assert_called_once()

  def test_cleanup_cloudrun_job_not_found(self):
      # Test cleanup of non-existent job
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.run_v2.JobsClient') as mock_client:
          mock_client.return_value.delete_job.side_effect = Exception("Job not found")
          
          # Should handle gracefully
          result = executor.cleanup('non-existent-job')
          self.assertFalse(result)

  def test_get_cloudrun_resource_usage(self):
      # Test resource usage monitoring
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = CloudRunExecutor(config)
      
      with patch('google.cloud.monitoring.MetricServiceClient') as mock_client:
          mock_client.return_value.list_time_series.return_value = []
          
          usage = executor.get_resource_usage('test-execution-123')
          self.assertIsInstance(usage, dict)
  ```

## Django Testing Patterns
- **Optional Dependency Testing:** Use `@unittest.skipUnless()` for Cloud Run tests
- **Mock Google Cloud APIs:** Comprehensive mocking of Google Cloud client libraries
- **Configuration Testing:** Test various Cloud Run configuration scenarios
- **Error Simulation:** Test Cloud API errors and network failures
- **Resource Management:** Test job lifecycle and cleanup operations

## Definition of Done
- [ ] All uncovered Cloud Run operations tested with mocked Google Cloud APIs
- [ ] Job creation, execution, and monitoring functionality covered
- [ ] Log retrieval and Cloud Logging integration tested
- [ ] Configuration validation and error handling comprehensively tested
- [ ] Resource management and cleanup operations covered
- [ ] Coverage target of 75% achieved
- [ ] Django testing best practices followed
- [ ] Optional dependency handling properly implemented