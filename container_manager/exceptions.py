"""
Custom exceptions for django-container-manager.

This module defines custom exception classes for better error handling
and debugging throughout the container management system.
"""


class ContainerManagerError(Exception):
    """Base exception for container manager operations"""
    pass


class JobExecutionError(ContainerManagerError):
    """Raised when job execution fails"""
    pass


class QueueError(ContainerManagerError):
    """Base exception for queue operations"""
    pass


class JobNotQueuedError(QueueError):
    """Raised when trying to operate on non-queued job"""
    pass


class JobAlreadyQueuedError(QueueError):
    """Raised when trying to queue already queued job"""
    pass


class QueueCapacityError(QueueError):
    """Raised when queue is at capacity"""
    pass


class InvalidStateTransitionError(ContainerManagerError):
    """Raised when attempting invalid job state transition"""
    pass