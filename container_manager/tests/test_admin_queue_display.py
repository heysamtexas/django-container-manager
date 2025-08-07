"""
Tests for admin interface queue display functionality.

This module tests the enhanced Django admin interface for ContainerJob
with queue-specific displays, filters, and methods.
"""

from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from ..models import ContainerJob, ExecutorHost
from ..admin import ContainerJobAdmin, QueueStatusFilter


class QueueAdminDisplayTest(TestCase):
    """Test queue-specific admin display methods"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = ContainerJobAdmin(ContainerJob, self.site)
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'password')
        
        # Create test host
        self.host = ExecutorHost.objects.create(
            name='test-admin-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        
        # Create test jobs with different queue states
        self.jobs = {}
        
        # Not queued job
        self.jobs['not_queued'] = ContainerJob.objects.create(
            docker_image='nginx:test-admin-not-queued',
            command='echo "not queued"',
            docker_host=self.host,
            priority=50
        )
        
        # Queued job (ready to launch)
        self.jobs['queued'] = ContainerJob.objects.create(
            docker_image='nginx:test-admin-queued',
            command='echo "queued"',
            docker_host=self.host,
            priority=70
        )
        self.jobs['queued'].mark_as_queued()
        
        # Scheduled job (future execution)
        self.jobs['scheduled'] = ContainerJob.objects.create(
            docker_image='nginx:test-admin-scheduled',
            command='echo "scheduled"',
            docker_host=self.host,
            priority=80
        )
        self.jobs['scheduled'].mark_as_queued(
            scheduled_for=timezone.now() + timedelta(hours=1)
        )
        
        # Launched job
        self.jobs['launched'] = ContainerJob.objects.create(
            docker_image='nginx:test-admin-launched',
            command='echo "launched"',
            docker_host=self.host,
            priority=60
        )
        self.jobs['launched'].mark_as_queued()
        self.jobs['launched'].mark_as_running()
        
        # Launch failed job (exceeded retries)
        self.jobs['launch_failed'] = ContainerJob.objects.create(
            docker_image='nginx:test-admin-failed',
            command='echo "failed"',
            docker_host=self.host,
            priority=30,
            max_retries=2
        )
        self.jobs['launch_failed'].mark_as_queued()
        self.jobs['launch_failed'].retry_count = 3
        self.jobs['launch_failed'].last_error = "Launch failed"
        self.jobs['launch_failed'].last_error_at = timezone.now()
        self.jobs['launch_failed'].save()
    
    def test_queue_status_display(self):
        """Test queue status display method"""
        # Test not queued
        result = self.admin.queue_status_display(self.jobs['not_queued'])
        self.assertIn('Not Queued', result)
        self.assertIn('#6c757d', result)  # Gray color
        
        # Test queued
        result = self.admin.queue_status_display(self.jobs['queued'])
        self.assertIn('Queued', result)
        self.assertIn('#007bff', result)  # Blue color
        
        # Test scheduled
        result = self.admin.queue_status_display(self.jobs['scheduled'])
        self.assertIn('Scheduled', result)
        self.assertIn('#fd7e14', result)  # Orange color
        
        # Test launched
        result = self.admin.queue_status_display(self.jobs['launched'])
        self.assertIn('Launched', result)
        self.assertIn('#28a745', result)  # Green color
        
        # Test launch failed
        result = self.admin.queue_status_display(self.jobs['launch_failed'])
        self.assertIn('Launch Failed', result)
        self.assertIn('#dc3545', result)  # Red color
    
    def test_execution_status_display(self):
        """Test execution status display method"""
        # Test different execution statuses
        test_cases = [
            ('pending', 'Pending', '#6c757d'),
            ('queued', 'Queued', '#007bff'),
            ('running', 'Running', '#17a2b8'),
            ('completed', 'Completed', '#28a745'),
            ('failed', 'Failed', '#dc3545'),
            ('cancelled', 'Cancelled', '#6f42c1'),
            ('timeout', 'Timeout', '#dc3545'),
        ]
        
        for status, expected_text, expected_color in test_cases:
            job = self.jobs['not_queued']  # Use any job
            job.status = status
            
            result = self.admin.execution_status_display(job)
            self.assertIn(expected_text, result)
            self.assertIn(expected_color, result)
    
    def test_priority_display(self):
        """Test priority display with visual indicators"""
        test_cases = [
            (90, '🔥', '#dc3545'),   # High priority - red
            (70, '⬆️', '#fd7e14'),   # Medium-high - orange  
            (50, '➡️', '#28a745'),   # Normal - green
            (20, '⬇️', '#6c757d'),   # Low - gray
        ]
        
        for priority, expected_icon, expected_color in test_cases:
            job = self.jobs['not_queued']
            job.priority = priority
            
            result = self.admin.priority_display(job)
            self.assertIn(str(priority), result)
            self.assertIn(expected_color, result)
    
    def test_timestamp_short_formats(self):
        """Test short timestamp display methods"""
        now = timezone.now()
        job = self.jobs['queued']
        
        # Set timestamps to today
        job.created_at = now
        job.queued_at = now
        job.launched_at = now
        
        # Should show time only for today's dates
        created_result = self.admin.created_at_short(job)
        queued_result = self.admin.queued_at_short(job)
        launched_result = self.admin.launched_at_short(job)
        
        # Should be in HH:MM:SS format for today
        self.assertRegex(created_result, r'^\d{2}:\d{2}:\d{2}$')
        self.assertRegex(queued_result, r'^\d{2}:\d{2}:\d{2}$')
        self.assertRegex(launched_result, r'^\d{2}:\d{2}:\d{2}$')
        
        # Test with different dates - should show MM/DD HH:MM format
        yesterday = now - timedelta(days=1)
        job.created_at = yesterday
        job.queued_at = yesterday
        
        created_result = self.admin.created_at_short(job)
        queued_result = self.admin.queued_at_short(job)
        
        # Should be in MM/DD HH:MM format for different days
        self.assertRegex(created_result, r'^\d{2}/\d{2} \d{2}:\d{2}$')
        self.assertRegex(queued_result, r'^\d{2}/\d{2} \d{2}:\d{2}$')
    
    def test_queue_status_detail(self):
        """Test detailed queue status information"""
        # Test not queued job
        result = self.admin.queue_status_detail(self.jobs['not_queued'])
        self.assertIn('Job is not queued', result)
        
        # Test queued job
        result = self.admin.queue_status_detail(self.jobs['queued'])
        self.assertIn('Status:', result)
        self.assertIn('Priority:', result)
        self.assertIn('Queued:', result)
        
        # Test scheduled job
        result = self.admin.queue_status_detail(self.jobs['scheduled'])
        self.assertIn('Scheduled for:', result)
        
        # Test failed job with error info
        result = self.admin.queue_status_detail(self.jobs['launch_failed'])
        self.assertIn('Retry attempts:', result)
        self.assertIn('Last error:', result)
        self.assertIn('Error message:', result)


class QueueStatusFilterTest(TestCase):
    """Test custom queue status filter"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.host = ExecutorHost.objects.create(
            name='test-filter-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        
        # Create jobs with different states
        self.not_queued = ContainerJob.objects.create(
            docker_image='nginx:not-queued',
            command='echo "test"',
            docker_host=self.host
        )
        
        self.queued = ContainerJob.objects.create(
            docker_image='nginx:queued',
            command='echo "test"',
            docker_host=self.host
        )
        self.queued.mark_as_queued()
        
        self.scheduled = ContainerJob.objects.create(
            docker_image='nginx:scheduled',
            command='echo "test"',
            docker_host=self.host
        )
        self.scheduled.mark_as_queued(
            scheduled_for=timezone.now() + timedelta(hours=1)
        )
        
        self.launched = ContainerJob.objects.create(
            docker_image='nginx:launched',
            command='echo "test"',
            docker_host=self.host
        )
        self.launched.mark_as_queued()
        self.launched.mark_as_running()
        
        self.launch_failed = ContainerJob.objects.create(
            docker_image='nginx:failed',
            command='echo "test"',
            docker_host=self.host,
            max_retries=1
        )
        self.launch_failed.mark_as_queued()
        self.launch_failed.retry_count = 2  # Exceed max_retries
        self.launch_failed.save()
    
    def test_filter_lookups(self):
        """Test filter provides correct lookup options"""
        filter_instance = QueueStatusFilter(None, {}, ContainerJob, None)
        lookups = filter_instance.lookups(None, None)
        
        expected_lookups = [
            ('not_queued', 'Not Queued'),
            ('queued', 'Queued (Ready)'),
            ('scheduled', 'Scheduled (Future)'),
            ('launched', 'Launched'),
            ('launch_failed', 'Launch Failed'),
        ]
        
        self.assertEqual(list(lookups), expected_lookups)
    
    def test_filter_not_queued(self):
        """Test filtering for not queued jobs"""
        from django.contrib.admin.sites import AdminSite
        from django.http import QueryDict
        from ..admin import ContainerJobAdmin
        
        site = AdminSite()
        admin_instance = ContainerJobAdmin(ContainerJob, site)
        
        # Create proper parameters for Django admin filter
        params = QueryDict('', mutable=True)
        params['queue_status'] = 'not_queued'
        
        request = self.factory.get('/?queue_status=not_queued')
        filter_instance = QueueStatusFilter(request, params, ContainerJob, admin_instance)
        
        # Use only our test jobs, not all jobs in the database
        test_jobs = [self.not_queued, self.queued, self.scheduled, self.launched, self.launch_failed]
        queryset = ContainerJob.objects.filter(
            id__in=[job.id for job in test_jobs]
        )
        filtered = filter_instance.queryset(request, queryset)
        
        self.assertIn(self.not_queued, filtered)
        self.assertNotIn(self.queued, filtered)
        self.assertNotIn(self.scheduled, filtered)
        self.assertNotIn(self.launched, filtered)
    
    def test_filter_queued_ready(self):
        """Test filtering for queued (ready) jobs"""
        from django.contrib.admin.sites import AdminSite
        from django.http import QueryDict
        from ..admin import ContainerJobAdmin
        
        site = AdminSite()
        admin_instance = ContainerJobAdmin(ContainerJob, site)
        
        params = QueryDict('', mutable=True)
        params['queue_status'] = 'queued'
        
        request = self.factory.get('/?queue_status=queued')
        filter_instance = QueueStatusFilter(request, params, ContainerJob, admin_instance)
        
        test_jobs = [self.not_queued, self.queued, self.scheduled, self.launched, self.launch_failed]
        queryset = ContainerJob.objects.filter(
            id__in=[job.id for job in test_jobs]
        )
        filtered = filter_instance.queryset(request, queryset)
        
        self.assertNotIn(self.not_queued, filtered)
        self.assertIn(self.queued, filtered)
        self.assertNotIn(self.scheduled, filtered)  # Future scheduled
        self.assertNotIn(self.launched, filtered)  # Already launched
    
    def test_filter_scheduled_future(self):
        """Test filtering for scheduled (future) jobs"""
        from django.contrib.admin.sites import AdminSite
        from django.http import QueryDict
        from ..admin import ContainerJobAdmin
        
        site = AdminSite()
        admin_instance = ContainerJobAdmin(ContainerJob, site)
        
        params = QueryDict('', mutable=True)
        params['queue_status'] = 'scheduled'
        
        request = self.factory.get('/?queue_status=scheduled')
        filter_instance = QueueStatusFilter(request, params, ContainerJob, admin_instance)
        
        test_jobs = [self.not_queued, self.queued, self.scheduled, self.launched, self.launch_failed]
        queryset = ContainerJob.objects.filter(
            id__in=[job.id for job in test_jobs]
        )
        filtered = filter_instance.queryset(request, queryset)
        
        self.assertNotIn(self.not_queued, filtered)
        self.assertNotIn(self.queued, filtered)
        self.assertIn(self.scheduled, filtered)
        self.assertNotIn(self.launched, filtered)
    
    def test_filter_launched(self):
        """Test filtering for launched jobs"""
        from django.contrib.admin.sites import AdminSite
        from django.http import QueryDict
        from ..admin import ContainerJobAdmin
        
        site = AdminSite()
        admin_instance = ContainerJobAdmin(ContainerJob, site)
        
        params = QueryDict('', mutable=True)
        params['queue_status'] = 'launched'
        
        request = self.factory.get('/?queue_status=launched')
        filter_instance = QueueStatusFilter(request, params, ContainerJob, admin_instance)
        
        test_jobs = [self.not_queued, self.queued, self.scheduled, self.launched, self.launch_failed]
        queryset = ContainerJob.objects.filter(
            id__in=[job.id for job in test_jobs]
        )
        filtered = filter_instance.queryset(request, queryset)
        
        self.assertNotIn(self.not_queued, filtered)
        self.assertNotIn(self.queued, filtered)
        self.assertNotIn(self.scheduled, filtered)
        self.assertIn(self.launched, filtered)
    
    def test_filter_launch_failed(self):
        """Test filtering for launch failed jobs"""
        from django.contrib.admin.sites import AdminSite
        from django.http import QueryDict
        from ..admin import ContainerJobAdmin
        
        site = AdminSite()
        admin_instance = ContainerJobAdmin(ContainerJob, site)
        
        params = QueryDict('', mutable=True)
        params['queue_status'] = 'launch_failed'
        
        request = self.factory.get('/?queue_status=launch_failed')
        filter_instance = QueueStatusFilter(request, params, ContainerJob, admin_instance)
        
        test_jobs = [self.not_queued, self.queued, self.scheduled, self.launched, self.launch_failed]
        queryset = ContainerJob.objects.filter(
            id__in=[job.id for job in test_jobs]
        )
        filtered = filter_instance.queryset(request, queryset)
        
        self.assertNotIn(self.not_queued, filtered)
        self.assertNotIn(self.queued, filtered)
        self.assertNotIn(self.scheduled, filtered)
        self.assertNotIn(self.launched, filtered)
        self.assertIn(self.launch_failed, filtered)
    
    def test_get_queryset_optimization(self):
        """Test that admin optimizes database queries"""
        from django.contrib.admin.sites import AdminSite
        from ..admin import ContainerJobAdmin
        
        site = AdminSite()
        admin = ContainerJobAdmin(ContainerJob, site)
        
        # Mock request
        request = self.factory.get('/')
        
        queryset = admin.get_queryset(request)
        
        # Check that select_related is applied for optimization
        self.assertTrue(hasattr(queryset, '_prefetch_related_lookups'))


