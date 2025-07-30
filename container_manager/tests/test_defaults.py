"""
Tests for container_manager.defaults module.

Tests settings retrieval functions and default constants validation.
"""

from unittest.mock import PropertyMock, patch

from django.test import TestCase

from ..defaults import (
    DEFAULT_CONTAINER_MANAGER_SETTINGS,
    DEFAULT_DEBUG_MODE,
    DEFAULT_USE_EXECUTOR_FACTORY,
    get_container_manager_setting,
    get_use_executor_factory,
)


class ContainerManagerSettingsTest(TestCase):
    """Test get_container_manager_setting function."""

    @patch("django.conf.settings")
    def test_get_container_manager_setting_with_django_configured(self, mock_settings):
        """Test settings retrieval when Django is properly configured."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {
            "MAX_CONCURRENT_JOBS": 15,
            "POLL_INTERVAL": 10,
        }

        result = get_container_manager_setting("MAX_CONCURRENT_JOBS")
        self.assertEqual(result, 15)

        result = get_container_manager_setting("POLL_INTERVAL")
        self.assertEqual(result, 10)

    @patch("django.conf.settings")
    def test_get_container_manager_setting_fallback_to_default(self, mock_settings):
        """Test fallback to default when setting not in Django config."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {}  # Empty config

        result = get_container_manager_setting("MAX_CONCURRENT_JOBS")
        self.assertEqual(result, 10)  # Should use DEFAULT_CONTAINER_MANAGER_SETTINGS

    @patch("django.conf.settings")
    def test_get_container_manager_setting_django_not_configured(self, mock_settings):
        """Test behavior when Django is not configured."""
        mock_settings.configured = False

        result = get_container_manager_setting("MAX_CONCURRENT_JOBS")
        self.assertEqual(result, 10)  # Should use default

    @patch("django.conf.settings")
    def test_get_container_manager_setting_with_override_default(self, mock_settings):
        """Test settings retrieval with explicit default override."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {}

        result = get_container_manager_setting("MAX_CONCURRENT_JOBS", default=20)
        self.assertEqual(result, 20)  # Should use provided default

    def test_get_container_manager_setting_django_import_error(self):
        """Test handling when Django is not available."""
        # Mock the django.conf import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "django.conf":
                raise ImportError("Django not available")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = get_container_manager_setting("MAX_CONCURRENT_JOBS")
            self.assertEqual(result, 10)  # Should fallback to default

    @patch("django.conf.settings")
    def test_get_container_manager_setting_general_exception(self, mock_settings):
        """Test handling of general exceptions during settings retrieval."""
        mock_settings.configured = True
        # Simulate exception when accessing CONTAINER_MANAGER
        type(mock_settings).CONTAINER_MANAGER = PropertyMock(
            side_effect=Exception("Settings error")
        )

        result = get_container_manager_setting("MAX_CONCURRENT_JOBS")
        self.assertEqual(result, 10)  # Should fallback to default

    @patch("django.conf.settings")
    def test_get_container_manager_setting_multiple_calls_consistency(
        self, mock_settings
    ):
        """Test that multiple calls return consistent results."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {"MAX_CONCURRENT_JOBS": 25}

        result1 = get_container_manager_setting("MAX_CONCURRENT_JOBS")
        result2 = get_container_manager_setting("MAX_CONCURRENT_JOBS")

        self.assertEqual(result1, result2)
        self.assertEqual(result1, 25)

    @patch("django.conf.settings")
    def test_get_container_manager_setting_with_partial_configuration(
        self, mock_settings
    ):
        """Test behavior with partial Django configuration."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {
            "MAX_CONCURRENT_JOBS": 20,
            # Missing other settings
        }

        # Should get configured value
        self.assertEqual(get_container_manager_setting("MAX_CONCURRENT_JOBS"), 20)

        # Should get default for missing setting
        self.assertEqual(get_container_manager_setting("POLL_INTERVAL"), 5)

    @patch("django.conf.settings")
    def test_get_container_manager_setting_none_handling(self, mock_settings):
        """Test handling of None values in settings."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {"MAX_CONCURRENT_JOBS": None}

        # Should return None when value is None (actual behavior)
        result = get_container_manager_setting("MAX_CONCURRENT_JOBS")
        self.assertIsNone(result)  # Should return None as configured in settings

        # Even with explicit default, the function returns the None value from settings
        # because dict.get() returns the None value when key exists with None value
        result_with_default = get_container_manager_setting(
            "MAX_CONCURRENT_JOBS", default=15
        )
        self.assertIsNone(result_with_default)  # Still returns None from settings

        # Test case where the key doesn't exist at all - then default should be used
        result_missing_key = get_container_manager_setting(
            "NONEXISTENT_KEY", default=15
        )
        self.assertEqual(result_missing_key, 15)  # Should use provided default

    @patch("django.conf.settings")
    def test_get_container_manager_setting_edge_case_values(self, mock_settings):
        """Test handling of edge case values."""
        mock_settings.configured = True
        mock_settings.CONTAINER_MANAGER = {
            "MAX_CONCURRENT_JOBS": 0,  # Zero value
            "POLL_INTERVAL": -1,  # Negative value
            "DEFAULT_NETWORK": "",  # Empty string
        }

        self.assertEqual(get_container_manager_setting("MAX_CONCURRENT_JOBS"), 0)
        self.assertEqual(get_container_manager_setting("POLL_INTERVAL"), -1)
        self.assertEqual(get_container_manager_setting("DEFAULT_NETWORK"), "")


