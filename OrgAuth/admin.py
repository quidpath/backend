# OrgAuth/admin.py

from django.contrib import admin
from django.utils.html import format_html

from Authentication.models.role import Role
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.billing_client import BillingServiceClient


@admin.register(Corporate)
class CorporateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "is_active",
        "billing_status",
        "is_approved",
        "created_at",
    )
    search_fields = ("name", "email")
    list_filter = ("is_approved", "is_active")
    readonly_fields = ("created_at", "updated_at", "get_billing_summary")
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Company Information",
            {
                "fields": (
                    "name",
                    "industry",
                    "company_size",
                    "description",
                    "website",
                    "logo",
                )
            },
        ),
        (
            "Contact Information",
            {
                "fields": (
                    "email",
                    "phone",
                    "address",
                    "city",
                    "state",
                    "country",
                    "zip_code",
                )
            },
        ),
        (
            "Registration Details",
            {"fields": ("registration_number", "tax_id", "message")},
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_approved",
                    "is_rejected",
                    "rejection_reason",
                    "is_seen",
                    "is_verified",
                )
            },
        ),
        (
            "Billing Information",
            {"fields": ("get_billing_summary",), "classes": ("collapse",)},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def billing_status(self, obj):
        """Display billing status in list view"""
        if not obj or not obj.id:
            return "-"

        billing_client = BillingServiceClient()
        result = billing_client.check_access(str(obj.id))

        if not result.get("success"):
            return format_html('<span style="color: gray;">Unknown</span>')

        has_access = result.get("has_access", False)
        access_type = result.get("access_type", "none")

        if has_access:
            if access_type == "trial":
                trial = result.get("trial", {})
                days = trial.get("days_remaining", 0)
                return format_html(
                    '<span style="color: orange;" title="Trial"> Trial ({} days)</span>',
                    days,
                )
            elif access_type == "subscription":
                return format_html(
                    '<span style="color: green;" title="Active">Active</span>'
                )
        else:
            return format_html(
                '<span style="color: red;" title="Expired">Expired</span>'
            )

    billing_status.short_description = "Billing Status"

    def get_billing_summary(self, obj):
        """Display detailed billing information"""
        if not obj or not obj.id:
            return "Save corporate first to view billing information."

        billing_client = BillingServiceClient()
        result = billing_client.admin_get_corporate_summary(str(obj.id))

        if not result.get("success"):
            return format_html(
                '<div style="color: red; padding: 10px; background: #fff3cd; border-radius: 5px;">'
                "<strong>Error loading billing data:</strong> {}"
                "</div>",
                result.get("message", "Unknown error"),
            )

        data = result.get("data", {})
        trial = data.get("trial")
        subscription = data.get("subscription")
        totals = data.get("totals", {})
        invoices = data.get("invoices", [])
        payments = data.get("payments", [])

        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px; font-family: Arial, sans-serif;">'

        # Access Status
        html += '<h2 style="margin-top: 0; color: #2c3e50;">Billing Overview</h2>'

        # Trial info
        if trial:
            status_color = "#28a745" if trial["status"] == "active" else "#6c757d"
            status_icon = "[ACTIVE]" if trial["status"] == "active" else "[PENDING]"
            html += f"""
                <div style="background: white; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid {status_color};">
                    <h3 style="margin-top: 0;">{status_icon} Trial Status</h3>
                    <p><strong>Status:</strong> <span style="color: {status_color}; text-transform: uppercase;">{trial["status"]}</span></p>
                    <p><strong>Days Remaining:</strong> {trial.get("days_remaining", "N/A")}</p>
                    <p><strong>End Date:</strong> {trial.get("end_date", "N/A")[:10]}</p>
                </div>
            """

        # Subscription info
        if subscription:
            html += f"""
                <div style="background: white; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #007bff;">
                    <h3 style="margin-top: 0;"> Active Subscription</h3>
                    <p><strong>Plan:</strong> {subscription["plan_name"]} <span style="background: #007bff; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{subscription["plan_tier"]}</span></p>
                    <p><strong>Billing Cycle:</strong> {subscription["billing_cycle"].upper()}</p>
                    <p><strong>Amount:</strong> <span style="font-size: 18px; font-weight: bold;">{subscription["currency"]} {subscription["total_amount"]}</span></p>
                    <p><strong>End Date:</strong> {subscription["end_date"][:10]}</p>
                </div>
            """

        # Financial summary
        outstanding_color = "#dc3545" if totals.get("outstanding", 0) > 0 else "#28a745"
        html += f"""
            <div style="background: white; padding: 15px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #ffc107;">
                <h3 style="margin-top: 0;">Financial Summary</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Total Invoiced:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">KES {totals.get("invoiced", 0):,.2f}</td>
                    </tr>
                    <tr style="background: #e7f5e7;">
                        <td style="padding: 5px 0;"><strong>Total Paid:</strong></td>
                        <td style="padding: 5px 0; text-align: right; color: #28a745;">KES {totals.get("paid", 0):,.2f}</td>
                    </tr>
                    <tr style="background: #fff3cd;">
                        <td style="padding: 5px 0;"><strong>Outstanding:</strong></td>
                        <td style="padding: 5px 0; text-align: right; color: {outstanding_color}; font-weight: bold;">KES {totals.get("outstanding", 0):,.2f}</td>
                    </tr>
                </table>
            </div>
        """

        # Recent invoices
        if invoices:
            html += """
                <div style="background: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                    <h3 style="margin-top: 0;">Recent Invoices</h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background: #e9ecef; text-align: left;">
                                <th style="padding: 8px;">Invoice #</th>
                                <th style="padding: 8px;">Status</th>
                                <th style="padding: 8px; text-align: right;">Amount</th>
                                <th style="padding: 8px;">Due Date</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            for inv in invoices[:5]:
                status_colors = {
                    "paid": "#28a745",
                    "pending": "#ffc107",
                    "overdue": "#dc3545",
                }
                status_color = status_colors.get(inv["status"], "#6c757d")
                html += f"""
                    <tr style="border-bottom: 1px solid #dee2e6;">
                        <td style="padding: 8px;">{inv["invoice_number"]}</td>
                        <td style="padding: 8px;">
                            <span style="color: {status_color}; font-weight: bold;">
                                {inv["status"].upper()}
                            </span>
                        </td>
                        <td style="padding: 8px; text-align: right;">KES {inv["total_amount"]:,.2f}</td>
                        <td style="padding: 8px;">{inv["due_date"][:10]}</td>
                    </tr>
                """
            html += "</tbody></table></div>"

        # Recent payments
        if payments:
            html += """
                <div style="background: white; padding: 15px; border-radius: 5px;">
                    <h3 style="margin-top: 0;">Recent Payments</h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background: #e9ecef; text-align: left;">
                                <th style="padding: 8px;">Amount</th>
                                <th style="padding: 8px;">Method</th>
                                <th style="padding: 8px;">Status</th>
                                <th style="padding: 8px;">Date</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            for pmt in payments[:5]:
                status_color = "#28a745" if pmt["status"] == "completed" else "#ffc107"
                html += f"""
                    <tr style="border-bottom: 1px solid #dee2e6;">
                        <td style="padding: 8px; font-weight: bold;">KES {pmt["amount"]:,.2f}</td>
                        <td style="padding: 8px; text-transform: uppercase;">{pmt["payment_method"]}</td>
                        <td style="padding: 8px;">
                            <span style="color: {status_color}; font-weight: bold;">
                                {pmt["status"].upper()}
                            </span>
                        </td>
                        <td style="padding: 8px;">{pmt["paid_at"][:10] if pmt["paid_at"] else "Pending"}</td>
                    </tr>
                """
            html += "</tbody></table></div>"

        html += "</div>"

        return format_html(html)

    get_billing_summary.short_description = "Billing Details"


@admin.register(CorporateUser)
class CorporateUserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "corporate", "is_active", "created_at")
    search_fields = ("username", "email")
    list_filter = ("corporate", "is_active")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("corporate",)
        return self.readonly_fields
