from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from Accounting.models.accounts import Account, AccountType, AccountSubType
from Accounting.models.customer import Customer
from Accounting.models.sales import (
    Quotation, QuotationLine,
    ProformaInvoice, ProformaInvoiceLine,
    Invoices, InvoiceLine,
    TaxRate, PurchaseOrderLine, VendorBillLine, PurchaseOrder, VendorBill
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


# === Core Accounting Admins ===
@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)
    list_filter = ('name',)


@admin.register(AccountSubType)
class AccountSubTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'account_type', 'description')
    search_fields = ('name', 'account_type__name')
    list_filter = ('account_type',)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name', 'corporate', 'account_type', 'account_sub_type', 'is_active')
    search_fields = ('code', 'name', 'account_type__name', 'account_sub_type__name', 'corporate__name')
    list_filter = ('account_type', 'account_sub_type', 'corporate', 'is_active')


# === Customers & Vendors ===
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


# === Sales & Purchases ===
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
    search_fields = ('number', 'customer__first_name', 'customer__last_name', 'customer__company_name')
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