class ExecutorFactorySettingsTest(TestCase):
    """Test get_use_executor_factory function."""

    @patch("django.conf.settings")
    def test_get_use_executor_factory_django_configured(self, mock_settings):
        """Test executor factory setting when Django is configured."""
        mock_settings.configured = True
        mock_settings.USE_EXECUTOR_FACTORY = True

        result = get_use_executor_factory()
        self.assertTrue(result)

    @patch("django.conf.settings")
    def test_get_use_executor_factory_default_value(self, mock_settings):
        """Test default value when setting not explicitly set."""
        mock_settings.configured = True
        # USE_EXECUTOR_FACTORY not set
        del mock_settings.USE_EXECUTOR_FACTORY

        result = get_use_executor_factory()
        self.assertEqual(result, DEFAULT_USE_EXECUTOR_FACTORY)

    @patch("django.conf.settings")
    def test_get_use_executor_factory_django_not_configured(self, mock_settings):
        """Test behavior when Django is not configured."""
        mock_settings.configured = False

        result = get_use_executor_factory()
        self.assertEqual(result, DEFAULT_USE_EXECUTOR_FACTORY)

    def test_get_use_executor_factory_django_import_error(self):
        """Test handling when Django is not available."""
        # Mock the django.conf import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "django.conf":
                raise ImportError("Django not available")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = get_use_executor_factory()
            self.assertEqual(result, DEFAULT_USE_EXECUTOR_FACTORY)

    @patch("django.conf.settings")
    def test_get_use_executor_factory_general_exception(self, mock_settings):
        """Test handling of general exceptions."""
        mock_settings.configured = True
        # Simulate exception when accessing USE_EXECUTOR_FACTORY
        type(mock_settings).USE_EXECUTOR_FACTORY = PropertyMock(
            side_effect=Exception("Settings error")
        )

        result = get_use_executor_factory()
        self.assertEqual(result, DEFAULT_USE_EXECUTOR_FACTORY)


