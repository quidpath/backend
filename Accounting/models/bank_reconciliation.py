"""
Bank Reconciliation Models
"""
import uuid
from django.db import models
from OrgAuth.models import Corporate, CorporateUser
from Banking.models import BankAccount, BankTransaction


class BankReconciliation(models.Model):
    """Model for bank reconciliation records"""
    
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('REVIEWED', 'Reviewed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    corporate = models.ForeignKey(
        Corporate,
        on_delete=models.CASCADE,
        related_name='bank_reconciliations'
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='accounting_reconciliations'
    )
    
    period_start = models.DateField()
    period_end = models.DateField()
    
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2)
    statement_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    book_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    total_deposits_in_transit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_outstanding_checks = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_bank_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_adjustments = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    difference = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')
    notes = models.TextField(blank=True, default='')
    
    reconciled_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        related_name='reconciliations_performed'
    )
    reviewed_by = models.ForeignKey(
        CorporateUser,
        on_delete=models.PROTECT,
        related_name='reconciliations_reviewed',
        null=True,
        blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bank_reconciliation'
        ordering = ['-period_end']
        unique_together = [('bank_account', 'period_start', 'period_end')]
    
    def __str__(self):
        return f"Reconciliation {self.bank_account} ({self.period_start} to {self.period_end})"

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

    def complete(self):
        """Mark reconciliation as completed"""
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        
        self.calculate_difference()
        
        if abs(self.difference) > Decimal("0.01"):
            raise ValidationError(
                f"Cannot complete reconciliation with difference of {self.difference}. "
                "Statement and book balances must match within 0.01."
            )
        
        self.status = "COMPLETED"
        self.save()


class ReconciliationItem(models.Model):
    """Model for individual reconciliation items"""
    
    ITEM_TYPE_CHOICES = [
        ('DEPOSIT_IN_TRANSIT', 'Deposit in Transit'),
        ('OUTSTANDING_CHECK', 'Outstanding Check'),
        ('BANK_CHARGE', 'Bank Charge'),
        ('BANK_ERROR', 'Bank Error'),
        ('BOOK_ERROR', 'Book Error'),
        ('ADJUSTMENT', 'Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    reconciliation = models.ForeignKey(
        BankReconciliation,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    item_type = models.CharField(max_length=30, choices=ITEM_TYPE_CHOICES)
    date = models.DateField()
    reference = models.CharField(max_length=100)
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    is_cleared = models.BooleanField(default=False)
    cleared_date = models.DateField(null=True, blank=True)
    
    transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.SET_NULL,
        related_name='reconciliation_items',
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'reconciliation_item'
        ordering = ['date']
    
    def __str__(self):
        return f"{self.item_type} - {self.reference} ({self.amount})"
