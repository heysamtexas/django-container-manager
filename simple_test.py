#!/usr/bin/env python3
"""
Simple test to validate django-container-manager package functionality
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return False
    print(f"SUCCESS: {result.stdout}")
    return True

def test_package_locally():
    """Test the package in the current environment"""

    print("🧪 Testing django-container-manager package locally...")

    # Get the path to our built package
    project_dir = Path(__file__).parent
    wheel_file = next(project_dir.glob("dist/*.whl"))

    print(f"📦 Installing package from {wheel_file}...")
    if not run_command([sys.executable, "-m", "pip", "install", str(wheel_file), "--force-reinstall"]):
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Working in temporary directory: {temp_dir}")
        os.chdir(temp_dir)

        # Create minimal Django project
        print("\n🏗️ Creating Django project...")
        if not run_command([sys.executable, "-m", "django", "startproject", "testproject", "."]):
            return False

        # Create test settings
        settings_content = '''
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'test-key-not-for-production'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'container_manager',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

CONTAINER_MANAGER = {
    "AUTO_PULL_IMAGES": True,
    "MAX_CONCURRENT_JOBS": 5,
}
'''

        with open('testproject/settings.py', 'w') as f:
            f.write(settings_content)

        print("\n🗄️ Testing Django functionality...")

        # Test Django check
        print("  ✓ Running Django check...")
        if not run_command([sys.executable, "manage.py", "check"]):
            return False

        # Test migrations
        print("  ✓ Running migrations...")
        if not run_command([sys.executable, "manage.py", "migrate"]):
            return False

        # Test management commands
        print("  ✓ Testing management commands...")
        result = subprocess.run([sys.executable, "manage.py", "help"],
                              capture_output=True, text=True)

        if "process_container_jobs" not in result.stdout:
            print("ERROR: process_container_jobs command not found")
            return False

        if "manage_container_job" not in result.stdout:
            print("ERROR: manage_container_job command not found")
            return False

        # Test imports
        print("  ✓ Testing imports...")
        test_script = '''
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings")
django.setup()

from container_manager.models import DockerHost, ContainerTemplate, ContainerJob
from container_manager.defaults import get_container_manager_setting
print("Models imported successfully")
print(f"MAX_CONCURRENT_JOBS setting: {get_container_manager_setting('MAX_CONCURRENT_JOBS')}")
'''

        with open('test_imports.py', 'w') as f:
            f.write(test_script)

        if not run_command([sys.executable, "test_imports.py"]):
            return False

        print("\n🎉 All tests passed!")
        return True

if __name__ == "__main__":
    if test_package_locally():
        print("✅ Package validation successful!")
    else:
        print("❌ Package validation failed!")
        sys.exit(1)
