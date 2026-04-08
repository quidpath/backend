"""
Petty Cash Management Models
"""
import uuid
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class PettyCashFund(BaseModel):
    """
    Petty cash fund for managing small cash transactions
    """
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="petty_cash_funds"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    custodian = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        related_name="managed_petty_cash_funds",
    )
    initial_amount = models.DecimalField(max_digits=15, decimal_places=2)
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        related_name="created_petty_cash_funds",
    )

    class Meta:
        db_table = "petty_cash_fund"
        unique_together = [["corporate", "name"]]

    def __str__(self):
        return f"{self.name} - {self.custodian.username}"

    def save(self, *args, **kwargs):
        if self.current_balance is None:  # Set initial balance if not set
            self.current_balance = self.initial_amount
        super().save(*args, **kwargs)


class PettyCashTransaction(BaseModel):
    """
    Individual petty cash transactions
    """
    TRANSACTION_TYPES = [
        ("DISBURSEMENT", "Disbursement"),
        ("REPLENISHMENT", "Replenishment"),
        ("ADJUSTMENT", "Adjustment"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("REVERSED", "Reversed"),
        ("COMPLETED", "Completed"),
    ]

    fund = models.ForeignKey(
        PettyCashFund, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    date = models.DateField()
    reference = models.CharField(max_length=50)
    description = models.TextField()
    category = models.CharField(max_length=100, blank=True, default="")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    recipient = models.CharField(max_length=200, blank=True, default="")
    receipt_number = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    
    # Approval tracking
    requested_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        related_name="petty_cash_requests",
    )
    approved_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="approved_petty_cash",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    
    # Accounting link
    journal_entry = models.ForeignKey(
        "Accounting.JournalEntry",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "petty_cash_transaction"
        unique_together = [["fund", "reference"]]

    def __str__(self):
        return f"{self.reference} - {self.transaction_type} ({self.amount})"

    def approve(self, approved_by_user):
        """Approve the transaction and update fund balance"""
        from django.utils import timezone
        
        if self.status != "PENDING":
            raise ValidationError("Only pending transactions can be approved")
        
        # Update fund balance
        if self.transaction_type == "DISBURSEMENT":
            if self.fund.current_balance < self.amount:
                raise ValidationError("Insufficient petty cash balance")
            self.fund.current_balance -= self.amount
        elif self.transaction_type == "REPLENISHMENT":
            self.fund.current_balance += self.amount
        elif self.transaction_type == "ADJUSTMENT":
            self.fund.current_balance = self.amount
        
        self.fund.save()
        
        self.status = "APPROVED"
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()

    def reject(self, rejected_by_user):
        """Reject the transaction"""
        if self.status == "APPROVED":
            raise ValidationError("Cannot reject an approved transaction. Use reverse() instead.")
        if self.status != "PENDING":
            raise ValidationError("Only pending transactions can be rejected")
        
        self.status = "REJECTED"
        self.approved_by = rejected_by_user
        self.save()

    def reverse(self, reversed_by_user):
        """Reverse an approved transaction and restore fund balance"""
        from django.utils import timezone
        
        if self.status != "APPROVED":
            raise ValidationError("Only approved transactions can be reversed")
        
        # Reverse the balance change
        if self.transaction_type == "DISBURSEMENT":
            self.fund.current_balance += self.amount
        elif self.transaction_type == "REPLENISHMENT":
            self.fund.current_balance -= self.amount
        elif self.transaction_type == "ADJUSTMENT":
            # For adjustments, we can't simply reverse - need manual intervention
            raise ValidationError("Adjustment transactions cannot be automatically reversed. Create a new adjustment.")
        
        self.fund.save()
        self.status = "REVERSED"
        self.approved_by = reversed_by_user
        self.approved_at = timezone.now()
        self.save()
