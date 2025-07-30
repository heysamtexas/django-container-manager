# Coverage Task: Docker Service Backward Compatibility Layer

**Priority:** High  
**Django Component:** Services/Docker Integration
**Estimated Effort:** Large
**Current Coverage:** 42.7% (88/206 statements covered)

## Coverage Gap Summary
- Current coverage: 42.7%
- Target coverage: 75% (minimum standard)
- Missing lines: 131-162, 166-181, 185-214, 218-222, 226-230, 234-251, 255-264, 271-285, 289-294, 298-326
- Critical impact: Docker container lifecycle management with significant gaps

## Uncovered Code Analysis
The `container_manager/docker_service.py` module serves as a backward compatibility layer for Docker operations. Major uncovered areas include:

### Container Lifecycle Operations (lines 131-214)
- Container creation and configuration
- Image pulling and management
- Container startup and monitoring
- Error handling for Docker API failures

### Container Management Methods (lines 218-285)
- Container stopping and cleanup
- Resource management and limits
- Volume and network configuration
- Container status monitoring

### Bulk Operations and Utilities (lines 289-326)
- Batch container operations
- Container discovery and listing
- Resource cleanup and garbage collection
- Docker host health checking

## Suggested Tests

### Test 1: Container Creation and Configuration
- **Purpose:** Test Docker container creation with various configurations
- **Django-specific considerations:** Model integration, executor delegation
- **Test outline:**
  ```python
  def test_create_container_success(self):
      # Test successful container creation
      service = DockerService()
      host = ExecutorHostFactory(executor_type='docker')
      job = ContainerJobFactory(docker_host=host)
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.create_container.return_value = 'container_id'
          result = service.create_container(job)
          self.assertEqual(result, 'container_id')

  def test_create_container_with_environment_variables(self):
      # Test container creation with environment variables
      service = DockerService()
      job = ContainerJobFactory(
          environment_variables='KEY1=value1\nKEY2=value2'
      )
      
      with patch.object(service, '_get_executor') as mock_executor:
          service.create_container(job)
          mock_executor.return_value.create_container.assert_called_once()

  def test_create_container_executor_error(self):
      # Test container creation failure
      service = DockerService()
      job = ContainerJobFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.create_container.side_effect = ExecutorError("Creation failed")
          with self.assertRaises(ContainerExecutionError):
              service.create_container(job)
  ```

### Test 2: Image Management Operations
- **Purpose:** Test Docker image pulling and management
- **Django-specific considerations:** Settings integration, timeout handling
- **Test outline:**
  ```python
  def test_pull_image_success(self):
      # Test successful image pulling
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.pull_image.return_value = True
          result = service.pull_image(host, 'ubuntu:latest')
          self.assertTrue(result)

  def test_pull_image_timeout(self):
      # Test image pull timeout handling
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.pull_image.side_effect = TimeoutError("Pull timeout")
          with self.assertRaises(ContainerExecutionError):
              service.pull_image(host, 'ubuntu:latest')

  def test_pull_image_not_found(self):
      # Test pulling non-existent image
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.pull_image.side_effect = NotFound("Image not found")
          with self.assertRaises(ContainerExecutionError):
              service.pull_image(host, 'nonexistent:image')
  ```

### Test 3: Container Lifecycle Management
- **Purpose:** Test container start, stop, and cleanup operations
- **Django-specific considerations:** Job state management, cleanup workflows
- **Test outline:**
  ```python
  def test_start_container_success(self):
      # Test successful container startup
      service = DockerService()
      job = ContainerJobFactory(container_id='test_container')
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value._start_container.return_value = True
          result = service.start_container(job)
          self.assertTrue(result)

  def test_stop_container_success(self):
      # Test successful container stopping
      service = DockerService()
      job = ContainerJobFactory(container_id='test_container')
      
      with patch.object(service, '_get_executor') as mock_executor:
          service.stop_container(job)
          mock_executor.return_value.stop_container.assert_called_once_with('test_container')

  def test_remove_container_success(self):
      # Test successful container removal
      service = DockerService()
      job = ContainerJobFactory(container_id='test_container')
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.cleanup.return_value = True
          result = service.remove_container(job)
          self.assertTrue(result)

  def test_cleanup_container_not_found(self):
      # Test cleanup when container doesn't exist
      service = DockerService()
      job = ContainerJobFactory(container_id='missing_container')
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.cleanup.side_effect = NotFound("Container not found")
          # Should not raise exception, just log and continue
          result = service.remove_container(job)
          self.assertFalse(result)
  ```

