"""
Tests for executor fallback logic.
"""

import time
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from ..executors.base import ContainerExecutor
from ..executors.fallback import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ExecutorFallbackManager,
    GracefulDegradationManager,
    HealthChecker,
)
from ..models import ContainerJob, ContainerTemplate, DockerHost


class ExecutorFallbackManagerTest(TestCase):
    """Test cases for ExecutorFallbackManager."""

    def setUp(self):
        self.manager = ExecutorFallbackManager()

        # Create test objects
        self.template = ContainerTemplate.objects.create(
            name="test-template",
            docker_image="test:latest",
            memory_limit=512,
            cpu_limit=1.0,
        )

        self.host = DockerHost.objects.create(
            name="test-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

        self.job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.host,
            name="test-job",
            status="pending",
        )

    def test_calculate_retry_delay(self):
        """Test retry delay calculation with exponential backoff."""
        # Test increasing delays
        delay1 = self.manager._calculate_retry_delay(0)
        delay2 = self.manager._calculate_retry_delay(1)
        delay3 = self.manager._calculate_retry_delay(2)

        # Should increase exponentially
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)

        # Should respect max delay
        delay_large = self.manager._calculate_retry_delay(10)
        self.assertLessEqual(
            delay_large, self.manager.max_delay * 1.1
        )  # Allow for jitter

    def test_execute_with_fallback_success_primary(self):
        """Test successful execution on primary executor."""
        # Mock executors
        primary_executor = Mock(spec=ContainerExecutor)
        primary_executor.launch_job.return_value = (True, "exec_123")

        fallback_executor = Mock(spec=ContainerExecutor)

        # Test execution
        success, result = self.manager.execute_with_fallback(
            self.job, primary_executor, [fallback_executor]
        )

        self.assertTrue(success)
        self.assertEqual(result, "exec_123")

        # Primary should be called, fallback should not
        primary_executor.launch_job.assert_called_once_with(self.job)
        fallback_executor.launch_job.assert_not_called()

    def test_execute_with_fallback_success_fallback(self):
        """Test successful execution on fallback executor."""
        # Mock executors
        primary_executor = Mock(spec=ContainerExecutor)
        primary_executor.launch_job.return_value = (False, "Primary failed")

        fallback_executor = Mock(spec=ContainerExecutor)
        fallback_executor.launch_job.return_value = (True, "exec_456")

        # Test execution
        success, result = self.manager.execute_with_fallback(
            self.job, primary_executor, [fallback_executor]
        )

        self.assertTrue(success)
        self.assertEqual(result, "exec_456")

        # Both should be called
        primary_executor.launch_job.assert_called_once_with(self.job)
        fallback_executor.launch_job.assert_called_once_with(self.job)

    def test_execute_with_fallback_all_fail(self):
        """Test when all executors fail."""
        # Mock executors
        primary_executor = Mock(spec=ContainerExecutor)
        primary_executor.launch_job.return_value = (False, "Primary failed")

        fallback_executor = Mock(spec=ContainerExecutor)
        fallback_executor.launch_job.return_value = (False, "Fallback failed")

        # Test execution
        success, result = self.manager.execute_with_fallback(
            self.job, primary_executor, [fallback_executor]
        )

        self.assertFalse(success)
        self.assertIn("Fallback failed", result)

        # Both should be called
        primary_executor.launch_job.assert_called_once_with(self.job)
        fallback_executor.launch_job.assert_called_once_with(self.job)

    @patch("time.sleep")
    def test_retry_with_backoff_success(self, mock_sleep):
        """Test successful retry execution."""
        executor = Mock(spec=ContainerExecutor)
        # Fail first attempt, succeed second
        executor.launch_job.side_effect = [
            (False, "Temporary failure"),
            (True, "exec_retry_123"),
        ]

        success, result = self.manager.retry_with_backoff(self.job, executor, 3)

        self.assertTrue(success)
        self.assertEqual(result, "exec_retry_123")
        self.assertEqual(executor.launch_job.call_count, 2)
        mock_sleep.assert_called_once()  # Should sleep between attempts

    @patch("time.sleep")
    def test_retry_with_backoff_all_fail(self, mock_sleep):
        """Test when all retry attempts fail."""
        executor = Mock(spec=ContainerExecutor)
        executor.launch_job.return_value = (False, "Persistent failure")

        success, result = self.manager.retry_with_backoff(self.job, executor, 2)

        self.assertFalse(success)
        self.assertIn("Persistent failure", result)
        self.assertEqual(executor.launch_job.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)  # Sleep between attempts