class DefaultSettingsConstantsTest(TestCase):
    """Test default settings constants validation."""

    def test_default_container_manager_settings_structure(self):
        """Test that all expected default settings are present."""
        expected_keys = [
            "AUTO_PULL_IMAGES",
            "IMAGE_PULL_TIMEOUT",
            "IMMEDIATE_CLEANUP",
            "CLEANUP_ENABLED",
            "CLEANUP_HOURS",
            "MAX_CONCURRENT_JOBS",
            "POLL_INTERVAL",
            "JOB_TIMEOUT_SECONDS",
            "DEFAULT_MEMORY_LIMIT",
            "DEFAULT_CPU_LIMIT",
            "LOG_RETENTION_DAYS",
            "ENABLE_METRICS",
            "ENABLE_HEALTH_CHECKS",
            "DEFAULT_NETWORK",
            "ENABLE_PRIVILEGED_CONTAINERS",
            "ENABLE_HOST_NETWORKING",
        ]

        for key in expected_keys:
            self.assertIn(key, DEFAULT_CONTAINER_MANAGER_SETTINGS)
            self.assertIsNotNone(DEFAULT_CONTAINER_MANAGER_SETTINGS[key])

    def test_default_settings_data_types(self):
        """Test that default settings have appropriate data types."""
        self.assertIsInstance(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["AUTO_PULL_IMAGES"], bool
        )
        self.assertIsInstance(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["IMAGE_PULL_TIMEOUT"], int
        )
        self.assertIsInstance(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["MAX_CONCURRENT_JOBS"], int
        )
        self.assertIsInstance(DEFAULT_CONTAINER_MANAGER_SETTINGS["POLL_INTERVAL"], int)
        self.assertIsInstance(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_MEMORY_LIMIT"], int
        )
        self.assertIsInstance(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_CPU_LIMIT"], float
        )
        self.assertIsInstance(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_NETWORK"], str
        )

    def test_default_boolean_flags(self):
        """Test boolean flag defaults."""
        self.assertTrue(DEFAULT_CONTAINER_MANAGER_SETTINGS["AUTO_PULL_IMAGES"])
        self.assertTrue(DEFAULT_CONTAINER_MANAGER_SETTINGS["IMMEDIATE_CLEANUP"])
        self.assertTrue(DEFAULT_CONTAINER_MANAGER_SETTINGS["CLEANUP_ENABLED"])
        self.assertTrue(DEFAULT_CONTAINER_MANAGER_SETTINGS["ENABLE_METRICS"])
        self.assertTrue(DEFAULT_CONTAINER_MANAGER_SETTINGS["ENABLE_HEALTH_CHECKS"])
        self.assertFalse(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["ENABLE_PRIVILEGED_CONTAINERS"]
        )
        self.assertFalse(DEFAULT_CONTAINER_MANAGER_SETTINGS["ENABLE_HOST_NETWORKING"])

    def test_default_executor_factory_setting(self):
        """Test executor factory default setting."""
        self.assertIsInstance(DEFAULT_USE_EXECUTOR_FACTORY, bool)
        self.assertFalse(DEFAULT_USE_EXECUTOR_FACTORY)  # Should default to False

    def test_default_debug_mode_setting(self):
        """Test debug mode default setting."""
        self.assertIsInstance(DEFAULT_DEBUG_MODE, bool)
        self.assertFalse(DEFAULT_DEBUG_MODE)  # Should default to False

    def test_default_settings_reasonable_values(self):
        """Test that default settings have reasonable values."""
        # Test numeric ranges
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["IMAGE_PULL_TIMEOUT"], 0)
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["MAX_CONCURRENT_JOBS"], 0)
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["POLL_INTERVAL"], 0)
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["JOB_TIMEOUT_SECONDS"], 0)
        self.assertGreater(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_MEMORY_LIMIT"], 0
        )
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_CPU_LIMIT"], 0)
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["LOG_RETENTION_DAYS"], 0)
        self.assertGreater(DEFAULT_CONTAINER_MANAGER_SETTINGS["CLEANUP_HOURS"], 0)

        # Test string values are non-empty
        self.assertNotEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_NETWORK"], "")

    def test_default_settings_specific_values(self):
        """Test specific default values match expected configuration."""
        # Test specific values from the task description
        self.assertEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["MAX_CONCURRENT_JOBS"], 10)
        self.assertEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["POLL_INTERVAL"], 5)
        self.assertEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["IMAGE_PULL_TIMEOUT"], 300)
        self.assertEqual(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_MEMORY_LIMIT"], 512
        )
        self.assertEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_CPU_LIMIT"], 1.0)
        self.assertEqual(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["DEFAULT_NETWORK"], "bridge"
        )
        self.assertEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["LOG_RETENTION_DAYS"], 30)
        self.assertEqual(DEFAULT_CONTAINER_MANAGER_SETTINGS["CLEANUP_HOURS"], 24)
        self.assertEqual(
            DEFAULT_CONTAINER_MANAGER_SETTINGS["JOB_TIMEOUT_SECONDS"], 3600
        )
