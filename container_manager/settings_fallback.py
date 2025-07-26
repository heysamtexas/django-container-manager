"""
Django settings for executor fallback and reliability features.
Add these settings to your Django settings file to configure fallback behavior.
"""

# Maximum number of retry attempts for failed jobs
EXECUTOR_MAX_RETRIES = 3

# Base delay for exponential backoff (in seconds)
EXECUTOR_BASE_RETRY_DELAY = 1.0

# Maximum retry delay (in seconds)
EXECUTOR_MAX_RETRY_DELAY = 60.0

# Jitter factor for retry delays (0.0 to 1.0)
EXECUTOR_RETRY_JITTER = 0.1

# Health check interval (in seconds)
EXECUTOR_HEALTH_CHECK_INTERVAL = 300  # 5 minutes

# Number of consecutive failures before marking executor as unhealthy
EXECUTOR_FAILURE_THRESHOLD = 3

# Number of consecutive successes needed to mark executor as healthy again
EXECUTOR_RECOVERY_THRESHOLD = 2

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5  # Failures before opening circuit
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60  # Seconds before attempting recovery

# Graceful degradation settings
DEGRADATION_RESOURCE_REDUCTION_FACTOR = 0.75  # Reduce resources by 25%
DEGRADATION_DELAY_THRESHOLD = "test|batch"  # Regex for jobs that can be delayed

# Fallback executor priorities (ordered by preference)
FALLBACK_EXECUTOR_PRIORITIES = {
    "docker": ["mock", "cloudrun", "fargate"],
    "cloudrun": ["docker", "fargate", "mock"],
    "fargate": ["cloudrun", "docker", "mock"],
    "mock": ["docker", "cloudrun", "fargate"],
}

# Enable/disable specific fallback features
FALLBACK_FEATURES = {
    "retry_enabled": True,
    "circuit_breaker_enabled": True,
    "graceful_degradation_enabled": True,
    "health_monitoring_enabled": True,
    "automatic_fallback_enabled": True,
}

# Logging configuration for fallback operations
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "fallback_file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "fallback.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "container_manager.executors.fallback": {
            "handlers": ["fallback_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "container_manager.executors.factory": {
            "handlers": ["fallback_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Example usage in your settings.py:
"""
# Import fallback settings
from container_manager.settings_fallback import *

# Override specific settings as needed
EXECUTOR_MAX_RETRIES = 5
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 10
"""
