# Coverage Task: Base Executor Abstract Implementation

**Priority:** Medium
**Django Component:** Executors/Base Classes
**Estimated Effort:** Medium
**Current Coverage:** 43.9% (36/82 statements covered)

## Coverage Gap Summary
- Current coverage: 43.9%
- Target coverage: 75% (minimum standard)
- Missing lines: 12, 169, 172, 189-211, 223, 259, 285-295, 319-337, 346-364, 387
- Critical impact: Base executor functionality with significant gaps

## Uncovered Code Analysis
The `container_manager/executors/base.py` module provides the abstract base class for all container executors. Major uncovered areas include:

### Abstract Method Validation (lines 12, 169, 172)
- Abstract method enforcement and validation
- Subclass implementation verification
- Interface contract validation

### Configuration Management (lines 189-211, 223)
- Executor configuration validation and parsing
- Configuration parameter validation
- Default configuration handling
- Configuration error reporting

### Resource Management (lines 259, 285-295)
- Resource allocation and tracking
- Resource limit enforcement
- Resource cleanup operations
- Resource utilization monitoring

### Health Checking and Monitoring (lines 319-364, 387)
- Health check implementation patterns
- Monitoring and metrics collection
- Performance tracking
- Failure detection and reporting

## Suggested Tests

### Test 1: Abstract Method Enforcement
- **Purpose:** Test that abstract methods are properly enforced
- **Django-specific considerations:** Interface contracts, inheritance patterns
- **Test outline:**
  ```python
  def test_base_executor_cannot_be_instantiated(self):
      # Test that base executor cannot be instantiated directly
      with self.assertRaises(TypeError):
          ContainerExecutor({})

  def test_concrete_executor_must_implement_abstract_methods(self):
      # Test that concrete executors must implement all abstract methods
      class IncompleteExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          # Missing required methods
      
      with self.assertRaises(TypeError):
          IncompleteExecutor({})

  def test_concrete_executor_with_all_methods_succeeds(self):
      # Test that complete implementation succeeds
      class CompleteExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job):
              return True, "test-execution-id"
          
          def check_status(self, execution_id):
              return "running"
          
          def get_logs(self, execution_id):
              return "test logs"
          
          def cleanup(self, execution_id):
              return True
          
          def health_check(self):
              return True
      
      # Should instantiate without errors
      executor = CompleteExecutor({'test': 'config'})
      self.assertIsInstance(executor, ContainerExecutor)

  def test_abstract_method_signatures(self):
      # Test that abstract methods have correct signatures
      from inspect import signature
      
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job):
              return True, "test-id"
          
          def check_status(self, execution_id):
              return "running"
          
          def get_logs(self, execution_id):
              return "logs"
          
          def cleanup(self, execution_id):
              return True
          
          def health_check(self):
              return True
      
      executor = TestExecutor({})
      
      # Verify method signatures
      self.assertEqual(len(signature(executor.launch_job).parameters), 1)
      self.assertEqual(len(signature(executor.check_status).parameters), 1)
      self.assertEqual(len(signature(executor.get_logs).parameters), 1)
      self.assertEqual(len(signature(executor.cleanup).parameters), 1)
      self.assertEqual(len(signature(executor.health_check).parameters), 0)
  ```

### Test 2: Configuration Management and Validation
- **Purpose:** Test configuration handling in base executor
- **Django-specific considerations:** Settings integration, validation patterns
- **Test outline:**
  ```python
  def test_base_executor_configuration_initialization(self):
      # Test configuration initialization
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      config = {
          'timeout': 300,
          'max_retries': 3,
          'debug_mode': True
      }
      
      executor = TestExecutor(config)
      self.assertEqual(executor.config, config)
      self.assertEqual(executor.timeout, 300)
      self.assertEqual(executor.max_retries, 3)
      self.assertTrue(executor.debug_mode)

  def test_base_executor_default_configuration(self):
      # Test default configuration values
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"  
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})  # Empty config
      
      # Should have default values
      self.assertIsNotNone(executor.timeout)
      self.assertIsNotNone(executor.max_retries)
      self.assertIsInstance(executor.debug_mode, bool)

  def test_base_executor_configuration_validation(self):
      # Test configuration parameter validation
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      # Test invalid timeout
      with self.assertRaises(ValueError):
          TestExecutor({'timeout': -1})
      
      # Test invalid max_retries
      with self.assertRaises(ValueError):
          TestExecutor({'max_retries': -1})
      
      # Test invalid debug_mode
      with self.assertRaises(ValueError):
          TestExecutor({'debug_mode': 'invalid'})

  def test_base_executor_configuration_override(self):
      # Test configuration parameter override
      class TestExecutor(ContainerExecutor):
          DEFAULT_TIMEOUT = 600
          DEFAULT_MAX_RETRIES = 5
          
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      # Should use class defaults
      executor = TestExecutor({})
      self.assertEqual(executor.timeout, 600)
      self.assertEqual(executor.max_retries, 5)
      
      # Should override with config
      executor = TestExecutor({'timeout': 300, 'max_retries': 2})
      self.assertEqual(executor.timeout, 300)
      self.assertEqual(executor.max_retries, 2)
  ```

