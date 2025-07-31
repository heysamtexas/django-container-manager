# Coverage Task: Docker Executor Implementation

**Priority:** High
**Django Component:** Executors/Docker Integration
**Estimated Effort:** Large
**Current Coverage:** 62.7% (207/330 statements covered)

## Coverage Gap Summary
- Current coverage: 62.7%
- Target coverage: 75% (minimum standard)
- Missing lines: 36-55, 81, 141-174, 178-196, 214, 228, 258, 290, 293, 299, 337-340, 355, 372-374, 416, 420, 426, 433, 444-448, 470-474, 510-512, 516-548, 552-557, 562, 582-602
- Critical impact: Core Docker execution engine with significant gaps

## Uncovered Code Analysis
The `container_manager/executors/docker.py` module implements the core Docker execution functionality. Major uncovered areas include:

### Container Creation and Validation (lines 36-55, 141-174)
- Job validation before container creation
- Docker image validation and pulling
- Container configuration setup
- Resource limits and constraints validation
- Network and volume configuration

### Container Lifecycle Management (lines 178-196, 337-374)
- Container starting and stopping operations
- Container status monitoring and health checks
- Container resource management
- Cleanup and removal operations

### Error Handling and Recovery (lines 444-474, 510-548)
- Docker API error handling
- Connection failure recovery
- Container state inconsistency handling
- Resource cleanup on failure

### Advanced Docker Features (lines 516-602)
- Network management and port mapping
- Volume mounting and data persistence
- Docker swarm integration (if applicable)
- Multi-host Docker coordination

## Suggested Tests

### Test 1: Container Creation and Configuration
- **Purpose:** Test Docker container creation with various configurations
- **Django-specific considerations:** Model integration, configuration validation
- **Test outline:**
  ```python
  def test_docker_create_container_success(self):
      # Test successful container creation
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(
          docker_image='alpine:latest',
          command='echo "Hello Docker"'
      )
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.id = 'test-container-123'
          mock_client.return_value.containers.create.return_value = mock_container
          
          container_id = executor._create_container(job)
          self.assertEqual(container_id, 'test-container-123')
          mock_client.return_value.containers.create.assert_called_once()

  def test_docker_create_container_with_environment_variables(self):
      # Test container creation with environment variables
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(
          override_environment='ENV_VAR1=value1\nENV_VAR2=value2'
      )
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.id = 'test-container-456'
          mock_client.return_value.containers.create.return_value = mock_container
          
          container_id = executor._create_container(job)
          self.assertIsNotNone(container_id)
          
          # Verify environment variables were passed
          call_args = mock_client.return_value.containers.create.call_args
          self.assertIn('environment', call_args.kwargs)

  def test_docker_create_container_with_resource_limits(self):
      # Test container creation with memory and CPU limits
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(
          memory_limit=512,
          cpu_limit=1.0
      )
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.id = 'test-container-789'
          mock_client.return_value.containers.create.return_value = mock_container
          
          container_id = executor._create_container(job)
          self.assertIsNotNone(container_id)
          
          # Verify resource limits were set
          call_args = mock_client.return_value.containers.create.call_args
          self.assertIn('mem_limit', call_args.kwargs)
          self.assertIn('cpu_quota', call_args.kwargs)

  def test_docker_validate_job_success(self):
      # Test successful job validation
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(
          docker_image='nginx:latest',
          command='nginx -g "daemon off;"'
      )
      
      # Should not raise any exceptions
      try:
          executor._validate_job(job)
      except Exception:
          self.fail("_validate_job raised exception unexpectedly")

  def test_docker_validate_job_missing_image(self):
      # Test job validation with missing image
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(
          docker_image='',
          command='echo test'
      )
      
      with self.assertRaises(ExecutorError):
          executor._validate_job(job)
  ```

### Test 2: Container Lifecycle Operations
- **Purpose:** Test container starting, stopping, and status monitoring
- **Django-specific considerations:** Job state management, async operations
- **Test outline:**
  ```python
  def test_docker_start_container_success(self):
      # Test successful container start
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory()
      container_id = 'test-container-123'
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_client.return_value.containers.get.return_value = mock_container
          
          success = executor._start_container(job, container_id)
          self.assertTrue(success)
          mock_container.start.assert_called_once()

  def test_docker_start_container_failure(self):
      # Test container start failure
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory()
      container_id = 'test-container-123'
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.start.side_effect = Exception("Start failed")
          mock_client.return_value.containers.get.return_value = mock_container
          
          with self.assertRaises(ExecutorError):
              executor._start_container(job, container_id)

  def test_docker_check_status_running(self):
      # Test status check for running container
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(container_id='test-container-123')
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.status = 'running'
          mock_client.return_value.containers.get.return_value = mock_container
          
          status = executor.check_status('test-container-123')
          self.assertEqual(status, 'running')

  def test_docker_check_status_exited(self):
      # Test status check for exited container
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(container_id='test-container-123')
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.status = 'exited'
          mock_client.return_value.containers.get.return_value = mock_container
          
          status = executor.check_status('test-container-123')
          self.assertEqual(status, 'exited')

  def test_docker_check_status_container_not_found(self):
      # Test status check for non-existent container
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.containers.get.side_effect = NotFound("Container not found")
          
          status = executor.check_status('non-existent-container')
          self.assertEqual(status, 'not-found')
  ```

