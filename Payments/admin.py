# Payments/admin.py
from django.contrib import admin
from .models import RecordPayment, RecordPaymentLine, VendorPayment, VendorPaymentLine, PaymentProvider


class RecordPaymentLineInline(admin.TabularInline):
    model = RecordPaymentLine
    extra = 1
    fields = ("invoice", "invoice_date", "invoice_amount", "amount_due", "amount_applied")
    readonly_fields = ("invoice_date", "invoice_amount", "amount_due")


@admin.register(RecordPayment)
class RecordPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "customer", "amount_received", "payment_date",
        "payment_method", "account", "amount_used", "amount_refunded", "amount_excess"
    )
    list_filter = ("payment_method", "payment_date", "customer")
    search_fields = ("payment_number", "reference_number")
    date_hierarchy = "payment_date"
    inlines = [RecordPaymentLineInline]


class VendorPaymentLineInline(admin.TabularInline):
    model = VendorPaymentLine
    extra = 1
    fields = ("bill", "bill_date", "bill_amount", "amount_due", "amount_applied")
    readonly_fields = ("bill_date", "bill_amount", "amount_due")


@admin.register(VendorPayment)
class VendorPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "vendor", "amount_disbursed", "payment_date",
        "payment_method", "account", "amount_used", "amount_refunded", "amount_excess"
    )
    list_filter = ("payment_method", "payment_date", "vendor")
    search_fields = ( "payment_number", "reference_number")
    date_hierarchy = "payment_date"
    inlines = [VendorPaymentLineInline]


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = ("id", "corporate", "provider_type", "name", "is_active", "is_default", "test_mode", "created_at")
    list_filter = ("provider_type", "is_active", "is_default", "test_mode", "created_at")
    search_fields = ("name", "corporate__name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
