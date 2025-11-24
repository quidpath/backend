# Recurring transactions model
from django.db import models
from decimal import Decimal
import json

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel
from Accounting.models.customer import Customer
from Accounting.models.vendor import Vendor


class RecurringTransaction(BaseModel):
    """
    Recurring transactions (invoices, bills, etc.) that are automatically generated.
    """
    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annually", "Annually"),
        ("custom", "Custom"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    TRANSACTION_TYPES = [
        ("invoice", "Invoice"),
        ("bill", "Vendor Bill"),
        ("expense", "Expense"),
        ("payment", "Payment"),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="recurring_transactions")
    created_by = models.ForeignKey(CorporateUser, on_delete=models.PROTECT, related_name="created_recurring_transactions")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    custom_days = models.IntegerField(null=True, blank=True)  # For custom frequency
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # None = never end
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    total_runs = models.IntegerField(default=0)
    max_runs = models.IntegerField(null=True, blank=True)  # None = unlimited
    
    # Template payload (JSON) - structure depends on transaction_type
    template_payload = models.JSONField(default=dict)
    
    # References to related entities
    customer = models.ForeignKey("Accounting.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_invoices")
    vendor = models.ForeignKey("Accounting.Vendor", on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_bills")
    
    # Auto-charge settings (for invoices)
    auto_charge = models.BooleanField(default=False)  # Automatically attempt payment
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # mpesa, card, etc.
    payment_account_id = models.UUIDField(null=True, blank=True)  # Account to charge from
    
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Recurring Transaction"
        verbose_name_plural = "Recurring Transactions"
        indexes = [
            models.Index(fields=['corporate', 'status']),
            models.Index(fields=['next_run_at', 'status']),
            models.Index(fields=['transaction_type', 'status']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_transaction_type_display()} ({self.get_frequency_display()})"








