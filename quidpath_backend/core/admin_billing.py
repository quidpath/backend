"""
Billing Admin Integration - Display billing data in main backend admin
"""

from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html

from OrgAuth.models import Corporate
from quidpath_backend.core.billing_client import BillingServiceClient


class BillingAdminMixin:
    """Mixin to add billing client to admin"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.billing_client = BillingServiceClient()


class BillingDashboardAdmin(admin.ModelAdmin):
    """Custom admin for billing dashboard"""

    change_list_template = "admin/billing_dashboard.html"

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.billing_client = BillingServiceClient()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        """Custom changelist view to show billing dashboard"""
        extra_context = extra_context or {}

        # Get billing stats
        stats_result = self.billing_client.admin_get_stats()
        extra_context["billing_stats"] = (
            stats_result.get("data", {}) if stats_result.get("success") else {}
        )

        # Get recent trials
        trials_result = self.billing_client.admin_list_trials(limit=10)
        extra_context["recent_trials"] = (
            trials_result.get("data", {}).get("trials", [])
            if trials_result.get("success")
            else []
        )

        # Get active subscriptions
        subs_result = self.billing_client.admin_list_subscriptions(
            status="active", limit=10
        )
        extra_context["active_subscriptions"] = (
            subs_result.get("data", {}).get("subscriptions", [])
            if subs_result.get("success")
            else []
        )

        # Get pending invoices
        invoices_result = self.billing_client.admin_list_invoices(
            status="pending", limit=10
        )
        extra_context["pending_invoices"] = (
            invoices_result.get("data", {}).get("invoices", [])
            if invoices_result.get("success")
            else []
        )

        return super().changelist_view(request, extra_context=extra_context)


# Custom inline admin for Corporate billing info
class CorporateBillingInline(admin.StackedInline):
    """Inline to show billing information on Corporate admin page"""

    model = Corporate
    can_delete = False
    verbose_name_plural = "Billing Information"
    readonly_fields = ["get_billing_info"]
    fields = ["get_billing_info"]

    def get_billing_info(self, obj):
        """Display billing information for this corporate"""
        if not obj or not obj.id:
            return "Save corporate first to view billing information."

        billing_client = BillingServiceClient()
        result = billing_client.admin_get_corporate_summary(str(obj.id))

        if not result.get("success"):
            return format_html(
                '<div style="color: red;">Error loading billing data: {}</div>',
                result.get("message", "Unknown error"),
            )

        data = result.get("data", {})
        trial = data.get("trial")
        subscription = data.get("subscription")
        totals = data.get("totals", {})

        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'

        # Trial info
        if trial:
            status_color = "green" if trial["status"] == "active" else "gray"
            html += f"""
                <h3>Trial Status</h3>
                <p><strong>Status:</strong> <span style="color: {status_color};">{trial["status"].upper()}</span></p>
                <p><strong>Days Remaining:</strong> {trial.get("days_remaining", "N/A")}</p>
                <p><strong>End Date:</strong> {trial.get("end_date", "N/A")}</p>
                <hr>
            """

        # Subscription info
        if subscription:
            html += f"""
                <h3>Active Subscription</h3>
                <p><strong>Plan:</strong> {subscription["plan_name"]} ({subscription["plan_tier"]})</p>
                <p><strong>Billing Cycle:</strong> {subscription["billing_cycle"]}</p>
                <p><strong>Amount:</strong> {subscription["currency"]} {subscription["total_amount"]}</p>
                <p><strong>End Date:</strong> {subscription["end_date"]}</p>
                <hr>
            """

        # Financial summary
        html += f"""
            <h3>Financial Summary</h3>
            <p><strong>Total Invoiced:</strong> KES {totals.get("invoiced", 0):.2f}</p>
            <p><strong>Total Paid:</strong> KES {totals.get("paid", 0):.2f}</p>
            <p><strong>Outstanding:</strong> <span style="color: red;">KES {totals.get("outstanding", 0):.2f}</span></p>
        """

        # Recent invoices
        invoices = data.get("invoices", [])
        if invoices:
            html += '<h3>Recent Invoices</h3><table style="width: 100%; border-collapse: collapse;">'
            html += '<tr style="background: #e9ecef;"><th>Invoice #</th><th>Status</th><th>Amount</th><th>Due Date</th></tr>'
            for inv in invoices[:5]:
                status_color = "green" if inv["status"] == "paid" else "orange"
                html += f"""
                    <tr style="border-bottom: 1px solid #dee2e6;">
                        <td>{inv["invoice_number"]}</td>
                        <td><span style="color: {status_color};">{inv["status"]}</span></td>
                        <td>KES {inv["total_amount"]:.2f}</td>
                        <td>{inv["due_date"][:10]}</td>
                    </tr>
                """
            html += "</table>"

        html += "</div>"

        return format_html(html)

    get_billing_info.short_description = "Billing Information"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Extend Corporate admin to include billing info
from OrgAuth.admin import CorporateAdmin as OriginalCorporateAdmin


class CorporateAdminWithBilling(OriginalCorporateAdmin):
    """Extended Corporate admin with billing information"""

    def get_inlines(self, request, obj=None):
        """Add billing inline to corporate admin"""
        inlines = list(super().get_inlines(request, obj))
        if obj and obj.id:  # Only show for existing corporates
            inlines.append(CorporateBillingInline)
        return inlines


def billing_trials_view(request):
    """View for listing all trials"""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)

    billing_client = BillingServiceClient()
    result = billing_client.admin_list_trials(limit=100)

    if result.get("success"):
        trials = result.get("data", {}).get("trials", [])
        return render(request, "admin/billing_trials.html", {"trials": trials})
    else:
        return render(
            request, "admin/billing_error.html", {"error": result.get("message")}
        )


def billing_subscriptions_view(request):
    """View for listing all subscriptions"""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)

    billing_client = BillingServiceClient()
    result = billing_client.admin_list_subscriptions(limit=100)

    if result.get("success"):
        subscriptions = result.get("data", {}).get("subscriptions", [])
        return render(
            request,
            "admin/billing_subscriptions.html",
            {"subscriptions": subscriptions},
        )
    else:
        return render(
            request, "admin/billing_error.html", {"error": result.get("message")}
        )


def billing_invoices_view(request):
    """View for listing all invoices"""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)

    billing_client = BillingServiceClient()
    result = billing_client.admin_list_invoices(limit=100)

    if result.get("success"):
        invoices = result.get("data", {}).get("invoices", [])
        return render(request, "admin/billing_invoices.html", {"invoices": invoices})
    else:
        return render(
            request, "admin/billing_error.html", {"error": result.get("message")}
        )


def billing_payments_view(request):
    """View for listing all payments"""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)

    billing_client = BillingServiceClient()
    result = billing_client.admin_list_payments(limit=100)

    if result.get("success"):
        payments = result.get("data", {}).get("payments", [])
        return render(request, "admin/billing_payments.html", {"payments": payments})
    else:
        return render(
            request, "admin/billing_error.html", {"error": result.get("message")}
        )
