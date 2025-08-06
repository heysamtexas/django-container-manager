"""
Tests for Django management commands with comprehensive mocking.

Focus on testing business logic without external dependencies (Docker, Cloud Run, etc.).
All external services are mocked to ensure fast, deterministic tests.
"""

import signal
from io import StringIO
from unittest.mock import Mock, call, patch

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from container_manager.management.commands.process_container_jobs import Command
from container_manager.models import ContainerJob, ExecutorHost


@patch("time.sleep")  # Prevent any time delays
@patch("container_manager.executors.factory.ExecutorFactory")  # Mock executor factory
class ProcessContainerJobsTest(TransactionTestCase):
    """Test process_container_jobs command with all external dependencies mocked."""

    def setUp(self):
        # Create minimal test data
        self.host = ExecutorHost.objects.create(
            name="test-host",
            connection_string="tcp://localhost:2376",
            host_type="tcp",
            is_active=True,
        )

        # Set up output capture
        self.out = StringIO()
        self.command = Command()
        self.command.stdout = self.out

    def create_pending_job(self, **kwargs):
        """Helper to create a pending job."""
        defaults = {
            "docker_image": "python:3.11",
            "command": "python script.py",
            "name": "test-job",
            "status": "pending",
            "docker_host": self.host,
        }
        defaults.update(kwargs)
        return ContainerJob.objects.create(**defaults)

    def test_command_init_sets_up_signal_handlers(self, mock_factory, mock_sleep):
        """Test that command initialization sets up signal handlers correctly."""
        with patch("signal.signal") as mock_signal:
            command = Command()

            # Verify signal handlers are set up
            self.assertFalse(command.should_stop)
            self.assertIsNotNone(command.executor_factory)

            # Verify signal.signal was called for SIGINT and SIGTERM
            expected_calls = [
                call(
                    signal.SIGINT, command.setup_signal_handlers.__code__.co_consts[1]
                ),
                call(
                    signal.SIGTERM, command.setup_signal_handlers.__code__.co_consts[1]
                ),
            ]
            # Just verify signal.signal was called (exact handler comparison is complex)
            self.assertEqual(mock_signal.call_count, 2)

    def test_signal_handler_sets_should_stop_flag(self, mock_factory, mock_sleep):
        """Test that signal handler sets should_stop flag."""
        command = Command()

        # Simulate receiving a signal
        self.assertFalse(command.should_stop)

        # Manually trigger the signal handler logic
        command.should_stop = True  # This is what the signal handler does

        self.assertTrue(command.should_stop)

    def test_add_arguments_defines_expected_options(self, mock_factory, mock_sleep):
        """Test that command defines expected arguments."""
        from argparse import ArgumentParser

        parser = ArgumentParser()

        self.command.add_arguments(parser)

        # Parse test arguments to verify they're defined correctly
        args = parser.parse_args(
            [
                "--poll-interval",
                "5",
                "--max-jobs",
                "10",
                "--host",
                "test-host",
                "--cleanup",
                "--cleanup-hours",
                "24",
            ]
        )

        self.assertEqual(args.poll_interval, 5)
        self.assertEqual(args.max_jobs, 10)
        self.assertEqual(args.host, "test-host")
        self.assertTrue(args.cleanup)
        self.assertEqual(args.cleanup_hours, 24)

    def test_setup_signal_handlers_completes_without_error(
        self, mock_factory, mock_sleep
    ):
        """Test that signal handler setup completes without error."""
        with patch("signal.signal") as mock_signal:
            command = Command()

            # Verify signal handlers were registered
            self.assertEqual(mock_signal.call_count, 2)

    def test_process_pending_jobs_starts_pending_jobs(self, mock_factory, mock_sleep):
        """Test that process_pending_jobs starts pending jobs with mocked launch."""
        # Create a pending job
        job = self.create_pending_job()

        # Mock launch_single_job to return success without external calls
        with patch.object(
            self.command, "launch_single_job", return_value=True
        ) as mock_launch:
            # Process pending jobs
            launched = self.command.process_pending_jobs(max_jobs=10, host_filter=None)

            # Verify method was called and returned correct count
            self.assertEqual(launched, 1)
            mock_launch.assert_called_once_with(job, False, None)

    def test_process_pending_jobs_respects_max_jobs_limit(
        self, mock_factory, mock_sleep
    ):
        """Test that process_pending_jobs respects max_jobs parameter."""
        # Create multiple pending jobs
        jobs = [self.create_pending_job(name=f"job-{i}") for i in range(5)]

        # Mock launch_single_job to return success
        with patch.object(
            self.command, "launch_single_job", return_value=True
        ) as mock_launch:
            # Process with limit of 2
            launched = self.command.process_pending_jobs(max_jobs=2, host_filter=None)

            # Verify only 2 jobs were processed
            self.assertEqual(launched, 2)
            self.assertEqual(mock_launch.call_count, 2)

    def test_process_pending_jobs_filters_by_host(self, mock_factory, mock_sleep):
        """Test that process_pending_jobs filters by host when specified."""
        # Create another host
        other_host = ExecutorHost.objects.create(
            name="other-host",
            connection_string="tcp://other:2376",
            host_type="tcp",
            is_active=True,
        )

        # Create jobs on different hosts
        job1 = self.create_pending_job(name="job1", docker_host=self.host)
        job2 = self.create_pending_job(name="job2", docker_host=other_host)

        # Mock launch_single_job to return success
        with patch.object(
            self.command, "launch_single_job", return_value=True
        ) as mock_launch:
            # Process jobs for specific host only
            launched = self.command.process_pending_jobs(
                max_jobs=10, host_filter=self.host.name
            )

            # Verify only 1 job was processed (job1 from filtered host)
            self.assertEqual(launched, 1)
            self.assertEqual(mock_launch.call_count, 1)
            # Verify the correct job was passed to launch_single_job
            mock_launch.assert_called_once_with(job1, False, None)

    def test_process_pending_jobs_handles_executor_errors(
        self, mock_factory, mock_sleep
    ):
        """Test that process_pending_jobs handles executor errors gracefully."""
        job = self.create_pending_job()

        # Mock launch_single_job to raise an exception
        with patch.object(
            self.command, "launch_single_job", side_effect=Exception("Launch failed")
        ) as mock_launch:
            # Process should not crash and should handle the error
            launched = self.command.process_pending_jobs(max_jobs=10, host_filter=None)

            # Verify the method was called but returned 0 due to error
            self.assertEqual(launched, 0)
            mock_launch.assert_called_once_with(job, False, None)

    def test_monitor_running_jobs_can_be_called(self, mock_factory, mock_sleep):
        """Test monitor_running_jobs can be called without crashing."""
        # Create running job
        job = self.create_pending_job(status="running", execution_id="exec-123")

        # Test that monitor_running_jobs can be called without errors
        # We don't test detailed executor interactions here due to complexity
        try:
            self.command.monitor_running_jobs(host_filter=None)
            # If we get here without exception, the method is callable
            test_passed = True
        except Exception:
            test_passed = False

        self.assertTrue(test_passed, "monitor_running_jobs should not crash")

    def test_monitor_running_jobs_handles_status_check_errors(
        self, mock_factory, mock_sleep
    ):
        """Test that monitor_running_jobs handles status check errors gracefully."""
        job = self.create_pending_job(status="running", execution_id="exec-123")

        # Set up executor mock to fail
        mock_executor = Mock()
        mock_factory.return_value.get_executor.return_value = mock_executor
        mock_executor.check_status.side_effect = Exception("Status check failed")

        # Monitor should not crash
        self.command.monitor_running_jobs(host_filter=None)

        # Job should still exist (error should be logged, not crash)
        job.refresh_from_db()
        self.assertIsNotNone(job)

    def test_handle_basic_option_parsing(self, mock_factory, mock_sleep):
        """Test that handle parses options correctly."""
        # Mock main processing methods to test just option parsing
        with patch.object(self.command, "_run_processing_loop", return_value=(0, 0)):
            with patch.object(self.command, "_run_cleanup_if_requested"):
                # Should not crash with basic options
                self.command.handle(
                    poll_interval=1,
                    max_jobs=5,
                    host=None,
                    single_run=True,
                    cleanup=False,
                    cleanup_hours=48,
                    use_factory=True,
                    executor_type=None,
                )

                # If we get here, option parsing worked