### Test 3: Log Retrieval and Monitoring
- **Purpose:** Test Docker container log retrieval and monitoring
- **Django-specific considerations:** Log formatting, large log handling
- **Test outline:**
  ```python
  def test_docker_get_logs_success(self):
      # Test successful log retrieval
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(container_id='test-container-123')
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.logs.return_value = b'Log line 1\nLog line 2\n'
          mock_client.return_value.containers.get.return_value = mock_container
          
          logs = executor.get_logs('test-container-123')
          self.assertIn('Log line 1', logs)
          self.assertIn('Log line 2', logs)

  def test_docker_get_logs_empty(self):
      # Test log retrieval for container with no logs
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.logs.return_value = b''
          mock_client.return_value.containers.get.return_value = mock_container
          
          logs = executor.get_logs('test-container-123')
          self.assertEqual(logs, '')

  def test_docker_get_logs_container_not_found(self):
      # Test log retrieval for non-existent container
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.containers.get.side_effect = NotFound("Container not found")
          
          logs = executor.get_logs('non-existent-container')
          self.assertIn('Container not found', logs)

  def test_docker_get_logs_with_tail_limit(self):
      # Test log retrieval with tail limit
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.logs.return_value = b'Log line 1\nLog line 2\nLog line 3\n'
          mock_client.return_value.containers.get.return_value = mock_container
          
          logs = executor.get_logs('test-container-123', tail=2)
          
          # Verify tail parameter was passed
          mock_container.logs.assert_called_with(tail=2, stdout=True, stderr=True)
  ```

### Test 4: Error Handling and Recovery
- **Purpose:** Test comprehensive error handling in Docker operations
- **Django-specific considerations:** Exception logging, graceful degradation
- **Test outline:**
  ```python
  def test_docker_connection_error_handling(self):
      # Test handling of Docker connection errors
      executor = DockerExecutor({'docker_host': 'tcp://unreachable:2376'})
      job = ContainerJobFactory()
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.side_effect = Exception("Connection refused")
          
          success, error_msg = executor.launch_job(job)
          self.assertFalse(success)
          self.assertIn('Connection refused', error_msg)

  def test_docker_api_error_handling(self):
      # Test handling of Docker API errors
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory()
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.containers.create.side_effect = Exception("API error")
          
          success, error_msg = executor.launch_job(job)
          self.assertFalse(success)
          self.assertIn('API error', error_msg)

  def test_docker_resource_exhaustion_handling(self):
      # Test handling of resource exhaustion
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory(memory_limit=16384)  # 16GB
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.containers.create.side_effect = Exception("Insufficient memory")
          
          success, error_msg = executor.launch_job(job)
          self.assertFalse(success)
          self.assertIn('Insufficient memory', error_msg)

  def test_docker_cleanup_on_failure(self):
      # Test cleanup operations when container fails to start
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      job = ContainerJobFactory()
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_container.id = 'failed-container-123'
          mock_container.start.side_effect = Exception("Start failed")
          mock_client.return_value.containers.create.return_value = mock_container
          mock_client.return_value.containers.get.return_value = mock_container
          
          success, error_msg = executor.launch_job(job)
          self.assertFalse(success)
          
          # Verify cleanup was attempted
          mock_container.remove.assert_called_once()
  ```

### Test 5: Resource Management and Cleanup
- **Purpose:** Test Docker resource management and cleanup operations
- **Django-specific considerations:** Resource lifecycle, cost management
- **Test outline:**
  ```python
  def test_docker_cleanup_container_success(self):
      # Test successful container cleanup
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_client.return_value.containers.get.return_value = mock_container
          
          result = executor.cleanup('test-container-123')
          self.assertTrue(result)
          mock_container.remove.assert_called_once()

  def test_docker_cleanup_container_not_found(self):
      # Test cleanup of non-existent container
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.containers.get.side_effect = NotFound("Container not found")
          
          # Should handle gracefully
          result = executor.cleanup('non-existent-container')
          self.assertTrue(result)  # Consider cleanup successful if container doesn't exist

  def test_docker_get_resource_usage(self):
      # Test resource usage monitoring
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_container = Mock()
          mock_stats = {
              'memory_stats': {'usage': 536870912, 'limit': 1073741824},
              'cpu_stats': {'cpu_usage': {'total_usage': 1000000000}},
              'precpu_stats': {'cpu_usage': {'total_usage': 900000000}}
          }
          mock_container.stats.return_value = [mock_stats]
          mock_client.return_value.containers.get.return_value = mock_container
          
          usage = executor.get_resource_usage('test-container-123')
          self.assertIsInstance(usage, dict)
          self.assertIn('memory_usage', usage)
          self.assertIn('cpu_usage', usage)

  def test_docker_health_check(self):
      # Test Docker daemon health check
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.ping.return_value = True
          
          is_healthy = executor.health_check()
          self.assertTrue(is_healthy)

  def test_docker_health_check_failure(self):
      # Test health check failure
      executor = DockerExecutor({'docker_host': 'unix:///var/run/docker.sock'})
      
      with patch('docker.DockerClient') as mock_client:
          mock_client.return_value.ping.side_effect = Exception("Connection failed")
          
          is_healthy = executor.health_check()
          self.assertFalse(is_healthy)
  ```

## Django Testing Patterns
- **Docker Integration Testing:** Mock Docker client for consistent test behavior
- **Resource Management:** Test container lifecycle and cleanup operations
- **Error Simulation:** Test Docker API errors and connection failures
- **Configuration Testing:** Test various Docker host configurations
- **Log Handling:** Test log retrieval and formatting

## Definition of Done
- [ ] All uncovered Docker container operations tested with mocked Docker client
- [ ] Container creation, lifecycle, and cleanup functionality covered
- [ ] Log retrieval and monitoring operations tested
- [ ] Error handling and recovery mechanisms comprehensively tested
- [ ] Resource management and usage monitoring covered
- [ ] Coverage target of 75% achieved
- [ ] Django testing best practices followed
- [ ] Multi-host Docker support tested