class HealthCheckerTest(TestCase):
    """Test cases for HealthChecker."""

    def setUp(self):
        self.checker = HealthChecker()

        self.host = DockerHost.objects.create(
            name="test-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            health_check_failures=0,
        )

    def test_check_host_health_inactive(self):
        """Test health check for inactive host."""
        self.host.is_active = False
        self.host.save()

        result = self.checker.check_host_health(self.host)
        self.assertFalse(result)

    def test_check_host_health_too_many_failures(self):
        """Test health check for host with too many failures."""
        self.host.health_check_failures = 5
        self.host.last_health_check = timezone.now()
        self.host.save()

        result = self.checker.check_host_health(self.host)
        self.assertFalse(result)

    @patch("container_manager.docker_service.docker_service.get_client")
    def test_check_host_health_success(self, mock_get_client):
        """Test successful health check."""
        # Mock successful connection
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_get_client.return_value = mock_client

        result = self.checker.check_host_health(self.host)
        self.assertTrue(result)

        # Should update host state
        self.host.refresh_from_db()
        self.assertLessEqual(self.host.health_check_failures, 0)

    @patch("container_manager.docker_service.docker_service.get_client")
    def test_check_host_health_failure(self, mock_get_client):
        """Test failed health check."""
        # Mock connection failure
        mock_get_client.side_effect = Exception("Connection failed")

        initial_failures = self.host.health_check_failures
        result = self.checker.check_host_health(self.host)
        self.assertFalse(result)

        # Should increment failure count
        self.host.refresh_from_db()
        self.assertEqual(self.host.health_check_failures, initial_failures + 1)

    def test_get_healthy_hosts(self):
        """Test getting list of healthy hosts."""
        # Create multiple hosts
        healthy_host = DockerHost.objects.create(
            name="healthy-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            health_check_failures=0,
        )

        unhealthy_host = DockerHost.objects.create(
            name="unhealthy-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
            health_check_failures=5,
            last_health_check=timezone.now(),
        )

        with patch.object(self.checker, "_perform_health_check") as mock_check:
            # Mock health check results
            def side_effect(host):
                return host.health_check_failures < 3

            mock_check.side_effect = side_effect

            healthy_hosts = self.checker.get_healthy_hosts()

            # Should only include healthy hosts
            self.assertIn(healthy_host, healthy_hosts)
            self.assertNotIn(unhealthy_host, healthy_hosts)


class CircuitBreakerTest(TestCase):
    """Test cases for CircuitBreaker."""

    def setUp(self):
        self.breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

    def test_circuit_closed_success(self):
        """Test successful execution with closed circuit."""

        def test_func():
            return "success"

        result = self.breaker.call("test-executor", test_func)
        self.assertEqual(result, "success")

    def test_circuit_opens_after_failures(self):
        """Test circuit opens after failure threshold."""

        def failing_func():
            raise Exception("Test failure")

        # First failure
        with self.assertRaises(Exception):
            self.breaker.call("test-executor", failing_func)

        # Second failure - should open circuit
        with self.assertRaises(Exception):
            self.breaker.call("test-executor", failing_func)

        # Third call should raise CircuitBreakerOpenError
        with self.assertRaises(CircuitBreakerOpenError):
            self.breaker.call("test-executor", failing_func)

    def test_circuit_half_open_after_timeout(self):
        """Test circuit goes to half-open after timeout."""

        def failing_func():
            raise Exception("Test failure")

        def success_func():
            return "recovered"

        # Trigger failures to open circuit
        with self.assertRaises(Exception):
            self.breaker.call("test-executor", failing_func)
        with self.assertRaises(Exception):
            self.breaker.call("test-executor", failing_func)

        # Should be open now
        with self.assertRaises(CircuitBreakerOpenError):
            self.breaker.call("test-executor", failing_func)

        # Wait for recovery timeout
        time.sleep(1.1)

        # Should allow one call (half-open)
        result = self.breaker.call("test-executor", success_func)
        self.assertEqual(result, "recovered")

        # Should be closed again
        result = self.breaker.call("test-executor", success_func)
        self.assertEqual(result, "recovered")


