# Code Coverage: Service Layer (Priority 3)

## Executive Summary

**Impact:** MEDIUM - Service layer provides Django integration, admin interface, and supporting infrastructure
**Current Coverage:**
- `admin.py` - **30%** (313 statements) - Django admin interface
- `docker_service.py` - **29%** (206 statements) - Docker service integration  
- `defaults.py` - **0%** (20 statements) - Default configuration
- `settings_fallback.py` - **0%** (15 statements) - Settings fallback

**Target:** Achieve **≥70%** coverage on service layer (focus on business logic, skip Django admin UI)

## Coverage Analysis by Priority

### 1. `docker_service.py` - 29% Coverage 🔴
**File:** `container_manager/docker_service.py`
**Current Coverage:** 59/206 statements covered
**Missing Coverage:** 147 statements (71% uncovered)
**Business Impact:** HIGH - Core Docker integration service

**Key Uncovered Functions:**
- `get_logs()` - Log retrieval from containers (complexity 9)
- `create_container()` - Container creation workflow
- `start_container()` - Container startup management
- `stop_container()` - Container shutdown management
- `get_container_status()` - Status monitoring
- `cleanup_container()` - Resource cleanup
- `test_connection()` - Host connectivity testing

**Testing Strategy:**
```python
class DockerServiceTest(TestCase):
    def setUp(self):
        # Mock Docker client for service testing
        self.mock_docker = Mock()
        self.service = DockerService()
        self.service.client = self.mock_docker
        
    def test_get_logs_retrieves_container_logs(self):
        # Test log retrieval with various options
        container_id = 'test-container-123'
        self.mock_docker.containers.get.return_value.logs.return_value = b'test logs'
        
        logs = self.service.get_logs(container_id, tail=100, follow=False)
        
        self.assertIn('test logs', logs)
        self.mock_docker.containers.get.assert_called_with(container_id)
        
    def test_create_container_with_complex_config(self):
        # Test container creation with volumes, environment, networking
        job = self.create_test_job_with_config()
        container = self.service.create_container(job)
        
        # Verify container creation call
        create_call = self.mock_docker.containers.create.call_args
        self.assertIn('image', create_call[1])
        self.assertIn('environment', create_call[1])
        self.assertIn('volumes', create_call[1])
        
    def test_get_container_status_maps_docker_states(self):
        # Test Docker state → our status mapping
        docker_states = [
            ('running', 'running'),
            ('exited', 'completed'),
            ('dead', 'failed'),
            ('created', 'pending')
        ]
        
        for docker_state, expected_status in docker_states:
            mock_container = Mock()
            mock_container.status = docker_state
            self.mock_docker.containers.get.return_value = mock_container
            
            status = self.service.get_container_status('container-id')
            self.assertEqual(status, expected_status)
            
    def test_test_connection_validates_docker_host(self):
        # Test Docker host connectivity
        self.mock_docker.ping.return_value = True
        result = self.service.test_connection()
        self.assertTrue(result)
        
        # Test connection failure
        self.mock_docker.ping.side_effect = Exception("Connection failed")
        result = self.service.test_connection()
        self.assertFalse(result)
```

**Complex Function Testing:**

**`get_logs()` (Complexity 9):**
```python
def test_get_logs_handles_all_options(self):
    # Test all log retrieval options
    test_cases = [
        {'tail': 100, 'follow': False, 'timestamps': True},
        {'tail': 'all', 'follow': True, 'timestamps': False},
        {'since': '2024-01-01', 'until': '2024-01-02'},
    ]
    
    for options in test_cases:
        logs = self.service.get_logs('container-id', **options)
        # Verify correct Docker API call
        
def test_get_logs_handles_container_not_found(self):
    # Test error handling for missing containers
    self.mock_docker.containers.get.side_effect = docker.errors.NotFound
    
    with self.assertRaises(ContainerNotFoundError):
        self.service.get_logs('nonexistent-container')
        
def test_get_logs_handles_permission_errors(self):
    # Test error handling for permission issues
    self.mock_docker.containers.get.side_effect = docker.errors.APIError
    
    with self.assertRaises(DockerServiceError):
        self.service.get_logs('container-id')
```

