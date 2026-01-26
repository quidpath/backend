# Generated migration for payment gateway fields
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('Payments', '0006_auto_20250912_1310'),
        ('Accounting', '0010_add_payment_fields_and_new_models'),
    ]

    operations = [
        # Add payment gateway fields to RecordPayment
        migrations.AddField(
            model_name='recordpayment',
            name='invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='Accounting.invoices'),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='currency',
            field=models.CharField(default='USD', max_length=3),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='exchange_rate_to_usd',
            field=models.DecimalField(decimal_places=6, default=Decimal('1.0'), max_digits=12),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='payment_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('success', 'Success'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='provider_reference',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='provider_metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='receipt_pdf_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='recordpayment',
            name='is_reconciled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name='recordpayment',
            index=models.Index(fields=['provider_reference'], name='Payments_provider_ref_idx'),
        ),
        migrations.AddIndex(
            model_name='recordpayment',
            index=models.Index(fields=['payment_status'], name='Payments_payment_status_idx'),
        ),
        migrations.AddIndex(
            model_name='recordpayment',
            index=models.Index(fields=['corporate', 'payment_date'], name='Payments_corp_date_idx'),
        ),
        
        # Add payment gateway fields to VendorPayment
        migrations.AddField(
            model_name='vendorpayment',
            name='bill',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='Accounting.vendorbill'),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='currency',
            field=models.CharField(default='USD', max_length=3),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='exchange_rate_to_usd',
            field=models.DecimalField(decimal_places=6, default=Decimal('1.0'), max_digits=12),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='payment_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('success', 'Success'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='provider_reference',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='provider_metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='receipt_pdf_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendorpayment',
            name='is_reconciled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name='vendorpayment',
            index=models.Index(fields=['provider_reference'], name='Payments_vendor_provider_ref_idx'),
        ),
        migrations.AddIndex(
            model_name='vendorpayment',
            index=models.Index(fields=['payment_status'], name='Payments_vendor_payment_status_idx'),
        ),
        migrations.AddIndex(
            model_name='vendorpayment',
            index=models.Index(fields=['corporate', 'payment_date'], name='Payments_vendor_corp_date_idx'),
        ),
        
        # Create PaymentProvider model
        migrations.CreateModel(
            name='PaymentProvider',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('provider_type', models.CharField(choices=[('mpesa', 'M-Pesa Daraja'), ('flutterwave', 'Flutterwave'), ('interswitch', 'Interswitch'), ('pesapal', 'Pesapal'), ('other', 'Other')], max_length=50)),
                ('name', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('config_json', models.JSONField(default=dict)),
                ('webhook_secret', models.CharField(blank=True, max_length=255, null=True)),
                ('test_mode', models.BooleanField(default=False)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_providers', to='OrgAuth.corporate')),
            ],
            options={
                'verbose_name': 'Payment Provider',
                'verbose_name_plural': 'Payment Providers',
            },
        ),
        migrations.AlterUniqueTogether(
            name='paymentprovider',
            unique_together={('corporate', 'provider_type', 'name')},
        ),
    ]








