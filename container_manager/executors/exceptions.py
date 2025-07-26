"""
Exception classes for container executors.

Provides a hierarchy of exceptions for different types of executor failures,
enabling proper error handling and graceful degradation across executor types.
"""


class ExecutorError(Exception):
    """Base exception for executor-related errors"""

    pass


class ExecutorConnectionError(ExecutorError):
    """Raised when executor cannot connect to backend service"""

    pass


class ExecutorConfigurationError(ExecutorError):
    """Raised when executor configuration is invalid"""

    pass


class ExecutorResourceError(ExecutorError):
    """Raised when executor lacks resources to execute job"""

    pass


class ExecutorAuthenticationError(ExecutorError):
    """Raised when executor authentication fails"""

    pass


class ExecutorTimeoutError(ExecutorError):
    """Raised when executor operation times out"""

    pass


class ExecutorCapacityError(ExecutorResourceError):
    """Raised when executor is at capacity"""

    pass
