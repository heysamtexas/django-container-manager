"""
Django Container Manager

A Django app for container orchestration with multi-executor support.
Supports Docker, Google Cloud Run, AWS Fargate, and custom executors.
"""

__version__ = "1.0.14"
__author__ = "Sam Texas"
__email__ = "dev@simplecto.com"

# Public API exports - imported lazily to avoid Django app loading issues
__all__ = [
    "ContainerExecution",
    "ContainerJob",
    "EnvironmentVariableTemplate",
    "ExecutorHost",
    "JobManager",
]
