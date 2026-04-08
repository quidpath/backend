# Banking models (full corrected code)
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from OrgAuth.models import Corporate
from quidpath_backend.core.base_models.base import BaseModel


class BankAccount(BaseModel):
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    bank_name = models.CharField(max_length=255)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    currency = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ledger_account = models.OneToOneField(
        "Accounting.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_account",
    )

    def __str__(self):
        return f"{self.bank_name} - {self.account_name}"


class BankTransaction(BaseModel):
    TRANSACTION_TYPES = [
        ("deposit", "Deposit"),
        ("withdrawal", "Withdrawal"),
        ("transfer", "Transfer"),
        ("charge", "Charge"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("reversed", "Reversed"),
    ]

    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True, null=True)
    narration = models.TextField(blank=True, null=True)
    transaction_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type.title()} - {self.amount}"


class BankReconciliation(BaseModel):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("reconciled", "Reconciled"),
        ("discrepancy", "Discrepancy"),
    ]

    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="banking_reconciliations"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reconciliation {self.period_start} to {self.period_end}"


class InternalTransfer(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    from_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="outgoing_transfers"
    )
    to_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="incoming_transfers"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    transfer_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transfer {self.amount} from {self.from_account} to {self.to_account}"


class PaymentMethod(BaseModel):
    METHOD_TYPES = [
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("mpesa", "MPESA"),
        ("other", "Other"),
    ]

    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="payment_methods"
    )
    method_type = models.CharField(max_length=50, choices=METHOD_TYPES)
    last4 = models.CharField(max_length=4, blank=True, null=True)
    provider = models.CharField(max_length=50, blank=True, null=True)
    token = models.CharField(max_length=255, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.method_type.upper()} - {self.last4}"


class BankCharge(BaseModel):
    CHARGE_TYPES = [
        ("transfer_fee", "Transfer Fee"),
        ("monthly_fee", "Monthly Maintenance"),
        ("withdrawal_fee", "Withdrawal Fee"),
        ("other", "Other"),
    ]

    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="charges"
    )
    charge_type = models.CharField(max_length=50, choices=CHARGE_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    charge_date = models.DateField(default=timezone.now)
    linked_transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="charges",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.charge_type} - {self.amount}"