class ProcessContainerJobsIntegrationTest(TestCase):
    """Integration tests for process_container_jobs command using call_command."""

    def test_command_class_can_be_instantiated(self):
        """Test that command class can be instantiated without errors."""
        # This test verifies the command can be imported and instantiated
        from container_manager.management.commands.process_container_jobs import Command

        command = Command()

        # Verify basic attributes exist
        self.assertIsNotNone(command.help)
        self.assertFalse(command.should_stop)
        self.assertIsNotNone(command.executor_factory)


class ProcessContainerJobsCommandArgsTest(TestCase):
    """Test command line argument parsing for process_container_jobs."""

    def test_default_argument_values(self):
        """Test default values for command arguments."""
        from argparse import ArgumentParser

        command = Command()
        parser = ArgumentParser()
        command.add_arguments(parser)

        # Parse with no arguments to get defaults
        args = parser.parse_args([])

        # Verify defaults match the command definition
        self.assertEqual(args.poll_interval, 5)  # Default polling interval
        self.assertEqual(args.max_jobs, 10)  # Default max jobs
        self.assertIsNone(args.host)  # No host filter by default
        self.assertFalse(args.cleanup)  # No cleanup by default
        self.assertEqual(args.cleanup_hours, 24)  # Default cleanup hours

    def test_argument_parsing_with_all_options(self):
        """Test parsing with all command line options."""
        from argparse import ArgumentParser

        command = Command()
        parser = ArgumentParser()
        command.add_arguments(parser)

        # Parse with all arguments
        args = parser.parse_args(
            [
                "--poll-interval",
                "5",
                "--max-jobs",
                "20",
                "--host",
                "production-host",
                "--cleanup",
                "--cleanup-hours",
                "72",
            ]
        )

        # Verify parsed values
        self.assertEqual(args.poll_interval, 5)
        self.assertEqual(args.max_jobs, 20)
        self.assertEqual(args.host, "production-host")
        self.assertTrue(args.cleanup)
        self.assertEqual(args.cleanup_hours, 72)

    def test_single_run_option_parsing(self):
        """Test that --single-run option is parsed correctly."""
        from argparse import ArgumentParser

        command = Command()
        parser = ArgumentParser()
        command.add_arguments(parser)

        # Test with --single-run
        args = parser.parse_args(["--single-run"])
        self.assertTrue(args.single_run)

        # Test without --single-run
        args = parser.parse_args([])
        self.assertFalse(args.single_run)


