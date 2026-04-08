# Generated migration for adding REVERSED status to PettyCashTransaction

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting', '0016_alter_invoices_fob_alter_invoices_ship_via_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pettycashtransaction',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending Approval'),
                    ('APPROVED', 'Approved'),
                    ('REJECTED', 'Rejected'),
                    ('REVERSED', 'Reversed'),
                    ('COMPLETED', 'Completed')
                ],
                default='PENDING',
                max_length=20
            ),
        ),
    ]
