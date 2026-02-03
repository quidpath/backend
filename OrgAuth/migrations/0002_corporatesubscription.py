# Generated migration for CorporateSubscription model

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('OrgAuth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateSubscription',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('corporate_id', models.UUIDField(db_index=True)),
                ('plan_id', models.UUIDField()),
                ('plan_name', models.CharField(max_length=100)),
                ('plan_slug', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('trial', 'Trial'), ('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled'), ('suspended', 'Suspended')], default='trial', max_length=20)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('trial_end_date', models.DateTimeField(blank=True, null=True)),
                ('features', models.JSONField(default=dict)),
                ('billing_subscription_id', models.UUIDField(unique=True)),
                ('last_synced_at', models.DateTimeField(auto_now=True)),
                ('sync_source', models.CharField(default='webhook', max_length=20)),
                ('auto_renew', models.BooleanField(default=True)),
                ('grace_period_days', models.IntegerField(default=7)),
            ],
            options={
                'db_table': 'corporate_subscriptions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='corporatesubscription',
            index=models.Index(fields=['corporate_id', 'status'], name='corporate_s_corpora_idx'),
        ),
        migrations.AddIndex(
            model_name='corporatesubscription',
            index=models.Index(fields=['billing_subscription_id'], name='corporate_s_billing_idx'),
        ),
        migrations.AddIndex(
            model_name='corporatesubscription',
            index=models.Index(fields=['end_date'], name='corporate_s_end_dat_idx'),
        ),
    ]
