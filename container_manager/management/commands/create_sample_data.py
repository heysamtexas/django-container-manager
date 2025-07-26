from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from container_manager.models import (
    ContainerJob,
    ContainerTemplate,
    DockerHost,
    EnvironmentVariable,
)


class Command(BaseCommand):
    help = "Create sample data for testing the container management system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-host",
            action="store_true",
            help="Skip creating Docker host (use existing)",
        )
        parser.add_argument(
            "--host-name",
            type=str,
            default="local-docker",
            help="Name for Docker host (default: local-docker)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Creating sample data...")

        # Create Docker host if not skipping
        if not options["skip_host"]:
            docker_host, created = DockerHost.objects.get_or_create(
                name=options["host_name"],
                defaults={
                    "host_type": "unix",
                    "connection_string": "unix:///var/run/docker.sock",
                    "is_active": True,
                    "auto_pull_images": True,
                },
            )
            if created:
                self.stdout.write(f"✓ Created Docker host: {docker_host.name}")
            else:
                self.stdout.write(f"✓ Using existing Docker host: {docker_host.name}")
        else:
            try:
                docker_host = DockerHost.objects.get(name=options["host_name"])
                self.stdout.write(f"✓ Using existing Docker host: {docker_host.name}")
            except DockerHost.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'Docker host "{options["host_name"]}" not found. '
                        "Remove --skip-host or create it first."
                    )
                )
                return

        # Create sample container templates
        templates_data = [
            {
                "name": "alpine-echo-test",
                "description": "Simple Alpine Linux echo test",
                "docker_image": "alpine:latest",
                "command": (
                    'echo "Hello from Alpine Linux! Container is working correctly."'
                ),
                "timeout_seconds": 60,
                "auto_remove": False,
                "env_vars": [],
            },
            {
                "name": "python-script-runner",
                "description": "Python container for running scripts",
                "docker_image": "python:3.11-slim",
                "command": (
                    'python -c "import os; '
                    "print(f'Hello from Python! "
                    'ENV_VAR={os.getenv("TEST_VAR", "not set")}\'); '
                    'import time; time.sleep(5)"'
                ),
                "timeout_seconds": 300,
                "memory_limit": 128,
                "cpu_limit": 0.5,
                "auto_remove": False,
                "env_vars": [
                    {"key": "TEST_VAR", "value": "Hello World", "is_secret": False},
                    {"key": "PYTHONUNBUFFERED", "value": "1", "is_secret": False},
                ],
            },
            {
                "name": "ubuntu-bash-test",
                "description": "Ubuntu container for bash commands",
                "docker_image": "ubuntu:22.04",
                "command": (
                    'bash -c "echo \\"Starting test...\\"; '
                    'sleep 3; echo \\"Environment: $TEST_ENV\\"; '
                    'ls -la /tmp; echo \\"Test completed\\""'
                ),
                "timeout_seconds": 120,
                "memory_limit": 64,
                "auto_remove": False,
                "env_vars": [
                    {"key": "TEST_ENV", "value": "production", "is_secret": False},
                ],
            },
        ]

        # Get admin user for created_by field
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
        except User.DoesNotExist:
            admin_user = None

        for template_data in templates_data:
            env_vars = template_data.pop("env_vars", [])

            template, created = ContainerTemplate.objects.get_or_create(
                name=template_data["name"],
                defaults={
                    **template_data,
                    "created_by": admin_user,
                },
            )

            if created:
                self.stdout.write(f"✓ Created template: {template.name}")

                # Add environment variables
                for env_var in env_vars:
                    EnvironmentVariable.objects.create(template=template, **env_var)
                    self.stdout.write(f"  - Added env var: {env_var['key']}")
            else:
                self.stdout.write(f"✓ Template already exists: {template.name}")

        # Create a sample job for the alpine template
        alpine_template = ContainerTemplate.objects.get(name="alpine-echo-test")
        job, created = ContainerJob.objects.get_or_create(
            template=alpine_template,
            docker_host=docker_host,
            name="Sample Alpine Echo Job",
            defaults={
                "created_by": admin_user,
            },
        )

        if created:
            self.stdout.write(f"✓ Created sample job: {job.name} (ID: {job.id})")
        else:
            self.stdout.write(f"✓ Sample job already exists: {job.name} (ID: {job.id})")

        self.stdout.write(self.style.SUCCESS("\nSample data created successfully!"))
        self.stdout.write("\nYou can now:")
        self.stdout.write("1. Visit the Django admin to see the templates and jobs")
        self.stdout.write("2. Start the sample job using the admin interface")
        self.stdout.write("3. Run: uv run python manage.py process_container_jobs")
        self.stdout.write(
            "4. Test with: uv run python manage.py manage_container_job list"
        )