### Test 3: Resource Management and Tracking
- **Purpose:** Test resource management functionality in base executor
- **Django-specific considerations:** Resource tracking, cleanup operations
- **Test outline:**
  ```python
  def test_base_executor_resource_allocation_tracking(self):
      # Test resource allocation tracking
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})
      
      # Test resource allocation
      executor.allocate_resources('test-job-1', {'memory': 512, 'cpu': 1.0})
      
      resources = executor.get_allocated_resources('test-job-1')
      self.assertEqual(resources['memory'], 512)
      self.assertEqual(resources['cpu'], 1.0)

  def test_base_executor_resource_limit_enforcement(self):
      # Test resource limit enforcement
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
              self.max_memory = 1024
              self.max_cpu = 2.0
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})
      
      # Should allow allocation within limits
      self.assertTrue(executor.can_allocate_resources({'memory': 512, 'cpu': 1.0}))
      
      # Should reject allocation exceeding limits
      self.assertFalse(executor.can_allocate_resources({'memory': 2048, 'cpu': 1.0}))
      self.assertFalse(executor.can_allocate_resources({'memory': 512, 'cpu': 4.0}))

  def test_base_executor_resource_cleanup(self):
      # Test resource cleanup operations
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})
      
      # Allocate resources
      executor.allocate_resources('test-job-1', {'memory': 512, 'cpu': 1.0})
      executor.allocate_resources('test-job-2', {'memory': 256, 'cpu': 0.5})
      
      # Cleanup specific job resources
      executor.cleanup_resources('test-job-1')
      
      # Should have cleaned up job-1 but not job-2
      self.assertIsNone(executor.get_allocated_resources('test-job-1'))
      self.assertIsNotNone(executor.get_allocated_resources('test-job-2'))

  def test_base_executor_resource_utilization_monitoring(self):
      # Test resource utilization monitoring
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
              self.total_memory = 2048
              self.total_cpu = 4.0
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})
      
      # Allocate some resources
      executor.allocate_resources('test-job-1', {'memory': 512, 'cpu': 1.0})
      executor.allocate_resources('test-job-2', {'memory': 256, 'cpu': 0.5})
      
      # Check utilization
      utilization = executor.get_resource_utilization()
      
      self.assertEqual(utilization['memory_used'], 768)
      self.assertEqual(utilization['memory_total'], 2048)
      self.assertEqual(utilization['memory_percent'], 37.5)
      self.assertEqual(utilization['cpu_used'], 1.5)
      self.assertEqual(utilization['cpu_total'], 4.0)
      self.assertEqual(utilization['cpu_percent'], 37.5)
  ```

### Test 4: Health Checking and Monitoring
- **Purpose:** Test health checking and monitoring functionality
- **Django-specific considerations:** Health status reporting, metrics collection
- **Test outline:**
  ```python
  def test_base_executor_health_check_interface(self):
      # Test health check interface
      class HealthyExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      class UnhealthyExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
          
          def launch_job(self, job): return True, "test"
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return False
      
      healthy_executor = HealthyExecutor({})
      unhealthy_executor = UnhealthyExecutor({})
      
      self.assertTrue(healthy_executor.health_check())
      self.assertFalse(unhealthy_executor.health_check())

  def test_base_executor_metrics_collection(self):
      # Test metrics collection functionality
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
              self.job_count = 0
              self.error_count = 0
          
          def launch_job(self, job):
              self.job_count += 1
              return True, "test"
          
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})
      
      # Launch some jobs to generate metrics
      job = ContainerJobFactory.build()
      executor.launch_job(job)
      executor.launch_job(job)
      
      metrics = executor.get_metrics()
      self.assertEqual(metrics['jobs_launched'], 2)
      self.assertEqual(metrics['errors'], 0)
      self.assertIn('uptime', metrics)

  def test_base_executor_performance_tracking(self):
      # Test performance tracking
      class TestExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
              self.operation_times = []
          
          def launch_job(self, job):
              start_time = time.time()
              # Simulate work
              time.sleep(0.01)
              end_time = time.time()
              self.operation_times.append(end_time - start_time)
              return True, "test"
          
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return True
      
      executor = TestExecutor({})
      
      # Perform operations
      job = ContainerJobFactory.build()
      executor.launch_job(job)
      executor.launch_job(job)
      
      performance = executor.get_performance_stats()
      self.assertEqual(len(performance['operation_times']), 2)
      self.assertGreater(performance['average_time'], 0)
      self.assertGreater(performance['total_time'], 0)

  def test_base_executor_failure_detection(self):
      # Test failure detection and reporting
      class FailingExecutor(ContainerExecutor):
          def __init__(self, config):
              super().__init__(config)
              self.failure_count = 0
          
          def launch_job(self, job):
              self.failure_count += 1
              if self.failure_count > 2:
                  return False, "Too many failures"
              return True, "test"
          
          def check_status(self, execution_id): return "running"
          def get_logs(self, execution_id): return "logs"
          def cleanup(self, execution_id): return True
          def health_check(self): return self.failure_count <= 3
      
      executor = FailingExecutor({})
      job = ContainerJobFactory.build()
      
      # Should succeed initially
      self.assertTrue(executor.launch_job(job)[0])
      self.assertTrue(executor.launch_job(job)[0])
      self.assertTrue(executor.health_check())
      
      # Should fail after threshold
      self.assertFalse(executor.launch_job(job)[0])
      self.assertFalse(executor.health_check())
  ```

## Django Testing Patterns
- **Abstract Base Class Testing:** Test abstract method enforcement and inheritance
- **Configuration Testing:** Test configuration validation and default handling
- **Resource Management:** Test resource allocation, tracking, and cleanup
- **Interface Testing:** Test abstract interface contracts and implementations
- **Monitoring Testing:** Test health checks and metrics collection

## Definition of Done
- [ ] All uncovered abstract method validation functionality tested
- [ ] Configuration management and validation comprehensively covered  
- [ ] Resource management and tracking operations tested
- [ ] Health checking and monitoring functionality covered
- [ ] Performance tracking and failure detection tested
- [ ] Coverage target of 75% achieved
- [ ] Django testing best practices followed
- [ ] Abstract interface contracts verified