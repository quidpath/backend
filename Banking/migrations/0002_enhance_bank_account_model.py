# Generated migration for enhanced BankAccount model

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('Banking', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankaccount',
            name='account_type',
            field=models.CharField(
                choices=[
                    ('bank', 'Bank Account'),
                    ('sacco', 'SACCO Account'),
                    ('mobile_money', 'Mobile Money'),
                    ('till', 'Till Number'),
                    ('cash', 'Cash Account'),
                    ('investment', 'Investment Account'),
                    ('other', 'Other'),
                ],
                default='bank',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='provider_name',
            field=models.CharField(
                blank=True,
                help_text='Provider name for mobile money, SACCO, etc.',
                max_length=255,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='branch_code',
            field=models.CharField(
                blank=True,
                help_text='Branch code or location identifier',
                max_length=50,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='swift_code',
            field=models.CharField(
                blank=True,
                help_text='SWIFT/BIC code for international transfers',
                max_length=20,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='opening_balance',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Opening balance when account was added to system',
                max_digits=15
            ),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='opening_balance_date',
            field=models.DateField(
                default=django.utils.timezone.now,
                help_text='Date of opening balance'
            ),
        ),
        migrations.AlterUniqueTogether(
            name='bankaccount',
            unique_together={('corporate', 'account_number', 'bank_name')},
        ),
        migrations.AddIndex(
            model_name='bankaccount',
            index=models.Index(fields=['corporate', 'is_active'], name='banking_bankaccount_corp_active_idx'),
        ),
        migrations.AddIndex(
            model_name='bankaccount',
            index=models.Index(fields=['account_type', 'is_active'], name='banking_bankaccount_type_active_idx'),
        ),
    ]