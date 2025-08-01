"""
Simple additional tests for process_container_jobs command to improve coverage.

These tests focus on simple coverage improvements without complex mocking.
"""

from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.test import TestCase

from container_manager.executors.exceptions import (
    ExecutorConnectionError,
    ExecutorResourceError,
)
from container_manager.management.commands.process_container_jobs import Command
from container_manager.models import ContainerJob, ExecutorHost


class ProcessContainerJobsSimpleTest(TestCase):
    """Simple tests for process_container_jobs command"""

    def setUp(self):
        # Create test data
        self.host = ExecutorHost.objects.create(
            name="test-host",
            connection_string="tcp://localhost:2376",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Set up command with mocked output
        self.command = Command()
        self.command.stdout = StringIO()

    def test_validate_host_filter_invalid_host(self):
        """Test _validate_host_filter with invalid host raises CommandError"""
        with self.assertRaises(CommandError) as context:
            self.command._validate_host_filter("nonexistent-host")

        self.assertIn(
            'Docker host "nonexistent-host" not found', str(context.exception)
        )

    def test_validate_host_filter_valid_host(self):
        """Test _validate_host_filter with valid host"""
        # Should not raise exception and should write output
        self.command._validate_host_filter("test-host")

        output = self.command.stdout.getvalue()
        self.assertIn("Processing jobs only for host: test-host", output)

    def test_validate_host_filter_none(self):
        """Test _validate_host_filter with None"""
        # Should not raise exception or write output
        self.command._validate_host_filter(None)

        output = self.command.stdout.getvalue()
        self.assertEqual(output, "")

    def test_display_completion_summary(self):
        """Test _display_completion_summary output"""
        self.command._display_completion_summary(processed_count=10, error_count=2)

        output = self.command.stdout.getvalue()
        self.assertIn("Job processor stopped", output)
        self.assertIn("Processed 10 jobs with 2 errors", output)

    def test_report_cycle_results_with_activity(self):
        """Test _report_cycle_results with activity"""
        self.command._report_cycle_results(
            launched=2, harvested=1, total_processed=5, total_errors=0
        )

        output = self.command.stdout.getvalue()
        self.assertIn("Launched 2 jobs", output)
        self.assertIn("harvested 1 jobs", output)
        self.assertIn("total processed: 5", output)
        self.assertIn("errors: 0", output)

    def test_report_cycle_results_no_activity(self):
        """Test _report_cycle_results with no activity"""
        self.command._report_cycle_results(
            launched=0, harvested=0, total_processed=5, total_errors=0
        )

        output = self.command.stdout.getvalue()
        self.assertEqual(output, "")  # No output when no activity

    def test_launch_single_job_routing_factory(self):
        """Test launch_single_job with factory routing"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command, "launch_job_with_factory", return_value=True
        ) as mock_factory:
            result = self.command.launch_single_job(
                job, use_factory=True, force_executor_type="docker"
            )

            self.assertTrue(result)
            mock_factory.assert_called_once_with(job, "docker")

    def test_launch_single_job_routing_executor_provider(self):
        """Test launch_single_job with docker service routing"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command, "launch_job_with_executor_provider", return_value=True
        ) as mock_docker:
            result = self.command.launch_single_job(
                job, use_factory=False, force_executor_type=None
            )

            self.assertTrue(result)
            mock_docker.assert_called_once_with(job)

    def test_process_single_cycle_basic(self):
        """Test _process_single_cycle basic functionality"""
        config = {
            "host_filter": None,
            "max_jobs": 5,
            "factory_enabled": True,
            "executor_type": None,
        }

        with patch.object(
            self.command, "process_pending_jobs", return_value=2
        ) as mock_pending:
            with patch.object(
                self.command, "monitor_running_jobs", return_value=1
            ) as mock_monitor:
                launched, harvested = self.command._process_single_cycle(config)

                self.assertEqual(launched, 2)
                self.assertEqual(harvested, 1)

                mock_pending.assert_called_once_with(None, 5, True, None)
                mock_monitor.assert_called_once_with(None)

    def test_run_cleanup_if_requested_enabled(self):
        """Test _run_cleanup_if_requested when cleanup is enabled shows deprecation warning"""
        config = {"cleanup": True, "cleanup_hours": 48}

        # Should show deprecation warning since docker_service is removed
        self.command._run_cleanup_if_requested(config)

        output = self.command.stdout.getvalue()
        self.assertIn("Container cleanup temporarily disabled", output)
        self.assertIn("docker_service deprecated", output)

    def test_run_cleanup_if_requested_disabled(self):
        """Test _run_cleanup_if_requested when cleanup is disabled"""
        config = {"cleanup": False, "cleanup_hours": 24}

        # Should complete without error when cleanup is disabled
        self.command._run_cleanup_if_requested(config)
        # No assertions needed - just verify it doesn't crash

    # New tests for uncovered code paths

    def test_launch_job_with_factory_force_executor_type(self):
        """Test launch_job_with_factory with forced executor type"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = patch(
                "container_manager.executors.docker.DockerExecutor"
            ).start()
            mock_executor.launch_job.return_value = (True, "container-123")
            mock_get_executor.return_value = mock_executor

            result = self.command.launch_job_with_factory(
                job, force_executor_type="docker"
            )

            self.assertTrue(result)
            job.refresh_from_db()
            self.assertEqual(job.docker_host.executor_type, "docker")
            self.assertIn("Forced to docker", job.routing_reason)

    def test_launch_job_with_factory_direct_assignment(self):
        """Test launch_job_with_factory with direct host assignment"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,  # Direct host assignment
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = patch(
                "container_manager.executors.docker.DockerExecutor"
            ).start()
            mock_executor.launch_job.return_value = (True, "container-456")
            mock_get_executor.return_value = mock_executor

            result = self.command.launch_job_with_factory(job)

            self.assertTrue(result)
            job.refresh_from_db()
            self.assertEqual(job.docker_host.executor_type, "docker")

    def test_launch_job_with_factory_executor_retrieval_failure(self):
        """Test launch_job_with_factory when executor retrieval fails"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        # Mock executor factory to fail on get_executor
        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_get_executor.side_effect = Exception("Executor creation failed")

            with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
                result = self.command.launch_job_with_factory(job)

                self.assertFalse(result)
                mock_mark_failed.assert_called_once_with(
                    job, "Executor creation failed"
                )

    def test_launch_job_with_factory_launch_failure(self):
        """Test launch_job_with_factory when job launch fails"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = patch(
                "container_manager.executors.docker.DockerExecutor"
            ).start()
            mock_executor.launch_job.return_value = (False, "Launch failed")
            mock_get_executor.return_value = mock_executor

            result = self.command.launch_job_with_factory(
                job, force_executor_type="docker"
            )

            self.assertFalse(result)

    def test_launch_job_with_factory_executor_resource_error(self):
        """Test launch_job_with_factory with ExecutorResourceError"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
                mock_get_executor.side_effect = ExecutorResourceError("No resources")

                result = self.command.launch_job_with_factory(
                    job, force_executor_type="docker"
                )

                self.assertFalse(result)
                mock_mark_failed.assert_called_once_with(
                    job, "No available executors: No resources"
                )

    def test_launch_job_with_factory_general_exception(self):
        """Test launch_job_with_factory with general exception"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
                mock_get_executor.side_effect = Exception("General error")

                result = self.command.launch_job_with_factory(
                    job, force_executor_type="docker"
                )

                self.assertFalse(result)
                mock_mark_failed.assert_called_once_with(job, "General error")

    def test_launch_job_with_executor_provider_connection_error(self):
        """Test launch_job_with_executor_provider with connection error"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_get_executor.side_effect = ExecutorConnectionError("Connection failed")

            with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
                result = self.command.launch_job_with_executor_provider(job)

                self.assertFalse(result)
                mock_mark_failed.assert_called_once_with(job, "Connection failed")

    def test_launch_job_with_executor_provider_success(self):
        """Test launch_job_with_executor_provider success"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.launch_job.return_value = (True, "execution-123")
            mock_get_executor.return_value = mock_executor

            result = self.command.launch_job_with_executor_provider(job)

            self.assertTrue(result)
            mock_executor.launch_job.assert_called_once_with(job)
            job.refresh_from_db()
            self.assertEqual(job.execution_id, "execution-123")

    def test_launch_job_with_executor_provider_launch_failure(self):
        """Test launch_job_with_executor_provider launch failure"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.launch_job.return_value = (False, "Launch failed")
            mock_get_executor.return_value = mock_executor

            result = self.command.launch_job_with_executor_provider(job)

            self.assertFalse(result)

    def test_launch_job_with_executor_provider_exception(self):
        """Test launch_job_with_executor_provider with exception"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.launch_job.side_effect = Exception("Launch error")
            mock_get_executor.return_value = mock_executor

            with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
                result = self.command.launch_job_with_executor_provider(job)

                self.assertFalse(result)
                mock_mark_failed.assert_called_once_with(job, "Launch error")

    def test_monitor_running_jobs_no_jobs(self):
        """Test monitor_running_jobs when no running jobs exist"""
        result = self.command.monitor_running_jobs()

        self.assertEqual(result, 0)

    def test_monitor_running_jobs_with_jobs(self):
        """Test monitor_running_jobs with running jobs"""
        # Create running jobs
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job-1",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job-2",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor._batch_check_statuses.return_value = 2  # Both jobs harvested
            # Ensure the executor has the required attributes for batch processing
            mock_executor._get_client = Mock()
            mock_get_executor.return_value = mock_executor

            result = self.command.monitor_running_jobs()

            self.assertEqual(result, 2)
            mock_executor._batch_check_statuses.assert_called_once()

    def test_monitor_running_jobs_with_exception(self):
        """Test monitor_running_jobs when monitoring throws exception"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_get_executor.side_effect = Exception("Executor error")

            result = self.command.monitor_running_jobs()

            self.assertEqual(result, 1)  # Job was counted as harvested due to failure

    def test_monitor_running_jobs_should_stop(self):
        """Test monitor_running_jobs respects should_stop flag"""
        # Create running jobs
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job-1",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job-2",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()

            # Set should_stop after first call to simulate early termination
            def batch_side_effect(*args):
                self.command.should_stop = True
                return 1  # Only process first job before stopping

            mock_executor._batch_check_statuses.side_effect = batch_side_effect
            mock_executor._get_client = Mock()
            mock_get_executor.return_value = mock_executor

            result = self.command.monitor_running_jobs()

            self.assertEqual(result, 1)  # Only first job processed
            mock_executor._batch_check_statuses.assert_called_once()

    def test_get_running_jobs_with_host_filter(self):
        """Test _get_running_jobs with host filter"""
        # Create jobs on different hosts
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="job-on-test-host",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        other_host = ExecutorHost.objects.create(
            name="other-host",
            connection_string="tcp://localhost:2378",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="job-on-other-host",
            status="running",
            docker_host=other_host,
            created_by=self.user,
        )

        # Test with host filter
        filtered_jobs = self.command._get_running_jobs("test-host")
        job_ids = [job.id for job in filtered_jobs]

        self.assertEqual(len(filtered_jobs), 1)
        self.assertIn(job1.id, job_ids)
        self.assertNotIn(job2.id, job_ids)

    def test_get_running_jobs_no_filter(self):
        """Test _get_running_jobs without host filter"""
        # Create running jobs
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job-1",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job-2",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        # Also create non-running job
        ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="pending-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        jobs = self.command._get_running_jobs()
        self.assertEqual(len(jobs), 2)  # Only running jobs returned

    def test_run_cleanup_if_requested_shows_deprecation_message(self):
        """Test _run_cleanup_if_requested shows deprecation message"""
        config = {"cleanup": True, "cleanup_hours": 24}

        # Should show deprecation message since docker_service is removed
        self.command._run_cleanup_if_requested(config)

        output = self.command.stdout.getvalue()
        self.assertIn("Container cleanup temporarily disabled", output)
        self.assertIn("docker_service deprecated", output)

    def test_display_startup_info_with_factory_disabled(self):
        """Test _display_startup_info with factory disabled"""
        config = {
            "poll_interval": 10,
            "max_jobs": 5,
            "factory_enabled": False,
        }

        self.command._display_startup_info(config)

        output = self.command.stdout.getvalue()
        self.assertIn("Starting container job processor", output)
        self.assertIn("poll_interval=10s", output)
        self.assertIn("max_jobs=5", output)
        self.assertIn("routing=Direct Docker", output)

    def test_display_startup_info_with_factory_enabled(self):
        """Test _display_startup_info with factory enabled"""
        config = {
            "poll_interval": 5,
            "max_jobs": 10,
            "factory_enabled": True,
            "executor_type": "docker",
        }

        with patch.object(self.command, "_display_executor_info") as mock_display:
            self.command._display_startup_info(config)

            output = self.command.stdout.getvalue()
            self.assertIn("routing=ExecutorFactory", output)
            mock_display.assert_called_once_with("docker")

    def test_display_executor_info_no_force(self):
        """Test _display_executor_info without forced executor type"""
        self.command._display_executor_info(None)

        output = self.command.stdout.getvalue()
        self.assertIn("Available executors:", output)
        self.assertIn("docker", output)

    def test_display_executor_info_with_force(self):
        """Test _display_executor_info with forced executor type"""
        self.command._display_executor_info("mock")

        output = self.command.stdout.getvalue()
        self.assertIn("Forcing executor type: mock", output)

    # New tests for previously uncovered areas

    def test_add_arguments(self):
        """Test add_arguments method adds all expected arguments"""
        import argparse

        parser = argparse.ArgumentParser()
        command = Command()
        command.add_arguments(parser)

        # Check that all expected arguments were added
        action_names = [
            action.dest for action in parser._actions if action.dest != "help"
        ]
        expected_args = [
            "poll_interval",
            "max_jobs",
            "host",
            "single_run",
            "cleanup",
            "cleanup_hours",
            "use_factory",
            "executor_type",
        ]

        for arg in expected_args:
            self.assertIn(arg, action_names)

    def test_parse_and_validate_options_defaults(self):
        """Test _parse_and_validate_options with default values"""
        options = {
            "poll_interval": 5,
            "max_jobs": 10,
            "host": None,
            "single_run": False,
            "cleanup": False,
            "cleanup_hours": 24,
            "use_factory": False,
            "executor_type": None,
        }

        config = self.command._parse_and_validate_options(options)

        self.assertEqual(config["poll_interval"], 5)
        self.assertEqual(config["max_jobs"], 10)
        self.assertIsNone(config["host_filter"])
        self.assertFalse(config["single_run"])
        self.assertFalse(config["cleanup"])
        self.assertEqual(config["cleanup_hours"], 24)
        self.assertFalse(config["use_factory"])
        self.assertIsNone(config["executor_type"])

    def test_parse_and_validate_options_with_executor_type(self):
        """Test _parse_and_validate_options enables factory when executor_type is set"""
        options = {
            "poll_interval": 5,
            "max_jobs": 10,
            "host": None,
            "single_run": False,
            "cleanup": False,
            "cleanup_hours": 24,
            "use_factory": False,
            "executor_type": "docker",
        }

        config = self.command._parse_and_validate_options(options)

        # Factory should be enabled when executor_type is specified
        self.assertTrue(config["factory_enabled"])
        self.assertEqual(config["executor_type"], "docker")

    def test_handle_method_basic_flow(self):
        """Test handle method basic flow without running main loop"""
        # Mock all the methods called by handle
        with patch.object(self.command, "_parse_and_validate_options") as mock_parse:
            with patch.object(self.command, "_display_startup_info") as mock_display:
                with patch.object(
                    self.command, "_run_cleanup_if_requested"
                ) as mock_cleanup:
                    with patch.object(
                        self.command, "_validate_host_filter"
                    ) as mock_validate:
                        with patch.object(
                            self.command, "_run_processing_loop"
                        ) as mock_loop:
                            with patch.object(
                                self.command, "_display_completion_summary"
                            ) as mock_summary:
                                mock_parse.return_value = {"test": "config"}
                                mock_loop.return_value = (
                                    10,
                                    2,
                                )  # processed_count, error_count

                                # Call handle with test options
                                options = {"poll_interval": 5}
                                self.command.handle(**options)

                                # Verify all methods were called
                                mock_parse.assert_called_once_with(options)
                                mock_display.assert_called_once_with({"test": "config"})
                                mock_cleanup.assert_called_once_with({"test": "config"})
                                mock_validate.assert_called_once_with(
                                    None
                                )  # config.get('host_filter')
                                mock_loop.assert_called_once_with({"test": "config"})
                                mock_summary.assert_called_once_with(10, 2)

    def test_process_pending_jobs_basic(self):
        """Test process_pending_jobs basic functionality"""
        # Create pending jobs
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job-1",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job-2",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "launch_single_job") as mock_launch:
            mock_launch.return_value = True

            launched = self.command.process_pending_jobs(max_jobs=5, use_factory=False)

            self.assertEqual(launched, 2)
            self.assertEqual(mock_launch.call_count, 2)

    def test_process_pending_jobs_with_host_filter(self):
        """Test process_pending_jobs with host filter"""
        # Create another host
        other_host = ExecutorHost.objects.create(
            name="other-host",
            connection_string="tcp://localhost:2377",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )

        # Create jobs on different hosts
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="job-on-test-host",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="job-on-other-host",
            status="pending",
            docker_host=other_host,
            created_by=self.user,
        )

        with patch.object(self.command, "launch_single_job") as mock_launch:
            mock_launch.return_value = True

            launched = self.command.process_pending_jobs(
                host_filter="test-host", max_jobs=10, use_factory=False
            )

            self.assertEqual(launched, 1)  # Only job on test-host should be processed
            mock_launch.assert_called_once_with(job1, False, None)

    def test_process_pending_jobs_should_stop(self):
        """Test process_pending_jobs respects should_stop flag"""
        # Create pending jobs
        job1 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job-1",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )
        job2 = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job-2",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        def side_effect_stop_after_first(*args):
            self.command.should_stop = True
            return True

        with patch.object(self.command, "launch_single_job") as mock_launch:
            mock_launch.side_effect = side_effect_stop_after_first

            launched = self.command.process_pending_jobs(max_jobs=10, use_factory=False)

            self.assertEqual(launched, 1)  # Should stop after first job
            self.assertEqual(mock_launch.call_count, 1)

    def test_process_pending_jobs_exception_handling(self):
        """Test process_pending_jobs handles exceptions gracefully"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "launch_single_job") as mock_launch:
            with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
                mock_launch.side_effect = Exception("Launch error")

                launched = self.command.process_pending_jobs(
                    max_jobs=10, use_factory=False
                )

                self.assertEqual(launched, 0)
                mock_mark_failed.assert_called_once_with(job, "Launch error")

    def test_mark_job_failed_basic(self):
        """Test mark_job_failed basic functionality"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
        )

        self.command.mark_job_failed(job, "Test error message")

        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIsNotNone(job.completed_at)
        self.assertIn("Test error message", job.docker_log)

    def test_mark_job_failed_with_existing_log(self):
        """Test mark_job_failed appends to existing log"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="test-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
            docker_log="Existing log content",
        )

        self.command.mark_job_failed(job, "New error message")

        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertIn("Existing log content", job.docker_log)
        self.assertIn("New error message", job.docker_log)

    # Tests for job monitoring and status checking functionality

    def test_monitor_single_job_timeout(self):
        """Test _monitor_single_job handles job timeout"""
        from datetime import timedelta

        from django.utils import timezone

        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="timeout-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
            started_at=timezone.now() - timedelta(seconds=3600),  # Started 1 hour ago
            timeout_seconds=1800,  # 30 minute timeout
        )

        with patch.object(self.command, "handle_job_timeout") as mock_timeout:
            result = self.command._monitor_single_job(job)

            self.assertEqual(result, 1)  # Job was harvested due to timeout
            mock_timeout.assert_called_once_with(job)

    def test_monitor_single_job_no_timeout(self):
        """Test _monitor_single_job when job hasn't timed out"""
        from django.utils import timezone

        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
            started_at=timezone.now(),  # Just started
            timeout_seconds=3600,  # 1 hour timeout
        )

        with patch.object(self.command, "check_job_status") as mock_check_status:
            with patch.object(self.command, "_handle_job_status") as mock_handle_status:
                mock_check_status.return_value = "running"
                mock_handle_status.return_value = 0

                result = self.command._monitor_single_job(job)

                self.assertEqual(result, 0)  # Job still running
                mock_check_status.assert_called_once_with(job)
                mock_handle_status.assert_called_once_with(job, "running")

    def test_job_has_timed_out_true(self):
        """Test _job_has_timed_out returns True when job timed out"""
        from datetime import timedelta

        from django.utils import timezone

        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="timeout-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
            started_at=timezone.now() - timedelta(seconds=3600),  # Started 1 hour ago
            timeout_seconds=1800,  # 30 minute timeout
        )

        now = timezone.now()
        result = self.command._job_has_timed_out(job, now)

        self.assertTrue(result)

    def test_job_has_timed_out_false(self):
        """Test _job_has_timed_out returns False when job hasn't timed out"""
        from django.utils import timezone

        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="running-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
            started_at=timezone.now(),  # Just started
            timeout_seconds=3600,  # 1 hour timeout
        )

        now = timezone.now()
        result = self.command._job_has_timed_out(job, now)

        self.assertFalse(result)

    def test_job_has_timed_out_no_started_at(self):
        """Test _job_has_timed_out returns False when started_at is None"""
        from django.utils import timezone

        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="not-started-job",
            status="pending",
            docker_host=self.host,
            created_by=self.user,
            started_at=None,
            timeout_seconds=3600,
        )

        now = timezone.now()
        result = self.command._job_has_timed_out(job, now)

        self.assertFalse(result)

    def test_handle_job_status_completed(self):
        """Test _handle_job_status with completed status"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="completed-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "_harvest_successful_job") as mock_harvest:
            mock_harvest.return_value = 1

            result = self.command._handle_job_status(job, "completed")

            self.assertEqual(result, 1)
            mock_harvest.assert_called_once_with(job)

    def test_handle_job_status_exited(self):
        """Test _handle_job_status with exited status"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="exited-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "_harvest_successful_job") as mock_harvest:
            mock_harvest.return_value = 1

            result = self.command._handle_job_status(job, "exited")

            self.assertEqual(result, 1)
            mock_harvest.assert_called_once_with(job)

    def test_handle_job_status_failed(self):
        """Test _handle_job_status with failed status"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="failed-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
            result = self.command._handle_job_status(job, "failed")

            self.assertEqual(result, 1)
            mock_mark_failed.assert_called_once_with(job, "Job execution failed")

    def test_handle_job_status_not_found(self):
        """Test _handle_job_status with not-found status"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="not-found-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "mark_job_failed") as mock_mark_failed:
            result = self.command._handle_job_status(job, "not-found")

            self.assertEqual(result, 1)
            mock_mark_failed.assert_called_once_with(job, "Execution not found")

    def test_handle_job_status_running(self):
        """Test _handle_job_status with running status"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="still-running-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        result = self.command._handle_job_status(job, "running")

        self.assertEqual(result, 0)  # Continue monitoring

    def test_harvest_successful_job_success(self):
        """Test _harvest_successful_job when harvest succeeds"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="harvest-success-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "harvest_completed_job") as mock_harvest:
            mock_harvest.return_value = True

            result = self.command._harvest_successful_job(job)

            self.assertEqual(result, 1)
            mock_harvest.assert_called_once_with(job)

            output = self.command.stdout.getvalue()
            self.assertIn(f"Harvested job {job.id}", output)

    def test_harvest_successful_job_failure(self):
        """Test _harvest_successful_job when harvest fails"""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="harvest-failure-job",
            status="running",
            docker_host=self.host,
            created_by=self.user,
        )

        with patch.object(self.command, "harvest_completed_job") as mock_harvest:
            mock_harvest.return_value = False

            result = self.command._harvest_successful_job(job)

            self.assertEqual(result, 0)
            mock_harvest.assert_called_once_with(job)

    def test_check_job_status_docker_executor(self):
        """Test check_job_status with docker executor"""
        docker_host = ExecutorHost.objects.create(
            name="docker-host",
            connection_string="tcp://localhost:2380",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="docker-job",
            status="running",
            docker_host=docker_host,
            created_by=self.user,
            execution_id="container-123",
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "running"
            mock_get_executor.return_value = mock_executor

            result = self.command.check_job_status(job)

            self.assertEqual(result, "running")
            mock_get_executor.assert_called_once_with(docker_host)
            mock_executor.check_status.assert_called_once_with("container-123")

    def test_check_job_status_with_execution_id(self):
        """Test check_job_status with execution_id"""
        docker_host = ExecutorHost.objects.create(
            name="docker-host-with-execution",
            connection_string="tcp://localhost:2381",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="job-with-execution",
            status="running",
            docker_host=docker_host,
            created_by=self.user,
            execution_id="container-456",
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "exited"
            mock_get_executor.return_value = mock_executor

            result = self.command.check_job_status(job)

            self.assertEqual(result, "exited")
            mock_executor.check_status.assert_called_once_with("container-456")

    def test_check_job_status_non_docker_executor(self):
        """Test check_job_status with non-docker executor"""
        mock_host = ExecutorHost.objects.create(
            name="mock-host",
            connection_string="tcp://localhost:2382",
            host_type="tcp",
            is_active=True,
            executor_type="mock",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="mock-job",
            status="running",
            docker_host=mock_host,
            created_by=self.user,
        )

        # Set execution_id for the job
        job.execution_id = "mock-execution-123"
        job.save()

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.check_status.return_value = "completed"
            mock_get_executor.return_value = mock_executor

            result = self.command.check_job_status(job)

            self.assertEqual(result, "completed")
            mock_get_executor.assert_called_once_with(job.docker_host)
            mock_executor.check_status.assert_called_once_with("mock-execution-123")

    def test_check_job_status_non_docker_executor_exception(self):
        """Test check_job_status with non-docker executor when exception occurs"""
        mock_host = ExecutorHost.objects.create(
            name="exception-host",
            connection_string="tcp://localhost:2383",
            host_type="tcp",
            is_active=True,
            executor_type="mock",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="exception-job",
            status="running",
            docker_host=mock_host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_get_executor.side_effect = Exception("Executor error")

            result = self.command.check_job_status(job)

            self.assertEqual(result, "error")

    def test_harvest_completed_job_docker_executor(self):
        """Test harvest_completed_job with docker executor"""
        docker_host = ExecutorHost.objects.create(
            name="docker-harvest-host",
            connection_string="tcp://localhost:2384",
            host_type="tcp",
            is_active=True,
            executor_type="docker",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="docker-harvest-job",
            status="running",
            docker_host=docker_host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.harvest_job.return_value = True
            mock_get_executor.return_value = mock_executor

            result = self.command.harvest_completed_job(job)

            self.assertTrue(result)
            mock_get_executor.assert_called_once_with(docker_host)
            mock_executor.harvest_job.assert_called_once_with(job)

    def test_harvest_completed_job_non_docker_executor(self):
        """Test harvest_completed_job with non-docker executor"""
        mock_host = ExecutorHost.objects.create(
            name="mock-harvest-host",
            connection_string="tcp://localhost:2385",
            host_type="tcp",
            is_active=True,
            executor_type="mock",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="mock-harvest-job",
            status="running",
            docker_host=mock_host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_executor = Mock()
            mock_executor.harvest_job.return_value = True
            mock_get_executor.return_value = mock_executor

            result = self.command.harvest_completed_job(job)

            self.assertTrue(result)
            mock_get_executor.assert_called_once_with(job.docker_host)
            mock_executor.harvest_job.assert_called_once_with(job)

    def test_harvest_completed_job_non_docker_executor_exception(self):
        """Test harvest_completed_job with non-docker executor when exception occurs"""
        mock_host = ExecutorHost.objects.create(
            name="exception-harvest-host",
            connection_string="tcp://localhost:2386",
            host_type="tcp",
            is_active=True,
            executor_type="mock",
        )
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            command="python script.py",
            name="exception-harvest-job",
            status="running",
            docker_host=mock_host,
            created_by=self.user,
        )

        with patch.object(
            self.command.executor_factory, "get_executor"
        ) as mock_get_executor:
            mock_get_executor.side_effect = Exception("Harvest error")

            result = self.command.harvest_completed_job(job)

            self.assertFalse(result)
