# OrgAuth/admin.py

from django.contrib import admin
from OrgAuth.models import Corporate, CorporateUser
from Authentication.models.role import Role


@admin.register(Corporate)
class CorporateAdmin(admin.ModelAdmin):
    list_display = ("id","name", "email", "is_active", "created_at","is_approved", "created_at")
    search_fields = ("name", "email")
    list_filter = ("is_approved", "is_active")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(CorporateUser)
class CorporateUserAdmin(admin.ModelAdmin):
    list_display = ("id","username", "email", "corporate", "is_active", "created_at")
    search_fields = ("username", "email")
    list_filter = ("corporate", "is_active")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("corporate",)
        return self.readonly_fields
