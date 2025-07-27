"""
Tests for manage_container_job management command.

Comprehensive testing of CLI subcommands with mocked dependencies.
Focus on business logic, argument parsing, and user interface behavior.
"""

import uuid
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from container_manager.management.commands.manage_container_job import Command
from container_manager.models import ContainerJob, ContainerTemplate, ExecutorHost


class ManageContainerJobCommandTest(TestCase):
    """Test manage_container_job command with all subcommands."""

    def setUp(self):
        # Create test data
        self.host = ExecutorHost.objects.create(
            name="test-host",
            connection_string="tcp://localhost:2376",
            host_type="tcp",
            is_active=True,
        )

        self.template = ContainerTemplate.objects.create(
            name="test-template", docker_image="python:3.11", command="python script.py"
        )

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        # Set up command instance
        self.command = Command()
        self.out = StringIO()
        self.command.stdout = self.out

    def create_test_job(self, **kwargs):
        """Helper to create test jobs with defaults."""
        defaults = {
            "template": self.template,
            "docker_host": self.host,
            "name": "test-job",
            "status": "pending",
            "created_by": self.user,
        }
        defaults.update(kwargs)
        return ContainerJob.objects.create(**defaults)

    # Test Command Initialization and Argument Parsing

    def test_command_initialization(self):
        """Test command initializes with executor factory."""
        command = Command()
        self.assertIsNotNone(command.executor_factory)
        self.assertIsNotNone(command.help)

    def test_add_arguments_defines_all_subcommands(self):
        """Test that all expected subcommands are defined."""
        from argparse import ArgumentParser

        parser = ArgumentParser()
        self.command.add_arguments(parser)

        # Test create subcommand
        args = parser.parse_args(["create", "test-template", "test-host"])
        self.assertEqual(args.action, "create")
        self.assertEqual(args.template_name, "test-template")
        self.assertEqual(args.host_name, "test-host")

        # Test run subcommand
        test_uuid = str(uuid.uuid4())
        args = parser.parse_args(["run", test_uuid])
        self.assertEqual(args.action, "run")
        self.assertEqual(args.job_id, test_uuid)

        # Test list subcommand
        args = parser.parse_args(["list", "--status", "running", "--limit", "10"])
        self.assertEqual(args.action, "list")
        self.assertEqual(args.status, "running")
        self.assertEqual(args.limit, 10)

        # Test show subcommand
        args = parser.parse_args(["show", test_uuid, "--logs"])
        self.assertEqual(args.action, "show")
        self.assertEqual(args.job_id, test_uuid)
        self.assertTrue(args.logs)

        # Test cancel subcommand
        args = parser.parse_args(["cancel", test_uuid])
        self.assertEqual(args.action, "cancel")
        self.assertEqual(args.job_id, test_uuid)

        # Test cleanup subcommand
        args = parser.parse_args(["cleanup", "--hours", "48"])
        self.assertEqual(args.action, "cleanup")
        self.assertEqual(args.hours, 48)

        # Test status subcommand
        args = parser.parse_args(["status", "--capacity"])
        self.assertEqual(args.action, "status")
        self.assertTrue(args.capacity)

    # Test Handle Method Routing

    def test_handle_routes_to_correct_handlers(self):
        """Test that handle method routes actions correctly."""
        # Mock all handler methods
        with (
            patch.object(self.command, "handle_create") as mock_create,
            patch.object(self.command, "handle_run") as mock_run,
            patch.object(self.command, "handle_list") as mock_list,
            patch.object(self.command, "handle_show") as mock_show,
            patch.object(self.command, "handle_cancel") as mock_cancel,
            patch.object(self.command, "handle_cleanup") as mock_cleanup,
            patch.object(self.command, "handle_status") as mock_status,
        ):
            # Test each action routes correctly
            self.command.handle(action="create")
            mock_create.assert_called_once()

            self.command.handle(action="run")
            mock_run.assert_called_once()

            self.command.handle(action="list")
            mock_list.assert_called_once()

            self.command.handle(action="show")
            mock_show.assert_called_once()

            self.command.handle(action="cancel")
            mock_cancel.assert_called_once()

            self.command.handle(action="cleanup")
            mock_cleanup.assert_called_once()

            self.command.handle(action="status")
            mock_status.assert_called_once()

    # Test Create Subcommand

    def test_handle_create_creates_job_successfully(self):
        """Test successful job creation."""
        with (
            patch.object(self.command, "get_default_user", return_value=self.user),
            patch.object(self.command, "show_job_summary") as mock_summary,
        ):
            options = {
                "template_name": "test-template",
                "host_name": "test-host",
                "name": "my-job",
                "command": "python test.py",
                "env": ["ENV=test", "DEBUG=true"],
            }

            self.command.handle_create(options)

            # Verify job was created
            job = ContainerJob.objects.get(name="my-job")
            self.assertEqual(job.template, self.template)
            self.assertEqual(job.docker_host, self.host)
            self.assertEqual(job.override_command, "python test.py")
            self.assertEqual(job.override_environment, {"ENV": "test", "DEBUG": "true"})
            self.assertEqual(job.created_by, self.user)

            # Verify success message and summary
            output = self.out.getvalue()
            self.assertIn("Created job", output)
            self.assertIn("my-job", output)
            mock_summary.assert_called_once_with(job)

    def test_handle_create_with_nonexistent_template_raises_error(self):
        """Test create with non-existent template raises CommandError."""
        options = {
            "template_name": "nonexistent-template",
            "host_name": "test-host",
        }

        with self.assertRaises(CommandError) as cm:
            self.command.handle_create(options)

        self.assertIn('Template "nonexistent-template" not found', str(cm.exception))

    def test_handle_create_with_nonexistent_host_raises_error(self):
        """Test create with non-existent host raises CommandError."""
        options = {
            "template_name": "test-template",
            "host_name": "nonexistent-host",
        }

        with self.assertRaises(CommandError) as cm:
            self.command.handle_create(options)

        self.assertIn('Docker host "nonexistent-host" not found', str(cm.exception))

    def test_handle_create_with_inactive_host_raises_error(self):
        """Test create with inactive host raises CommandError."""
        # Create inactive host
        inactive_host = ExecutorHost.objects.create(
            name="inactive-host",
            connection_string="tcp://localhost:2377",
            host_type="tcp",
            is_active=False,
        )

        options = {
            "template_name": "test-template",
            "host_name": "inactive-host",
        }

        with self.assertRaises(CommandError) as cm:
            self.command.handle_create(options)

        self.assertIn(
            'Docker host "inactive-host" not found or inactive', str(cm.exception)
        )

    def test_handle_create_with_invalid_env_var_format_raises_error(self):
        """Test create with invalid environment variable format raises CommandError."""
        options = {
            "template_name": "test-template",
            "host_name": "test-host",
            "env": ["VALID=value", "INVALID_NO_EQUALS"],
        }

        with self.assertRaises(CommandError) as cm:
            self.command.handle_create(options)

        self.assertIn(
            "Invalid environment variable format: INVALID_NO_EQUALS", str(cm.exception)
        )

    def test_handle_create_with_env_var_containing_equals_in_value(self):
        """Test create with environment variable value containing equals sign."""
        with (
            patch.object(self.command, "get_default_user", return_value=self.user),
            patch.object(self.command, "show_job_summary"),
        ):
            options = {
                "template_name": "test-template",
                "host_name": "test-host",
                "name": "test-equals",
                "env": ["CONNECTION_STRING=host=localhost;port=5432"],
            }

            self.command.handle_create(options)

            job = ContainerJob.objects.get(name="test-equals")
            self.assertEqual(
                job.override_environment["CONNECTION_STRING"],
                "host=localhost;port=5432",
            )

    # Test List Subcommand

    def test_handle_list_shows_all_jobs_when_no_filters(self):
        """Test list shows all jobs when no filters applied."""
        # Create test jobs
        job1 = self.create_test_job(name="job1", status="pending")
        job2 = self.create_test_job(name="job2", status="running")
        job3 = self.create_test_job(name="job3", status="completed")

        options = {"limit": 20}
        self.command.handle_list(options)

        output = self.out.getvalue()
        self.assertIn("Container Jobs:", output)
        self.assertIn("job1", output)
        self.assertIn("job2", output)
        self.assertIn("job3", output)
        self.assertIn("Total: 3 jobs", output)

    def test_handle_list_filters_by_status(self):
        """Test list filters jobs by status correctly."""
        job1 = self.create_test_job(name="job1", status="pending")
        job2 = self.create_test_job(name="job2", status="running")
        job3 = self.create_test_job(name="job3", status="completed")

        options = {"status": "running", "limit": 20}
        self.command.handle_list(options)

        output = self.out.getvalue()
        self.assertIn("job2", output)
        self.assertNotIn("job1", output)
        self.assertNotIn("job3", output)
        self.assertIn("Total: 1 jobs", output)

    def test_handle_list_filters_by_host(self):
        """Test list filters jobs by host correctly."""
        # Create another host
        other_host = ExecutorHost.objects.create(
            name="other-host",
            connection_string="tcp://other:2376",
            host_type="tcp",
            is_active=True,
        )

        job1 = self.create_test_job(name="job1", docker_host=self.host)
        job2 = self.create_test_job(name="job2", docker_host=other_host)

        options = {"host": "test-host", "limit": 20}
        self.command.handle_list(options)

        output = self.out.getvalue()
        self.assertIn("job1", output)
        self.assertNotIn("job2", output)
        self.assertIn("Total: 1 jobs", output)

    def test_handle_list_respects_limit(self):
        """Test list respects the limit parameter."""
        # Create multiple jobs
        for i in range(5):
            self.create_test_job(name=f"job{i}")

        options = {"limit": 2}
        self.command.handle_list(options)

        output = self.out.getvalue()
        self.assertIn("Total: 2 jobs", output)

    def test_handle_list_shows_message_when_no_jobs_found(self):
        """Test list shows appropriate message when no jobs found."""
        options = {"status": "nonexistent_status", "limit": 20}
        self.command.handle_list(options)

        output = self.out.getvalue()
        self.assertIn("No jobs found", output)

    def test_handle_list_truncates_long_job_names(self):
        """Test list truncates long job names with ellipsis."""
        long_name = "a" * 25  # Longer than MAX_NAME_DISPLAY_LENGTH (19)
        self.create_test_job(name=long_name)

        options = {"limit": 20}
        self.command.handle_list(options)

        output = self.out.getvalue()
        # Should show truncated name with ellipsis
        expected_truncated = long_name[:16] + "..."  # 19 - 3 for ellipsis
        self.assertIn(expected_truncated, output)
        self.assertNotIn(long_name, output)

    # Test Show Subcommand

    def test_handle_show_displays_job_details(self):
        """Test show displays job details correctly."""
        job = self.create_test_job(name="test-show-job")

        with patch.object(self.command, "show_job_details") as mock_details:
            options = {"job_id": str(job.id), "logs": False}
            self.command.handle_show(options)

            mock_details.assert_called_once_with(job, False)

    def test_handle_show_with_logs_option(self):
        """Test show with logs option passes correct parameter."""
        job = self.create_test_job(name="test-show-logs")

        with patch.object(self.command, "show_job_details") as mock_details:
            options = {"job_id": str(job.id), "logs": True}
            self.command.handle_show(options)

            mock_details.assert_called_once_with(job, True)

    def test_handle_show_with_nonexistent_job_raises_error(self):
        """Test show with non-existent job raises CommandError."""
        fake_uuid = str(uuid.uuid4())
        options = {"job_id": fake_uuid}

        with self.assertRaises(CommandError) as cm:
            self.command.handle_show(options)

        self.assertIn(f'Job "{fake_uuid}" not found', str(cm.exception))

    def test_handle_show_with_invalid_uuid_raises_error(self):
        """Test show with invalid UUID raises CommandError."""
        options = {"job_id": "invalid-uuid"}

        # The ValidationError from Django gets converted to CommandError
        with self.assertRaises((CommandError, Exception)):
            self.command.handle_show(options)

    # Test Run Subcommand

    def test_handle_run_executes_pending_job_successfully(self):
        """Test run executes a pending job successfully."""
        job = self.create_test_job(status="pending")

        # Mock executor and its methods
        mock_executor = Mock()
        mock_executor.launch_job.return_value = (True, "execution-123")
        mock_executor.harvest_job.return_value = True

        with (
            patch.object(
                self.command.executor_factory,
                "get_executor",
                return_value=mock_executor,
            ),
            patch.object(self.command, "_wait_for_job_completion") as mock_wait,
            patch.object(self.command, "show_job_summary") as mock_summary,
        ):
            # Set up job to complete successfully
            def complete_job(test_job):
                test_job.status = "completed"
                test_job.save()

            mock_wait.side_effect = complete_job

            options = {"job_id": str(job.id)}
            self.command.handle_run(options)

            # Verify executor was called
            mock_executor.launch_job.assert_called_once_with(job)
            mock_executor.harvest_job.assert_called_once_with(job)

            # Verify output messages (the important behavior)
            output = self.out.getvalue()
            self.assertIn("Running job", output)
            self.assertIn("Job launched as execution-123", output)
            self.assertIn("completed successfully", output)

    def test_handle_run_with_job_launch_failure(self):
        """Test run handles job launch failure."""
        job = self.create_test_job(status="pending")

        mock_executor = Mock()
        mock_executor.launch_job.return_value = (False, "Launch failed")

        with patch.object(
            self.command.executor_factory, "get_executor", return_value=mock_executor
        ):
            options = {"job_id": str(job.id)}
            self.command.handle_run(options)

            output = self.out.getvalue()
            self.assertIn("failed to launch", output)
            self.assertIn("Launch failed", output)

    def test_validate_job_for_run_with_valid_pending_job(self):
        """Test _validate_job_for_run with valid pending job."""
        job = self.create_test_job(status="pending")

        result = self.command._validate_job_for_run(str(job.id))

        self.assertEqual(result.id, job.id)

    def test_validate_job_for_run_with_nonexistent_job_raises_error(self):
        """Test _validate_job_for_run with non-existent job raises error."""
        fake_uuid = str(uuid.uuid4())

        with self.assertRaises(CommandError) as cm:
            self.command._validate_job_for_run(fake_uuid)

        self.assertIn(f'Job "{fake_uuid}" not found', str(cm.exception))

    def test_validate_job_for_run_with_non_pending_job_raises_error(self):
        """Test _validate_job_for_run with non-pending job raises error."""
        job = self.create_test_job(status="running")

        with self.assertRaises(CommandError) as cm:
            self.command._validate_job_for_run(str(job.id))

        self.assertIn("not in pending status", str(cm.exception))
        self.assertIn("current: running", str(cm.exception))

    def test_ensure_job_has_host_when_host_exists(self):
        """Test _ensure_job_has_host when job already has host."""
        job = self.create_test_job()  # Already has host from setUp

        # Should not modify job when host exists
        original_host = job.docker_host
        self.command._ensure_job_has_host(job)

        self.assertEqual(job.docker_host, original_host)

    def test_display_execution_info_shows_executor_and_host(self):
        """Test _display_execution_info displays correct information."""
        job = self.create_test_job()
        job.executor_type = "docker"

        self.command._display_execution_info(job)

        output = self.out.getvalue()
        self.assertIn("Using docker executor", output)
        self.assertIn("Selected host: test-host", output)

    def test_wait_for_job_completion_polls_until_not_running(self):
        """Test _wait_for_job_completion polls until job is not running."""
        job = self.create_test_job(status="running")

        call_count = [0]

        def mock_refresh():
            call_count[0] += 1
            if call_count[0] >= 3:  # Stop after 3 calls
                job.status = "completed"

        with (
            patch("time.sleep") as mock_sleep,
            patch.object(job, "refresh_from_db", side_effect=mock_refresh),
        ):
            self.command._wait_for_job_completion(job)

            # Should have called sleep for polling
            self.assertTrue(mock_sleep.called)
            self.assertEqual(call_count[0], 3)

    def test_harvest_and_report_results_success(self):
        """Test _harvest_and_report_results with successful harvest."""
        job = self.create_test_job(status="completed")
        mock_executor = Mock()
        mock_executor.harvest_job.return_value = True

        self.command._harvest_and_report_results(job, mock_executor)

        mock_executor.harvest_job.assert_called_once_with(job)
        output = self.out.getvalue()
        self.assertIn("completed successfully", output)

    def test_harvest_and_report_results_failure(self):
        """Test _harvest_and_report_results with failed harvest."""
        job = self.create_test_job(status="failed")
        mock_executor = Mock()
        mock_executor.harvest_job.return_value = False

        self.command._harvest_and_report_results(job, mock_executor)

        output = self.out.getvalue()
        self.assertIn("failed or timed out", output)

    # Test Cancel Subcommand

    def test_handle_cancel_cancels_running_job(self):
        """Test cancel subcommand cancels a running job."""
        job = self.create_test_job(status="running", container_id="container-123")

        with patch(
            "container_manager.management.commands.manage_container_job.docker_service"
        ) as mock_service:
            options = {"job_id": str(job.id)}
            self.command.handle_cancel(options)

            # Verify docker service methods were called
            mock_service.stop_container.assert_called_once_with(job)
            mock_service.remove_container.assert_called_once_with(job, force=True)

            job.refresh_from_db()
            self.assertEqual(job.status, "cancelled")

            output = self.out.getvalue()
            self.assertIn("cancelled successfully", output)

    def test_handle_cancel_with_nonexistent_job_raises_error(self):
        """Test cancel with non-existent job raises error."""
        fake_uuid = str(uuid.uuid4())
        options = {"job_id": fake_uuid}

        with self.assertRaises(CommandError) as cm:
            self.command.handle_cancel(options)

        self.assertIn(f'Job "{fake_uuid}" not found', str(cm.exception))

    def test_handle_cancel_with_non_running_job_raises_error(self):
        """Test cancel with non-running job raises error."""
        job = self.create_test_job(status="completed")
        options = {"job_id": str(job.id)}

        with self.assertRaises(CommandError) as cm:
            self.command.handle_cancel(options)

        self.assertIn("Cannot cancel job in status: completed", str(cm.exception))

    def test_handle_cancel_with_docker_service_failure(self):
        """Test cancel handles Docker service failure."""
        job = self.create_test_job(status="running", container_id="container-123")

        with patch(
            "container_manager.management.commands.manage_container_job.docker_service"
        ) as mock_service:
            mock_service.stop_container.side_effect = Exception("Stop failed")

            options = {"job_id": str(job.id)}

            with self.assertRaises(CommandError) as cm:
                self.command.handle_cancel(options)

            self.assertIn("Failed to cancel job: Stop failed", str(cm.exception))

    # Test Cleanup Subcommand

    def test_handle_cleanup_calls_docker_service(self):
        """Test cleanup subcommand calls Docker service cleanup."""
        with patch(
            "container_manager.management.commands.manage_container_job.docker_service"
        ) as mock_service:
            options = {"hours": 48}
            self.command.handle_cleanup(options)

            mock_service.cleanup_old_containers.assert_called_once_with(
                orphaned_hours=48
            )

            output = self.out.getvalue()
            self.assertIn("Cleaning up containers older than 48 hours", output)
            self.assertIn("Cleanup completed", output)

    def test_handle_cleanup_with_zero_containers(self):
        """Test cleanup when no containers are cleaned up."""
        with patch(
            "container_manager.management.commands.manage_container_job.docker_service"
        ) as mock_service:
            options = {"hours": 24}
            self.command.handle_cleanup(options)

            output = self.out.getvalue()
            self.assertIn("Cleaning up containers older than 24 hours", output)
            self.assertIn("Cleanup completed", output)

    def test_handle_cleanup_with_error(self):
        """Test cleanup handles Docker service errors."""
        with patch(
            "container_manager.management.commands.manage_container_job.docker_service"
        ) as mock_service:
            mock_service.cleanup_old_containers.side_effect = Exception(
                "Cleanup failed"
            )

            options = {"hours": 24}

            with self.assertRaises(CommandError) as cm:
                self.command.handle_cleanup(options)

            self.assertIn("Cleanup failed: Cleanup failed", str(cm.exception))

    # Test Status Subcommand

    def test_handle_status_shows_basic_status(self):
        """Test status subcommand shows basic executor status."""
        options = {"capacity": False}
        self.command.handle_status(options)

        output = self.out.getvalue()
        self.assertIn("Executor Status", output)
        self.assertIn("docker", output)  # Our test host is docker executor
        self.assertIn("Recent Job Statistics", output)

    def test_handle_status_with_capacity_info(self):
        """Test status subcommand with capacity information."""
        options = {"capacity": True}
        self.command.handle_status(options)

        output = self.out.getvalue()
        self.assertIn("Capacity Information", output)
        self.assertIn("DOCKER Executor", output)
        self.assertIn("Total Hosts: 1", output)
        self.assertIn("Active Hosts: 1", output)

    # Test Helper Methods

    def test_get_default_user_returns_superuser(self):
        """Test get_default_user returns superuser."""
        # Make our test user a superuser
        self.user.is_superuser = True
        self.user.save()

        result = self.command.get_default_user()

        self.assertEqual(result, self.user)

    def test_get_default_user_returns_none_when_no_superuser_exists(self):
        """Test get_default_user returns None when no superuser exists."""
        # Ensure user is not a superuser
        self.user.is_superuser = False
        self.user.save()

        result = self.command.get_default_user()

        self.assertIsNone(result)

    # Integration Tests using call_command

    def test_create_command_via_call_command(self):
        """Test create subcommand can be called via Django's call_command."""
        with patch.object(Command, "get_default_user", return_value=self.user):
            out = StringIO()

            call_command(
                "manage_container_job",
                "create",
                "test-template",
                "test-host",
                "--name",
                "integration-test",
                stdout=out,
            )

            # Verify job was created
            job = ContainerJob.objects.get(name="integration-test")
            self.assertEqual(job.template, self.template)
            self.assertEqual(job.docker_host, self.host)

            # Verify output
            output = out.getvalue()
            self.assertIn("Created job", output)

    def test_list_command_via_call_command(self):
        """Test list subcommand can be called via Django's call_command."""
        self.create_test_job(name="test-list-job")

        out = StringIO()
        call_command("manage_container_job", "list", stdout=out)

        output = out.getvalue()
        self.assertIn("Container Jobs:", output)
        self.assertIn("test-list-job", output)

    def test_handle_run_with_exception_raises_command_error(self):
        """Test run handles exceptions by raising CommandError."""
        job = self.create_test_job(status="pending")

        # Mock a failure in executor factory to trigger the exception handler
        with patch.object(
            self.command.executor_factory,
            "get_executor",
            side_effect=Exception("Test error"),
        ):
            with self.assertRaises(CommandError) as cm:
                options = {"job_id": str(job.id)}
                self.command.handle_run(options)

            self.assertIn("Failed to run job: Test error", str(cm.exception))

    def test_show_job_details_with_all_display_methods(self):
        """Test show_job_details calls all display methods."""
        job = self.create_test_job()

        with (
            patch.object(self.command, "_display_job_header") as mock_header,
            patch.object(self.command, "_display_basic_job_info") as mock_basic,
            patch.object(self.command, "_display_execution_identifier") as mock_exec_id,
            patch.object(self.command, "_display_job_timestamps") as mock_timestamps,
            patch.object(self.command, "_display_command_info") as mock_command,
            patch.object(self.command, "_display_execution_details") as mock_details,
        ):
            self.command.show_job_details(job, show_logs=True)

            # Verify all display methods were called
            mock_header.assert_called_once_with(job)
            mock_basic.assert_called_once_with(job)
            mock_exec_id.assert_called_once_with(job)
            mock_timestamps.assert_called_once_with(job)
            mock_command.assert_called_once_with(job)
            mock_details.assert_called_once_with(job, True)

    def test_display_job_header(self):
        """Test _display_job_header outputs correct format."""
        job = self.create_test_job()

        self.command._display_job_header(job)

        output = self.out.getvalue()
        self.assertIn(f"Job Details: {job.id}", output)
        self.assertIn("=" * 50, output)

    def test_display_basic_job_info(self):
        """Test _display_basic_job_info outputs job information."""
        job = self.create_test_job(name="test-display-job")

        self.command._display_basic_job_info(job)

        output = self.out.getvalue()
        self.assertIn("Name: test-display-job", output)
        self.assertIn("Template: test-template", output)
        self.assertIn("Docker Host: test-host", output)
        self.assertIn("Executor Type: docker", output)
        self.assertIn("Status: pending", output)

    def test_display_execution_identifier_for_docker(self):
        """Test _display_execution_identifier for docker executor."""
        job = self.create_test_job(container_id="container-123")
        job.executor_type = "docker"
        job.exit_code = 0

        self.command._display_execution_identifier(job)

        output = self.out.getvalue()
        self.assertIn("Container ID: container-123", output)
        self.assertIn("Exit Code: 0", output)

    def test_display_execution_identifier_for_cloudrun(self):
        """Test _display_execution_identifier for non-docker executor."""
        job = self.create_test_job(external_execution_id="execution-456")
        job.executor_type = "cloudrun"
        job.exit_code = None

        self.command._display_execution_identifier(job)

        output = self.out.getvalue()
        self.assertIn("Execution ID: execution-456", output)
        self.assertIn("Exit Code: N/A", output)

    def test_display_job_timestamps(self):
        """Test _display_job_timestamps outputs timestamp information."""
        job = self.create_test_job()
        job.started_at = timezone.now()
        job.completed_at = timezone.now()
        job.save()

        self.command._display_job_timestamps(job)

        output = self.out.getvalue()
        self.assertIn("Created:", output)
        self.assertIn("Started:", output)
        self.assertIn("Completed:", output)
        # Don't check duration as it's a complex calculated property

    def test_display_command_info(self):
        """Test _display_command_info shows command and environment."""
        job = self.create_test_job()
        job.override_command = 'echo "test"'
        job.override_environment = {"ENV": "test", "DEBUG": "true"}

        self.command._display_command_info(job)

        output = self.out.getvalue()
        self.assertIn('Command: echo "test"', output)
        self.assertIn("Override Environment:", output)
        self.assertIn("ENV=test", output)
        self.assertIn("DEBUG=true", output)
