from django.db import models
from Accounting.models.customer import Customer
from OrgAuth.models import CorporateUser, Corporate
from quidpath_backend.core.base_models.base import BaseModel


class TaxRate(BaseModel):
    TAX_CHOICES = [
        ("exempt", "Exempt (0%)"),
        ("zero_rated", "Zero Rated (0%)"),
        ("general_rated", "VAT (16%)"),
    ]

    name = models.CharField(
        max_length=50,
        choices=TAX_CHOICES,
        default="general_rated"
    )

    def __str__(self):
        return dict(self.TAX_CHOICES).get(self.name, self.name)

class Quotation(BaseModel):
    STATUS = {
        "DRAFT": "DRAFT",
        "SENT": "SENT",
        "INVOICED": "INVOICED",
        "REJECTED": "REJECTED",
    }
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="quotations")
    corporate = models.ForeignKey(Corporate, on_delete= models.CASCADE, related_name= "quotations")
    date = models.DateField()
    number = models.CharField(max_length=255)
    status = models.CharField(max_length=255, choices=STATUS.items(), default=STATUS["DRAFT"])
    valid_until = models.DateField()
    comments = models.CharField(max_length=255)
    T_and_C = models.CharField(max_length=255)
    salesperson = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, related_name="quotations")
    ship_date = models.DateField()
    ship_via = models.CharField(max_length=255)
    terms = models.CharField(max_length=255)
    fob = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.number} - {self.customer}"


class QuotationLine(BaseModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2)
    taxable = models.ForeignKey(TaxRate, on_delete=models.CASCADE, related_name="quotation_lines")
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.CharField(max_length=255)
    tax_total = models.CharField(max_length=255)
    sub_total = models.CharField(max_length=255)
    total = models.CharField(max_length=255)
    total_discount = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.quotation} - {self.description}"

class ProformaInvoice(BaseModel):
    STATUS = {
        "DRAFT": "DRAFT",
        "SENT": "SENT",
        "INVOICED": "INVOICED",
        "REJECTED": "REJECTED",
    }
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="proforma_invoices")
    corporate = models.ForeignKey(Corporate, on_delete= models.CASCADE, related_name= "profoma_invoices")
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, null=True, blank=True, related_name="proforma_invoices")
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS.items(), default=STATUS["DRAFT"])
    valid_until = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    salesperson = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, related_name="proforma_invoices")
    ship_date = models.DateField(null=True, blank=True)
    ship_via = models.CharField(max_length=255, blank=True)
    fob = models.CharField(max_length=255, blank=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.number} - {self.customer}"


class ProformaInvoiceLine(BaseModel):
    proforma_invoice = models.ForeignKey(ProformaInvoice, on_delete=models.CASCADE, related_name="lines")
    quotation_line = models.ForeignKey(QuotationLine, on_delete=models.SET_NULL, null=True, blank=True, related_name="proforma_invoice_lines")
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    taxable = models.ForeignKey(TaxRate, on_delete=models.CASCADE, related_name="proforma_invoice_lines")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.proforma_invoice} - {self.description}"



class Invoices(BaseModel):
    STATUS = {
        "DRAFT": "DRAFT",
        "ISSUED": "ISSUED",
        "PAID": "PAID",
        "PARTIALLY_PAID": "PARTIALLY PAID",
        "OVERDUE": "OVERDUE",
        "CANCELLED": "CANCELLED",
    }
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="invoices")
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="invoices")
    proforma_invoice = models.ForeignKey(ProformaInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    purchase_order = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS.items(), default=STATUS["DRAFT"])
    due_date = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    salesperson = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, related_name="invoices")
    ship_date = models.DateField(null=True, blank=True)
    ship_via = models.CharField(max_length=255, blank=True)
    fob = models.CharField(max_length=255, blank=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.number} - {self.customer}"


class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(Invoices, on_delete=models.CASCADE, related_name="lines")
    quotation_line = models.ForeignKey(QuotationLine, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_lines")
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    taxable = models.ForeignKey(TaxRate, on_delete=models.CASCADE, related_name="invoice_lines")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.invoice} - {self.description}"
