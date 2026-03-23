"""
ERP payment models — customer and vendor payments within the accounting module.
These are NOT subscription/billing payments (those live in the billing microservice).
"""
from decimal import Decimal

from django.db import models

from Accounting.models.customer import Customer
from Accounting.models.sales import Invoices, VendorBill
from Accounting.models.vendor import Vendor
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class RecordPayment(BaseModel):
    """Payment received from a customer, allocated to invoices."""

    METHOD_TYPES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("mpesa", "MPESA"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    invoice = models.ForeignKey(
        Invoices, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    amount_received = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate_to_usd = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1.0"))
    bank_charges = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    payment_date = models.DateField()
    payment_number = models.CharField(max_length=255, blank=True, null=True)
    payment_method = models.CharField(max_length=50, choices=METHOD_TYPES)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    account = models.ForeignKey("Accounting.Account", on_delete=models.CASCADE)
    reference_number = models.CharField(max_length=255, blank=True, null=True)
    provider_reference = models.CharField(max_length=255, blank=True, null=True)
    provider_metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(CorporateUser, on_delete=models.PROTECT, blank=True, null=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    receipt_pdf_url = models.URLField(blank=True, null=True)
    is_reconciled = models.BooleanField(default=False)
    amount_used = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_refunded = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_excess = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    journal_entry = models.ForeignKey(
        "Accounting.JournalEntry", on_delete=models.SET_NULL, blank=True, null=True
    )
    is_posted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Customer Payment"
        verbose_name_plural = "Customer Payments"
        indexes = [
            models.Index(fields=["provider_reference"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["corporate", "payment_date"]),
        ]

    def __str__(self):
        name = self.customer.company_name if self.customer.category == "company" else f"{self.customer.first_name} {self.customer.last_name}".strip()
        return f"Payment from {name} - {self.amount_received} {self.currency}"


class RecordPaymentLine(BaseModel):
    """Allocation of a customer payment to a specific invoice."""

    payment = models.ForeignKey(RecordPayment, on_delete=models.CASCADE, related_name="lines")
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE)
    invoice_date = models.DateField(blank=True, null=True)
    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_applied = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    def __str__(self):
        return f"{self.amount_applied} applied to Invoice {getattr(self.invoice, 'invoice_number', self.invoice.id)}"


class VendorPayment(BaseModel):
    """Payment made to a vendor, allocated to bills."""

    METHOD_TYPES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("mpesa", "MPESA"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    bill = models.ForeignKey(VendorBill, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    created_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, blank=True, null=True)
    amount_disbursed = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate_to_usd = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1.0"))
    bank_charges = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    payment_date = models.DateField()
    payment_number = models.CharField(max_length=255, blank=True, null=True)
    payment_method = models.CharField(max_length=50, choices=METHOD_TYPES)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    account = models.ForeignKey("Accounting.Account", on_delete=models.CASCADE)
    bill_number = models.CharField(max_length=255, blank=True, null=True)
    provider_reference = models.CharField(max_length=255, blank=True, null=True)
    provider_metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, null=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    receipt_pdf_url = models.URLField(blank=True, null=True)
    is_reconciled = models.BooleanField(default=False)
    amount_used = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_refunded = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_excess = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    journal_entry = models.ForeignKey(
        "Accounting.JournalEntry", on_delete=models.SET_NULL, blank=True, null=True
    )
    is_posted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Vendor Payment"
        verbose_name_plural = "Vendor Payments"
        indexes = [
            models.Index(fields=["provider_reference"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["corporate", "payment_date"]),
        ]

    def __str__(self):
        name = getattr(self.vendor, "company_name", None) or getattr(self.vendor, "name", None) or str(self.vendor.id)
        return f"Payment to {name} - {self.amount_disbursed} {self.currency}"


class VendorPaymentLine(BaseModel):
    """Allocation of a vendor payment to a specific bill."""

    payment = models.ForeignKey(VendorPayment, on_delete=models.CASCADE, related_name="lines")
    bill = models.ForeignKey(VendorBill, on_delete=models.CASCADE)
    bill_date = models.DateField(blank=True, null=True)
    bill_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    amount_applied = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    def __str__(self):
        return f"{self.amount_applied} applied to Bill {getattr(self.bill, 'bill_number', None) or self.bill.id}"


class PaymentProvider(BaseModel):
    """Payment gateway configuration per organisation (Flutterwave, etc.)."""

    PROVIDER_TYPES = [
        ("flutterwave", "Flutterwave"),
        ("other", "Other"),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="payment_providers")
    provider_type = models.CharField(max_length=50, choices=PROVIDER_TYPES)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    config_json = models.JSONField(default=dict)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)
    test_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Payment Provider"
        verbose_name_plural = "Payment Providers"
        unique_together = [["corporate", "provider_type", "name"]]

    def __str__(self):
        return f"{self.corporate.name} - {self.get_provider_type_display()} ({self.name})"
