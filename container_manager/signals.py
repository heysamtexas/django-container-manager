"""
Graceful shutdown and signal handling for django-container-manager queue processors.

This module provides comprehensive shutdown coordination to prevent job corruption
and ensure clean termination of queue processing operations.
"""

import logging
import signal
import threading
import time

from django.utils import timezone

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handles graceful shutdown for queue processors"""

    def __init__(self, timeout=30):
        self.shutdown_event = threading.Event()
        self.timeout = timeout
        self.start_time = None
        self.stats = {
            "shutdown_initiated": None,
            "jobs_completed_during_shutdown": 0,
            "jobs_interrupted": 0,
            "clean_exit": False,
        }

    def setup_signal_handlers(self, status_callback=None):
        """
        Set up signal handlers for graceful shutdown.

        Args:
            status_callback: Function to call for status reporting
        """

        def shutdown_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")

            self.stats["shutdown_initiated"] = timezone.now()
            self.start_time = time.time()
            self.shutdown_event.set()

        def status_handler(signum, frame):
            if status_callback:
                try:
                    status_callback()
                except Exception as e:
                    logger.error(f"Error in status callback: {e}")
            else:
                self._default_status_report()

        # Graceful shutdown signals
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        # Status reporting signal (only available on Unix systems)
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, status_handler)
            logger.info("Signal handlers configured (TERM/INT=shutdown, USR1=status)")
        else:
            logger.info(
                "Signal handlers configured (TERM/INT=shutdown, USR1=not available)"
            )

    def is_shutdown_requested(self):
        """Check if shutdown has been requested"""
        return self.shutdown_event.is_set()

    def wait_for_shutdown(self, poll_interval=1):
        """
        Wait for shutdown signal with timeout.

        Args:
            poll_interval: How often to check for shutdown

        Returns:
            bool: True if shutdown was requested, False if timeout
        """
        return self.shutdown_event.wait(poll_interval)

    def check_timeout(self):
        """
        Check if shutdown timeout has been exceeded.

        Returns:
            bool: True if timeout exceeded
        """
        if not self.start_time:
            return False

        elapsed = time.time() - self.start_time
        if elapsed > self.timeout:
            logger.warning(f"Graceful shutdown timeout ({self.timeout}s) exceeded")
            return True

        return False

    def _default_status_report(self):
        """Default status reporting"""
        try:
            from container_manager.queue import queue_manager

            metrics = queue_manager.get_worker_metrics()
            logger.info(f"Queue status: {metrics}")
            print(f"Queue metrics: {metrics}")  # Also print to stdout for operators
        except Exception as e:
            logger.error(f"Error getting queue metrics: {e}")


class JobCompletionTracker:
    """Tracks job completion during shutdown"""

    def __init__(self):
        self.running_jobs = set()
        self.completed_jobs = set()
        self.lock = threading.Lock()

    def add_running_job(self, job_id):
        """Add a job to the running set"""
        with self.lock:
            self.running_jobs.add(str(job_id))  # Ensure string for consistency

    def mark_job_completed(self, job_id):
        """Mark a job as completed"""
        with self.lock:
            job_id_str = str(job_id)
            if job_id_str in self.running_jobs:
                self.running_jobs.remove(job_id_str)
                self.completed_jobs.add(job_id_str)
                logger.debug(f"Job {job_id} marked as completed")

    def get_running_count(self):
        """Get count of still-running jobs"""
        with self.lock:
            return len(self.running_jobs)

    def get_running_jobs(self):
        """Get list of running job IDs"""
        with self.lock:
            return list(self.running_jobs)

    def wait_for_completion(self, timeout=30, poll_interval=1):
        """
        Wait for all running jobs to complete.

        Args:
            timeout: Maximum time to wait
            poll_interval: How often to check

        Returns:
            bool: True if all jobs completed, False if timeout
        """
        start_time = time.time()

        while self.get_running_count() > 0:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(
                    f"Timeout waiting for {self.get_running_count()} jobs to complete"
                )
                return False

            logger.debug(f"Waiting for {self.get_running_count()} jobs to complete...")
            time.sleep(poll_interval)

        logger.info(f"All jobs completed in {time.time() - start_time:.1f}s")
        return True

    def get_stats(self):
        """Get completion tracking statistics"""
        with self.lock:
            return {
                "running": len(self.running_jobs),
                "completed": len(self.completed_jobs),
                "total_tracked": len(self.running_jobs) + len(self.completed_jobs),
            }

    def clear(self):
        """Clear all tracked jobs (useful for testing)"""
        with self.lock:
            self.running_jobs.clear()
            self.completed_jobs.clear()


# Global instances for use across the application
graceful_shutdown = GracefulShutdown()
job_completion_tracker = JobCompletionTracker()