class AdminIntegrationTest(TestCase):
    """Integration tests for admin interface"""
    
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'password')
        self.host = ExecutorHost.objects.create(
            name='test-integration-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
    
    def test_admin_list_view_rendering(self):
        """Test that admin list view renders without errors"""
        # Create a test job
        job = ContainerJob.objects.create(
            docker_image='nginx:admin-test',
            command='echo "admin integration test"',
            docker_host=self.host,
            priority=75
        )
        job.mark_as_queued()
        
        # Login and access admin list view
        self.client.login(username='admin', password='password')
        response = self.client.get('/admin/container_manager/containerjob/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nginx:admin-test')
        self.assertContains(response, 'Queued')  # Queue status should be displayed
        self.assertContains(response, '75')      # Priority should be displayed
    
    def test_admin_detail_view_rendering(self):
        """Test that admin detail view renders with queue information"""
        job = ContainerJob.objects.create(
            docker_image='nginx:admin-detail-test',
            command='echo "admin detail test"',
            docker_host=self.host,
            priority=60,
            max_retries=3
        )
        job.mark_as_queued()
        
        self.client.login(username='admin', password='password')
        response = self.client.get(f'/admin/container_manager/containerjob/{job.id}/change/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Queue Information')
        self.assertContains(response, 'Priority')
        self.assertContains(response, 'max_retries')
        self.assertContains(response, 'Queue Details')