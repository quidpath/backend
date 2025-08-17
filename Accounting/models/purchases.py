from django.db import models

from Accounting.models.sales import TaxRate
from Accounting.models.vendor import Vendor  # Assuming Vendor model exists
from OrgAuth.models import CorporateUser, Corporate
from quidpath_backend.core.base_models.base import BaseModel

class PurchaseOrder(BaseModel):
    STATUS = {
        "DRAFT": "DRAFT",
        "SENT": "SENT",
        "CONFIRMED": "CONFIRMED",
        "RECEIVED": "RECEIVED",
        "PARTIALLY_RECEIVED": "PARTIALLY RECEIVED",
        "CANCELLED": "CANCELLED",
    }
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="purchase_orders")
    corporate = models.ForeignKey(Corporate, on_delete= models.CASCADE, related_name= "purchase_orders")
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS.items(), default=STATUS["DRAFT"])
    expected_delivery = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, related_name="purchase_orders")
    ship_date = models.DateField(null=True, blank=True)
    ship_via = models.CharField(max_length=255, blank=True)
    fob = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.number} - {self.vendor}"

class PurchaseOrderLine(BaseModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    taxable = models.ForeignKey(TaxRate, on_delete=models.CASCADE, related_name="purchase_order_lines")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.purchase_order} - {self.description}"

class VendorBill(BaseModel):
    STATUS = {
        "DRAFT": "DRAFT",
        "POSTED": "POSTED",
        "PAID": "PAID",
        "PARTIALLY_PAID": "PARTIALLY PAID",
        "OVERDUE": "OVERDUE",
        "CANCELLED": "CANCELLED",
    }
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="vendor_bills")
    corporate = models.ForeignKey(Corporate, on_delete= models.CASCADE, related_name= "vendor_bills")
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_bills")
    date = models.DateField()
    number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=STATUS.items(), default=STATUS["DRAFT"])
    due_date = models.DateField()
    comments = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE, related_name="vendor_bills")
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.number} - {self.vendor}"

class VendorBillLine(BaseModel):
    vendor_bill = models.ForeignKey(VendorBill, on_delete=models.CASCADE, related_name="lines")
    purchase_order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_bill_lines")
    description = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    taxable = models.ForeignKey(TaxRate, on_delete=models.CASCADE, related_name="vendor_bill_lines")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.vendor_bill} - {self.description}"