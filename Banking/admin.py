from django.contrib import admin

from Banking.models import BankAccount, BankTransaction, BankReconciliation, InternalTransfer, BankCharge
from OrgAuth.models import Corporate, CorporateUser
from Authentication.models.role import Role


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("id","bank_name", "account_name", "account_number", "is_active", "currency","is_default", "created_at")
    search_fields = ("account_name", "account_number")
    list_filter = ("created_at", "is_active")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ("id","bank_account", "transaction_type", "amount", "reference", "narration","transaction_date","status", "created_at")
    search_fields = ("reference", "transaction_date")
    list_filter = ("created_at", "reference")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ("id","bank_account", "period_start", "period_end", "opening_balance", "closing_balance","status", "created_at")
    search_fields = ("period_start", "period_end")
    list_filter = ("created_at", "period_end")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

@admin.register(InternalTransfer)
class InternalTransferAdmin(admin.ModelAdmin):
    list_display = ("id","from_account", "to_account", "reason", "created_by", "transfer_date","status", "created_at")
    search_fields = ("from_account__incoming_transfers__transfer_date", "to_account__outgoing_transfers__transfer_date")
    list_filter = ("created_at", "id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

@admin.register(BankCharge)
class BankChargeAdmin(admin.ModelAdmin):
    list_display = ("id","bank_account", "charge_type", "amount", "description", "charge_date","linked_transaction", "created_at")
    search_fields = ("charge_date", "charge_type")
    list_filter = ("created_at", "charge_date")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
