"""
Core app admin - Billing Management
"""

from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from quidpath_backend.core.Services.billing_service import BillingServiceClient


class BillingOverviewAdmin(admin.ModelAdmin):
    """Admin interface for billing overview"""

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "overview/",
                self.admin_site.admin_view(self.overview_view),
                name="billing_overview",
            ),
            path(
                "trials/",
                self.admin_site.admin_view(self.trials_view),
                name="billing_trials",
            ),
            path(
                "subscriptions/",
                self.admin_site.admin_view(self.subscriptions_view),
                name="billing_subscriptions",
            ),
            path(
                "invoices/",
                self.admin_site.admin_view(self.invoices_view),
                name="billing_invoices",
            ),
            path(
                "payments/",
                self.admin_site.admin_view(self.payments_view),
                name="billing_payments",
            ),
        ]
        return custom_urls + urls

    def overview_view(self, request):
        """Billing overview dashboard"""
        billing_client = BillingServiceClient()
        stats_result = billing_client.admin_get_stats()

        context = {
            "title": "Billing Overview",
            "opts": self.model._meta,
            "has_permission": True,
            "site_header": "Billing Management",
            "stats": (
                stats_result.get("data", {}) if stats_result.get("success") else {}
            ),
            "error": (
                None if stats_result.get("success") else stats_result.get("message")
            ),
        }

        return render(request, "admin/billing/overview.html", context)

    def trials_view(self, request):
        """View all trials"""
        billing_client = BillingServiceClient()
        result = billing_client.admin_list_trials(limit=200)

        context = {
            "title": "All Trials",
            "opts": self.model._meta,
            "has_permission": True,
            "trials": (
                result.get("data", {}).get("trials", [])
                if result.get("success")
                else []
            ),
            "error": None if result.get("success") else result.get("message"),
        }

        return render(request, "admin/billing/trials.html", context)

    def subscriptions_view(self, request):
        """View all subscriptions"""
        billing_client = BillingServiceClient()
        result = billing_client.admin_list_subscriptions(limit=200)

        context = {
            "title": "All Subscriptions",
            "opts": self.model._meta,
            "has_permission": True,
            "subscriptions": (
                result.get("data", {}).get("subscriptions", [])
                if result.get("success")
                else []
            ),
            "error": None if result.get("success") else result.get("message"),
        }

        return render(request, "admin/billing/subscriptions.html", context)

    def invoices_view(self, request):
        """View all invoices"""
        billing_client = BillingServiceClient()
        result = billing_client.admin_list_invoices(limit=200)

        context = {
            "title": "All Invoices",
            "opts": self.model._meta,
            "has_permission": True,
            "invoices": (
                result.get("data", {}).get("invoices", [])
                if result.get("success")
                else []
            ),
            "error": None if result.get("success") else result.get("message"),
        }

        return render(request, "admin/billing/invoices.html", context)

    def payments_view(self, request):
        """View all payments"""
        billing_client = BillingServiceClient()
        result = billing_client.admin_list_payments(limit=200)

        context = {
            "title": "All Payments",
            "opts": self.model._meta,
            "has_permission": True,
            "payments": (
                result.get("data", {}).get("payments", [])
                if result.get("success")
                else []
            ),
            "error": None if result.get("success") else result.get("message"),
        }

        return render(request, "admin/billing/payments.html", context)

    def changelist_view(self, request, extra_context=None):
        """Redirect to overview"""
        return redirect("admin:billing_overview")


# Don't register the billing admin for now - can be added later with proper model
# The billing information is already integrated into Corporate admin
