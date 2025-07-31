# Generated manually to remove fallback-related fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('container_manager', '0009_remove_redundant_executor_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='executorhost',
            name='health_check_failures',
        ),
        migrations.RemoveField(
            model_name='executorhost',
            name='last_health_check',
        ),
    ]