# Generated migration for adding description field to Role model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Authentication', '0013_rename_accounting_to_finance'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='description',
            field=models.TextField(blank=True, null=True, help_text='Role description'),
        ),
    ]
