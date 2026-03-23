"""
Remove billing-specific models from the main backend.
All subscription, invoice, and payment data for billing purposes
now lives exclusively in the billing microservice.

The ERP payment models (RecordPayment, VendorPayment, PaymentProvider)
are kept — they track customer/vendor payments within the accounting module.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Payments', '0009_auto_20260224_1532'),
    ]

    operations = [
        # Drop individual billing tables
        migrations.DeleteModel(name='IndividualPayment'),
        migrations.DeleteModel(name='IndividualSubscription'),
        migrations.DeleteModel(name='IndividualSubscriptionPlan'),
        # Drop organization billing tables
        migrations.DeleteModel(name='OrganizationPayment'),
        migrations.DeleteModel(name='OrganizationInvoice'),
        migrations.DeleteModel(name='OrganizationSubscription'),
    ]
