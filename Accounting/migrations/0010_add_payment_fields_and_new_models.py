# Generated migration for payment fields and new models
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('Accounting', '0009_alter_account_account_type'),
        ('OrgAuth', '0001_initial'),  # Adjust based on your actual migration
        ('Authentication', '0001_initial'),  # Adjust based on your actual migration
    ]

    operations = [
        # Add payment fields to Invoices model
        migrations.AddField(
            model_name='invoices',
            name='payment_status',
            field=models.CharField(choices=[('unpaid', 'Unpaid'), ('partial', 'Partially Paid'), ('paid', 'Paid'), ('overpaid', 'Overpaid')], default='unpaid', max_length=20),
        ),
        migrations.AddField(
            model_name='invoices',
            name='payment_reference',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoices',
            name='currency',
            field=models.CharField(default='USD', max_length=3),
        ),
        migrations.AddField(
            model_name='invoices',
            name='exchange_rate_to_usd',
            field=models.DecimalField(decimal_places=6, default=Decimal('1.0'), max_digits=12),
        ),
        migrations.AddField(
            model_name='invoices',
            name='issued_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoices',
            name='paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoices',
            name='receipt_pdf_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoices',
            name='is_reconciled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name='invoices',
            index=models.Index(fields=['payment_status'], name='Accounting_payment_idx'),
        ),
        migrations.AddIndex(
            model_name='invoices',
            index=models.Index(fields=['corporate', 'date'], name='Accounting_corp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='invoices',
            index=models.Index(fields=['payment_reference'], name='Accounting_pay_ref_idx'),
        ),
        
        # Create DocumentAttachment model
        migrations.CreateModel(
            name='DocumentAttachment',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file_name', models.CharField(max_length=255)),
                ('file_url', models.URLField()),
                ('file_size', models.BigIntegerField(default=0)),
                ('mime_type', models.CharField(blank=True, max_length=100, null=True)),
                ('checksum', models.CharField(blank=True, max_length=64, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_public', models.BooleanField(default=False)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='OrgAuth.corporate')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='uploaded_attachments', to='OrgAuth.CorporateUser')),
            ],
            options={
                'verbose_name': 'Document Attachment',
                'verbose_name_plural': 'Document Attachments',
            },
        ),
        migrations.AddField(
            model_name='documentattachment',
            name='object_id',
            field=models.UUIDField(),
        ),
        migrations.AddIndex(
            model_name='documentattachment',
            index=models.Index(fields=['content_type', 'object_id'], name='Accounting_content_idx'),
        ),
        migrations.AddIndex(
            model_name='documentattachment',
            index=models.Index(fields=['corporate', 'created_at'], name='Accounting_corp_attach_idx'),
        ),
        
        # Create AuditLog model
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('action_type', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('view', 'View'), ('export', 'Export'), ('send', 'Send'), ('approve', 'Approve'), ('reject', 'Reject'), ('post', 'Post'), ('payment', 'Payment'), ('login', 'Login'), ('logout', 'Logout'), ('password_change', 'Password Change'), ('permission_change', 'Permission Change')], max_length=50)),
                ('model_name', models.CharField(max_length=100)),
                ('object_id_str', models.CharField(blank=True, max_length=255, null=True)),
                ('changes', models.JSONField(blank=True, default=dict)),
                ('description', models.TextField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype')),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='OrgAuth.corporate')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='OrgAuth.CorporateUser')),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='auditlog',
            name='object_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['corporate', 'created_at'], name='Accounting_corp_audit_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', 'created_at'], name='Accounting_user_audit_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action_type', 'created_at'], name='Accounting_action_audit_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['content_type', 'object_id'], name='Accounting_content_audit_idx'),
        ),
        
        # Create RecurringTransaction model
        migrations.CreateModel(
            name='RecurringTransaction',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('transaction_type', models.CharField(choices=[('invoice', 'Invoice'), ('bill', 'Vendor Bill'), ('expense', 'Expense'), ('payment', 'Payment')], max_length=50)),
                ('frequency', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annually', 'Annually'), ('custom', 'Custom')], max_length=20)),
                ('custom_days', models.IntegerField(blank=True, null=True)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('next_run_at', models.DateTimeField(blank=True, null=True)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('paused', 'Paused'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='active', max_length=20)),
                ('total_runs', models.IntegerField(default=0)),
                ('max_runs', models.IntegerField(blank=True, null=True)),
                ('template_payload', models.JSONField(default=dict)),
                ('auto_charge', models.BooleanField(default=False)),
                ('payment_method', models.CharField(blank=True, max_length=50, null=True)),
                ('payment_account_id', models.UUIDField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recurring_transactions', to='OrgAuth.corporate')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_recurring_transactions', to='OrgAuth.CorporateUser')),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_invoices', to='Accounting.customer')),
                ('vendor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurring_bills', to='Accounting.vendor')),
            ],
            options={
                'verbose_name': 'Recurring Transaction',
                'verbose_name_plural': 'Recurring Transactions',
            },
        ),
        migrations.AddIndex(
            model_name='recurringtransaction',
            index=models.Index(fields=['corporate', 'status'], name='Accounting_corp_recur_idx'),
        ),
        migrations.AddIndex(
            model_name='recurringtransaction',
            index=models.Index(fields=['next_run_at', 'status'], name='Accounting_next_recur_idx'),
        ),
        migrations.AddIndex(
            model_name='recurringtransaction',
            index=models.Index(fields=['transaction_type', 'status'], name='Accounting_type_recur_idx'),
        ),
        
        # Create Warehouse model
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(blank=True, max_length=50, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('state', models.CharField(blank=True, max_length=100, null=True)),
                ('country', models.CharField(blank=True, max_length=100, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='warehouses', to='OrgAuth.corporate')),
            ],
            options={
                'verbose_name': 'Warehouse',
                'verbose_name_plural': 'Warehouses',
            },
        ),
        migrations.AlterUniqueTogether(
            name='warehouse',
            unique_together={('corporate', 'code')},
        ),
        
        # Create InventoryItem model
        migrations.CreateModel(
            name='InventoryItem',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('sku', models.CharField(max_length=100, unique=True)),
                ('barcode', models.CharField(blank=True, max_length=100, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('category', models.CharField(blank=True, max_length=100, null=True)),
                ('unit_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('standard_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('average_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('selling_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('valuation_method', models.CharField(choices=[('fifo', 'FIFO (First In, First Out)'), ('average_cost', 'Average Cost'), ('standard_cost', 'Standard Cost')], default='fifo', max_length=20)),
                ('track_quantity', models.BooleanField(default=True)),
                ('quantity_on_hand', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('quantity_reserved', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('quantity_available', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('reorder_point', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('reorder_quantity', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('unit_of_measure', models.CharField(default='pcs', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('is_tracked', models.BooleanField(default=True)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_items', to='OrgAuth.corporate')),
                ('cost_of_goods_sold_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='cogs_items', to='Accounting.account')),
                ('income_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='income_items', to='Accounting.account')),
                ('inventory_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='inventory_items', to='Accounting.account')),
            ],
            options={
                'verbose_name': 'Inventory Item',
                'verbose_name_plural': 'Inventory Items',
            },
        ),
        migrations.AddIndex(
            model_name='inventoryitem',
            index=models.Index(fields=['corporate', 'sku'], name='Accounting_corp_sku_idx'),
        ),
        migrations.AddIndex(
            model_name='inventoryitem',
            index=models.Index(fields=['corporate', 'is_active'], name='Accounting_corp_active_idx'),
        ),
        
        # Create StockMovement model
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('movement_type', models.CharField(choices=[('purchase', 'Purchase'), ('sale', 'Sale'), ('adjustment', 'Adjustment'), ('transfer', 'Transfer'), ('return', 'Return'), ('damage', 'Damage'), ('loss', 'Loss')], max_length=20)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('posted', 'Posted'), ('cancelled', 'Cancelled')], default='draft', max_length=20)),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=12)),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, max_digits=12)),
                ('invoice_id', models.UUIDField(blank=True, null=True)),
                ('bill_id', models.UUIDField(blank=True, null=True)),
                ('purchase_order_id', models.UUIDField(blank=True, null=True)),
                ('reference_number', models.CharField(blank=True, max_length=255, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('movement_date', models.DateField()),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='OrgAuth.corporate')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_stock_movements', to='OrgAuth.CorporateUser')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='Accounting.inventoryitem')),
                ('journal_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='Accounting.journalentry')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='Accounting.warehouse')),
            ],
            options={
                'verbose_name': 'Stock Movement',
                'verbose_name_plural': 'Stock Movements',
            },
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['corporate', 'movement_date'], name='Accounting_corp_mov_date_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['item', 'movement_date'], name='Accounting_item_mov_date_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['warehouse', 'movement_date'], name='Accounting_wh_mov_date_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['status', 'movement_date'], name='Accounting_status_mov_idx'),
        ),
    ]