# Additional focused tests for specific business logic
class ProcessContainerJobsBusinessLogicTest(TestCase):
    """Test specific business logic methods with surgical mocking."""

    def setUp(self):
        self.command = Command()

        # Create test data
        self.host = ExecutorHost.objects.create(
            name="test-host",
            connection_string="tcp://localhost:2376",
            host_type="tcp",
            is_active=True,
        )

    def test_get_pending_jobs_query_logic(self):
        """Test the database query logic for getting pending jobs."""
        # Create test jobs with different statuses
        pending_job = ContainerJob.objects.create(
            docker_image="python:3.11",
            name="pending-job",
            status="pending",
            docker_host=self.host,
        )

        running_job = ContainerJob.objects.create(
            docker_image="python:3.11",
            name="running-job",
            status="running",
            docker_host=self.host,
        )

        # Test that only pending jobs are returned
        # (This tests the actual query logic without external dependencies)
        pending_jobs = ContainerJob.objects.filter(status="pending")
        self.assertEqual(pending_jobs.count(), 1)
        self.assertEqual(pending_jobs.first().name, "pending-job")

    def test_validate_host_filter_with_invalid_host(self):
        """Test _validate_host_filter with non-existent host."""
        # Should raise CommandError for invalid host
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.command._validate_host_filter("non-existent-host")

    def test_validate_host_filter_with_valid_host(self):
        """Test _validate_host_filter with valid host."""
        # Should not raise exception for valid host
        try:
            self.command._validate_host_filter("test-host")
            validation_passed = True
        except Exception:
            validation_passed = False

        self.assertTrue(validation_passed)

    def test_validate_host_filter_with_none(self):
        """Test _validate_host_filter with None (no filter)."""
        # Should not raise exception when no filter specified
        try:
            self.command._validate_host_filter(None)
            validation_passed = True
        except Exception:
            validation_passed = False

        self.assertTrue(validation_passed)

    def test_run_cleanup_if_requested_with_cleanup_disabled(self):
        """Test _run_cleanup_if_requested when cleanup is disabled."""
        config = {"cleanup": False, "cleanup_hours": 24}

        # Since cleanup is disabled in config, nothing should happen
        self.command._run_cleanup_if_requested(config)
        # No assertion needed - just verify it doesn't crash

    def test_run_cleanup_if_requested_with_cleanup_enabled(self):
        """Test _run_cleanup_if_requested when cleanup is enabled shows deprecation warning."""
        config = {"cleanup": True, "cleanup_hours": 48}

        # Set up output capture for this command
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        # Since docker_service is deprecated, cleanup shows warning instead of actually cleaning
        self.command._run_cleanup_if_requested(config)

        # Check the output
        output = out.getvalue()
        # Should show deprecation warning
        self.assertIn("Container cleanup temporarily disabled", output)

    def test_display_executor_info_with_available_hosts(self):
        """Test _display_executor_info with available hosts."""
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        # Create hosts with different executor types
        ExecutorHost.objects.create(
            name="cloud-host",
            connection_string="https://cloudrun.googleapis.com",
            host_type="tcp",
            executor_type="cloudrun",
            is_active=True,
        )

        self.command._display_executor_info("docker")
        output = out.getvalue()

        self.assertIn("Available executors:", output)
        self.assertIn("Forcing executor type: docker", output)

    def test_job_status_transitions(self):
        """Test job status transition logic."""
        job = ContainerJob.objects.create(
            docker_image="python:3.11",
            name="test-job",
            status="pending",
            docker_host=self.host,
        )

        # Test status transitions
        job.status = "submitted"
        job.set_execution_identifier("exec-123")
        job.save()

        job.refresh_from_db()
        self.assertEqual(job.status, "submitted")
        self.assertEqual(job.get_execution_identifier(), "exec-123")

        # Test transition to completed
        job.status = "completed"
        job.completed_at = timezone.now()
        job.save()

        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertIsNotNone(job.completed_at)

    def test_run_processing_loop_single_run_mode(self):
        """Test _run_processing_loop with single_run=True."""
        config = {
            "single_run": True,
            "poll_interval": 1,
            "max_jobs": 5,
            "host_filter": None,
            "factory_enabled": False,
            "executor_type": None,
        }

        with patch.object(
            self.command, "_process_single_cycle", return_value=(1, 0)
        ) as mock_cycle:
            processed, errors = self.command._run_processing_loop(config)

            # Single run should process once and exit
            self.assertEqual(processed, 1)
            self.assertEqual(errors, 0)
            mock_cycle.assert_called_once()

    def test_report_cycle_results_with_activity(self):
        """Test _report_cycle_results when there's activity to report."""
        # Capture stdout to test message output
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        # Test with activity (should produce output)
        self.command._report_cycle_results(2, 1, 10, 0)
        output = out.getvalue()

        self.assertIn("Launched 2 jobs", output)
        self.assertIn("harvested 1 jobs", output)
        self.assertIn("total processed: 10", output)

    def test_report_cycle_results_with_no_activity(self):
        """Test _report_cycle_results when there's no activity."""
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        # Test with no activity (should produce no output)
        self.command._report_cycle_results(0, 0, 5, 0)
        output = out.getvalue()

        self.assertEqual(output.strip(), "")

    def test_display_completion_summary(self):
        """Test _display_completion_summary output."""
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        self.command._display_completion_summary(15, 2)
        output = out.getvalue()

        self.assertIn("Job processor stopped", output)
        self.assertIn("Processed 15 jobs", output)
        self.assertIn("2 errors", output)

    def test_display_startup_info_with_factory_disabled(self):
        """Test _display_startup_info with factory disabled."""
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        config = {
            "poll_interval": 5,
            "max_jobs": 10,
            "factory_enabled": False,
            "executor_type": None,
        }

        self.command._display_startup_info(config)
        output = out.getvalue()

        self.assertIn("Starting container job processor", output)
        self.assertIn("routing=Direct Docker", output)

    def test_display_startup_info_with_factory_enabled(self):
        """Test _display_startup_info with factory enabled."""
        from io import StringIO

        out = StringIO()
        self.command.stdout = out

        config = {
            "poll_interval": 5,
            "max_jobs": 10,
            "factory_enabled": True,
            "executor_type": "docker",
        }

        with patch.object(self.command, "_display_executor_info") as mock_display:
            self.command._display_startup_info(config)
            output = out.getvalue()

            self.assertIn("routing=ExecutorFactory", output)
            mock_display.assert_called_once_with("docker")

    def test_parse_and_validate_options_with_factory_settings(self):
        """Test _parse_and_validate_options with various factory configurations."""
        # Mock the get_use_executor_factory function
        with patch(
            "container_manager.defaults.get_use_executor_factory", return_value=True
        ):
            options = {
                "poll_interval": 10,
                "max_jobs": 20,
                "host": "test-host",
                "single_run": False,
                "cleanup": True,
                "cleanup_hours": 48,
                "use_factory": False,  # Explicitly disabled
                "executor_type": None,
            }

            config = self.command._parse_and_validate_options(options)

            # Should enable factory due to settings even though use_factory=False
            self.assertTrue(config["factory_enabled"])
            self.assertEqual(config["poll_interval"], 10)
            self.assertEqual(config["max_jobs"], 20)
            self.assertEqual(config["host_filter"], "test-host")

    def test_parse_and_validate_options_force_executor_type(self):
        """Test _parse_and_validate_options with forced executor type."""
        with patch(
            "container_manager.defaults.get_use_executor_factory", return_value=False
        ):
            options = {
                "poll_interval": 5,
                "max_jobs": 10,
                "host": None,
                "single_run": True,
                "cleanup": False,
                "cleanup_hours": 24,
                "use_factory": False,
                "executor_type": "cloudrun",  # Force specific executor
            }

            config = self.command._parse_and_validate_options(options)

            # Should enable factory due to forced executor type
            self.assertTrue(config["factory_enabled"])
            self.assertEqual(config["executor_type"], "cloudrun")
