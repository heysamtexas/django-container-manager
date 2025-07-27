"""
Exception classes for container executors.

Provides a hierarchy of exceptions for different types of executor failures,
enabling proper error handling and graceful degradation across executor types.
"""


class ExecutorError(Exception):
    """Base exception for executor-related errors"""


class ExecutorConnectionError(ExecutorError):
    """Raised when executor cannot connect to backend service"""


class ExecutorConfigurationError(ExecutorError):
    """Raised when executor configuration is invalid"""


class ExecutorResourceError(ExecutorError):
    """Raised when executor lacks resources to execute job"""


class ExecutorAuthenticationError(ExecutorError):
    """Raised when executor authentication fails"""


class ExecutorTimeoutError(ExecutorError):
    """Raised when executor operation times out"""


class ExecutorCapacityError(ExecutorResourceError):
    """Raised when executor is at capacity"""
