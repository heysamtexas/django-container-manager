# Coverage Task: Executor Factory and Job Routing

**Priority:** High
**Django Component:** Executors/Factory Pattern
**Estimated Effort:** Medium
**Current Coverage:** 83.2% (79/95 statements covered)

## Coverage Gap Summary
- Current coverage: 83.2%
- Target coverage: 90% (new feature standard)
- Missing lines: 38-40, 81, 94, 114, 176-186, 195-200, 215, 219
- Critical impact: Job routing and executor selection logic with gaps

## Uncovered Code Analysis
The `container_manager/executors/factory.py` module provides executor factory pattern implementation for job routing and executor selection. Major uncovered areas include:

### Executor Availability Checking (lines 38-40, 81, 94)
- `_is_executor_available()` method for checking executor health
- Executor capacity and resource availability validation
- Fallback executor selection when primary is unavailable

### Advanced Routing Logic (lines 114, 176-186)
- Weight-based routing algorithm implementation
- Load balancing across multiple executor hosts
- Geographic and resource-based routing decisions
- Routing preference and constraint handling

### Error Handling and Fallback (lines 195-200, 215, 219)
- Exception handling for routing failures
- Fallback routing when preferred executors fail
- Configuration error handling and validation
- Routing decision logging and debugging

## Suggested Tests

### Test 1: Executor Availability and Health Checking
- **Purpose:** Test executor availability checking and health validation
- **Django-specific considerations:** Database queries, executor health status
- **Test outline:**
  ```python
  def test_is_executor_available_healthy_executor(self):
      # Test availability check for healthy executor
      factory = ExecutorFactory()
      host = ExecutorHostFactory(
          is_active=True,
          last_health_check=django_timezone.now()
      )
      
      with patch.object(factory, 'get_executor') as mock_get_executor:
          mock_executor = Mock()
          mock_executor.health_check.return_value = True
          mock_get_executor.return_value = mock_executor
          
          is_available = factory._is_executor_available(host.executor_type)
          self.assertTrue(is_available)
          mock_executor.health_check.assert_called_once()

  def test_is_executor_available_unhealthy_executor(self):
      # Test availability check for unhealthy executor
      factory = ExecutorFactory()
      host = ExecutorHostFactory(
          is_active=True,
          last_health_check=django_timezone.now() - timedelta(hours=2)
      )
      
      with patch.object(factory, 'get_executor') as mock_get_executor:
          mock_executor = Mock()
          mock_executor.health_check.return_value = False
          mock_get_executor.return_value = mock_executor
          
          is_available = factory._is_executor_available(host.executor_type)
          self.assertFalse(is_available)

  def test_is_executor_available_inactive_host(self):
      # Test availability check for inactive host
      factory = ExecutorFactory()
      host = ExecutorHostFactory(is_active=False)
      
      is_available = factory._is_executor_available(host.executor_type)
      self.assertFalse(is_available)

  def test_is_executor_available_exception_handling(self):
      # Test availability check with executor exceptions
      factory = ExecutorFactory()
      host = ExecutorHostFactory(is_active=True)
      
      with patch.object(factory, 'get_executor') as mock_get_executor:
          mock_get_executor.side_effect = ExecutorConfigurationError("Config error")
          
          is_available = factory._is_executor_available(host.executor_type)
          self.assertFalse(is_available)

  def test_executor_capacity_checking(self):
      # Test executor capacity and resource availability
      factory = ExecutorFactory()
      host = ExecutorHostFactory(max_concurrent_jobs=5)
      
      # Create jobs up to capacity
      for _ in range(5):
          ContainerJobFactory(docker_host=host, status='running')
      
      with patch.object(factory, 'get_executor') as mock_get_executor:
          mock_executor = Mock()
          mock_executor.health_check.return_value = True
          mock_executor.get_capacity_info.return_value = {
              'max_jobs': 5,
              'current_jobs': 5,
              'available_slots': 0
          }
          mock_get_executor.return_value = mock_executor
          
          is_available = factory._is_executor_available(host.executor_type)
          self.assertFalse(is_available)  # At capacity
  ```

