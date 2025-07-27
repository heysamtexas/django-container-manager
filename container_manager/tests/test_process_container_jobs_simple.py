"""
Simple additional tests for process_container_jobs command to improve coverage.

These tests focus on simple coverage improvements without complex mocking.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import TestCase

from container_manager.management.commands.process_container_jobs import Command
from container_manager.models import ContainerJob, ContainerTemplate, ExecutorHost


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

        self.template = ContainerTemplate.objects.create(
            name="test-template",
            docker_image="python:3.11",
            command="python script.py",
            timeout_seconds=300,
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
            template=self.template,
            name="test-job",
            status="pending",
            docker_host=self.host,
        )

        with patch.object(
            self.command, "launch_job_with_factory", return_value=True
        ) as mock_factory:
            result = self.command.launch_single_job(
                job, use_factory=True, force_executor_type="docker"
            )

            self.assertTrue(result)
            mock_factory.assert_called_once_with(job, "docker")

    def test_launch_single_job_routing_docker_service(self):
        """Test launch_single_job with docker service routing"""
        job = ContainerJob.objects.create(
            template=self.template,
            name="test-job",
            status="pending",
            docker_host=self.host,
        )

        with patch.object(
            self.command, "launch_job_with_docker_service", return_value=True
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

    @patch(
        "container_manager.management.commands.process_container_jobs.docker_service"
    )
    def test_run_cleanup_if_requested_enabled(self, mock_docker_service):
        """Test _run_cleanup_if_requested when cleanup is enabled"""
        config = {"cleanup": True, "cleanup_hours": 48}
        mock_docker_service.cleanup_old_containers.return_value = 3

        self.command._run_cleanup_if_requested(config)

        mock_docker_service.cleanup_old_containers.assert_called_once_with(
            orphaned_hours=48
        )

    @patch(
        "container_manager.management.commands.process_container_jobs.docker_service"
    )
    def test_run_cleanup_if_requested_disabled(self, mock_docker_service):
        """Test _run_cleanup_if_requested when cleanup is disabled"""
        config = {"cleanup": False, "cleanup_hours": 24}

        self.command._run_cleanup_if_requested(config)

        mock_docker_service.cleanup_old_containers.assert_not_called()