### 2. `admin.py` - 30% Coverage 🔴
**File:** `container_manager/admin.py`
**Current Coverage:** 93/313 statements covered
**Missing Coverage:** 220 statements (70% uncovered)
**Business Impact:** LOW - Django admin interface (skip UI testing per guidelines)

**Focus Areas for Testing:**
- **Business logic only** - Skip Django admin UI functionality
- **Custom admin actions** - Test bulk operations and custom workflows
- **Data validation** - Test admin form validation
- **Permissions** - Test admin permission logic

**Selective Testing Strategy:**
```python
class AdminBusinessLogicTest(TestCase):
    def test_bulk_actions_process_correctly(self):
        # Test custom admin actions that contain business logic
        
    def test_custom_validation_works(self):
        # Test any custom validation in admin forms
        
    def test_admin_permissions_enforced(self):
        # Test custom permission logic (if any)
        
    # NOTE: Skip testing Django admin UI rendering
    # Focus only on custom business logic within admin
```

**Coverage Strategy:**
- **Target:** Improve to 50% (focus on business logic)
- **Skip:** Django admin UI components, form rendering, list displays
- **Focus:** Custom actions, validation, permissions, business workflows

### 3. `defaults.py` - 0% Coverage 🔴
**File:** `container_manager/defaults.py`
**Statements:** 20
**Business Impact:** MEDIUM - Default configuration values

**Key Functions:**
- Configuration constants and defaults
- Default executor settings
- Default resource limits
- Default timeout values

**Testing Strategy:**
```python
class DefaultsTest(TestCase):
    def test_default_values_are_reasonable(self):
        # Test that default values make sense
        from container_manager import defaults
        
        self.assertGreater(defaults.DEFAULT_TIMEOUT, 0)
        self.assertIsInstance(defaults.DEFAULT_MEMORY_LIMIT, int)
        self.assertIn(defaults.DEFAULT_EXECUTOR_TYPE, ['docker', 'cloudrun'])
        
    def test_default_config_is_valid(self):
        # Test that default configuration is internally consistent
        config = defaults.get_default_config()
        
        # Validate configuration structure
        self.assertIn('executors', config)
        self.assertIn('resources', config)
        self.assertIn('timeouts', config)
        
    def test_environment_variable_overrides(self):
        # Test environment variable override functionality
        with patch.dict(os.environ, {'CONTAINER_TIMEOUT': '300'}):
            config = defaults.get_default_config()
            self.assertEqual(config['timeout'], 300)
```

### 4. `settings_fallback.py` - 0% Coverage 🔴
**File:** `container_manager/settings_fallback.py`
**Statements:** 15
**Business Impact:** LOW - Fallback settings for missing configuration

**Key Functions:**
- Fallback configuration loading
- Missing settings detection
- Default value provision

**Testing Strategy:**
```python
class SettingsFallbackTest(TestCase):
    def test_fallback_provides_missing_settings(self):
        # Test fallback for missing Django settings
        
    def test_fallback_preserves_existing_settings(self):
        # Test that existing settings are not overridden
        
    def test_fallback_handles_import_errors(self):
        # Test graceful handling of import failures
```

## Testing Infrastructure for Service Layer

### Django Admin Testing Pattern
```python
class AdminTestMixin:
    """Utilities for testing Django admin business logic only"""
    
    def setUp(self):
        # Create admin user for testing
        self.admin_user = User.objects.create_superuser(
            'admin', 'admin@test.com', 'password'
        )
        self.client.login(username='admin', password='password')
        
    def test_admin_business_logic_only(self):
        # Helper to focus on business logic, not UI
        pass
        
    def skip_ui_testing(self):
        # Explicitly skip Django admin UI testing
        # Focus on custom actions and validation only
        pass
```

### Docker Service Mocking
```python
class MockDockerService:
    """Comprehensive mock for Docker service operations"""
    
    def __init__(self):
        self.containers = {}
        self.networks = {}
        self.volumes = {}
        
    def create_container(self, config):
        # Mock container creation
        container_id = f"mock-container-{len(self.containers)}"
        self.containers[container_id] = {
            'status': 'created',
            'config': config
        }
        return container_id
        
    def get_logs(self, container_id, **options):
        # Mock log retrieval
        if container_id not in self.containers:
            raise ContainerNotFoundError(f"Container {container_id} not found")
        return f"Mock logs for {container_id}"
```

