# Coverage Task: Services Module Business Logic

**Priority:** High
**Django Component:** Services/Business Logic
**Estimated Effort:** Medium
**Current Coverage:** 0.0% (0/43 statements covered)

## Coverage Gap Summary
- Current coverage: 0.0%
- Target coverage: 85% (business logic standard)
- Missing lines: 9-222 (entire module uncovered)
- Critical impact: Core service layer with no test coverage

## Uncovered Code Analysis
The `container_manager/services.py` module contains critical business logic for job management operations using executor polymorphism. This is a complete coverage gap for essential Django service layer functionality:

### JobManagementService (lines 20-179)
- `validate_job_for_execution()` - Critical validation logic
- `get_job_execution_details()` - Display logic for job information  
- `prepare_job_for_launch()` - Pre-launch validation and preparation
- `get_host_display_info()` - Host display information logic

### JobValidationService (lines 181-217)
- `validate_job()` - Job validation wrapper
- `is_job_valid()` - Boolean validation check

### Module-level instances (lines 219-222)
- Default service instances for application use

## Suggested Tests

### Test 1: JobManagementService Validation Tests
- **Purpose:** Test job validation logic with various executor types
- **Django-specific considerations:** Model validation, executor factory integration
- **Test outline:**
  ```python
  def test_validate_job_for_execution_success(self):
      # Test successful validation with valid job
      service = JobManagementService()
      job = ContainerJobFactory(status='pending')
      errors = service.validate_job_for_execution(job)
      self.assertEqual(errors, [])

  def test_validate_job_for_execution_invalid_job(self):
      # Test validation failure with invalid job
      service = JobManagementService()
      job = ContainerJobFactory(docker_host=None)
      errors = service.validate_job_for_execution(job)
      self.assertGreater(len(errors), 0)

  def test_validate_job_for_execution_executor_error(self):
      # Test validation when executor factory fails
      mock_factory = Mock()
      mock_factory.get_executor.side_effect = Exception("Factory error")
      service = JobManagementService(mock_factory)
      job = ContainerJobFactory()
      errors = service.validate_job_for_execution(job)
      self.assertIn("Validation failed: Factory error", errors)
  ```

### Test 2: Job Execution Details Tests
- **Purpose:** Test polymorphic display logic for different executor types
- **Django-specific considerations:** Model display methods, executor polymorphism
- **Test outline:**
  ```python
  def test_get_job_execution_details_success(self):
      # Test successful details retrieval
      service = JobManagementService()
      job = ContainerJobFactory()
      details = service.get_job_execution_details(job)
      self.assertIn('type_name', details)
      self.assertIn('id_label', details)
      self.assertIn('id_value', details)
      self.assertIn('status_detail', details)

  def test_get_job_execution_details_executor_error(self):
      # Test error handling in details retrieval
      mock_factory = Mock()
      mock_factory.get_executor.side_effect = Exception("Executor error")
      service = JobManagementService(mock_factory)
      job = ContainerJobFactory()
      details = service.get_job_execution_details(job)
      self.assertEqual(details['type_name'], 'Unknown Executor')
      self.assertIn('Error: Executor error', details['status_detail'])
  ```

### Test 3: Job Launch Preparation Tests
- **Purpose:** Test comprehensive launch preparation workflow
- **Django-specific considerations:** Job state management, validation integration
- **Test outline:**
  ```python
  def test_prepare_job_for_launch_valid_job(self):
      # Test successful job preparation
      service = JobManagementService()
      job = ContainerJobFactory(status='pending')
      success, errors = service.prepare_job_for_launch(job)
      self.assertTrue(success)
      self.assertEqual(errors, [])

  def test_prepare_job_for_launch_invalid_job(self):
      # Test preparation failure with invalid job
      service = JobManagementService()
      job = ContainerJobFactory(docker_host=None)
      success, errors = service.prepare_job_for_launch(job)
      self.assertFalse(success)
      self.assertGreater(len(errors), 0)
  ```

### Test 4: Host Display Information Tests
- **Purpose:** Test executor-specific host display logic
- **Django-specific considerations:** Model display methods, executor type handling
- **Test outline:**
  ```python
  def test_get_host_display_info_docker(self):
      # Test Docker host display information
      service = JobManagementService()
      host = ExecutorHostFactory(executor_type='docker')
      info = service.get_host_display_info(host)
      self.assertEqual(info['type_name'], 'Docker')
      self.assertIn('name', info)
      self.assertIn('connection_info', info)

  def test_get_host_display_info_cloudrun(self):
      # Test Cloud Run host display information
      service = JobManagementService()
      host = ExecutorHostFactory(
          executor_type='cloudrun',
          executor_config={'region': 'us-central1'}
      )
      info = service.get_host_display_info(host)
      self.assertEqual(info['type_name'], 'Cloud Run')
      self.assertIn('Region: us-central1', info['connection_info'])
  ```

### Test 5: JobValidationService Tests
- **Purpose:** Test specialized validation service functionality
- **Django-specific considerations:** Service composition, validation logic
- **Test outline:**
  ```python
  def test_job_validation_service_validate_job(self):
      # Test validation service wrapper
      validator = JobValidationService()
      job = ContainerJobFactory()
      errors = validator.validate_job(job)
      self.assertIsInstance(errors, list)

  def test_job_validation_service_is_job_valid(self):
      # Test boolean validation check
      validator = JobValidationService()
      valid_job = ContainerJobFactory(status='pending')
      self.assertTrue(validator.is_job_valid(valid_job))
      
      invalid_job = ContainerJobFactory(docker_host=None)
      self.assertFalse(validator.is_job_valid(invalid_job))
  ```

### Test 6: Module-level Service Instances Tests
- **Purpose:** Test default service instances availability
- **Django-specific considerations:** Module imports, singleton behavior
- **Test outline:**
  ```python
  def test_module_level_service_instances(self):
      # Test that module-level instances are available
      from container_manager.services import job_service, job_validator
      self.assertIsInstance(job_service, JobManagementService)
      self.assertIsInstance(job_validator, JobValidationService)
  ```

## Django Testing Patterns
- **Service Layer Testing:** Focus on business logic validation and error handling
- **Mocking External Dependencies:** Mock ExecutorFactory for isolated service testing
- **Model Integration:** Use Django model factories for test data creation
- **Exception Handling:** Test both success and failure scenarios thoroughly
- **Polymorphic Behavior:** Test service behavior with different executor types

## Definition of Done
- [ ] All service methods have comprehensive test coverage
- [ ] Error handling paths are tested with appropriate mocks
- [ ] Executor polymorphism is tested with different executor types
- [ ] Module-level service instances are tested
- [ ] Coverage target of 85% achieved for business logic
- [ ] Django testing best practices followed
- [ ] Edge cases covered (invalid jobs, missing hosts, factory errors)