### Test 4: Bulk Operations and Container Discovery
- **Purpose:** Test batch operations and container listing
- **Django-specific considerations:** Django ORM integration, bulk queries
- **Test outline:**
  ```python
  def test_list_containers_success(self):
      # Test container listing
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.list_containers.return_value = [
              {'id': 'container1', 'status': 'running'},
              {'id': 'container2', 'status': 'stopped'}
          ]
          containers = service.list_containers(host)
          self.assertEqual(len(containers), 2)

  def test_cleanup_old_containers_success(self):
      # Test bulk cleanup of old containers
      service = DockerService()
      host = ExecutorHostFactory()
      cutoff_time = django_timezone.now() - timedelta(hours=24)
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.cleanup_old_containers.return_value = 3
          count = service.cleanup_old_containers(host, cutoff_time)
          self.assertEqual(count, 3)

  def test_get_container_stats(self):
      # Test container resource statistics
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_stats = {'cpu_percent': 50.0, 'memory_usage': 256}
          mock_executor.return_value.get_container_stats.return_value = mock_stats
          stats = service.get_container_stats(host, 'container_id')
          self.assertEqual(stats['cpu_percent'], 50.0)
  ```

### Test 5: Health Checking and Monitoring
- **Purpose:** Test Docker host health monitoring
- **Django-specific considerations:** Model status updates, periodic tasks
- **Test outline:**
  ```python
  def test_health_check_healthy_host(self):
      # Test health check for responsive Docker host
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.health_check.return_value = True
          is_healthy = service.health_check(host)
          self.assertTrue(is_healthy)

  def test_health_check_unhealthy_host(self):
      # Test health check for unresponsive Docker host
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.health_check.side_effect = DockerConnectionError("Connection failed")
          is_healthy = service.health_check(host)
          self.assertFalse(is_healthy)

  def test_get_docker_version(self):
      # Test Docker version retrieval
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          mock_executor.return_value.get_version.return_value = "20.10.7"
          version = service.get_docker_version(host)
          self.assertEqual(version, "20.10.7")
  ```

### Test 6: Error Handling and Edge Cases
- **Purpose:** Test comprehensive error handling scenarios
- **Django-specific considerations:** Exception logging, graceful degradation
- **Test outline:**
  ```python
  def test_executor_not_found_error(self):
      # Test behavior when executor cannot be created
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_get_executor:
          mock_get_executor.side_effect = ExecutorConnectionError("No executor available")
          with self.assertRaises(DockerConnectionError):
              service.create_container(ContainerJobFactory(docker_host=host))

  def test_connection_retry_logic(self):
      # Test connection retry behavior
      service = DockerService()
      host = ExecutorHostFactory()
      
      with patch.object(service, '_get_executor') as mock_executor:
          # First call fails, second succeeds
          mock_executor.return_value.health_check.side_effect = [
              DockerConnectionError("Temporary failure"),
              True
          ]
          # Test retry logic implementation
          pass  # Implementation depends on actual retry logic

  def test_concurrent_operations(self):
      # Test thread safety of service operations
      service = DockerService()
      host1 = ExecutorHostFactory()
      host2 = ExecutorHostFactory()
      
      # Test that multiple hosts can be managed concurrently
      executor1 = service._get_executor(host1)
      executor2 = service._get_executor(host2)
      self.assertIsNotNone(executor1)
      self.assertIsNotNone(executor2)
  ```

## Django Testing Patterns
- **Service Layer Mocking:** Mock DockerExecutor to isolate service logic
- **Exception Handling:** Test Docker API exceptions and service error handling
- **Model Integration:** Test service interactions with Django models
- **Backward Compatibility:** Ensure legacy interface behavior is preserved
- **Resource Management:** Test container lifecycle and cleanup operations

## Definition of Done
- [ ] All uncovered container lifecycle operations tested
- [ ] Image management and pulling operations covered
- [ ] Bulk operations and container discovery tested
- [ ] Health checking and monitoring functionality covered
- [ ] Comprehensive error handling scenarios tested
- [ ] Coverage target of 75% achieved
- [ ] Django testing best practices followed
- [ ] Backward compatibility preserved