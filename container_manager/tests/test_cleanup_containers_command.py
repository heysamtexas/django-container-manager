"""
Tests for cleanup_containers management command
"""
import unittest
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from container_manager.models import ContainerJob, ContainerTemplate, ExecutorHost


class CleanupContainersCommandTest(TestCase):
    """Test suite for cleanup_containers management command"""

    def setUp(self):
        super().setUp()
        
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )
        
        # Create test ExecutorHost
        self.docker_host = ExecutorHost.objects.create(
            name="test-docker-host",
            host_type="unix",
            connection_string="unix:///var/run/docker.sock",
            is_active=True,
        )
        
        # Create test template
        self.template = ContainerTemplate.objects.create(
            name="test-template",
            description="Test template for cleanup testing",
            docker_image="alpine:latest", 
            command='echo "test"',
            created_by=self.user,
        )
        
        self.old_time = timezone.now() - timedelta(hours=48)
        self.recent_time = timezone.now() - timedelta(hours=1)

    def _create_old_completed_job(self):
        """Create a completed job that's old enough for cleanup"""
        job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Old Completed Job",
            status="completed",
            container_id="old_container_123",
            started_at=self.old_time,
            completed_at=self.old_time + timedelta(minutes=5),
        )
        return job

    def _create_recent_completed_job(self):
        """Create a completed job that's too recent for cleanup"""
        job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Recent Completed Job", 
            status="completed",
            container_id="recent_container_456",
            started_at=self.recent_time,
            completed_at=self.recent_time + timedelta(minutes=5),
        )
        return job

    def _create_running_job(self):
        """Create a running job that should not be cleaned"""
        job = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Running Job",
            status="running",
            container_id="running_container_789",
            started_at=self.old_time,
        )
        return job

    def test_command_arguments_parsing(self):
        """Test that command arguments are parsed correctly"""
        out = StringIO()
        
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.return_value = 0
            
            call_command('cleanup_containers', 
                        '--orphaned-hours=48', 
                        '--dry-run',
                        stdout=out)
            
        output = out.getvalue()
        self.assertIn("Orphaned containers older than: 48 hours", output)
        self.assertIn("Dry run: True", output)
        self.assertIn("DRY RUN MODE", output)

    def test_default_arguments(self):
        """Test command works with default arguments"""
        out = StringIO()
        
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.return_value = 5
            
            call_command('cleanup_containers', stdout=out)
            
        output = out.getvalue()
        self.assertIn("Orphaned containers older than: 24 hours", output)
        self.assertIn("Dry run: False", output)

    @override_settings(CONTAINER_MANAGER={'CLEANUP_ENABLED': False})
    def test_cleanup_disabled_in_settings(self):
        """Test that cleanup respects settings when disabled"""
        out = StringIO()
        
        call_command('cleanup_containers', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Container cleanup is disabled in settings", output)
        self.assertIn("Use --force to override", output)

    @override_settings(CONTAINER_MANAGER={'CLEANUP_ENABLED': False})
    def test_cleanup_force_override(self):
        """Test that --force overrides disabled settings"""
        out = StringIO()
        
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.return_value = 3
            
            call_command('cleanup_containers', '--force', stdout=out)
            
        output = out.getvalue()
        self.assertNotIn("Container cleanup is disabled", output)
        self.assertIn("Successfully cleaned up 3 containers", output)

    def test_dry_run_preview_with_orphaned_jobs(self):
        """Test dry run mode shows preview of what would be cleaned"""
        # Create test jobs
        old_job1 = self._create_old_completed_job()
        old_job2 = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Old Failed Job",
            status="failed",
            container_id="old_failed_123",
            started_at=self.old_time,
            completed_at=self.old_time + timedelta(minutes=2),
        )
        recent_job = self._create_recent_completed_job()
        running_job = self._create_running_job()
        
        out = StringIO()
        call_command('cleanup_containers', '--dry-run', '--orphaned-hours=24', stdout=out)
        
        output = out.getvalue()
        self.assertIn("DRY RUN MODE", output)
        self.assertIn("Orphaned container cleanup preview", output)
        self.assertIn("Orphaned containers to clean: 2", output)
        self.assertIn(str(old_job1.id), output)
        self.assertIn(str(old_job2.id), output)
        self.assertNotIn(str(recent_job.id), output)
        self.assertNotIn(str(running_job.id), output)

    def test_dry_run_preview_no_orphaned_jobs(self):
        """Test dry run mode when no jobs need cleanup"""
        recent_job = self._create_recent_completed_job()
        running_job = self._create_running_job()
        
        out = StringIO()
        call_command('cleanup_containers', '--dry-run', '--orphaned-hours=24', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Orphaned containers to clean: 0", output)
        self.assertNotIn("Orphaned containers that would be removed", output)

    def test_dry_run_preview_display_limit(self):
        """Test dry run mode respects display limit for large numbers of jobs"""
        # Create 15 old completed jobs (more than the display limit of 10)
        for i in range(15):
            ContainerJob.objects.create(
                template=self.template,
                docker_host=self.docker_host,
                name=f"Old Job {i}",
                status="completed",
                container_id=f"old_container_{i}",
                started_at=self.old_time,
                completed_at=self.old_time + timedelta(minutes=1),
            )
        
        out = StringIO()
        call_command('cleanup_containers', '--dry-run', '--orphaned-hours=24', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Orphaned containers to clean: 15", output)
        self.assertIn("... and 5 more orphaned containers", output)

    def test_actual_cleanup_execution(self):
        """Test actual cleanup execution calls docker service"""
        old_job = self._create_old_completed_job()
        
        out = StringIO()
        
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.return_value = 1
            
            call_command('cleanup_containers', '--orphaned-hours=24', stdout=out)
            
            mock_service.cleanup_old_containers.assert_called_once_with(orphaned_hours=24)
        
        output = out.getvalue()
        self.assertIn("Successfully cleaned up 1 containers", output)

    def test_cleanup_no_containers_found(self):
        """Test cleanup when no containers need to be cleaned"""
        recent_job = self._create_recent_completed_job()
        
        out = StringIO()
        
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.return_value = 0
            
            call_command('cleanup_containers', '--orphaned-hours=24', stdout=out)
        
        output = out.getvalue()
        self.assertIn("No containers needed cleanup", output)

    def test_cleanup_error_handling(self):
        """Test error handling during cleanup execution"""
        out = StringIO()
        
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.side_effect = Exception("Docker connection failed")
            
            with self.assertRaises(Exception):
                call_command('cleanup_containers', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Cleanup failed: Docker connection failed", output)

    @patch('container_manager.management.commands.cleanup_containers.logger')
    def test_cleanup_error_logging(self, mock_logger):
        """Test that cleanup errors are properly logged"""
        with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
            mock_service.cleanup_old_containers.side_effect = Exception("Docker error")
            
            with self.assertRaises(Exception):
                call_command('cleanup_containers')
            
            mock_logger.exception.assert_called_once_with("Container cleanup error")

    def test_cleanup_with_missing_settings(self):
        """Test cleanup works when CONTAINER_MANAGER settings are missing"""
        out = StringIO()
        
        with override_settings():
            # Remove CONTAINER_MANAGER from settings
            from django.conf import settings
            if hasattr(settings, 'CONTAINER_MANAGER'):
                delattr(settings, 'CONTAINER_MANAGER')
            
            with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
                mock_service.cleanup_old_containers.return_value = 2
                
                call_command('cleanup_containers', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Successfully cleaned up 2 containers", output)

    def test_orphaned_hours_validation(self):
        """Test that orphaned hours parameter works with different values"""
        test_values = [1, 24, 48, 168]  # 1 hour, 1 day, 2 days, 1 week
        
        for hours in test_values:
            with self.subTest(hours=hours):
                out = StringIO()
                
                with patch('container_manager.management.commands.cleanup_containers.docker_service') as mock_service:
                    mock_service.cleanup_old_containers.return_value = 0
                    
                    call_command('cleanup_containers', f'--orphaned-hours={hours}', stdout=out)
                    
                    mock_service.cleanup_old_containers.assert_called_with(orphaned_hours=hours)
                
                output = out.getvalue()
                self.assertIn(f"Orphaned containers older than: {hours} hours", output)

    def test_dry_run_job_filtering_logic(self):
        """Test that dry run properly filters jobs by status and completion time"""
        # Create jobs with different statuses and times
        jobs_data = [
            ("completed", self.old_time, True),  # Should be included
            ("failed", self.old_time, True),     # Should be included  
            ("timeout", self.old_time, True),    # Should be included
            ("cancelled", self.old_time, True),  # Should be included
            ("pending", self.old_time, False),   # Should be excluded (status)
            ("running", self.old_time, False),   # Should be excluded (status)
            ("completed", self.recent_time, False), # Should be excluded (time)
        ]
        
        created_jobs = []
        for status, completion_time, should_include in jobs_data:
            job = ContainerJob.objects.create(
                template=self.template,
                docker_host=self.docker_host,
                name=f"Test Job {status}",
                status=status,
                container_id=f"container_{status}",
                started_at=completion_time - timedelta(minutes=5),
                completed_at=completion_time if status in ["completed", "failed", "timeout", "cancelled"] else None,
            )
            created_jobs.append((job, should_include))
        
        out = StringIO()
        call_command('cleanup_containers', '--dry-run', '--orphaned-hours=24', stdout=out)
        
        output = out.getvalue()
        
        # Count expected jobs to be cleaned
        expected_count = sum(1 for _, should_include in created_jobs if should_include)
        self.assertIn(f"Orphaned containers to clean: {expected_count}", output)
        
        # Check that correct jobs are mentioned
        for job, should_include in created_jobs:
            if should_include:
                self.assertIn(str(job.id), output)
            # Note: We can't easily check exclusions since only first 10 are shown

    def test_jobs_without_container_id_excluded(self):
        """Test that jobs without container_id are excluded from cleanup preview"""
        # Create job without container_id
        job_no_container = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Job Without Container ID",
            status="completed",
            container_id="",  # Empty container ID
            started_at=self.old_time,
            completed_at=self.old_time + timedelta(minutes=5),
        )
        
        # Create job with container_id
        job_with_container = ContainerJob.objects.create(
            template=self.template,
            docker_host=self.docker_host,
            name="Job With Container ID",
            status="completed",
            container_id="has_container_123",
            started_at=self.old_time,
            completed_at=self.old_time + timedelta(minutes=5),
        )
        
        out = StringIO()
        call_command('cleanup_containers', '--dry-run', '--orphaned-hours=24', stdout=out)
        
        output = out.getvalue()
        self.assertIn("Orphaned containers to clean: 1", output)
        self.assertNotIn(str(job_no_container.id), output)
        self.assertIn(str(job_with_container.id), output)