from decimal import Decimal

from django.db import models

from Accounting.models.customer import Customer
from Accounting.models.vendor import Vendor
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class TaxRate(BaseModel):
    TAX_CHOICES = [
        ("exempt", "Exempt (0%)"),
        ("zero_rated", "Zero Rated (0%)"),
        ("general_rated", "VAT (16%)"),
    ]

    corporate = models.ForeignKey(
        Corporate,
        on_delete=models.CASCADE,
        related_name="tax_rates",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=50, choices=TAX_CHOICES, default="general_rated")
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("16.00"))
    sales_account = models.ForeignKey(
        "Accounting.Account",
        on_delete=models.PROTECT,
        related_name="sales_tax_rates",
        blank=True,
        null=True,
    )
    purchase_account = models.ForeignKey(
        "Accounting.Account",
        on_delete=models.PROTECT,
        related_name="purchase_tax_rates",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "tax_rate"
        unique_together = [["corporate", "name"]]

    def __str__(self):
        return dict(self.TAX_CHOICES).get(self.name, self.name)

    def save(self, *args, **kwargs):
        if self.name in ["exempt", "zero_rated"]:
            self.rate = Decimal("0.00")
        elif self.name == "general_rated":
            self.rate = Decimal("16.00")
        super().save(*args, **kwargs)


class Quotation(BaseModel):
    STATUS = [
        ("DRAFT", "DRAFT"),
        ("POSTED", "POSTED"),
        ("INVOICED", "INVOICED"),
        ("REJECTED", "REJECTED"),
    ]
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="quotations"
    )
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="quotations"
    )
    date = models.DateField()
    number = models.CharField(max_length=255)
    status = models.CharField(max_length=255, choices=STATUS, default="DRAFT")
    valid_until = models.DateField()
    comments = models.CharField(max_length=255)
    T_and_C = models.CharField(max_length=255)
    salesperson = models.ForeignKey(
        CorporateUser, on_delete=models.CASCADE, related_name="quotations"
    )
    ship_date = models.DateField()
    ship_via = models.CharField(max_length=255)
    terms = models.CharField(max_length=255)
    fob = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.number} - {self.customer}"


class QuotationLine(BaseModel):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(
        "Accounting.Account", on_delete=models.PROTECT, blank=True, null=True
    )
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    taxable = models.ForeignKey(
        TaxRate, on_delete=models.CASCADE, related_name="quotation_lines"
    )
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    tax_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    sub_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    def __str__(self):
        return f"{self.quotation} - {self.description}"


class PurchaseOrder(BaseModel):
    STATUS = [
        ("DRAFT", "DRAFT"),
        ("POSTED", "POSTED"),
        ("INVOICED", "INVOICED"),
        ("CONFIRMED", "CONFIRMED"),
        ("RECEIVED", "RECEIVED"),
        ("PARTIALLY_RECEIVED", "PARTIALLY RECEIVED"),
        ("CANCELLED", "CANCELLED"),
    ]
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    quotation = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS, default="DRAFT")
    expected_delivery = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        CorporateUser, on_delete=models.CASCADE, related_name="purchase_orders"
    )
    ship_date = models.DateField(null=True, blank=True)
    ship_via = models.CharField(max_length=255, blank=True)
    fob = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.number} - {self.vendor}"


class PurchaseOrderLine(BaseModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(
        "Accounting.Account", on_delete=models.PROTECT, blank=True, null=True
    )
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    taxable = models.ForeignKey(
        TaxRate, on_delete=models.CASCADE, related_name="purchase_order_lines"
    )
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    total_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    def __str__(self):
        return f"{self.purchase_order} - {self.description}"


class ProformaInvoice(BaseModel):
    STATUS = [
        ("DRAFT", "DRAFT"),
        ("POSTED", "POSTED"),
        ("INVOICED", "INVOICED"),
        ("REJECTED", "REJECTED"),
    ]
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="proforma_invoices"
    )
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="proforma_invoices"
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proforma_invoices",
    )
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS, default="DRAFT")
    valid_until = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    salesperson = models.ForeignKey(
        CorporateUser, on_delete=models.CASCADE, related_name="proforma_invoices"
    )
    ship_date = models.DateField(null=True, blank=True)
    ship_via = models.CharField(max_length=255, blank=True)
    fob = models.CharField(max_length=255, blank=True)
    sub_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    tax_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    def __str__(self):
        return f"{self.number} - {self.customer}"


