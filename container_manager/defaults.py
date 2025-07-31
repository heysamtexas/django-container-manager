"""
Default settings for django-container-manager.

These settings provide sensible defaults for all container management functionality.
Users can override any of these by adding CONTAINER_MANAGER settings to their Django settings.py.

Example usage in settings.py:
    CONTAINER_MANAGER = {
        "AUTO_PULL_IMAGES": False,
        "MAX_CONCURRENT_JOBS": 5,
        "POLL_INTERVAL": 10,
    }
"""

DEFAULT_CONTAINER_MANAGER_SETTINGS = {
    # Image Management
    "AUTO_PULL_IMAGES": True,
    "IMAGE_PULL_TIMEOUT": 300,
    # Container Cleanup
    "IMMEDIATE_CLEANUP": True,
    "CLEANUP_ENABLED": True,
    "CLEANUP_HOURS": 24,
    # Job Processing
    "MAX_CONCURRENT_JOBS": 10,
    "POLL_INTERVAL": 5,
    "JOB_TIMEOUT_SECONDS": 3600,
    # Docker Operation Timeouts (seconds)
    "DOCKER_TIMEOUT": 30,  # General Docker API operations
    "DOCKER_CREATE_TIMEOUT": 60,  # Container creation
    "DOCKER_START_TIMEOUT": 30,  # Container start
    "DOCKER_LOGS_TIMEOUT": 30,  # Log retrieval
    "DOCKER_WAIT_TIMEOUT": 120,  # Container wait operations
    # Resource Limits
    "DEFAULT_MEMORY_LIMIT": 512,  # MB
    "DEFAULT_CPU_LIMIT": 1.0,  # cores
    # Logging and Monitoring
    "LOG_RETENTION_DAYS": 30,
    "ENABLE_METRICS": True,
    "ENABLE_HEALTH_CHECKS": True,
    # Network and Security
    "DEFAULT_NETWORK": "bridge",
    "ENABLE_PRIVILEGED_CONTAINERS": False,
    "ENABLE_HOST_NETWORKING": False,
}

# Executor factory settings
DEFAULT_USE_EXECUTOR_FACTORY = False

# Environment variable to determine if running in development
DEFAULT_DEBUG_MODE = False


def get_container_manager_setting(key: str, default=None):
    """
    Get a container manager setting with fallback to defaults.

    Args:
        key: Setting key to retrieve
        default: Override default if provided

    Returns:
        Setting value or default
    """
    try:
        from django.conf import settings

        if settings.configured:
            container_settings = getattr(settings, "CONTAINER_MANAGER", {})
            return container_settings.get(
                key, default or DEFAULT_CONTAINER_MANAGER_SETTINGS.get(key)
            )
        else:
            return default or DEFAULT_CONTAINER_MANAGER_SETTINGS.get(key)
    except (ImportError, Exception):
        # Django not available or not configured, return default
        return default or DEFAULT_CONTAINER_MANAGER_SETTINGS.get(key)


def get_use_executor_factory():
    """
    Get the USE_EXECUTOR_FACTORY setting with fallback.

    Returns:
        bool: Whether to use the executor factory
    """
    try:
        from django.conf import settings

        if settings.configured:
            return getattr(
                settings, "USE_EXECUTOR_FACTORY", DEFAULT_USE_EXECUTOR_FACTORY
            )
        else:
            return DEFAULT_USE_EXECUTOR_FACTORY
    except (ImportError, Exception):
        return DEFAULT_USE_EXECUTOR_FACTORY
