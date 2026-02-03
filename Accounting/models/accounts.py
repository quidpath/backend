import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

from Accounting.models.customer import Customer
from Accounting.models.vendor import Vendor
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class AccountType(BaseModel):
    """
    Standard accounting types: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    """

    ACCOUNT_TYPES = [
        ("ASSET", "Asset"),
        ("LIABILITY", "Liability"),
        ("EQUITY", "Equity"),
        ("REVENUE", "Revenue"),
        ("EXPENSE", "Expense"),
    ]

    name = models.CharField(max_length=20, choices=ACCOUNT_TYPES, unique=True)
    description = models.TextField(blank=True, default="")
    normal_balance = models.CharField(
        max_length=6,
        choices=[("DEBIT", "Debit"), ("CREDIT", "Credit")],
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "account_type"

    def __str__(self):
        return self.get_name_display()

    def save(self, *args, **kwargs):
        # Set normal balance based on account type
        if self.name in ["ASSET", "EXPENSE"]:
            self.normal_balance = "DEBIT"
        else:
            self.normal_balance = "CREDIT"
        super().save(*args, **kwargs)


class AccountSubType(BaseModel):
    """
    Sub-categories for account types
    """

    account_type = models.ForeignKey(
        AccountType, on_delete=models.CASCADE, related_name="sub_types"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "account_sub_type"
        unique_together = ["account_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.account_type.name})"


class Account(BaseModel):
    """
    Chart of Accounts - individual accounts for each corporate
    """

    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="accounts"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    account_type = models.ForeignKey(
        AccountType, on_delete=models.PROTECT, null=True, blank=True
    )
    account_sub_type = models.ForeignKey(
        AccountSubType, on_delete=models.PROTECT, blank=True, null=True
    )
    parent_account = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="sub_accounts",
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "account"
        unique_together = [["corporate", "code"], ["corporate", "name"]]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if (
            self.account_sub_type
            and self.account_sub_type.account_type != self.account_type
        ):
            raise ValidationError(
                "Account sub-type must belong to the selected account type"
            )

    def get_balance(self, as_of_date=None):
        """Calculate account balance as of a specific date"""
        if as_of_date is None:
            as_of_date = date.today()

        # Get all journal entry lines for this account up to the date
        lines = JournalEntryLine.objects.filter(
            account=self,
            journal_entry__is_posted=True,
            journal_entry__date__lte=as_of_date,
        ).aggregate(
            total_debit=Sum("debit") or Decimal("0"),
            total_credit=Sum("credit") or Decimal("0"),
        )

        balance = lines["total_debit"] - lines["total_credit"]

        # For liability, equity, and revenue accounts, return negative of calculated balance
        # since these normally have credit balances
        if self.account_type.normal_balance == "CREDIT":
            balance = -balance

        return balance


class JournalEntry(BaseModel):
    """
    Journal entries for recording transactions
    """

    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="journal_entries"
    )
    date = models.DateField()
    reference = models.CharField(max_length=50)
    description = models.TextField(blank=True, default="")
    source_type = models.CharField(
        max_length=50, blank=True
    )  # 'invoice', 'vendor_bill', 'manual', etc.
    source_id = models.UUIDField(blank=True, null=True)  # ID of the source document
    is_posted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        CorporateUser, on_delete=models.PROTECT, blank=True, null=True
    )

    class Meta:
        db_table = "journal_entry"
        unique_together = [["corporate", "reference"]]

    def __str__(self):
        return f"{self.reference} - {self.date} ({'Posted' if self.is_posted else 'Draft'})"

    def get_total_debits(self):
        return self.lines.aggregate(total=Sum("debit"))["total"] or Decimal("0")

    def get_total_credits(self):
        return self.lines.aggregate(total=Sum("credit"))["total"] or Decimal("0")

    def is_balanced(self):
        return self.get_total_debits() == self.get_total_credits()

    def post(self):
        """Post the journal entry after validation"""
        if not self.is_balanced():
            raise ValidationError(
                "Journal entry is not balanced - debits must equal credits"
            )
        if not self.lines.exists():
            raise ValidationError("Journal entry must have at least one line")

        self.is_posted = True
        self.save()

    def unpost(self):
        """Unpost the journal entry"""
        self.is_posted = False
        self.save()


class JournalEntryLine(BaseModel):
    """
    Individual lines within a journal entry
    """

    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    debit = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    credit = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "journal_entry_line"

    def __str__(self):
        return f"{self.journal_entry.reference} - {self.account.name} (Dr: {self.debit}, Cr: {self.credit})"

    def clean(self):
        # Ensure account belongs to the same corporate as the journal entry
        if self.account.corporate != self.journal_entry.corporate:
            raise ValidationError(
                "Account must belong to the same corporate as the journal entry"
            )

        # Ensure either debit or credit is zero (not both non-zero)
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("A line cannot have both debit and credit amounts")

        # Ensure at least one amount is greater than zero
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("A line must have either a debit or credit amount")


class Expense(BaseModel):
    """
    Direct expense entries not linked to vendor bills
    """

    EXPENSE_CATEGORIES = [
        ("OPERATING", "Operating Expense"),
        ("ADMINISTRATIVE", "Administrative Expense"),
        ("SELLING", "Selling Expense"),
        ("FINANCIAL", "Financial Expense"),
        ("OTHER", "Other Expense"),
    ]

    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="expenses"
    )
    date = models.DateField()
    reference = models.CharField(max_length=50)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORIES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Account assignments
    expense_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="expenses"
    )
    payment_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="expense_payments"
    )

    # Optional vendor link
    vendor = models.ForeignKey(
        "Accounting.Vendor",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="expenses",
    )

    # Tax information
    tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    tax_rate = models.ForeignKey(
        "Accounting.TaxRate", on_delete=models.PROTECT, blank=True, null=True
    )

    # Journal entry
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, blank=True, null=True
    )

    created_by = models.ForeignKey(CorporateUser, on_delete=models.PROTECT)
    is_posted = models.BooleanField(default=False)

    class Meta:
        db_table = "expense"
        unique_together = [["corporate", "reference"]]

    def __str__(self):
        return f"{self.reference} - {self.description} ({self.amount})"

    def get_total_amount(self):
        return self.amount + self.tax_amount


class FinancialReport(BaseModel):
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    report_type = models.CharField(
        max_length=20,
        choices=[
            ("PROFIT_LOSS", "Profit and Loss"),
            ("BALANCE_SHEET", "Balance Sheet"),
            ("CASH_FLOW", "Cash Flow"),
            ("INCOME_STATEMENT", "Income Statement"),
        ],
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField()
    data = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "financial_report"

    def __str__(self):
        return f"{self.report_type} for {self.corporate} ending {self.end_date}"
