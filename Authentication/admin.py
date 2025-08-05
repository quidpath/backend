#register the models so that I can see them in the database
from django.contrib import admin

from .models.forgotPassword import ForgotPassword
from .models.logbase import State, NotificationType, Notification, TransactionType, Transaction, Organisation
from .models.permisssions import Permission
from .models.role import Role
from .models.user import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email','password','last_login', 'is_staff', 'is_active', 'date_joined','otp_code','last_otp_sent_at')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_active')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

# ✅ State Admin
@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("created_at",)


# ✅ NotificationType Admin
@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ("id" ,"name", "description")
    search_fields = ("name",)


# ✅ Notification Admin
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title", "destination", "notification_type",
        "state", "created_at"
    )
    search_fields = ("title", "destination", "message")
    list_filter = ("notification_type", "state", "created_at")


# ✅ TransactionType Admin
@admin.register(TransactionType)
class TransactionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "simple_name", "class_name", "created_at")
    search_fields = ("name", "simple_name", "class_name")
    list_filter = ("created_at",)


# ✅ Transaction Admin
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "transaction_type", "message", "user", "amount",
        "state", "source_ip", "created_at"
    )
    search_fields = ("reference", "message", "user__username", "transaction_type__name")
    list_filter = ("transaction_type", "state", "created_at")


# ✅ Organisation Admin
@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "created_at", "updated_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)


@admin.register(ForgotPassword)
class ForgotPassword(admin.ModelAdmin):
    list_display = ("id","user", "otp", "is_valid","is_verified", "used_at", "created_at")
    search_fields = ("used_at", "created_at")
    list_filter = ("created_at",)

