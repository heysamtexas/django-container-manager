# Coverage Task: Django Models Business Logic

**Priority:** High
**Django Component:** Models/Business Logic
**Estimated Effort:** Medium
**Current Coverage:** 100.0% (172/172 statements covered) - TASK COMPLETED

## Coverage Gap Summary
- Current coverage: 74.0%
- Target coverage: 85% (business logic standard)
- Missing lines: 36, 45-58, 147, 157, 234, 255, 280, 471, 476-486, 491-507, 512, 522-529, 557, 561-566, 616, 620-640, 652-680, 685-687, 731, 753-754
- Critical impact: Core Django model business logic with significant gaps

## Uncovered Code Analysis
The `container_manager/models.py` module contains critical Django model business logic. Major uncovered areas include:

### Model Validation and Clean Methods (lines 45-58, 147, 157)
- Custom model validation logic
- Field-specific validation rules
- Cross-field validation constraints
- Business rule enforcement in model clean methods

### Model Properties and Computed Fields (lines 234, 255, 280)
- Dynamic property calculations
- Status-based computed fields
- Resource utilization calculations
- Display-friendly property methods

### Model Lifecycle Methods (lines 471, 476-507)
- Custom save() method logic
- Pre-save and post-save processing
- Model state change handling
- Cascading operations and side effects

### QuerySet and Manager Methods (lines 522-566)
- Custom manager methods for business operations
- Complex querysets for reporting and analytics
- Bulk operation methods
- Performance-optimized database operations

### Model Relationships and Foreign Key Logic (lines 616, 620-680)
- Related model access patterns
- Foreign key constraint handling
- Many-to-many relationship management
- Model relationship validation

## Suggested Tests

### Test 1: Model Validation and Clean Methods
- **Purpose:** Test Django model validation and clean method logic
- **Django-specific considerations:** Model validation, ValidationError handling
- **Test outline:**
  ```python
  def test_container_job_clean_validation_success(self):
      # Test successful model validation
      job = ContainerJobFactory.build(
          image='nginx:latest',
          command='echo "test"',
          docker_host=ExecutorHostFactory()
      )
      
      # Should not raise ValidationError
      try:
          job.clean()
      except ValidationError:
          self.fail("clean() raised ValidationError unexpectedly")

  def test_container_job_clean_validation_missing_image(self):
      # Test validation failure for missing image
      job = ContainerJobFactory.build(
          image='',
          command='echo "test"',
          docker_host=ExecutorHostFactory()
      )
      
      with self.assertRaises(ValidationError) as context:
          job.clean()
      
      self.assertIn('image', str(context.exception))

  def test_container_job_clean_validation_invalid_host(self):
      # Test validation failure for invalid host configuration
      job = ContainerJobFactory.build(
          image='nginx:latest',
          command='echo "test"',
          docker_host=None
      )
      
      with self.assertRaises(ValidationError) as context:
          job.clean()
      
      self.assertIn('host', str(context.exception).lower())

  def test_executor_host_clean_validation_connection_string(self):
      # Test executor host connection string validation
      host = ExecutorHostFactory.build(
          executor_type='docker',
          connection_string='invalid://connection'
      )
      
      with self.assertRaises(ValidationError) as context:
          host.clean()
      
      self.assertIn('connection', str(context.exception).lower())

  def test_environment_variable_template_clean_validation(self):
      # Test environment variable template validation
      template = EnvironmentVariableTemplateFactory.build(
          environment_variables_text='INVALID_FORMAT_NO_EQUALS'
      )
      
      with self.assertRaises(ValidationError) as context:
          template.clean()
      
      self.assertIn('environment', str(context.exception).lower())
  ```

### Test 2: Model Properties and Computed Fields
- **Purpose:** Test Django model properties and computed field logic
- **Django-specific considerations:** Property caching, database queries
- **Test outline:**
  ```python
  def test_container_job_is_terminal_status_property(self):
      # Test terminal status property for various job states
      completed_job = ContainerJobFactory(status='completed')
      self.assertTrue(completed_job.is_terminal_status)
      
      failed_job = ContainerJobFactory(status='failed')
      self.assertTrue(failed_job.is_terminal_status)
      
      running_job = ContainerJobFactory(status='running')
      self.assertFalse(running_job.is_terminal_status)
      
      pending_job = ContainerJobFactory(status='pending')
      self.assertFalse(pending_job.is_terminal_status)

  def test_container_job_runtime_duration_property(self):
      # Test runtime duration calculation
      start_time = django_timezone.now() - timedelta(minutes=30)
      end_time = django_timezone.now()
      
      job = ContainerJobFactory(
          started_at=start_time,
          finished_at=end_time
      )
      
      duration = job.runtime_duration
      self.assertIsNotNone(duration)
      self.assertAlmostEqual(duration.total_seconds(), 1800, delta=10)  # ~30 minutes

  def test_container_job_runtime_duration_still_running(self):
      # Test runtime duration for running job
      start_time = django_timezone.now() - timedelta(minutes=15)
      
      job = ContainerJobFactory(
          status='running',
          started_at=start_time,
          finished_at=None
      )
      
      duration = job.runtime_duration
      self.assertIsNotNone(duration)
      self.assertGreater(duration.total_seconds(), 800)  # At least ~15 minutes

  def test_executor_host_display_name_property(self):
      # Test executor host display name property
      docker_host = ExecutorHostFactory(
          name='production-docker',
          executor_type='docker'
      )
      
      display_name = docker_host.display_name
      self.assertIn('production-docker', display_name)
      self.assertIn('Docker', display_name)

  def test_environment_variable_template_environment_dict_property(self):
      # Test environment variables dictionary property
      template = EnvironmentVariableTemplateFactory(
          environment_variables_text='KEY1=value1\nKEY2=value2\nKEY3=value3'
      )
      
      env_dict = template.get_environment_variables_dict()
      expected = {'KEY1': 'value1', 'KEY2': 'value2', 'KEY3': 'value3'}
      self.assertEqual(env_dict, expected)

  def test_container_job_resource_utilization_property(self):
      # Test resource utilization calculation
      job = ContainerJobFactory(
          memory_limit=1024,
          cpu_limit=2.0,
          memory_usage=512,
          cpu_usage=1.5
      )
      
      utilization = job.resource_utilization
      self.assertEqual(utilization['memory_percent'], 50.0)
      self.assertEqual(utilization['cpu_percent'], 75.0)
  ```

