"""
Custom exceptions for django-container-manager.

This module defines custom exception classes for better error handling
and debugging throughout the container management system.
"""


class ContainerManagerError(Exception):
    """Base exception for container manager operations"""


class JobExecutionError(ContainerManagerError):
    """Raised when job execution fails"""


class QueueError(ContainerManagerError):
    """Base exception for queue operations"""


class JobNotQueuedError(QueueError):
    """Raised when trying to operate on non-queued job"""


class JobAlreadyQueuedError(QueueError):
    """Raised when trying to queue already queued job"""


class QueueCapacityError(QueueError):
    """Raised when queue is at capacity"""


class InvalidStateTransitionError(ContainerManagerError):
    """Raised when attempting invalid job state transition"""
