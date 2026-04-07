"""
Bank Reconciliation Models
"""
import uuid
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class BankReconciliation(BaseModel):
    """
    Bank reconciliation records
    """
    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("REVIEWED", "Reviewed"),
    ]

    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="bank_reconciliations"
    )
    bank_account = models.ForeignKey(
        "Banking.BankAccount",
        on_delete=models.CASCADE,
        related_name="accounting_reconciliations",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Balances
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2)
    statement_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    book_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    
    # Reconciliation details
    total_deposits_in_transit = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_outstanding_checks = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_bank_charges = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    total_adjustments = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    
    difference = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="IN_PROGRESS"
    )
    notes = models.TextField(blank=True, default="")
    
    # Tracking
    reconciled_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        related_name="reconciliations_performed",
    )
    reviewed_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="reconciliations_reviewed",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "bank_reconciliation"
        unique_together = [["bank_account", "period_start", "period_end"]]
        ordering = ["-period_end"]

    def __str__(self):
        return f"Reconciliation {self.bank_account.account_name} ({self.period_start} to {self.period_end})"

    def calculate_difference(self):
        """Calculate the difference between statement and book balance"""
        adjusted_book_balance = (
            self.book_balance
            + self.total_deposits_in_transit
            - self.total_outstanding_checks
            - self.total_bank_charges
            + self.total_adjustments
        )
        self.difference = self.statement_balance - adjusted_book_balance
        return self.difference

    def is_balanced(self):
        """Check if reconciliation is balanced (difference is zero or near zero)"""
        return abs(self.calculate_difference()) < Decimal("0.01")

    def complete(self):
        """Mark reconciliation as completed"""
        if not self.is_balanced():
            raise ValidationError(
                f"Cannot complete reconciliation with difference of {self.difference}"
            )
        self.status = "COMPLETED"
        self.save()

    def review(self, reviewer):
        """Mark reconciliation as reviewed"""
        from django.utils import timezone
        
        if self.status != "COMPLETED":
            raise ValidationError("Only completed reconciliations can be reviewed")
        
        self.status = "REVIEWED"
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()


class ReconciliationItem(BaseModel):
    """
    Individual items in a bank reconciliation
    """
    ITEM_TYPES = [
        ("DEPOSIT_IN_TRANSIT", "Deposit in Transit"),
        ("OUTSTANDING_CHECK", "Outstanding Check"),
        ("BANK_CHARGE", "Bank Charge"),
        ("BANK_ERROR", "Bank Error"),
        ("BOOK_ERROR", "Book Error"),
        ("ADJUSTMENT", "Adjustment"),
    ]

    reconciliation = models.ForeignKey(
        BankReconciliation, on_delete=models.CASCADE, related_name="items"
    )
    item_type = models.CharField(max_length=30, choices=ITEM_TYPES)
    date = models.DateField()
    reference = models.CharField(max_length=100)
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_cleared = models.BooleanField(default=False)
    cleared_date = models.DateField(blank=True, null=True)
    
    # Link to transaction if applicable
    transaction = models.ForeignKey(
        "Banking.BankTransaction",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reconciliation_items",
    )

    class Meta:
        db_table = "reconciliation_item"
        ordering = ["date"]

    def __str__(self):
        return f"{self.item_type} - {self.reference} ({self.amount})"

    def clear(self, cleared_date=None):
        """Mark item as cleared"""
        from django.utils import timezone
        
        self.is_cleared = True
        self.cleared_date = cleared_date or timezone.now().date()
        self.save()