### Test 3: Model Lifecycle and Save Methods
- **Purpose:** Test Django model save methods and lifecycle hooks
- **Django-specific considerations:** Signal handling, database transactions
- **Test outline:**
  ```python
  def test_container_job_save_sets_creation_timestamp(self):
      # Test that save() sets creation timestamp for new objects
      job = ContainerJobFactory.build()
      self.assertIsNone(job.created_at)
      
      job.save()
      self.assertIsNotNone(job.created_at)
      self.assertAlmostEqual(
          job.created_at,
          django_timezone.now(),
          delta=timedelta(seconds=5)
      )

  def test_container_job_save_updates_modified_timestamp(self):
      # Test that save() updates modification timestamp
      job = ContainerJobFactory()
      original_modified = job.modified_at
      
      # Simulate some time passing
      time.sleep(0.1)
      job.status = 'running'
      job.save()
      
      self.assertGreater(job.modified_at, original_modified)

  def test_container_job_save_status_transition_validation(self):
      # Test save() validates status transitions
      job = ContainerJobFactory(status='completed')
      
      # Should not allow transition from completed to pending
      job.status = 'pending'
      
      with self.assertRaises(ValidationError):
          job.save()

  def test_executor_host_save_normalizes_connection_string(self):
      # Test that save() normalizes connection strings
      host = ExecutorHostFactory.build(
          connection_string='  unix:///var/run/docker.sock  '
      )
      
      host.save()
      self.assertEqual(host.connection_string, 'unix:///var/run/docker.sock')

  def test_container_job_save_validates_image_format(self):
      # Test that save() validates Docker image format
      job = ContainerJobFactory.build(
          docker_image='invalid_image_name'
      )
      
      with self.assertRaises(ValidationError):
          job.save()

  def test_container_job_save_cascade_updates(self):
      # Test save() performs cascade updates to related objects
      job = ContainerJobFactory(status='running')
      execution = ContainerExecutionFactory(job=job)
      
      job.status = 'completed'
      job.save()
      
      execution.refresh_from_db()
      # Related execution should be updated
      self.assertEqual(execution.status, 'completed')
  ```

### Test 4: Custom Manager and QuerySet Methods
- **Purpose:** Test custom Django manager and queryset methods
- **Django-specific considerations:** Database optimization, query efficiency
- **Test outline:**
  ```python
  def test_container_job_manager_pending_jobs(self):
      # Test manager method for retrieving pending jobs
      ContainerJobFactory(status='pending')
      ContainerJobFactory(status='running')
      ContainerJobFactory(status='pending')
      
      pending_jobs = ContainerJob.objects.pending()
      self.assertEqual(pending_jobs.count(), 2)
      
      for job in pending_jobs:
          self.assertEqual(job.status, 'pending')

  def test_container_job_manager_active_jobs(self):
      # Test manager method for retrieving active jobs
      ContainerJobFactory(status='running')
      ContainerJobFactory(status='starting')
      ContainerJobFactory(status='completed')
      
      active_jobs = ContainerJob.objects.active()
      self.assertEqual(active_jobs.count(), 2)
      
      active_statuses = {job.status for job in active_jobs}
      self.assertEqual(active_statuses, {'running', 'starting'})

  def test_container_job_manager_by_host(self):
      # Test manager method for filtering by host
      host1 = ExecutorHostFactory()
      host2 = ExecutorHostFactory()
      
      ContainerJobFactory(docker_host=host1)
      ContainerJobFactory(docker_host=host1)
      ContainerJobFactory(docker_host=host2)
      
      host1_jobs = ContainerJob.objects.by_host(host1)
      self.assertEqual(host1_jobs.count(), 2)
      
      for job in host1_jobs:
          self.assertEqual(job.docker_host, host1)

  def test_container_job_manager_recent_jobs(self):
      # Test manager method for retrieving recent jobs
      old_job = ContainerJobFactory()
      old_job.created_at = django_timezone.now() - timedelta(days=2)
      old_job.save()
      
      recent_job = ContainerJobFactory()
      
      recent_jobs = ContainerJob.objects.recent(hours=24)
      self.assertEqual(recent_jobs.count(), 1)
      self.assertEqual(recent_jobs.first(), recent_job)

  def test_executor_host_manager_available_hosts(self):
      # Test manager method for available hosts
      ExecutorHostFactory(is_active=True, last_health_check=django_timezone.now())
      ExecutorHostFactory(is_active=False)
      ExecutorHostFactory(
          is_active=True,
          last_health_check=django_timezone.now() - timedelta(hours=2)
      )
      
      available_hosts = ExecutorHost.objects.available()
      self.assertEqual(available_hosts.count(), 1)

  def test_environment_variable_template_manager_by_category(self):
      # Test environment template manager filtering by category
      EnvironmentVariableTemplateFactory(name='web-env', description='Web environment')
      EnvironmentVariableTemplateFactory(name='worker-env', description='Worker environment')
      EnvironmentVariableTemplateFactory(name='web-prod-env', description='Web production environment')
      
      web_templates = EnvironmentVariableTemplate.objects.filter(description__icontains='web')
      self.assertEqual(web_templates.count(), 2)
      
      for template in web_templates:
          self.assertIn('web', template.description.lower())
  ```

