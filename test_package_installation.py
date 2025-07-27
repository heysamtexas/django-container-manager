#!/usr/bin/env python3
"""
Test script to validate django-container-manager package installation
and functionality in a fresh Django project.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a command and return result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(f"STDOUT: {result.stdout}")
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    return result


def test_package_installation():
    """Test installing and using the package in a fresh Django project"""

    print("🧪 Testing django-container-manager package installation...")

    # Get the path to our built package
    container_manager_dir = Path(__file__).parent / "container_manager"
    wheel_file = next(container_manager_dir.glob("dist/*.whl"))

    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Working in temporary directory: {temp_dir}")
        os.chdir(temp_dir)

        # Create a virtual environment using uv
        print("\n🔧 Creating virtual environment...")
        run_command(["uv", "venv", "test_env"])

        # Set up environment variables for the virtual environment
        venv_path = os.path.join(temp_dir, "test_env")
        python_path = os.path.join(venv_path, "bin", "python")
        # pip_path would be needed for pip operations

        # Install Django first
        print("\n📦 Installing Django...")
        run_command([python_path, "-m", "pip", "install", "django>=4.2,<6.0"])

        # Install our package
        print(f"\n📦 Installing django-container-manager from {wheel_file}...")
        run_command([python_path, "-m", "pip", "install", str(wheel_file)])

        # Create minimal Django project
        print("\n🏗️ Creating Django project...")
        run_command([python_path, "-m", "django", "startproject", "testproject", "."])

        # Create test settings
        settings_content = """
# Test settings for django-container-manager
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'test-key-not-for-production-use-only'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'container_manager',  # Our package
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'testproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = '/static/'

# Container manager settings (optional)
CONTAINER_MANAGER = {
    "AUTO_PULL_IMAGES": True,
    "MAX_CONCURRENT_JOBS": 5,
    "POLL_INTERVAL": 10,
}

USE_EXECUTOR_FACTORY = False
"""

        with open("testproject/settings.py", "w") as f:
            f.write(settings_content)

        print("\n🗄️ Testing Django setup...")

        # Test Django check
        print("  ✓ Running Django system checks...")
        run_command([python_path, "manage.py", "check"])

        # Test migrations
        print("  ✓ Running migrations...")
        run_command([python_path, "manage.py", "migrate"])

        # Test that management commands are available
        print("  ✓ Testing management commands...")
        result = run_command([python_path, "manage.py", "help"], check=False)

        required_commands = ["process_container_jobs", "manage_container_job"]
        for cmd in required_commands:
            if cmd not in result.stdout:
                raise AssertionError(
                    f"Management command '{cmd}' not found in help output"
                )

        # Test that models can be imported
        print("  ✓ Testing model imports...")
        test_import_script = """
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings")
django.setup()

from container_manager.models import DockerHost, ContainerTemplate, ContainerJob
from container_manager.defaults import get_container_manager_setting

print("✓ Successfully imported models")
print(f"✓ Default AUTO_PULL_IMAGES: {get_container_manager_setting('AUTO_PULL_IMAGES')}")
print(f"✓ Custom MAX_CONCURRENT_JOBS: {get_container_manager_setting('MAX_CONCURRENT_JOBS')}")
"""

        with open("test_imports.py", "w") as f:
            f.write(test_import_script)

        run_command([python_path, "test_imports.py"])

        # Test admin integration
        print("  ✓ Testing admin integration...")
        admin_test_script = """
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings")
django.setup()

from django.contrib import admin
from container_manager.models import DockerHost, ContainerTemplate, ContainerJob

# Check that models are registered in admin
registered_models = [model for model in admin.site._registry.keys()]
required_models = [DockerHost, ContainerTemplate, ContainerJob]

for model in required_models:
    if model not in registered_models:
        raise AssertionError(f"Model {model.__name__} not registered in admin")

print("✓ All models registered in admin")
"""

        with open("test_admin.py", "w") as f:
            f.write(admin_test_script)

        run_command([python_path, "test_admin.py"])

        # Test that settings defaults work
        print("  ✓ Testing settings defaults...")
        settings_test_script = """
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings")
django.setup()

from container_manager.defaults import get_container_manager_setting, get_use_executor_factory

# Test that our custom settings work
max_jobs = get_container_manager_setting("MAX_CONCURRENT_JOBS")
assert max_jobs == 5, f"Expected 5, got {max_jobs}"

# Test that defaults work for unset values
default_memory = get_container_manager_setting("DEFAULT_MEMORY_LIMIT")
assert default_memory == 512, f"Expected 512, got {default_memory}"

# Test executor factory setting
use_factory = get_use_executor_factory()
assert use_factory == False, f"Expected False, got {use_factory}"

print("✓ Settings and defaults working correctly")
"""

        with open("test_settings.py", "w") as f:
            f.write(settings_test_script)

        run_command([python_path, "test_settings.py"])

        print("\n🎉 All tests passed! Package installation successful!")
        print("\n📋 Test Summary:")
        print("  ✅ Package installs correctly with uv")
        print("  ✅ Django integration works")
        print("  ✅ Migrations run successfully")
        print("  ✅ Management commands available")
        print("  ✅ Models can be imported and used")
        print("  ✅ Admin integration functional")
        print("  ✅ Settings and defaults work correctly")
        print("  ✅ All dependencies resolved")


if __name__ == "__main__":
    try:
        test_package_installation()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