class ProformaInvoiceLine(BaseModel):
    proforma_invoice = models.ForeignKey(
        ProformaInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    quotation_line = models.ForeignKey(
        QuotationLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proforma_invoice_lines",
    )
    account = models.ForeignKey(
        "Accounting.Account", on_delete=models.PROTECT, blank=True, null=True
    )
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    taxable = models.ForeignKey(
        TaxRate, on_delete=models.CASCADE, related_name="proforma_invoice_lines"
    )
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.proforma_invoice} - {self.description}"


class Invoices(BaseModel):
    STATUS = [
        ("DRAFT", "DRAFT"),
        ("POSTED", "POSTED"),
        ("PAID", "PAID"),
        ("PARTIALLY_PAID", "PARTIALLY PAID"),
        ("OVERDUE", "OVERDUE"),
        ("CANCELLED", "CANCELLED"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("overpaid", "Overpaid"),
    ]
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="invoices"
    )
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="invoices"
    )
    proforma_invoice = models.ForeignKey(
        ProformaInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    purchase_order = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS, default="DRAFT")
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid"
    )
    payment_reference = models.CharField(
        max_length=255, blank=True, null=True
    )  # Payment reference from gateway
    currency = models.CharField(max_length=3, default="USD")  # USD, KES, etc.
    exchange_rate_to_usd = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("1.0")
    )  # Rate at invoice creation
    due_date = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    salesperson = models.ForeignKey(
        CorporateUser, on_delete=models.CASCADE, related_name="invoices"
    )
    ship_date = models.DateField(null=True, blank=True)
    ship_via = models.CharField(max_length=255, blank=True)
    fob = models.CharField(max_length=255, blank=True)
    sub_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    tax_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    receivable_account = models.ForeignKey(
        "Accounting.Account",
        on_delete=models.PROTECT,
        related_name="invoices_as_receivable",
        blank=True,
        null=True,
    )
    journal_entry = models.ForeignKey(
        "Accounting.JournalEntry", on_delete=models.SET_NULL, blank=True, null=True
    )
    issued_at = models.DateTimeField(
        null=True, blank=True
    )  # When invoice was issued/sent
    paid_at = models.DateTimeField(null=True, blank=True)  # When invoice was fully paid
    receipt_pdf_url = models.URLField(blank=True, null=True)  # S3 URL for receipt PDF
    is_reconciled = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["payment_status"]),
            models.Index(fields=["corporate", "date"]),
            models.Index(fields=["payment_reference"]),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer}"


class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(
        Invoices, on_delete=models.CASCADE, related_name="lines"
    )
    quotation_line = models.ForeignKey(
        QuotationLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_lines",
    )
    account = models.ForeignKey(
        "Accounting.Account", on_delete=models.PROTECT, blank=True, null=True
    )
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    taxable = models.ForeignKey(
        TaxRate, on_delete=models.CASCADE, related_name="invoice_lines"
    )
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.invoice} - {self.description}"


class VendorBill(BaseModel):
    STATUS = [
        ("DRAFT", "DRAFT"),
        ("POSTED", "POSTED"),
        ("PAID", "PAID"),
        ("PARTIALLY_PAID", "PARTIALLY PAID"),
        ("OVERDUE", "OVERDUE"),
        ("CANCELLED", "CANCELLED"),
    ]
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="vendor_bills"
    )
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="vendor_bills"
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_bills",
    )
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS, default="DRAFT")
    due_date = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        CorporateUser, on_delete=models.CASCADE, related_name="vendor_bills"
    )
    sub_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    tax_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    payable_account = models.ForeignKey(
        "Accounting.Account",
        on_delete=models.PROTECT,
        related_name="vendor_bills_as_payable",
        blank=True,
        null=True,
    )
    journal_entry = models.ForeignKey(
        "Accounting.JournalEntry", on_delete=models.SET_NULL, blank=True, null=True
    )

    def __str__(self):
        return f"{self.number} - {self.vendor}"


class VendorBillLine(BaseModel):
    vendor_bill = models.ForeignKey(
        VendorBill, on_delete=models.CASCADE, related_name="lines"
    )
    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_bill_lines",
    )
    account = models.ForeignKey(
        "Accounting.Account", on_delete=models.PROTECT, blank=True, null=True
    )
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    taxable = models.ForeignKey(
        TaxRate, on_delete=models.CASCADE, related_name="vendor_bill_lines"
    )
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.vendor_bill} - {self.description}"