### Test 5: Model Relationships and Foreign Key Logic
- **Purpose:** Test Django model relationships and foreign key constraints
- **Django-specific considerations:** Related manager, cascade behavior
- **Test outline:**
  ```python
  def test_container_job_docker_host_relationship(self):
      # Test job-host relationship and related manager
      host = ExecutorHostFactory()
      job1 = ContainerJobFactory(docker_host=host)
      job2 = ContainerJobFactory(docker_host=host)
      
      # Test forward relationship
      self.assertEqual(job1.docker_host, host)
      
      # Test reverse relationship
      host_jobs = host.containerjob_set.all()
      self.assertEqual(host_jobs.count(), 2)
      self.assertIn(job1, host_jobs)
      self.assertIn(job2, host_jobs)

  def test_container_job_environment_template_relationship(self):
      # Test job-environment template relationship
      env_template = EnvironmentVariableTemplateFactory()
      job = ContainerJobFactory(environment_template=env_template)
      
      self.assertEqual(job.environment_template, env_template)
      
      # Test that job can access template environment variables
      env_vars = job.get_all_environment_variables()
      self.assertIsInstance(env_vars, dict)

  def test_container_execution_job_relationship(self):
      # Test execution-job relationship and cascade behavior
      job = ContainerJobFactory()
      execution = ContainerExecutionFactory(job=job)
      
      self.assertEqual(execution.job, job)
      
      # Test cascade delete
      job.delete()
      
      with self.assertRaises(ContainerExecution.DoesNotExist):
          execution.refresh_from_db()

  def test_executor_host_cascade_behavior(self):
      # Test host deletion behavior with related jobs
      host = ExecutorHostFactory()
      job = ContainerJobFactory(docker_host=host)
      
      # Host deletion should be prevented if jobs exist
      with self.assertRaises(ProtectedError):
          host.delete()
      
      # After job completion, host can be deleted
      job.status = 'completed'
      job.save()
      job.delete()
      
      # Now host deletion should succeed
      host.delete()

  def test_environment_variable_template_job_relationship(self):
      # Test environment template used by multiple jobs
      env_template = EnvironmentVariableTemplateFactory(
          name='production-env',
          environment_variables_text='ENV=production\nDEBUG=false'
      )
      
      job1 = ContainerJobFactory(environment_template=env_template)
      job2 = ContainerJobFactory(environment_template=env_template)
      
      self.assertEqual(job1.environment_template, env_template)
      self.assertEqual(job2.environment_template, env_template)
      
      # Test that both jobs get the same base environment
      job1_env = job1.get_all_environment_variables()
      job2_env = job2.get_all_environment_variables()
      
      self.assertEqual(job1_env.get('ENV'), 'production')
      self.assertEqual(job2_env.get('ENV'), 'production')
  ```

## Django Testing Patterns
- **Model Validation Testing:** Test clean() methods and ValidationError handling
- **Property Testing:** Test computed properties and cached attributes
- **Manager/QuerySet Testing:** Test custom database operations and filtering
- **Relationship Testing:** Test foreign keys, reverse relationships, and cascade behavior
- **Lifecycle Testing:** Test save() methods, signals, and state transitions

## Definition of Done
- [ ] All uncovered model validation and clean methods tested
- [ ] Model properties and computed fields comprehensively covered
- [ ] Custom save methods and lifecycle hooks tested
- [ ] Manager and queryset methods fully covered
- [ ] Model relationships and foreign key logic tested
- [ ] Coverage target of 85% achieved for business logic
- [ ] Django testing best practices followed
- [ ] Edge cases and error conditions covered