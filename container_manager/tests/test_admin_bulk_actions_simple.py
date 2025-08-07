"""
Simple tests for admin bulk actions functionality.

This module tests the core functionality of admin bulk actions
without the complex Django admin middleware setup.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from ..models import ContainerJob, ExecutorHost
from ..admin import ContainerJobAdmin
from django.contrib.admin.sites import AdminSite


class SimpleBulkActionsTest(TestCase):
    """Simple tests for admin bulk actions"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = ContainerJobAdmin(ContainerJob, self.site)
        self.superuser = User.objects.create_superuser('admin', 'admin@test.com', 'password')
        
        # Create test host
        self.host = ExecutorHost.objects.create(
            name='test-simple-host',
            host_type='unix',
            connection_string='unix:///var/run/docker.sock',
            is_active=True
        )
        
        # Create test jobs
        self.pending_job = ContainerJob.objects.create(
            docker_image='nginx:test-simple-pending',
            command='echo "pending"',
            docker_host=self.host,
            status='pending'
        )
        
        self.failed_job = ContainerJob.objects.create(
            docker_image='nginx:test-simple-failed',
            command='echo "failed"',
            docker_host=self.host,
            status='failed'
        )
        
    def _create_request(self, user):
        """Helper to create request with messages support"""
        request = self.factory.post('/')
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request
    
    def test_queue_job_functionality(self):
        """Test that we can queue jobs using the queue manager directly"""
        from ..queue import queue_manager
        
        # Queue a pending job
        queue_manager.queue_job(self.pending_job)
        
        # Refresh and verify
        self.pending_job.refresh_from_db()
        self.assertTrue(self.pending_job.is_queued)
        self.assertIsNotNone(self.pending_job.queued_at)
    
    def test_dequeue_job_functionality(self):
        """Test that we can dequeue jobs using the queue manager directly"""
        from ..queue import queue_manager
        
        # First queue the job
        queue_manager.queue_job(self.pending_job)
        self.pending_job.refresh_from_db()
        self.assertTrue(self.pending_job.is_queued)
        
        # Then dequeue it
        queue_manager.dequeue_job(self.pending_job)
        self.pending_job.refresh_from_db()
        self.assertFalse(self.pending_job.is_queued)
        self.assertIsNone(self.pending_job.queued_at)
    
    def test_retry_failed_job_functionality(self):
        """Test that we can retry failed jobs using the queue manager directly"""
        from ..queue import queue_manager
        
        # Retry a failed job
        queue_manager.retry_failed_job(self.failed_job, reset_count=True)
        
        # Refresh and verify
        self.failed_job.refresh_from_db()
        self.assertTrue(self.failed_job.is_queued)
        self.assertEqual(self.failed_job.retry_count, 0)  # Reset count
    
    def test_bulk_priority_setting(self):
        """Test bulk priority setting"""
        request = self._create_request(self.superuser)
        queryset = ContainerJob.objects.filter(id__in=[self.pending_job.id, self.failed_job.id])
        
        # Test setting high priority
        self.admin.set_high_priority(request, queryset)
        
        self.pending_job.refresh_from_db()
        self.failed_job.refresh_from_db()
        
        self.assertEqual(self.pending_job.priority, 80)
        self.assertEqual(self.failed_job.priority, 80)
        
        # Test setting normal priority
        self.admin.set_normal_priority(request, queryset)
        
        self.pending_job.refresh_from_db()
        self.failed_job.refresh_from_db()
        
        self.assertEqual(self.pending_job.priority, 50)
        self.assertEqual(self.failed_job.priority, 50)
        
        # Test setting low priority
        self.admin.set_low_priority(request, queryset)
        
        self.pending_job.refresh_from_db()
        self.failed_job.refresh_from_db()
        
        self.assertEqual(self.pending_job.priority, 20)
        self.assertEqual(self.failed_job.priority, 20)
    
    def test_queue_manager_worker_metrics(self):
        """Test that queue manager provides worker metrics"""
        from ..queue import queue_manager
        
        # Queue a job
        queue_manager.queue_job(self.pending_job)
        
        # Get metrics
        metrics = queue_manager.get_worker_metrics()
        
        # Verify expected keys exist
        expected_keys = ['ready_now', 'scheduled_future', 'running', 'launch_failed', 'queue_depth']
        for key in expected_keys:
            self.assertIn(key, metrics)
        
        # Should have at least 1 ready job now
        self.assertGreaterEqual(metrics['ready_now'], 1)
        self.assertGreaterEqual(metrics['queue_depth'], 1)
    
    def test_admin_action_descriptions(self):
        """Test that admin actions have proper descriptions"""
        # Verify admin actions are configured
        expected_actions = [
            'queue_selected_jobs',
            'dequeue_selected_jobs', 
            'retry_failed_jobs',
            'set_high_priority',
            'set_normal_priority',
            'set_low_priority',
        ]
        
        for action_name in expected_actions:
            self.assertIn(action_name, self.admin.actions)
            
            # Verify the action method exists and has description
            action_method = getattr(self.admin, action_name)
            self.assertTrue(callable(action_method))
            self.assertTrue(hasattr(action_method, 'short_description'))
            self.assertIsNotNone(action_method.short_description)
    
    def test_admin_custom_urls_exist(self):
        """Test that custom admin URLs are configured"""
        urls = self.admin.get_urls()
        url_names = [url.name for url in urls if hasattr(url, 'name') and url.name]
        
        expected_url_names = [
            'container_manager_containerjob_dequeue',
            'container_manager_containerjob_requeue', 
            'container_manager_containerjob_cancel',
            'container_manager_containerjob_queue_stats'
        ]
        
        for url_name in expected_url_names:
            self.assertIn(url_name, url_names)
    
    def test_job_state_transitions(self):
        """Test that job state transitions work correctly for admin actions"""
        from ..queue import queue_manager
        
        # Test pending -> queued
        self.assertEqual(self.pending_job.status, 'pending')
        self.assertFalse(self.pending_job.is_queued)
        
        queue_manager.queue_job(self.pending_job)
        self.pending_job.refresh_from_db()
        
        self.assertEqual(self.pending_job.status, 'queued')
        self.assertTrue(self.pending_job.is_queued)
        
        # Test failed -> retry -> queued
        self.assertEqual(self.failed_job.status, 'failed')
        self.assertFalse(self.failed_job.is_queued)
        
        queue_manager.retry_failed_job(self.failed_job)
        self.failed_job.refresh_from_db()
        
        self.assertEqual(self.failed_job.status, 'queued')
        self.assertTrue(self.failed_job.is_queued)