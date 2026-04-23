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
    
    # Bank account link (for tracking which account was used)
    bank_account = models.ForeignKey(
        "Banking.BankAccount",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="petty_cash_transactions",
        help_text="Bank account used for replenishment or linked to this petty cash"
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
        
        # Create bank transaction if bank account is linked
        if self.bank_account:
            self._create_bank_transaction()
        
        self.status = "APPROVED"
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()
    
    def _create_bank_transaction(self):
        """Create corresponding bank transaction"""
        from Banking.models import BankTransaction
        from django.utils import timezone
        
        # Determine transaction type for bank
        if self.transaction_type == "DISBURSEMENT":
            # Money leaving bank to petty cash
            bank_txn_type = "withdrawal"
            narration = f"Petty Cash Disbursement - {self.description}"
        elif self.transaction_type == "REPLENISHMENT":
            # Money coming from bank to replenish petty cash
            bank_txn_type = "withdrawal"
            narration = f"Petty Cash Replenishment - {self.description}"
        else:
            # Adjustment - no bank transaction
            return
        
        try:
            BankTransaction.objects.create(
                bank_account=self.bank_account,
                transaction_type=bank_txn_type,
                amount=self.amount,
                reference=self.reference,
                narration=narration,
                transaction_date=self.date,
                status="confirmed",
                created_by=self.approved_by,
            )
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create bank transaction for petty cash: {str(e)}")

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
        
        # Create reversing bank transaction if bank account is linked
        if self.bank_account:
            self._create_reversing_bank_transaction()
        
        self.status = "REVERSED"
        self.approved_by = reversed_by_user
        self.approved_at = timezone.now()
        self.save()
    
    def _create_reversing_bank_transaction(self):
        """Create reversing bank transaction"""
        from Banking.models import BankTransaction
        from django.utils import timezone
        
        # Opposite of original transaction
        if self.transaction_type == "DISBURSEMENT":
            # Reversing disbursement means money back to bank
            bank_txn_type = "deposit"
            narration = f"REVERSAL: Petty Cash Disbursement - {self.description}"
        elif self.transaction_type == "REPLENISHMENT":
            # Reversing replenishment means money back to bank
            bank_txn_type = "deposit"
            narration = f"REVERSAL: Petty Cash Replenishment - {self.description}"
        else:
            return
        
        try:
            BankTransaction.objects.create(
                bank_account=self.bank_account,
                transaction_type=bank_txn_type,
                amount=self.amount,
                reference=f"REV-{self.reference}",
                narration=narration,
                transaction_date=timezone.now().date(),
                status="confirmed",
                created_by=self.approved_by,
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create reversing bank transaction: {str(e)}")