class GracefulDegradationManagerTest(TestCase):
    """Test cases for GracefulDegradationManager."""

    def setUp(self):
        self.manager = GracefulDegradationManager()

        self.template = ContainerTemplate.objects.create(
            name="test-template",
            docker_image="test:latest",
            memory_limit=2048,  # High memory for degradation testing
            cpu_limit=2.0,
        )

        self.host = DockerHost.objects.create(
            name="test-host",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

        self.job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.host,
            name="test-job",
            status="pending",
        )

    def test_get_prioritized_strategies(self):
        """Test strategy prioritization based on job characteristics."""
        strategies = self.manager._get_prioritized_strategies(self.job)

        # High memory job should include resource reduction
        self.assertIn("reduce_resources", strategies)
        self.assertIn("redirect_to_fallback", strategies)
        self.assertIn("queue_jobs", strategies)

    def test_reduce_resource_limits(self):
        """Test resource limit reduction strategy."""
        mock_executors = [Mock(spec=ContainerExecutor)]

        success, message = self.manager._reduce_resource_limits(
            self.job, mock_executors
        )

        self.assertTrue(success)
        self.assertIn("Reduced resource limits", message)

        # Should update job metadata
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.executor_metadata)
        self.assertEqual(
            self.job.executor_metadata["degradation"]["strategy"], "reduce_resources"
        )

    def test_delay_non_critical_jobs(self):
        """Test job delay strategy."""
        # Test with a non-critical job name
        self.job.name = "test-batch-job"
        self.job.save()

        mock_executors = [Mock(spec=ContainerExecutor)]

        success, message = self.manager._delay_non_critical_jobs(
            self.job, mock_executors
        )

        self.assertTrue(success)
        self.assertIn("delayed", message)

        # Should update job metadata
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.executor_metadata)
        self.assertEqual(
            self.job.executor_metadata["degradation"]["strategy"], "delay_execution"
        )

    def test_queue_jobs_for_later(self):
        """Test job queuing strategy."""
        mock_executors = []  # No executors available

        success, message = self.manager._queue_jobs_for_later(self.job, mock_executors)

        self.assertTrue(success)
        self.assertIn("queued", message)

        # Should update job metadata
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.executor_metadata)
        self.assertEqual(
            self.job.executor_metadata["degradation"]["strategy"], "queue_jobs"
        )

    def test_redirect_to_fallback_executor(self):
        """Test fallback executor redirect strategy."""
        mock_executor = Mock(spec=ContainerExecutor)
        mock_executor.__class__.__name__ = "MockExecutor"
        mock_executors = [mock_executor]

        success, message = self.manager._redirect_to_fallback_executor(
            self.job, mock_executors
        )

        self.assertTrue(success)
        self.assertIn("MockExecutor", message)

        # Should update job metadata
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.executor_metadata)
        self.assertEqual(
            self.job.executor_metadata["degradation"]["strategy"],
            "redirect_to_fallback",
        )

    def test_apply_degradation(self):
        """Test applying degradation strategies."""
        mock_executors = [Mock(spec=ContainerExecutor)]

        success, message = self.manager.apply_degradation(self.job, mock_executors)

        self.assertTrue(success)

        # Should have applied at least one strategy
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.executor_metadata)
        self.assertIn("degradation", self.job.executor_metadata)
