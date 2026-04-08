"""
Document Template Model
Stores customizable document templates for each corporate
"""
from django.db import models
from OrgAuth.models import Corporate
from quidpath_backend.core.base_models.base import BaseModel


class DocumentTemplate(BaseModel):
    """
    Stores document template settings for invoices, quotes, POs, and bills
    """
    DOCUMENT_TYPES = [
        ('quotation', 'Quotation'),
        ('invoice', 'Invoice'),
        ('purchase_order', 'Purchase Order'),
        ('vendor_bill', 'Vendor Bill'),
    ]
    
    LOGO_ALIGN_CHOICES = [
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right'),
    ]
    
    BORDER_STYLE_CHOICES = [
        ('none', 'None'),
        ('thin', 'Thin'),
        ('thick', 'Thick'),
    ]
    
    corporate = models.ForeignKey(
        Corporate,
        on_delete=models.CASCADE,
        related_name='document_templates'
    )
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPES,
        db_index=True
    )
    
    # Branding
    accent_color = models.CharField(max_length=7, default='#1565C0')  # Hex color
    font = models.CharField(max_length=50, default='Inter')
    logo_align = models.CharField(max_length=10, choices=LOGO_ALIGN_CHOICES, default='left')
    show_logo = models.BooleanField(default=True)
    show_tagline = models.BooleanField(default=False)
    tagline = models.CharField(max_length=255, blank=True, default='')
    
    # Layout
    border_style = models.CharField(max_length=10, choices=BORDER_STYLE_CHOICES, default='thin')
    header_bg = models.BooleanField(default=True)
    
    # Footer
    footer_text = models.TextField(default='Thank you for your business.')
    show_bank_details = models.BooleanField(default=True)
    show_signature_line = models.BooleanField(default=True)
    show_stamp = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'document_template'
        unique_together = [['corporate', 'document_type']]
        indexes = [
            models.Index(fields=['corporate', 'document_type']),
        ]
    
    def __str__(self):
        return f"{self.corporate.name} - {self.get_document_type_display()}"
