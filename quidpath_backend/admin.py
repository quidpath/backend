from django.contrib import admin

from Authentication.models.logbase import (Notification, NotificationType,
                                           Organisation, State, Transaction,
                                           TransactionType)


# State Admin
@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("created_at",)


# NotificationType Admin
@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("created_at",)


# Notification Admin
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "destination", "notification_type", "state", "created_at")
    search_fields = ("title", "destination", "message")
    list_filter = ("notification_type", "state", "created_at")


# TransactionType Admin
@admin.register(TransactionType)
class TransactionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "simple_name", "class_name", "created_at")
    search_fields = ("name", "simple_name", "class_name")
    list_filter = ("created_at",)


# Transaction Admin
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "transaction_type",
        "user",
        "amount",
        "state",
        "source_ip",
        "created_at",
    )
    search_fields = ("reference", "message", "user__username", "transaction_type__name")
    list_filter = ("transaction_type", "state", "created_at")


# Organisation Admin
@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "created_at", "updated_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)
