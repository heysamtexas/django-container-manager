from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from container_manager.models import (
    ContainerJob,
    EnvironmentVariableTemplate,
    ExecutorHost,
)


class Command(BaseCommand):
    help = """
    Create sample data for testing and demonstrating the container management system.

    This command creates a complete set of sample data including:
    - Docker/Executor host configurations
    - Environment variable templates
    - Sample container jobs with different configurations
    - Realistic test scenarios for development and demonstration

    Usage Examples:
        # Create complete sample data set
        python manage.py create_sample_data

        # Use existing Docker host instead of creating new one
        python manage.py create_sample_data --skip-host --host-name production

        # Create with custom host name
        python manage.py create_sample_data --host-name development-docker

    Sample Data Created:
        - ExecutorHost: Local Docker daemon configuration
        - Environment Templates: Python, Alpine, Ubuntu configurations
        - Sample Jobs: Echo test, Python script, Bash commands
        - Realistic resource limits and timeout settings

    Sample Job Types:
        1. Alpine Echo Test: Simple container validation
        2. Python Script Runner: Environment variable demonstration
        3. Ubuntu Bash Test: Multi-step command execution

    After Creation:
        1. Visit Django admin to explore created objects
        2. Start jobs manually through admin interface
        3. Run: python manage.py process_container_jobs --single-run
        4. Monitor job execution and results

    Development Workflow:
        This command is designed for:
        - New system setup and configuration
        - Feature development and testing
        - Demonstration of system capabilities
        - Learning the system's data model

    SAFE TO RUN MULTIPLE TIMES: Uses get_or_create to avoid duplicates.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-host",
            action="store_true",
            help=(
                "Skip creating Docker host (use existing). "
                "Requires existing host with name specified in --host-name. "
                "Useful when working with pre-configured environments."
            ),
        )
        parser.add_argument(
            "--host-name",
            type=str,
            default="local-docker",
            help=(
                "Name for Docker host (default: local-docker). "
                "Used for both creating new hosts and finding existing ones. "
                "Should match your ExecutorHost configuration."
            ),
        )

    def handle(self, *args, **options):
        self.stdout.write("Creating sample data...")

        # Create or get Docker host
        docker_host = self._get_or_create_docker_host(options)
        if not docker_host:
            return

        # Create templates
        admin_user = self._get_admin_user()
        self._create_sample_templates(admin_user)

        # Create sample jobs
        self._create_sample_jobs(docker_host, admin_user)

        # Show completion message
        self._show_completion_message()

    def _get_or_create_docker_host(self, options):
        """Get or create Docker host based on options"""
        if not options["skip_host"]:
            docker_host, created = ExecutorHost.objects.get_or_create(
                name=options["host_name"],
                defaults={
                    "host_type": "unix",
                    "connection_string": "unix:///var/run/docker.sock",
                    "is_active": True,
                    "auto_pull_images": True,
                },
            )
            status = "Created" if created else "Using existing"
            self.stdout.write(f"✓ {status} Docker host: {docker_host.name}")
            return docker_host
        else:
            try:
                docker_host = ExecutorHost.objects.get(name=options["host_name"])
                self.stdout.write(f"✓ Using existing Docker host: {docker_host.name}")
                return docker_host
            except ExecutorHost.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'Docker host "{options["host_name"]}" not found. '
                        "Remove --skip-host or create it first."
                    )
                )
                return None

    def _get_admin_user(self):
        """Get admin user for created_by field"""
        try:
            return User.objects.filter(is_superuser=True).first()
        except User.DoesNotExist:
            return None

    def _get_sample_templates_data(self):
        """Get sample template data definitions"""
        return [
            {
                "name": "alpine-echo-test",
                "description": "Simple Alpine Linux echo test",
                "docker_image": "alpine:latest",
                "command": 'echo "Hello from Alpine Linux! Container is working correctly."',
                "timeout_seconds": 60,
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
                "env_vars": [
                    {"key": "TEST_ENV", "value": "production", "is_secret": False},
                ],
            },
        ]

    def _create_sample_templates(self, admin_user):
        """Create sample environment variable templates"""
        templates_data = self._get_sample_templates_data()

        for template_data in templates_data:
            env_vars = template_data.get("env_vars", [])

            # Only create environment variable template if there are env vars
            if env_vars:
                env_template_name = f"{template_data['name']}-env"

                # Convert env_vars list to text format
                env_text_lines = []
                for env_var in env_vars:
                    env_text_lines.append(f"{env_var['key']}={env_var['value']}")
                env_text = "\n".join(env_text_lines)

                env_template, created = (
                    EnvironmentVariableTemplate.objects.get_or_create(
                        name=env_template_name,
                        defaults={
                            "description": f"Environment variables for {template_data['name']}",
                            "environment_variables_text": env_text,
                            "created_by": admin_user,
                        },
                    )
                )

                if created:
                    self.stdout.write(
                        f"✓ Created environment template: {env_template.name}"
                    )
                    for env_var in env_vars:
                        self.stdout.write(f"  - Added env var: {env_var['key']}")
                else:
                    self.stdout.write(
                        f"✓ Environment template already exists: {env_template.name}"
                    )

    def _create_sample_jobs(self, docker_host, admin_user):
        """Create sample jobs for demonstration"""
        templates_data = self._get_sample_templates_data()

        for template_data in templates_data:
            # Get environment template if it exists
            env_template = None
            if template_data.get("env_vars"):
                env_template_name = f"{template_data['name']}-env"
                try:
                    env_template = EnvironmentVariableTemplate.objects.get(
                        name=env_template_name
                    )
                except EnvironmentVariableTemplate.DoesNotExist:
                    pass

            # Create job with direct field specification
            job_name = f"Sample {template_data['name'].replace('-', ' ').title()} Job"
            job, created = ContainerJob.objects.get_or_create(
                docker_host=docker_host,
                name=job_name,
                defaults={
                    "created_by": admin_user,
                    "description": template_data["description"],
                    "docker_image": template_data["docker_image"],
                    "command": template_data["command"],
                    "timeout_seconds": template_data["timeout_seconds"],
                    "memory_limit": template_data.get("memory_limit"),
                    "cpu_limit": template_data.get("cpu_limit"),
                    "environment_template": env_template,
                },
            )

            status = "Created" if created else "already exists"
            self.stdout.write(f"✓ Sample job {status}: {job.name} (ID: {job.id})")
            if env_template:
                self.stdout.write(
                    f"  - Linked to environment template: {env_template.name}"
                )

    def _show_completion_message(self):
        """Show completion message and next steps"""
        self.stdout.write(self.style.SUCCESS("\nSample data created successfully!"))
        self.stdout.write("\nYou can now:")
        self.stdout.write("1. Visit the Django admin to see the templates and jobs")
        self.stdout.write("2. Start the sample job using the admin interface")
        self.stdout.write("3. Run: uv run python manage.py process_container_jobs")
        self.stdout.write(
            "4. Test with: uv run python manage.py process_container_jobs --once"
        )
