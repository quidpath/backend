# Generated migration for DocumentTemplate model

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('OrgAuth', '0009_merge_20260209_1215'),  # Update to the actual latest migration
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document_type', models.CharField(
                    choices=[
                        ('quotation', 'Quotation'),
                        ('invoice', 'Invoice'),
                        ('purchase_order', 'Purchase Order'),
                        ('vendor_bill', 'Vendor Bill')
                    ],
                    db_index=True,
                    max_length=50
                )),
                ('accent_color', models.CharField(default='#1565C0', max_length=7)),
                ('font', models.CharField(default='Inter', max_length=50)),
                ('logo_align', models.CharField(
                    choices=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')],
                    default='left',
                    max_length=10
                )),
                ('show_logo', models.BooleanField(default=True)),
                ('show_tagline', models.BooleanField(default=False)),
                ('tagline', models.CharField(blank=True, default='', max_length=255)),
                ('border_style', models.CharField(
                    choices=[('none', 'None'), ('thin', 'Thin'), ('thick', 'Thick')],
                    default='thin',
                    max_length=10
                )),
                ('header_bg', models.BooleanField(default=True)),
                ('footer_text', models.TextField(default='Thank you for your business.')),
                ('show_bank_details', models.BooleanField(default=True)),
                ('show_signature_line', models.BooleanField(default=True)),
                ('show_stamp', models.BooleanField(default=False)),
                ('corporate', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='document_templates',
                    to='OrgAuth.corporate'
                )),
            ],
            options={
                'db_table': 'document_template',
                'indexes': [
                    models.Index(fields=['corporate', 'document_type'], name='document_te_corpora_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='documenttemplate',
            constraint=models.UniqueConstraint(
                fields=('corporate', 'document_type'),
                name='unique_corporate_document_type'
            ),
        ),
    ]
