"""
Tests for ExecutorFactory routing and management logic.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from ..executors.exceptions import ExecutorConfigurationError, ExecutorResourceError
from ..executors.factory import ExecutorFactory
from ..models import ContainerJob, ContainerTemplate, ExecutorHost


class ExecutorFactoryTest(TestCase):
    """Test ExecutorFactory routing and executor management"""

    def setUp(self):
        """Set up test data"""
        # Create test user and groups
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )
        self.premium_group = Group.objects.create(name="premium")

        # Create test Docker host
        self.docker_host = ExecutorHost.objects.create(
            name="test-docker",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            max_concurrent_jobs=5,
            current_job_count=0,
        )

        # Create test templates
        self.regular_template = ContainerTemplate.objects.create(
            name="regular-job",
            docker_image="nginx:latest",
            memory_limit=512,
            cpu_limit=1.0,
            timeout_seconds=600,
        )

        self.high_memory_template = ContainerTemplate.objects.create(
            name="ml-training",
            docker_image="tensorflow/tensorflow:latest",
            memory_limit=16384,  # 16GB
            cpu_limit=8.0,
            timeout_seconds=7200,
        )

        self.batch_template = ContainerTemplate.objects.create(
            name="batch-processor",
            docker_image="python:3.9",
            memory_limit=1024,
            cpu_limit=2.0,
            timeout_seconds=1800,
        )

        self.test_template = ContainerTemplate.objects.create(
            name="test-template",
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
        )

        # Create factory instance
        self.factory = ExecutorFactory()

    def test_route_job_default_docker(self):
        """Test routing to default Docker executor"""
        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        executor_type = self.factory.route_job_to_executor_type(job)

        self.assertEqual(executor_type, "docker")
        self.assertEqual(job.routing_reason, "Default fallback to docker")


    @override_settings(
        EXECUTOR_ROUTING_RULES=[
            {
                "condition": "memory_mb > 8192",
                "executor": "fargate",
                "reason": "High memory requirement (>8GB)",
                "priority": 1,
            }
        ],
        CONTAINER_EXECUTORS={
            "docker": {"enabled": True, "default": True},
            "cloudrun": {"enabled": False},
            "fargate": {"enabled": False},
            "mock": {"enabled": True},
        },
    )
    def test_route_job_high_memory_rule(self):
        """Test routing based on memory requirement rule"""
        # Create factory with overridden settings
        factory = ExecutorFactory()

        job = ContainerJob.objects.create(
            template=self.high_memory_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Since fargate is not available, should fall back to docker
        executor_type = factory.route_job_to_executor_type(job)

        self.assertEqual(executor_type, "docker")
        self.assertEqual(job.routing_reason, "Default fallback to docker")

    @override_settings(
        EXECUTOR_ROUTING_RULES=[
            {
                "condition": 'template.name.startswith("batch-")',
                "executor": "cloudrun",
                "reason": "Batch processing template",
                "priority": 1,
            }
        ],
        CONTAINER_EXECUTORS={
            "docker": {"enabled": True, "default": True},
            "cloudrun": {"enabled": False},
            "fargate": {"enabled": False},
            "mock": {"enabled": True},
        },
    )
    def test_route_job_template_name_rule(self):
        """Test routing based on template name rule"""
        # Create factory with overridden settings
        factory = ExecutorFactory()

        job = ContainerJob.objects.create(
            template=self.batch_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Since cloudrun is not available, should fall back to docker
        executor_type = factory.route_job_to_executor_type(job)

        self.assertEqual(executor_type, "docker")
        self.assertEqual(job.routing_reason, "Default fallback to docker")


    @override_settings(
        EXECUTOR_ROUTING_RULES=[
            {
                "condition": 'user and user.groups.filter(name="premium").exists()',
                "executor": "cloudrun",
                "reason": "Premium user priority",
                "priority": 1,
            }
        ],
        CONTAINER_EXECUTORS={
            "docker": {"enabled": True, "default": True},
            "cloudrun": {"enabled": False},
            "fargate": {"enabled": False},
            "mock": {"enabled": True},
        },
    )
    def test_route_job_premium_user(self):
        """Test routing for premium users"""
        # Create factory with overridden settings
        factory = ExecutorFactory()

        # Add user to premium group
        self.user.groups.add(self.premium_group)

        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Since cloudrun is not available, should fall back to docker
        executor_type = factory.route_job_to_executor_type(job)

        self.assertEqual(executor_type, "docker")
        self.assertEqual(job.routing_reason, "Default fallback to docker")

    def test_route_job_no_available_executors(self):
        """Test error when no executors are available"""
        # Disable docker host
        self.docker_host.is_active = False
        self.docker_host.save()

        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        with self.assertRaises(ExecutorResourceError):
            self.factory.route_job_to_executor_type(job)

    def test_get_executor_docker(self):
        """Test getting Docker executor instance"""
        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            executor_type="docker",
            created_by=self.user,
        )

        executor = self.factory.get_executor(job)

        self.assertIsNotNone(executor)
        self.assertEqual(executor.__class__.__name__, "DockerExecutor")

    def test_get_executor_mock(self):
        """Test getting Mock executor instance"""
        job = ContainerJob.objects.create(
            template=self.test_template,
            docker_host=self.docker_host,
            executor_type="mock",
            created_by=self.user,
        )

        executor = self.factory.get_executor(job)

        self.assertIsNotNone(executor)
        self.assertEqual(executor.__class__.__name__, "MockExecutor")

    def test_get_executor_cloudrun(self):
        """Test getting CloudRun executor instance"""
        # Create CloudRun host
        cloudrun_host = ExecutorHost.objects.create(
            name="test-cloudrun",
            executor_type="cloudrun",
            connection_string="cloudrun://demo-project/us-central1",
            is_active=True,
        )

        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=cloudrun_host,
            executor_type="cloudrun",
            created_by=self.user,
        )

        executor = self.factory.get_executor(job)

        self.assertIsNotNone(executor)
        self.assertEqual(executor.__class__.__name__, "CloudRunExecutor")

        # Test that configuration was properly loaded
        self.assertEqual(executor.project_id, "demo-project")
        self.assertEqual(executor.region, "us-central1")

    def test_cloudrun_cost_estimation(self):
        """Test CloudRun cost estimation through factory"""
        cloudrun_host = ExecutorHost.objects.create(
            name="cost-test-cloudrun",
            executor_type="cloudrun",
            connection_string="cloudrun://demo-project/us-central1",
            is_active=True,
        )

        job = ContainerJob.objects.create(
            template=self.high_memory_template,
            docker_host=cloudrun_host,
            executor_type="cloudrun",
            created_by=self.user,
        )

        executor = self.factory.get_executor(job)
        cost = executor.get_cost_estimate(job)

        self.assertIn("cpu_cost", cost)
        self.assertIn("memory_cost", cost)
        self.assertIn("request_cost", cost)
        self.assertIn("total_cost", cost)
        self.assertEqual(cost["currency"], "USD")
        self.assertGreater(cost["total_cost"], 0)


    def test_get_executor_unknown_type(self):
        """Test error for unknown executor type"""
        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            executor_type="unknown",
            created_by=self.user,
        )

        with self.assertRaises(ExecutorConfigurationError):
            self.factory.get_executor(job)

    def test_get_executor_no_type(self):
        """Test error when job has no executor type"""
        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Clear the default executor_type to test the error condition
        job.executor_type = ""
        job.save()

        with self.assertRaises(ExecutorConfigurationError):
            self.factory.get_executor(job)


    def test_get_executor_capacity_docker(self):
        """Test getting Docker executor capacity"""
        capacity = self.factory.get_executor_capacity("docker")

        self.assertEqual(capacity["total_capacity"], 5)
        self.assertEqual(capacity["current_usage"], 0)
        self.assertEqual(capacity["available_slots"], 5)


    def test_executor_caching(self):
        """Test that executor instances are cached"""
        job1 = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            executor_type="docker",
            created_by=self.user,
        )

        job2 = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            executor_type="docker",
            created_by=self.user,
        )

        executor1 = self.factory.get_executor(job1)
        executor2 = self.factory.get_executor(job2)

        # Should be the same instance due to caching
        self.assertIs(executor1, executor2)

    def test_clear_cache(self):
        """Test clearing executor cache"""
        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            executor_type="docker",
            created_by=self.user,
        )

        executor1 = self.factory.get_executor(job)
        self.factory.clear_cache()
        executor2 = self.factory.get_executor(job)

        # Should be different instances after cache clear
        self.assertIsNot(executor1, executor2)

    def test_docker_host_availability_checking(self):
        """Test that Docker host availability is checked"""
        # Fill up Docker host capacity
        self.docker_host.current_job_count = 5  # At max capacity
        self.docker_host.save()

        self.assertFalse(self.factory._is_executor_available("docker"))

        # Free up capacity
        self.docker_host.current_job_count = 3
        self.docker_host.save()

        self.assertTrue(self.factory._is_executor_available("docker"))

    def test_invalid_routing_rule(self):
        """Test handling of invalid routing rules"""
        # Create factory with invalid rule
        factory = ExecutorFactory()

        # Mock invalid rule
        factory._routing_rules = [
            {
                "condition": "invalid.syntax.here(",
                "executor": "docker",
                "reason": "Invalid rule",
            }
        ]

        job = ContainerJob.objects.create(
            template=self.regular_template,
            docker_host=self.docker_host,
            created_by=self.user,
        )

        # Should not raise exception, just skip invalid rule
        executor_type = factory.route_job_to_executor_type(job)
        self.assertEqual(executor_type, "docker")