### Test 2: Advanced Routing Logic and Load Balancing
- **Purpose:** Test weight-based routing and load balancing algorithms
- **Django-specific considerations:** Database queries, host selection logic
- **Test outline:**
  ```python
  def test_route_job_to_host_weight_based_selection(self):
      # Test weight-based host selection
      factory = ExecutorFactory()
      
      # Create hosts with different weights
      host1 = ExecutorHostFactory(routing_weight=10, is_active=True)
      host2 = ExecutorHostFactory(routing_weight=30, is_active=True)
      host3 = ExecutorHostFactory(routing_weight=60, is_active=True)
      
      job = ContainerJobFactory.build()
      
      # Mock random selection to ensure deterministic testing
      with patch('random.choices') as mock_choices:
          mock_choices.return_value = [host2]
          
          selected_host = factory.route_job_to_host(job)
          self.assertEqual(selected_host, host2)
          
          # Verify weights were used correctly
          mock_choices.assert_called_once()
          call_args = mock_choices.call_args
          hosts = call_args[0][0]
          weights = call_args[1]['weights']
          
          self.assertIn(host1, hosts)
          self.assertIn(host2, hosts)
          self.assertIn(host3, hosts)
          self.assertEqual(len(weights), 3)

  def test_route_job_to_host_no_available_hosts(self):
      # Test routing when no hosts are available
      factory = ExecutorFactory()
      
      # Create inactive hosts
      ExecutorHostFactory(is_active=False)
      ExecutorHostFactory(is_active=False)
      
      job = ContainerJobFactory.build()
      
      selected_host = factory.route_job_to_host(job)
      self.assertIsNone(selected_host)

  def test_route_job_to_host_resource_constraints(self):
      # Test routing with resource constraints
      factory = ExecutorFactory()
      
      # Host with insufficient resources
      low_resource_host = ExecutorHostFactory(
          max_memory_mb=512,
          max_cpu_cores=1.0,
          is_active=True
      )
      
      # Host with sufficient resources
      high_resource_host = ExecutorHostFactory(
          max_memory_mb=2048,
          max_cpu_cores=4.0,
          is_active=True
      )
      
      # Job requiring high resources
      job = ContainerJobFactory.build(
          memory_limit=1024,
          cpu_limit=2.0
      )
      
      with patch.object(factory, '_check_resource_availability') as mock_check:
          mock_check.side_effect = lambda host, job: host == high_resource_host
          
          selected_host = factory.route_job_to_host(job)
          self.assertEqual(selected_host, high_resource_host)

  def test_route_job_to_executor_type_preferred_executor(self):
      # Test routing with preferred executor type
      factory = ExecutorFactory()
      
      docker_host = ExecutorHostFactory(executor_type='docker', is_active=True)
      cloudrun_host = ExecutorHostFactory(executor_type='cloudrun', is_active=True)
      
      job = ContainerJobFactory.build(preferred_executor='docker')
      
      with patch.object(factory, '_is_executor_available') as mock_available:
          mock_available.return_value = True
          
          executor_type = factory.route_job_to_executor_type(job)
          self.assertEqual(executor_type, 'docker')
          
          # Verify job was updated with routing info
          self.assertIn('Preferred executor', job.routing_reason)

  def test_route_job_geographic_constraints(self):
      # Test routing with geographic/regional constraints
      factory = ExecutorFactory()
      
      us_host = ExecutorHostFactory(region='us-central1', is_active=True)
      eu_host = ExecutorHostFactory(region='europe-west1', is_active=True)
      
      job = ContainerJobFactory.build(region_preference='us-central1')
      
      with patch.object(factory, '_matches_geographic_constraints') as mock_geo:
          mock_geo.side_effect = lambda host, job: host.region == job.region_preference
          
          selected_host = factory.route_job_to_host(job)
          self.assertEqual(selected_host, us_host)
  ```

### Test 3: Error Handling and Fallback Routing
- **Purpose:** Test error handling and fallback mechanisms in routing
- **Django-specific considerations:** Exception handling, graceful degradation
- **Test outline:**
  ```python
  def test_route_job_fallback_on_preferred_executor_failure(self):
      # Test fallback when preferred executor is unavailable
      factory = ExecutorFactory()
      
      # Preferred executor is unavailable
      docker_host = ExecutorHostFactory(executor_type='docker', is_active=False)
      cloudrun_host = ExecutorHostFactory(executor_type='cloudrun', is_active=True)
      
      job = ContainerJobFactory.build(preferred_executor='docker')
      
      with patch.object(factory, '_is_executor_available') as mock_available:
          # Docker unavailable, CloudRun available
          mock_available.side_effect = lambda executor_type: executor_type == 'cloudrun'
          
          with patch.object(factory, 'route_job_to_host') as mock_route_host:
              mock_route_host.return_value = cloudrun_host
              
              executor_type = factory.route_job_to_executor_type(job)
              self.assertEqual(executor_type, 'cloudrun')

  def test_route_job_configuration_error_handling(self):
      # Test handling of configuration errors during routing
      factory = ExecutorFactory()
      job = ContainerJobFactory.build()
      
      with patch.object(factory, 'get_available_hosts') as mock_get_hosts:
          mock_get_hosts.side_effect = ExecutorConfigurationError("Config error")
          
          with self.assertRaises(ExecutorConfigurationError):
              factory.route_job_to_host(job)

  def test_route_job_resource_exhaustion_handling(self):
      # Test handling when all executors are at capacity
      factory = ExecutorFactory()
      
      host = ExecutorHostFactory(is_active=True)
      job = ContainerJobFactory.build()
      
      with patch.object(factory, '_is_executor_available') as mock_available:
          mock_available.return_value = False  # All executors at capacity
          
          with self.assertRaises(ExecutorResourceError):
              factory.route_job_to_executor_type(job)

  def test_route_job_database_error_handling(self):
      # Test handling of database errors during routing
      factory = ExecutorFactory()
      job = ContainerJobFactory.build()
      
      with patch('container_manager.models.ExecutorHost.objects.filter') as mock_filter:
          mock_filter.side_effect = Exception("Database connection error")
          
          with self.assertRaises(Exception):
              factory.route_job_to_host(job)

  def test_route_job_logging_and_debugging(self):
      # Test routing decision logging
      factory = ExecutorFactory()
      host = ExecutorHostFactory(is_active=True)
      job = ContainerJobFactory.build()
      
      with patch('container_manager.executors.factory.logger') as mock_logger:
          with patch.object(factory, 'route_job_to_host') as mock_route:
              mock_route.return_value = host
              
              factory.route_job_to_executor_type(job)
              
              # Verify logging occurred
              mock_logger.info.assert_called()
              log_message = mock_logger.info.call_args[0][0]
              self.assertIn('routing', log_message.lower())
  ```