### Configuration Testing Utilities
```python
class ConfigTestMixin:
    """Utilities for testing configuration and defaults"""
    
    def assert_config_valid(self, config):
        # Validate configuration structure and values
        required_keys = ['executors', 'resources', 'timeouts']
        for key in required_keys:
            self.assertIn(key, config)
            
    def mock_environment_variables(self, env_vars):
        # Helper to mock environment variable overrides
        return patch.dict(os.environ, env_vars)
```

## Implementation Plan

### Phase 1: Docker Service (Highest Business Impact)
1. **`docker_service.py`** - 29% → 70% coverage
   - Focus on core service methods
   - Mock Docker client comprehensively
   - Test error handling and edge cases
   - **Estimated effort:** 8-12 hours

### Phase 2: Configuration and Defaults
2. **`defaults.py`** - 0% → 80% coverage
3. **`settings_fallback.py`** - 0% → 80% coverage
   - **Estimated effort:** 3-4 hours combined

### Phase 3: Admin Business Logic (Selective)
4. **`admin.py`** - 30% → 50% coverage
   - Focus only on custom business logic
   - Skip Django admin UI components
   - Test custom actions and validation
   - **Estimated effort:** 4-6 hours

## Testing Challenges & Solutions

### Challenge 1: Django Admin UI Complexity
**Problem:** Django admin has extensive UI that's difficult to test
**Solution:**
- **Skip UI testing** per CLAUDE.md guidelines
- **Focus on business logic** within admin classes
- **Test custom actions** and validation only

### Challenge 2: Docker Service Dependencies
**Problem:** Docker service depends on Docker daemon
**Solution:**
- **Mock Docker client** at the service level
- **Test service logic** without actual containers
- **Simulate Docker errors** for error path testing

### Challenge 3: Configuration Overlap
**Problem:** Multiple configuration files with overlapping concerns
**Solution:**
- **Test configuration hierarchy** (defaults → settings → environment)
- **Validate configuration consistency** across files
- **Test override behavior** systematically

### Challenge 4: Low Business Value Areas
**Problem:** Some areas have low business impact
**Solution:**
- **Prioritize by business impact** - Docker service first
- **Set realistic targets** - 70% for service layer vs 85% for executors
- **Focus on testable business logic** over configuration

## Success Metrics

### Coverage Targets
- `docker_service.py`: 29% → **≥70%** (144+ statements covered)
- `defaults.py`: 0% → **≥80%** (16+ statements covered)
- `settings_fallback.py`: 0% → **≥80%** (12+ statements covered)
- `admin.py`: 30% → **≥50%** (156+ statements covered) - *selective focus*

### Quality Metrics
- **Docker service functionality** fully tested
- **Configuration loading** validated and consistent
- **Error handling** comprehensive for service operations
- **Business logic separation** from Django admin UI

### Functional Coverage
- **Docker operations** (create, start, stop, logs, cleanup)
- **Service error handling** (connection, permission, not found)
- **Configuration management** (defaults, overrides, validation)
- **Admin business logic** (custom actions, validation)

## Risk Assessment

### Low Risk Areas
- **Configuration testing** - Straightforward validation
- **Default value testing** - Simple constant verification
- **Service error mocking** - Predictable error scenarios

### Medium Risk Areas
- **Docker service integration** - External dependency mocking
- **Admin business logic** - Separating from Django internals
- **Configuration hierarchy** - Override behavior complexity

### Mitigation Strategies
- **Comprehensive Docker mocking** to avoid flaky tests
- **Focus on business value** over coverage percentage
- **Test configuration combinations** systematically
- **Skip low-value Django admin UI** testing

## Timeline Estimate

### Conservative Estimate: 19-26 hours
- **Docker service:** 12 hours
- **Configuration files:** 4 hours
- **Admin business logic:** 6 hours
- **Integration testing:** 3-4 hours

### Optimistic Estimate: 13-18 hours
- **Docker service:** 8 hours
- **Configuration files:** 3 hours
- **Admin business logic:** 4 hours
- **Integration testing:** 1-3 hours

## Dependencies

### Prerequisites
- Mock infrastructure established
- Docker client mocking patterns
- Django test database configuration
- Coverage measurement tools

### Coordination
- Benefits from executor testing mock patterns
- Requires Docker service testing utilities
- May inform infrastructure testing approaches
- Should align with management command testing