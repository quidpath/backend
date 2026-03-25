"""
analytics_views.py — Aggregated analytics data for the frontend dashboard.
Returns revenue trends, expense breakdown, top customers, and KPIs.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def _safe_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _get_corporate_id(registry, user):
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return None, ResponseProvider(message="User ID not found", code=400).bad_request()
    corp_users = registry.database("CorporateUser", "filter",
                                   data={"customuser_ptr_id": user_id, "is_active": True})
    if not corp_users:
        return None, ResponseProvider(message="No corporate association", code=400).bad_request()
    return corp_users[0]["corporate_id"], None


@csrf_exempt
def get_analytics_overview(request):
    """
    Returns comprehensive analytics data for the dashboard.
    Params (optional): start_date, end_date (default: last 12 months)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    registry = ServiceRegistry()
    corporate_id, err = _get_corporate_id(registry, user)
    if err:
        return err

    today = date.today()
    start_date_str = data.get("start_date") or request.GET.get("start_date")
    end_date_str = data.get("end_date") or request.GET.get("end_date")

    end_date = _safe_date(end_date_str) or today
    start_date = _safe_date(start_date_str) or (today - timedelta(days=365))

    try:
        # ── Invoices ──────────────────────────────────────────────────────────
        invoices = registry.database("Invoices", "filter",
                                     data={"corporate_id": corporate_id})
        period_invoices = []
        for inv in invoices:
            d = _safe_date(inv.get("date"))
            if d and start_date <= d <= end_date:
                period_invoices.append(inv)

        total_revenue = sum(Decimal(str(inv.get("total", 0))) for inv in period_invoices
                            if inv.get("status") in ("POSTED", "PAID"))
        total_outstanding = sum(Decimal(str(inv.get("total", 0))) for inv in period_invoices
                                if inv.get("status") == "POSTED")
        total_overdue = sum(Decimal(str(inv.get("total", 0))) for inv in period_invoices
                            if inv.get("status") == "OVERDUE")

        # ── Expenses ──────────────────────────────────────────────────────────
        expenses = registry.database("Expense", "filter",
                                     data={"corporate_id": corporate_id})
        period_expenses = []
        for exp in expenses:
            d = _safe_date(exp.get("date"))
            if d and start_date <= d <= end_date:
                period_expenses.append(exp)

        total_expenses = sum(Decimal(str(e.get("amount", 0))) for e in period_expenses)

        # ── Vendor Bills ──────────────────────────────────────────────────────
        bills = registry.database("VendorBill", "filter",
                                  data={"corporate_id": corporate_id})
        period_bills = []
        for b in bills:
            d = _safe_date(b.get("date"))
            if d and start_date <= d <= end_date:
                period_bills.append(b)

        total_bills = sum(Decimal(str(b.get("total", 0))) for b in period_bills)

        # ── Monthly Revenue Trend ─────────────────────────────────────────────
        monthly_revenue = defaultdict(Decimal)
        monthly_expenses = defaultdict(Decimal)

        for inv in period_invoices:
            if inv.get("status") in ("POSTED", "PAID"):
                d = _safe_date(inv.get("date"))
                if d:
                    key = f"{d.year}-{d.month:02d}"
                    monthly_revenue[key] += Decimal(str(inv.get("total", 0)))

        for exp in period_expenses:
            d = _safe_date(exp.get("date"))
            if d:
                key = f"{d.year}-{d.month:02d}"
                monthly_expenses[key] += Decimal(str(exp.get("amount", 0)))

        # Build sorted month list
        all_months = sorted(set(list(monthly_revenue.keys()) + list(monthly_expenses.keys())))
        revenue_trend = [
            {
                "month": m,
                "revenue": float(monthly_revenue.get(m, 0)),
                "expenses": float(monthly_expenses.get(m, 0)),
                "profit": float(monthly_revenue.get(m, 0) - monthly_expenses.get(m, 0)),
            }
            for m in all_months
        ]

        # ── Expense Breakdown by Category ─────────────────────────────────────
        expense_by_category = defaultdict(Decimal)
        for exp in period_expenses:
            cat = exp.get("category", "Other")
            expense_by_category[cat] += Decimal(str(exp.get("amount", 0)))

        expense_breakdown = [
            {"category": cat, "amount": float(amt)}
            for cat, amt in sorted(expense_by_category.items(), key=lambda x: -x[1])
        ]

        # ── Top Customers ─────────────────────────────────────────────────────
        customer_revenue = defaultdict(Decimal)
        customer_names = {}
        for inv in period_invoices:
            if inv.get("status") in ("POSTED", "PAID"):
                cid = inv.get("customer_id")
                if cid:
                    customer_revenue[cid] += Decimal(str(inv.get("total", 0)))
                    if cid not in customer_names:
                        customer_names[cid] = inv.get("customer__name", "")

        top_customers = sorted(
            [{"customer": customer_names.get(cid, str(cid)), "revenue": float(amt)}
             for cid, amt in customer_revenue.items()],
            key=lambda x: -x["revenue"]
        )[:10]

        # ── Invoice Status Distribution ───────────────────────────────────────
        status_counts = defaultdict(int)
        for inv in period_invoices:
            status_counts[inv.get("status", "UNKNOWN")] += 1

        invoice_status = [{"status": s, "count": c} for s, c in status_counts.items()]

        # ── KPIs ──────────────────────────────────────────────────────────────
        net_profit = total_revenue - total_expenses
        profit_margin = float(net_profit / total_revenue * 100) if total_revenue > 0 else 0

        # Previous period for comparison
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - (end_date - start_date)
        prev_invoices = [inv for inv in invoices
                         if inv.get("status") in ("POSTED", "PAID")
                         and _safe_date(inv.get("date"))
                         and prev_start <= _safe_date(inv.get("date")) <= prev_end]
        prev_revenue = sum(Decimal(str(inv.get("total", 0))) for inv in prev_invoices)
        revenue_growth = float(
            (total_revenue - prev_revenue) / prev_revenue * 100
        ) if prev_revenue > 0 else 0

        result = {
            "period": {"start": str(start_date), "end": str(end_date)},
            "kpis": {
                "total_revenue": float(total_revenue),
                "total_expenses": float(total_expenses),
                "net_profit": float(net_profit),
                "profit_margin": round(profit_margin, 2),
                "total_outstanding": float(total_outstanding),
                "total_overdue": float(total_overdue),
                "total_bills": float(total_bills),
                "revenue_growth": round(revenue_growth, 2),
                "invoice_count": len(period_invoices),
                "expense_count": len(period_expenses),
            },
            "revenue_trend": revenue_trend,
            "expense_breakdown": expense_breakdown,
            "top_customers": top_customers,
            "invoice_status": invoice_status,
        }

        TransactionLogBase.log(
            transaction_type="ANALYTICS_OVERVIEW_RETRIEVED",
            user=user,
            message=f"Analytics overview retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            data=result,
            message="Analytics overview retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ANALYTICS_OVERVIEW_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred: {str(e)}", code=500
        ).exception()