### Test 4: Executor Caching and Performance
- **Purpose:** Test executor caching and performance optimization
- **Django-specific considerations:** Cache efficiency, memory management
- **Test outline:**
  ```python
  def test_executor_caching_mechanism(self):
      # Test that executors are properly cached
      factory = ExecutorFactory()
      host = ExecutorHostFactory(executor_type='docker')
      
      with patch('container_manager.executors.docker.DockerExecutor') as mock_docker:
          mock_executor = Mock()
          mock_docker.return_value = mock_executor
          
          # First call should create executor
          executor1 = factory.get_executor(host)
          self.assertEqual(executor1, mock_executor)
          mock_docker.assert_called_once()
          
          # Second call should use cached executor
          executor2 = factory.get_executor(host)
          self.assertEqual(executor2, mock_executor)
          # Should not call constructor again
          mock_docker.assert_called_once()

  def test_executor_cache_invalidation(self):
      # Test executor cache invalidation
      factory = ExecutorFactory()
      host = ExecutorHostFactory(executor_type='docker')
      
      with patch('container_manager.executors.docker.DockerExecutor') as mock_docker:
          mock_executor1 = Mock()
          mock_executor2 = Mock()
          mock_docker.side_effect = [mock_executor1, mock_executor2]
          
          # Get executor (cached)
          executor1 = factory.get_executor(host)
          self.assertEqual(executor1, mock_executor1)
          
          # Invalidate cache
          factory.invalidate_executor_cache(host)
          
          # Next call should create new executor
          executor2 = factory.get_executor(host)
          self.assertEqual(executor2, mock_executor2)
          self.assertEqual(mock_docker.call_count, 2)

  def test_route_job_performance_optimization(self):
      # Test performance optimization in routing
      factory = ExecutorFactory()
      
      # Create many hosts
      hosts = [ExecutorHostFactory(is_active=True) for _ in range(100)]
      job = ContainerJobFactory.build()
      
      with patch('container_manager.models.ExecutorHost.objects.filter') as mock_filter:
          mock_filter.return_value.filter.return_value = hosts
          
          # Should use efficient database queries
          with self.assertNumQueries(1):  # Should be a single optimized query
              selected_host = factory.route_job_to_host(job)
              self.assertIn(selected_host, hosts)

  def test_concurrent_routing_thread_safety(self):
      # Test thread safety of routing operations
      factory = ExecutorFactory()
      host = ExecutorHostFactory(is_active=True)
      
      def route_job():
          job = ContainerJobFactory.build()
          return factory.route_job_to_host(job)
      
      # Simulate concurrent routing
      with ThreadPoolExecutor(max_workers=5) as executor:
          futures = [executor.submit(route_job) for _ in range(10)]
          results = [future.result() for future in futures]
          
          # All should succeed without errors
          self.assertEqual(len(results), 10)
          for result in results:
              self.assertEqual(result, host)
  ```

## Django Testing Patterns
- **Factory Pattern Testing:** Test factory instantiation and caching mechanisms
- **Routing Logic Testing:** Test complex routing algorithms and decision trees
- **Performance Testing:** Test query optimization and caching efficiency
- **Concurrency Testing:** Test thread safety and concurrent access patterns
- **Error Recovery:** Test fallback mechanisms and graceful degradation

## Definition of Done
- [ ] All uncovered executor availability checking functionality tested
- [ ] Advanced routing logic and load balancing algorithms covered
- [ ] Error handling and fallback routing mechanisms tested
- [ ] Executor caching and performance optimization covered
- [ ] Concurrent routing and thread safety tested
- [ ] Coverage target of 90% achieved for new feature
- [ ] Django testing best practices followed
- [ ] Routing decision logging and debugging verified