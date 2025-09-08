from django.db import models
from Accounting.models.customer import Customer
from Accounting.models.sales import Invoices, VendorBill
from Accounting.models.vendor import Vendor
from Banking.models import BankAccount
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class RecordPayment(BaseModel):
    """
    Records a payment received from a customer with summary allocation.
    """
    METHOD_TYPES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("mpesa", "MPESA"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, blank=True, null =True)
    amount_received = models.DecimalField(max_digits=12, decimal_places=2)  # total payment
    bank_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField()
    payment_number = models.CharField(max_length=255, blank=True, null=True)  # e.g., receipt no
    payment_method = models.CharField(max_length=50, choices=METHOD_TYPES)
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)  # Deposit To
    reference_number = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # summary fields (auto-calculated)
    amount_used = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_refunded = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_excess = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Customer Payment"
        verbose_name_plural = "Customer Payments"

    def __str__(self):
        customer = self.customer
        if customer.category == "company":
            display_name = customer.company_name or "Unnamed Company"
        else:
            display_name = f"{customer.first_name} {customer.last_name}".strip()
        return f"Payment from {display_name} - {self.amount_received}"


class RecordPaymentLine(BaseModel):
    """
    Line allocations: each row connects a payment to a specific invoice.
    """
    payment = models.ForeignKey(RecordPayment, on_delete=models.CASCADE, related_name="lines")
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE)
    invoice_date = models.DateField(blank=True, null=True)
    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_applied = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.amount_applied} applied to Invoice {getattr(self.invoice, 'invoice_number', self.invoice.id)}"


class VendorPayment(BaseModel):
    """
    Records a payment made to a vendor with summary allocation.
    """
    METHOD_TYPES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("mpesa", "MPESA"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, blank=True, null =True)
    created_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, blank=True, null=True)
    amount_disbursed = models.DecimalField(max_digits=12, decimal_places=2)
    bank_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField()
    payment_number = models.CharField(max_length=255, blank=True, null=True)  # e.g., cheque no
    payment_method = models.CharField(max_length=50, choices=METHOD_TYPES)
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)  # Paid From
    bill_number = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # summary fields (auto-calculated)
    amount_used = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_refunded = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_excess = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Vendor Payment"
        verbose_name_plural = "Vendor Payments"

    def __str__(self):
        vendor = self.vendor
        display_name = getattr(vendor, "company_name", None) or getattr(vendor, "name", None) or str(vendor.id)
        return f"Payment to {display_name} - {self.amount_disbursed}"


class VendorPaymentLine(BaseModel):
    """
    Line allocations: each row connects a vendor payment to a bill.
    """
    payment = models.ForeignKey(VendorPayment, on_delete=models.CASCADE, related_name="lines")
    bill = models.ForeignKey(VendorBill, on_delete=models.CASCADE)
    bill_date = models.DateField(blank=True, null=True)
    bill_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_applied = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        bill_ref = getattr(self.bill, "bill_number", None) or str(self.bill.id)
        return f"{self.amount_applied} applied to Bill {bill_ref}"
