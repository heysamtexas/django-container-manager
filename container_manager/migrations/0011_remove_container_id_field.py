# Generated manually to remove legacy execution identifier fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('container_manager', '0010_remove_fallback_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='containerjob',
            name='container_id',
        ),
        migrations.RemoveField(
            model_name='containerjob',
            name='external_execution_id',
        ),
    ]