# Organization billing and subscription models
from django.db import models
from decimal import Decimal
from datetime import datetime, timedelta

from OrgAuth.models import Corporate
from quidpath_backend.core.base_models.base import BaseModel


class OrganizationSubscription(BaseModel):
    """
    Organization subscription plans and billing.
    """
    PLAN_TYPES = [
        ("basic", "Basic"),
        ("standard", "Standard"),
        ("premium", "Premium"),
        ("enterprise", "Enterprise"),
    ]
    
    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("pending", "Pending"),
    ]
    
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="subscriptions")
    plan_type = models.CharField(max_length=50, choices=PLAN_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    # Pricing
    monthly_price_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate_to_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('1.00'))
    
    # Billing period
    start_date = models.DateField()
    end_date = models.DateField()
    billing_cycle = models.CharField(max_length=20, default="monthly")  # monthly, quarterly, annually
    
    # User limits
    max_users = models.IntegerField(default=1)
    current_users = models.IntegerField(default=0)
    
    # Features
    features = models.JSONField(default=dict, blank=True)  # Feature flags
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Organization Subscription"
        verbose_name_plural = "Organization Subscriptions"
        indexes = [
            models.Index(fields=['corporate', 'status']),
            models.Index(fields=['status', 'end_date']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.corporate.name} - {self.get_plan_type_display()} ({self.status})"


class OrganizationInvoice(BaseModel):
    """
    Organization billing invoices.
    """
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]
    
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="billing_invoices")
    subscription = models.ForeignKey(OrganizationSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    
    invoice_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    # Amounts
    subtotal_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate_to_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('1.00'))
    
    # Billing period
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Payment reference
    payment_reference = models.CharField(max_length=255, blank=True, null=True)
    payment_provider = models.CharField(max_length=50, blank=True, null=True)  # flutterwave, etc.
    
    # PDF
    invoice_pdf_url = models.URLField(blank=True, null=True)
    
    # Metadata
    line_items = models.JSONField(default=list, blank=True)  # Invoice line items
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Organization Invoice"
        verbose_name_plural = "Organization Invoices"
        indexes = [
            models.Index(fields=['corporate', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['due_date', 'status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.corporate.name} ({self.status})"


class OrganizationPayment(BaseModel):
    """
    Organization payments for subscriptions/invoices.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    
    PAYMENT_METHODS = [
        ("mpesa", "M-Pesa"),
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("mobile_money", "Mobile Money"),
    ]
    
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="billing_payments")
    invoice = models.ForeignKey(OrganizationInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate_to_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('1.00'))
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    # Payment provider references
    provider = models.CharField(max_length=50, default="flutterwave")
    provider_reference = models.CharField(max_length=255, blank=True, null=True)
    provider_metadata = models.JSONField(default=dict, blank=True)
    
    # Payment details
    paid_at = models.DateTimeField(null=True, blank=True)
    receipt_pdf_url = models.URLField(blank=True, null=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Organization Payment"
        verbose_name_plural = "Organization Payments"
        indexes = [
            models.Index(fields=['corporate', 'status']),
            models.Index(fields=['invoice', 'status']),
            models.Index(fields=['provider_reference']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.corporate.name} - {self.amount} {self.currency} ({self.status})"

