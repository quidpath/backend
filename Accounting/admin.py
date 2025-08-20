from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from Accounting.models.customer import Customer
from Accounting.models.purchases import PurchaseOrderLine, VendorBillLine, PurchaseOrder, VendorBill
from Accounting.models.sales import (
    Quotation, QuotationLine,
    ProformaInvoice, ProformaInvoiceLine,
    Invoices, InvoiceLine,
    TaxRate
)
from Accounting.models.vendor import Vendor

# Inlines
class QuotationLineInline(admin.TabularInline):
    model = QuotationLine
    extra = 1

class ProformaInvoiceLineInline(admin.TabularInline):
    model = ProformaInvoiceLine
    extra = 1

class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1

class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1

class VendorBillLineInline(admin.TabularInline):
    model = VendorBillLine
    extra = 1

# Admins
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'category', 'company_name', 'city', 'country', 'is_active')
    search_fields = ('first_name', 'last_name', 'email', 'company_name')
    list_filter = ('category', 'is_active', 'country')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'category', 'company_name', 'city', 'country', 'is_active')
    search_fields = ('first_name', 'last_name', 'email', 'company_name')
    list_filter = ('category', 'is_active', 'country')


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    list_filter = ('name',)


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'customer', 'date', 'status', 'valid_until', 'salesperson')
    search_fields = ('number', 'customer__first_name', 'customer__last_name', 'customer__company_name')
    list_filter = ('status', 'date', 'valid_until')
    inlines = [QuotationLineInline]


@admin.register(ProformaInvoice)
class ProformaInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'customer', 'date', 'status', 'valid_until', 'salesperson')
    search_fields = ('number', 'customer__first_name', 'customer__last_name', 'customer__company_name')
    list_filter = ('status', 'date', 'valid_until')
    inlines = [ProformaInvoiceLineInline]


@admin.register(Invoices)
class InvoicesAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'customer', 'date', 'status', 'due_date', 'salesperson')
    search_fields = ('number', '', 'customer__last_name', 'customer__company_name')
    list_filter = ('status', 'date', 'due_date')
    inlines = [InvoiceLineInline]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'vendor', 'date', 'status', 'expected_delivery', 'created_by')
    search_fields = ('number', 'vendor__first_name', 'vendor__last_name', 'vendor__company_name')
    list_filter = ('status', 'date', 'expected_delivery')
    inlines = [PurchaseOrderLineInline]


@admin.register(VendorBill)
class VendorBillAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'vendor', 'date', 'status', 'due_date', 'created_by')
    search_fields = ('number', 'vendor__first_name', 'vendor__last_name', 'vendor__company_name')
    list_filter = ('status', 'date', 'due_date')
    inlines = [VendorBillLineInline]
