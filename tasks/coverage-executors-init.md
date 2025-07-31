# Coverage Task: Executors Init Module

**Priority:** High
**Django Component:** Executors/Factory Pattern
**Estimated Effort:** Small
**Current Coverage:** 23.5% (4/17 statements covered)

## Coverage Gap Summary
- Current coverage: 23.5%
- Target coverage: 75% (minimum standard)
- Missing lines: 48-69
- Critical impact: Executor factory function completely uncovered

## Uncovered Code Analysis
The `container_manager/executors/__init__.py` module implements the executor factory pattern. Major uncovered areas include:

### Factory Function Implementation (lines 48-69)
- Executor type validation and error handling
- Dynamic executor instantiation for different backends
- Configuration validation and passing
- Error handling for unknown executor types

## Suggested Tests

### Test 1: Executor Factory Function Basic Operations
- **Purpose:** Test the get_executor factory function with various executor types
- **Django-specific considerations:** Module imports, configuration handling
- **Test outline:**
  ```python
  from container_manager.executors import get_executor
  from container_manager.executors.exceptions import ExecutorConfigurationError
  
  def test_get_executor_docker_type(self):
      # Test factory function with docker executor type
      executor = get_executor('docker', {'docker_host': 'unix:///var/run/docker.sock'})
      self.assertIsNotNone(executor)
      self.assertEqual(executor.__class__.__name__, 'DockerExecutor')

  def test_get_executor_cloudrun_type(self):
      # Test factory function with cloudrun executor type
      config = {'project_id': 'test-project', 'region': 'us-central1'}
      executor = get_executor('cloudrun', config)
      self.assertIsNotNone(executor)
      self.assertEqual(executor.__class__.__name__, 'CloudRunExecutor')

  def test_get_executor_mock_type(self):
      # Test factory function with mock executor type
      executor = get_executor('mock', {})
      self.assertIsNotNone(executor)
      self.assertEqual(executor.__class__.__name__, 'MockExecutor')

  def test_get_executor_empty_type_error(self):
      # Test factory function with empty executor type
      with self.assertRaises(ExecutorConfigurationError) as context:
          get_executor('', {})
      self.assertIn('executor_type cannot be empty', str(context.exception))

  def test_get_executor_none_type_error(self):
      # Test factory function with None executor type
      with self.assertRaises(ExecutorConfigurationError) as context:
          get_executor(None, {})
      self.assertIn('executor_type cannot be empty', str(context.exception))

  def test_get_executor_unknown_type_error(self):
      # Test factory function with unknown executor type
      with self.assertRaises(ExecutorConfigurationError) as context:
          get_executor('unknown-executor', {})
      self.assertIn('Unknown executor type: unknown-executor', str(context.exception))

  def test_get_executor_with_none_config(self):
      # Test factory function with None config (should use default empty dict)
      executor = get_executor('docker', None)
      self.assertIsNotNone(executor)
      self.assertEqual(executor.__class__.__name__, 'DockerExecutor')

  def test_get_executor_without_config(self):
      # Test factory function without config parameter
      executor = get_executor('docker')
      self.assertIsNotNone(executor)
      self.assertEqual(executor.__class__.__name__, 'DockerExecutor')
  ```

## Django Testing Patterns
- **Factory Pattern Testing:** Test dynamic module imports and instantiation
- **Error Handling:** Test various error conditions and validation
- **Configuration Passing:** Verify config is properly passed to executors
- **Import Testing:** Test dynamic imports work correctly

## Definition of Done
- [ ] All factory function branches tested
- [ ] All executor types covered (docker, cloudrun, mock)
- [ ] Error cases comprehensively tested (empty type, unknown type)
- [ ] Configuration handling tested (None, empty, valid configs)
- [ ] Coverage target of 75% achieved
- [ ] Django testing best practices followed