"""
Tests for the enhanced MockExecutor with configurable behaviors.
"""

import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ..executors.mock import MockExecutor
from ..models import ContainerJob, ExecutorHost


class MockExecutorTest(TestCase):
    """Test MockExecutor with various configuration scenarios"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        self.docker_host = ExecutorHost.objects.create(
            name="test-docker",
            executor_type="docker",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )

    def test_basic_mock_executor(self):
        """Test basic MockExecutor functionality"""
        config = {
            "execution_delay": 0.1,
            "exit_code_distribution": {0: 1.0},  # 100% success for this test
        }
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        # Test launch
        success, execution_id = executor.launch_job(job)

        self.assertTrue(success)
        self.assertTrue(execution_id.startswith("mock-"))

        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertIsNotNone(job.started_at)

        # Test status check
        status = executor.check_status(execution_id)
        self.assertEqual(status, "completed")  # Mock completes immediately

        # Test harvest
        harvest_success = executor.harvest_job(job)
        self.assertTrue(harvest_success)

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.exit_code, 0)
        self.assertIsNotNone(job.completed_at)

    def test_failure_simulation(self):
        """Test failure simulation configuration"""
        config = {
            "simulate_failures": True,
            "failure_rate": 1.0,  # 100% failure rate
            "execution_delay": 0.1,
        }
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        # Should fail due to 100% failure rate
        success, error_msg = executor.launch_job(job)

        self.assertFalse(success)
        self.assertIn("Mock launch failure", error_msg)

    def test_custom_exit_code_distribution(self):
        """Test custom exit code distribution"""
        config = {
            "exit_code_distribution": {
                0: 0.0,  # 0% success
                1: 1.0,  # 100% failure
            },
            "execution_delay": 0.1,
        }

        with patch("random.random", return_value=0.5):  # Fixed random value
            executor = MockExecutor(config)

            job = ContainerJob.objects.create(
                docker_host=self.docker_host,
                docker_image="alpine:latest",
                memory_limit=128,
                cpu_limit=0.5,
                timeout_seconds=300,
                # executor_type now determined by docker_host
                created_by=self.user,
            )

            success, execution_id = executor.launch_job(job)
            self.assertTrue(success)

            # Harvest should result in failure due to exit code 1
            harvest_success = executor.harvest_job(job)
            self.assertTrue(harvest_success)  # Harvest succeeds

            job.refresh_from_db()
            self.assertEqual(job.status, "failed")  # But job failed
            self.assertEqual(job.exit_code, 1)

    def test_cpu_usage_patterns(self):
        """Test different CPU usage patterns"""
        test_cases = [
            ("low", 15.0),
            ("medium", 45.0),
            ("high", 85.0),
            (75.5, 75.5),  # Custom percentage
        ]

        for pattern, expected_base in test_cases:
            with self.subTest(pattern=pattern):
                config = {"cpu_usage_pattern": pattern, "execution_delay": 0.1}
                executor = MockExecutor(config)

                job = ContainerJob.objects.create(
                    docker_host=self.docker_host,
                    docker_image="alpine:latest",
                    memory_limit=128,
                    cpu_limit=0.5,
                    timeout_seconds=300,
                    # executor_type now determined by docker_host
                    created_by=self.user,
                )

                success, execution_id = executor.launch_job(job)
                self.assertTrue(success)

                # Check resource usage
                usage = executor.get_resource_usage(execution_id)
                self.assertIsNotNone(usage)

                cpu_percent = usage["cpu_usage_percent"]
                if isinstance(pattern, str):
                    # Should be exactly the expected value (no fluctuation by default)
                    self.assertEqual(cpu_percent, expected_base)
                else:
                    # Custom value should be exact
                    self.assertEqual(cpu_percent, expected_base)

    def test_resource_fluctuation(self):
        """Test resource usage fluctuation"""
        config = {
            "cpu_usage_pattern": "medium",
            "resource_fluctuation": True,
            "execution_delay": 0.1,
        }
        executor = MockExecutor(config)

        # Run multiple jobs to see variation
        cpu_values = []
        for _ in range(10):
            job = ContainerJob.objects.create(
                docker_host=self.docker_host,
                docker_image="alpine:latest",
                memory_limit=128,
                cpu_limit=0.5,
                timeout_seconds=300,
                # executor_type now determined by docker_host
                created_by=self.user,
            )

            success, execution_id = executor.launch_job(job)
            self.assertTrue(success)

            usage = executor.get_resource_usage(execution_id)
            cpu_values.append(usage["cpu_usage_percent"])

        # Should have some variation due to fluctuation
        self.assertGreater(max(cpu_values) - min(cpu_values), 5.0)

    def test_custom_log_patterns(self):
        """Test custom log patterns"""
        custom_patterns = [
            "Custom application starting...",
            "Loading custom configuration...",
            "Custom processing complete",
        ]

        config = {"log_patterns": custom_patterns, "execution_delay": 0.1}
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        success, execution_id = executor.launch_job(job)
        self.assertTrue(success)

        logs = executor.get_logs(execution_id)

        # Check that custom patterns are in the logs
        for pattern in custom_patterns:
            self.assertIn(pattern, logs)

    def test_execution_time_calculation(self):
        """Test execution time calculation based on job properties"""
        config = {"execution_delay": 2.0}
        executor = MockExecutor(config)

        # Test with high memory job
        high_memory_job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="tensorflow/tensorflow:latest",
            memory_limit=16384,
            cpu_limit=8.0,
            timeout_seconds=7200,
            created_by=self.user,
        )

        # Test with regular job
        regular_job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        high_memory_time = executor._calculate_execution_time(high_memory_job)
        regular_time = executor._calculate_execution_time(regular_job)

        # High memory job should take longer
        self.assertGreater(high_memory_time, regular_time)

    def test_performance_stats_tracking(self):
        """Test performance statistics tracking"""
        config = {"execution_delay": 0.1}
        executor = MockExecutor(config)

        # Initially no stats
        stats = executor.get_performance_stats()
        self.assertEqual(stats["total_executions"], 0)

        # Run a job
        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        success, execution_id = executor.launch_job(job)
        self.assertTrue(success)

        harvest_success = executor.harvest_job(job)
        self.assertTrue(harvest_success)

        # Should have stats now
        stats = executor.get_performance_stats()
        self.assertEqual(stats["total_executions"], 1)
        self.assertGreater(stats["avg_execution_time"], 0)
        self.assertGreater(stats["avg_memory_peak"], 0)
        self.assertGreater(stats["avg_cpu_usage"], 0)

    def test_active_executions_tracking(self):
        """Test active executions tracking"""
        config = {"execution_delay": 10.0}  # Long execution
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        # No active executions initially
        active = executor.get_active_executions()
        self.assertEqual(len(active), 0)

        # Launch job
        success, execution_id = executor.launch_job(job)
        self.assertTrue(success)

        # Should have one active execution
        active = executor.get_active_executions()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["execution_id"], execution_id)
        self.assertEqual(active[0]["job_id"], str(job.id))

        # Cleanup removes from tracking
        executor.cleanup(execution_id)
        active = executor.get_active_executions()
        self.assertEqual(len(active), 0)

    def test_timeout_simulation(self):
        """Test timeout simulation"""
        config = {
            "simulate_timeout": True,
            "timeout_rate": 1.0,  # 100% timeout rate
            "execution_delay": 0.1,
        }
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        success, execution_id = executor.launch_job(job)
        self.assertTrue(success)

        # Harvest should mark as timeout
        harvest_success = executor.harvest_job(job)
        self.assertTrue(harvest_success)

        job.refresh_from_db()
        self.assertEqual(job.status, "timeout")

    def test_execution_not_found(self):
        """Test behavior when execution is not found"""
        config = {}
        executor = MockExecutor(config)

        # Check status for non-existent execution
        status = executor.check_status("non-existent-id")
        self.assertEqual(status, "not-found")

        # Get logs for non-existent execution
        logs = executor.get_logs("non-existent-id")
        self.assertIn("Execution not found", logs)

        # Get resource usage for non-existent execution
        usage = executor.get_resource_usage("non-existent-id")
        self.assertIsNotNone(usage)  # Should return defaults

    def test_realistic_status_progression(self):
        """Test realistic status progression over time"""
        config = {
            "execution_delay": 1.0,  # 1 second execution
            "exit_code_distribution": {0: 1.0},  # Ensure success
        }

        # Mock the random execution time calculation to be deterministic
        with patch("random.uniform", return_value=1.0):  # No randomness
            executor = MockExecutor(config)

            job = ContainerJob.objects.create(
                docker_host=self.docker_host,
                docker_image="alpine:latest",
                memory_limit=128,
                cpu_limit=0.5,
                timeout_seconds=300,
                # executor_type now determined by docker_host
                created_by=self.user,
            )

            success, execution_id = executor.launch_job(job)
            self.assertTrue(success)

            # Should be running initially for longer executions
            status = executor.check_status(execution_id)
            self.assertEqual(status, "running")

            # Wait for completion
            time.sleep(1.1)

            # Should be completed now
            status = executor.check_status(execution_id)
            self.assertEqual(status, "completed")

    def test_execution_record_creation(self):
        """Test that execution records are properly created"""
        config = {"execution_delay": 0.1}
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        success, execution_id = executor.launch_job(job)
        self.assertTrue(success)

        # Should have updated job with execution data
        job.refresh_from_db()
        self.assertIsNotNone(job.stdout_log)
        self.assertIn("Mock execution started", job.stdout_log)
        self.assertIn("Mock container", job.docker_log)

        # Harvest should update execution record
        harvest_success = executor.harvest_job(job)
        self.assertTrue(harvest_success)

        job.refresh_from_db()
        self.assertGreater(job.max_memory_usage, 0)
        self.assertGreater(job.cpu_usage_percent, 0)

    def test_reset_performance_stats(self):
        """Test resetting performance statistics"""
        config = {"execution_delay": 0.1}
        executor = MockExecutor(config)

        # Run a job to generate stats
        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            created_by=self.user,
        )

        success, execution_id = executor.launch_job(job)
        self.assertTrue(success)

        harvest_success = executor.harvest_job(job)
        self.assertTrue(harvest_success)

        # Should have stats
        stats = executor.get_performance_stats()
        self.assertEqual(stats["total_executions"], 1)

        # Reset stats
        executor.reset_performance_stats()

        # Should be empty again
        stats = executor.get_performance_stats()
        self.assertEqual(stats["total_executions"], 0)

    def test_container_config_generation(self):
        """Test container configuration generation"""
        config = {}
        executor = MockExecutor(config)

        job = ContainerJob.objects.create(
            docker_host=self.docker_host,
            docker_image="alpine:latest",
            memory_limit=128,
            cpu_limit=0.5,
            timeout_seconds=300,
            command="echo 'custom command'",
            override_environment="TEST_VAR=test_value",
            created_by=self.user,
        )

        container_config = executor._get_container_config(job)

        self.assertEqual(container_config["image"], "alpine:latest")
        self.assertEqual(container_config["memory_limit"], "128MB")
        self.assertEqual(container_config["cpu_limit"], 0.5)
        self.assertTrue(container_config["command_override"])
        self.assertEqual(container_config["environment_vars"], 1)
