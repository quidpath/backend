# Generated migration for Petty Cash and Bank Reconciliation models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting', '0012_invoices_drafted_at_invoices_posted_at_and_more'),
        ('OrgAuth', '0001_initial'),
        ('Banking', '0001_initial'),
    ]

    operations = [
        # Petty Cash Fund
        migrations.CreateModel(
            name='PettyCashFund',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, default='')),
                ('initial_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('current_balance', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('is_active', models.BooleanField(default=True)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='petty_cash_funds', to='OrgAuth.corporate')),
                ('custodian', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='managed_petty_cash_funds', to='OrgAuth.corporateuser')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_petty_cash_funds', to='OrgAuth.corporateuser')),
            ],
            options={
                'db_table': 'petty_cash_fund',
                'unique_together': {('corporate', 'name')},
            },
        ),
        # Petty Cash Transaction
        migrations.CreateModel(
            name='PettyCashTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('transaction_type', models.CharField(choices=[('DISBURSEMENT', 'Disbursement'), ('REPLENISHMENT', 'Replenishment'), ('ADJUSTMENT', 'Adjustment')], max_length=20)),
                ('date', models.DateField()),
                ('reference', models.CharField(max_length=50)),
                ('description', models.TextField()),
                ('category', models.CharField(blank=True, default='', max_length=100)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('recipient', models.CharField(blank=True, default='', max_length=200)),
                ('receipt_number', models.CharField(blank=True, default='', max_length=50)),
                ('status', models.CharField(choices=[('PENDING', 'Pending Approval'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('COMPLETED', 'Completed')], default='PENDING', max_length=20)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('fund', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='Accounting.pettycashfund')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='petty_cash_requests', to='OrgAuth.corporateuser')),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='approved_petty_cash', to='OrgAuth.corporateuser')),
                ('journal_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='Accounting.journalentry')),
            ],
            options={
                'db_table': 'petty_cash_transaction',
                'unique_together': {('fund', 'reference')},
            },
        ),
        # Bank Reconciliation
        migrations.CreateModel(
            name='BankReconciliation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('opening_balance', models.DecimalField(decimal_places=2, max_digits=15)),
                ('closing_balance', models.DecimalField(decimal_places=2, max_digits=15)),
                ('statement_balance', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('book_balance', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('total_deposits_in_transit', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('total_outstanding_checks', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('total_bank_charges', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('total_adjustments', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('difference', models.DecimalField(decimal_places=2, default=0.00, max_digits=15)),
                ('status', models.CharField(choices=[('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('REVIEWED', 'Reviewed')], default='IN_PROGRESS', max_length=20)),
                ('notes', models.TextField(blank=True, default='')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_reconciliations', to='OrgAuth.corporate')),
                ('bank_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounting_reconciliations', to='Banking.bankaccount')),
                ('reconciled_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reconciliations_performed', to='OrgAuth.corporateuser')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reconciliations_reviewed', to='OrgAuth.corporateuser')),
            ],
            options={
                'db_table': 'bank_reconciliation',
                'ordering': ['-period_end'],
                'unique_together': {('bank_account', 'period_start', 'period_end')},
            },
        ),
        # Reconciliation Item
        migrations.CreateModel(
            name='ReconciliationItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('item_type', models.CharField(choices=[('DEPOSIT_IN_TRANSIT', 'Deposit in Transit'), ('OUTSTANDING_CHECK', 'Outstanding Check'), ('BANK_CHARGE', 'Bank Charge'), ('BANK_ERROR', 'Bank Error'), ('BOOK_ERROR', 'Book Error'), ('ADJUSTMENT', 'Adjustment')], max_length=30)),
                ('date', models.DateField()),
                ('reference', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('is_cleared', models.BooleanField(default=False)),
                ('cleared_date', models.DateField(blank=True, null=True)),
                ('reconciliation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='Accounting.bankreconciliation')),
                ('transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reconciliation_items', to='Banking.banktransaction')),
            ],
            options={
                'db_table': 'reconciliation_item',
                'ordering': ['date'],
            },
        ),
    ]
