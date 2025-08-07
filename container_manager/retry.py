"""
Retry logic and error classification system for django-container-manager.

This module provides intelligent retry strategies with error classification,
exponential backoff, and configurable retry policies for different job types.
"""

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of errors for retry decision making"""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class ErrorClassifier:
    """Classifies errors to determine retry strategy"""

    from typing import ClassVar

    TRANSIENT_PATTERNS: ClassVar[list[str]] = [
        # Docker daemon issues
        r"connection.*refused",
        r"docker.*daemon.*not.*running",
        r"timeout.*connecting",
        # Resource constraints
        r"out of memory",
        r"no space left",
        r"resource temporarily unavailable",
        # Network issues
        r"network.*timeout",
        r"connection.*reset",
        r"temporary failure in name resolution",
        # System load
        r"system overloaded",
        r"too many open files",
        r"cannot allocate memory",
    ]

    PERMANENT_PATTERNS: ClassVar[list[str]] = [
        # Image issues
        r"image.*not found",
        r"no such image",
        r"repository.*not found",
        # Configuration errors
        r"invalid.*configuration",
        r"permission denied",
        r"access denied",
        r"authorization.*failed",
        # Command issues
        r"executable.*not found",
        r"command.*not found",
        r"invalid.*command",
    ]

    @classmethod
    def classify_error(cls, error_message):
        """
        Classify error as transient, permanent, or unknown.

        Args:
            error_message: Error message string

        Returns:
            ErrorType: Classification of the error
        """
        error_lower = error_message.lower()

        # Check for transient errors first
        for pattern in cls.TRANSIENT_PATTERNS:
            if re.search(pattern, error_lower):
                logger.debug(f"Classified as TRANSIENT: {pattern}")
                return ErrorType.TRANSIENT

        # Check for permanent errors
        for pattern in cls.PERMANENT_PATTERNS:
            if re.search(pattern, error_lower):
                logger.debug(f"Classified as PERMANENT: {pattern}")
                return ErrorType.PERMANENT

        # Default to unknown (treat as transient with caution)
        logger.debug("Classified as UNKNOWN")
        return ErrorType.UNKNOWN


class RetryStrategy:
    """Defines retry behavior for different error types"""

    def __init__(
        self, max_attempts=3, base_delay=1.0, max_delay=300.0, backoff_factor=2.0
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def should_retry(self, attempt_count, error_type):
        """
        Determine if job should be retried.

        Args:
            attempt_count: Current attempt number (1-based)
            error_type: ErrorType classification

        Returns:
            bool: True if should retry
        """
        if error_type == ErrorType.PERMANENT:
            return False

        return attempt_count < self.max_attempts

    def get_retry_delay(self, attempt_count):
        """
        Calculate delay before retry.

        Args:
            attempt_count: Current attempt number (1-based)

        Returns:
            float: Delay in seconds
        """
        if attempt_count <= 1:
            return 0  # First attempt has no delay

        delay = self.base_delay * (self.backoff_factor ** (attempt_count - 2))
        return min(delay, self.max_delay)


# Predefined strategies for different scenarios
RETRY_STRATEGIES = {
    "default": RetryStrategy(max_attempts=3, base_delay=2.0, max_delay=60.0),
    "aggressive": RetryStrategy(max_attempts=5, base_delay=1.0, max_delay=30.0),
    "conservative": RetryStrategy(max_attempts=2, base_delay=5.0, max_delay=300.0),
    "high_priority": RetryStrategy(max_attempts=5, base_delay=0.5, max_delay=15.0),
}
