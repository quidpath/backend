# Generated migration for adding is_read and corporate fields to Notification model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Authentication', '0006_forgotpassword'),
        ('OrgAuth', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='is_read',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notification',
            name='corporate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notifications',
                to='OrgAuth.corporate'
            ),
        ),
    ]
