from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from Accounting.models.accounts import (Account, AccountSubType, AccountType,
                                        JournalEntry, JournalEntryLine)
from Accounting.models.attachments import DocumentAttachment
from Accounting.models.audit import AuditLog
from Accounting.models.customer import Customer
from Accounting.models.inventory import InventoryItem, StockMovement, Warehouse
from Accounting.models.recurring import RecurringTransaction
from Accounting.models.sales import (InvoiceLine, Invoices, ProformaInvoice,
                                     ProformaInvoiceLine, PurchaseOrder,
                                     PurchaseOrderLine, Quotation,
                                     QuotationLine, TaxRate, VendorBill,
                                     VendorBillLine)
from Accounting.models.vendor import Vendor


# === Inlines ===
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


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 1


# === Core Accounting Admins ===
@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    search_fields = ("name",)
    list_filter = ("name",)


@admin.register(AccountSubType)
class AccountSubTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "account_type", "description")
    search_fields = ("name", "account_type__name")
    list_filter = ("account_type",)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "name",
        "corporate",
        "account_type",
        "account_sub_type",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "account_type__name",
        "account_sub_type__name",
        "corporate",
    )
    list_filter = ("account_type", "account_sub_type", "corporate", "is_active")


# === Journals ===
@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "reference", "date", "corporate", "is_posted")
    search_fields = ("reference", "description", "corporate__name")
    list_filter = ("date", "is_posted", "corporate")
    inlines = [JournalEntryLineInline]


@admin.register(JournalEntryLine)
class JournalEntryLineAdmin(admin.ModelAdmin):
    list_display = ("id", "journal_entry", "account", "debit", "credit", "description")
    search_fields = ("journal_entry__reference", "account__name")
    list_filter = ("account",)


# === Customers & Vendors ===
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "email",
        "category",
        "company_name",
        "city",
        "country",
        "is_active",
    )
    search_fields = ("first_name", "last_name", "email", "company_name")
    list_filter = ("category", "is_active", "country")


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "email",
        "category",
        "company_name",
        "city",
        "country",
        "is_active",
    )
    search_fields = ("first_name", "last_name", "email", "company_name")
    list_filter = ("category", "is_active", "country")


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    list_filter = ("name",)


# === Sales & Purchases ===
@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "number",
        "customer",
        "date",
        "status",
        "valid_until",
        "salesperson",
    )
    search_fields = (
        "number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
    )
    list_filter = ("status", "date", "valid_until")
    inlines = [QuotationLineInline]


@admin.register(ProformaInvoice)
class ProformaInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "number",
        "customer",
        "date",
        "status",
        "valid_until",
        "salesperson",
    )
    search_fields = (
        "number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
    )
    list_filter = ("status", "date", "valid_until")
    inlines = [ProformaInvoiceLineInline]


@admin.register(Invoices)
class InvoicesAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "number",
        "customer",
        "date",
        "status",
        "due_date",
        "salesperson",
    )
    search_fields = ("number", "date", "status")
    list_filter = ("status", "date", "due_date")
    inlines = [InvoiceLineInline]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "number",
        "vendor",
        "date",
        "status",
        "expected_delivery",
        "created_by",
    )
    search_fields = (
        "number",
        "vendor__first_name",
        "vendor__last_name",
        "vendor__company_name",
    )
    list_filter = ("status", "date", "expected_delivery")
    inlines = [PurchaseOrderLineInline]


@admin.register(VendorBill)
class VendorBillAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "number",
        "vendor",
        "date",
        "status",
        "due_date",
        "created_by",
    )
    search_fields = (
        "number",
        "vendor__first_name",
        "vendor__last_name",
        "vendor__company_name",
    )
    list_filter = ("status", "date", "due_date")
    inlines = [VendorBillLineInline]


# === Inventory Management ===
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "code",
        "corporate",
        "city",
        "country",
        "is_active",
        "is_default",
    )
    search_fields = ("name", "code", "city", "country")
    list_filter = ("corporate", "is_active", "is_default", "country")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "sku",
        "corporate",
        "category",
        "quantity_on_hand",
        "quantity_available",
        "unit_cost",
        "selling_price",
        "is_active",
    )
    search_fields = ("name", "sku", "barcode", "category")
    list_filter = ("corporate", "category", "is_active", "valuation_method")
    readonly_fields = ("created_at", "updated_at", "quantity_available")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "warehouse",
        "movement_type",
        "quantity",
        "movement_date",
        "status",
        "reference_number",
    )
    search_fields = ("item__name", "item__sku", "reference_number", "notes")
    list_filter = ("movement_type", "status", "movement_date", "warehouse")
    readonly_fields = ("created_at", "updated_at")


# === Document Attachments ===
@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "file_name",
        "corporate",
        "uploaded_by",
        "content_type",
        "object_id",
        "file_size",
        "is_public",
        "created_at",
    )
    search_fields = ("file_name", "description")
    list_filter = ("corporate", "content_type", "is_public", "mime_type", "created_at")
    readonly_fields = ("created_at", "updated_at", "checksum")


# === Audit Logs ===
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "corporate",
        "action_type",
        "model_name",
        "object_id_str",
        "ip_address",
        "created_at",
    )
    search_fields = ("user__username", "model_name", "description", "ip_address")
    list_filter = ("action_type", "model_name", "corporate", "created_at")
    readonly_fields = ("created_at", "updated_at")


# === Recurring Transactions ===
@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "corporate",
        "transaction_type",
        "frequency",
        "status",
        "start_date",
        "end_date",
        "next_run_at",
        "last_run_at",
    )
    search_fields = ("name", "description")
    list_filter = ("transaction_type", "frequency", "status", "corporate", "created_at")
    readonly_fields = ("created_at", "updated_at", "last_run_at")
