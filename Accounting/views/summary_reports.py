# summary_reports.py
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def _safe_parse_date(value):
    """Convert DB date field into a datetime.date or None."""
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


@csrf_exempt
def get_sales_summary(request):
    """
    Retrieve Sales Summary grouped by date, customer.

    Expected data (optional):
    - start_date: Start date in YYYY-MM-DD format (default: first day of current month)
    - end_date: End date in YYYY-MM-DD format (default: today)
    - group_by: "date", "customer", or "both" (default: "both")

    Returns:
    - 200: Sales summary data
    - 400: Bad request (invalid data)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        # Parse dates
        today = date.today()
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        group_by = data.get("group_by", "both")

        start_date = (
            today.replace(day=1)
            if not start_date_str
            else _safe_parse_date(str(start_date_str)) or today.replace(day=1)
        )
        end_date = (
            today if not end_date_str else _safe_parse_date(str(end_date_str)) or today
        )

        if start_date > end_date:
            return ResponseProvider(
                message="Start date must be before end date", code=400
            ).bad_request()

        # Get posted invoices
        invoices = registry.database(
            model_name="Invoices",
            operation="filter",
            data={"corporate_id": corporate_id, "status": "POSTED"},
        )

        # Filter by date range
        filtered_invoices = []
        for invoice in invoices:
            inv_date = _safe_parse_date(invoice.get("date"))
            if inv_date and start_date <= inv_date <= end_date:
                filtered_invoices.append(invoice)

        # Get customer information
        customer_ids = {
            inv.get("customer_id")
            for inv in filtered_invoices
            if inv.get("customer_id")
        }
        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id__in": list(customer_ids), "corporate_id": corporate_id},
        )
        customer_map = {c["id"]: c for c in customers}

        # Group data
        if group_by in ["date", "both"]:
            date_summary = defaultdict(
                lambda: {
                    "count": 0,
                    "sub_total": Decimal("0.00"),
                    "tax_total": Decimal("0.00"),
                    "total": Decimal("0.00"),
                }
            )

            for invoice in filtered_invoices:
                inv_date = _safe_parse_date(invoice.get("date"))
                if inv_date:
                    date_key = str(inv_date)
                    date_summary[date_key]["count"] += 1
                    date_summary[date_key]["sub_total"] += Decimal(
                        str(invoice.get("sub_total", 0))
                    )
                    date_summary[date_key]["tax_total"] += Decimal(
                        str(invoice.get("tax_total", 0))
                    )
                    date_summary[date_key]["total"] += Decimal(
                        str(invoice.get("total", 0))
                    )

            date_summary_list = [
                {
                    "date": date_key,
                    "count": summary["count"],
                    "sub_total": str(summary["sub_total"]),
                    "tax_total": str(summary["tax_total"]),
                    "total": str(summary["total"]),
                }
                for date_key, summary in sorted(date_summary.items())
            ]
        else:
            date_summary_list = []

        if group_by in ["customer", "both"]:
            customer_summary = defaultdict(
                lambda: {
                    "count": 0,
                    "sub_total": Decimal("0.00"),
                    "tax_total": Decimal("0.00"),
                    "total": Decimal("0.00"),
                }
            )

            for invoice in filtered_invoices:
                customer_id = invoice.get("customer_id")
                if customer_id:
                    customer_summary[customer_id]["count"] += 1
                    customer_summary[customer_id]["sub_total"] += Decimal(
                        str(invoice.get("sub_total", 0))
                    )
                    customer_summary[customer_id]["tax_total"] += Decimal(
                        str(invoice.get("tax_total", 0))
                    )
                    customer_summary[customer_id]["total"] += Decimal(
                        str(invoice.get("total", 0))
                    )

            customer_summary_list = [
                {
                    "customer_id": str(customer_id),
                    "customer_name": customer_map.get(customer_id, {}).get("name", ""),
                    "customer_code": customer_map.get(customer_id, {}).get("code", ""),
                    "count": summary["count"],
                    "sub_total": str(summary["sub_total"]),
                    "tax_total": str(summary["tax_total"]),
                    "total": str(summary["total"]),
                }
                for customer_id, summary in customer_summary.items()
            ]
        else:
            customer_summary_list = []

        # Calculate totals
        total_count = len(filtered_invoices)
        total_sub_total = sum(
            Decimal(str(inv.get("sub_total", 0))) for inv in filtered_invoices
        )
        total_tax = sum(
            Decimal(str(inv.get("tax_total", 0))) for inv in filtered_invoices
        )
        total_amount = sum(
            Decimal(str(inv.get("total", 0))) for inv in filtered_invoices
        )

        summary_data = {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "group_by": group_by,
            "by_date": date_summary_list,
            "by_customer": customer_summary_list,
            "totals": {
                "count": total_count,
                "sub_total": str(total_sub_total),
                "tax_total": str(total_tax),
                "total": str(total_amount),
            },
        }

        TransactionLogBase.log(
            transaction_type="SALES_SUMMARY_RETRIEVED",
            user=user,
            message=f"Sales summary retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            data=summary_data,
            message="Sales summary retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="SALES_SUMMARY_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving sales summary", code=500
        ).exception()


@csrf_exempt
def get_purchases_summary(request):
    """
    Retrieve Purchases Summary grouped by date, vendor.

    Expected data (optional):
    - start_date: Start date in YYYY-MM-DD format (default: first day of current month)
    - end_date: End date in YYYY-MM-DD format (default: today)
    - group_by: "date", "vendor", or "both" (default: "both")

    Returns:
    - 200: Purchases summary data
    - 400: Bad request (invalid data)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        # Parse dates
        today = date.today()
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        group_by = data.get("group_by", "both")

        start_date = (
            today.replace(day=1)
            if not start_date_str
            else _safe_parse_date(str(start_date_str)) or today.replace(day=1)
        )
        end_date = (
            today if not end_date_str else _safe_parse_date(str(end_date_str)) or today
        )

        if start_date > end_date:
            return ResponseProvider(
                message="Start date must be before end date", code=400
            ).bad_request()

        # Get posted vendor bills
        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"corporate_id": corporate_id, "status": "POSTED"},
        )

        # Filter by date range
        filtered_bills = []
        for bill in vendor_bills:
            bill_date = _safe_parse_date(bill.get("date"))
            if bill_date and start_date <= bill_date <= end_date:
                filtered_bills.append(bill)

        # Get vendor information
        vendor_ids = {
            bill.get("vendor_id") for bill in filtered_bills if bill.get("vendor_id")
        }
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id__in": list(vendor_ids), "corporate_id": corporate_id},
        )
        vendor_map = {v["id"]: v for v in vendors}

        # Group data (similar to sales)
        if group_by in ["date", "both"]:
            date_summary = defaultdict(
                lambda: {
                    "count": 0,
                    "sub_total": Decimal("0.00"),
                    "tax_total": Decimal("0.00"),
                    "total": Decimal("0.00"),
                }
            )

            for bill in filtered_bills:
                bill_date = _safe_parse_date(bill.get("date"))
                if bill_date:
                    date_key = str(bill_date)
                    date_summary[date_key]["count"] += 1
                    date_summary[date_key]["sub_total"] += Decimal(
                        str(bill.get("sub_total", 0))
                    )
                    date_summary[date_key]["tax_total"] += Decimal(
                        str(bill.get("tax_total", 0))
                    )
                    date_summary[date_key]["total"] += Decimal(
                        str(bill.get("total", 0))
                    )

            date_summary_list = [
                {
                    "date": date_key,
                    "count": summary["count"],
                    "sub_total": str(summary["sub_total"]),
                    "tax_total": str(summary["tax_total"]),
                    "total": str(summary["total"]),
                }
                for date_key, summary in sorted(date_summary.items())
            ]
        else:
            date_summary_list = []

        if group_by in ["vendor", "both"]:
            vendor_summary = defaultdict(
                lambda: {
                    "count": 0,
                    "sub_total": Decimal("0.00"),
                    "tax_total": Decimal("0.00"),
                    "total": Decimal("0.00"),
                }
            )

            for bill in filtered_bills:
                vendor_id = bill.get("vendor_id")
                if vendor_id:
                    vendor_summary[vendor_id]["count"] += 1
                    vendor_summary[vendor_id]["sub_total"] += Decimal(
                        str(bill.get("sub_total", 0))
                    )
                    vendor_summary[vendor_id]["tax_total"] += Decimal(
                        str(bill.get("tax_total", 0))
                    )
                    vendor_summary[vendor_id]["total"] += Decimal(
                        str(bill.get("total", 0))
                    )

            vendor_summary_list = [
                {
                    "vendor_id": str(vendor_id),
                    "vendor_name": vendor_map.get(vendor_id, {}).get("name", ""),
                    "vendor_code": vendor_map.get(vendor_id, {}).get("code", ""),
                    "count": summary["count"],
                    "sub_total": str(summary["sub_total"]),
                    "tax_total": str(summary["tax_total"]),
                    "total": str(summary["total"]),
                }
                for vendor_id, summary in vendor_summary.items()
            ]
        else:
            vendor_summary_list = []

        # Calculate totals
        total_count = len(filtered_bills)
        total_sub_total = sum(
            Decimal(str(bill.get("sub_total", 0))) for bill in filtered_bills
        )
        total_tax = sum(
            Decimal(str(bill.get("tax_total", 0))) for bill in filtered_bills
        )
        total_amount = sum(
            Decimal(str(bill.get("total", 0))) for bill in filtered_bills
        )

        summary_data = {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "group_by": group_by,
            "by_date": date_summary_list,
            "by_vendor": vendor_summary_list,
            "totals": {
                "count": total_count,
                "sub_total": str(total_sub_total),
                "tax_total": str(total_tax),
                "total": str(total_amount),
            },
        }

        TransactionLogBase.log(
            transaction_type="PURCHASES_SUMMARY_RETRIEVED",
            user=user,
            message=f"Purchases summary retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            data=summary_data,
            message="Purchases summary retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASES_SUMMARY_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving purchases summary", code=500
        ).exception()


@csrf_exempt
def get_expenses_summary(request):
    """
    Retrieve Expenses Summary grouped by date, category.

    Expected data (optional):
    - start_date: Start date in YYYY-MM-DD format (default: first day of current month)
    - end_date: End date in YYYY-MM-DD format (default: today)
    - group_by: "date", "category", or "both" (default: "both")

    Returns:
    - 200: Expenses summary data
    - 400: Bad request (invalid data)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        # Parse dates
        today = date.today()
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        group_by = data.get("group_by", "both")

        start_date = (
            today.replace(day=1)
            if not start_date_str
            else _safe_parse_date(str(start_date_str)) or today.replace(day=1)
        )
        end_date = (
            today if not end_date_str else _safe_parse_date(str(end_date_str)) or today
        )

        if start_date > end_date:
            return ResponseProvider(
                message="Start date must be before end date", code=400
            ).bad_request()

        # Get posted expenses
        expenses = registry.database(
            model_name="Expense",
            operation="filter",
            data={"corporate_id": corporate_id, "is_posted": True},
        )

        # Filter by date range
        filtered_expenses = []
        for expense in expenses:
            exp_date = _safe_parse_date(expense.get("date"))
            if exp_date and start_date <= exp_date <= end_date:
                filtered_expenses.append(expense)

        # Group data
        if group_by in ["date", "both"]:
            date_summary = defaultdict(
                lambda: {
                    "count": 0,
                    "amount": Decimal("0.00"),
                    "tax_amount": Decimal("0.00"),
                    "total": Decimal("0.00"),
                }
            )

            for expense in filtered_expenses:
                exp_date = _safe_parse_date(expense.get("date"))
                if exp_date:
                    date_key = str(exp_date)
                    date_summary[date_key]["count"] += 1
                    date_summary[date_key]["amount"] += Decimal(
                        str(expense.get("amount", 0))
                    )
                    date_summary[date_key]["tax_amount"] += Decimal(
                        str(expense.get("tax_amount", 0))
                    )
                    date_summary[date_key]["total"] += Decimal(
                        str(expense.get("amount", 0))
                    ) + Decimal(str(expense.get("tax_amount", 0)))

            date_summary_list = [
                {
                    "date": date_key,
                    "count": summary["count"],
                    "amount": str(summary["amount"]),
                    "tax_amount": str(summary["tax_amount"]),
                    "total": str(summary["total"]),
                }
                for date_key, summary in sorted(date_summary.items())
            ]
        else:
            date_summary_list = []

        if group_by in ["category", "both"]:
            category_summary = defaultdict(
                lambda: {
                    "count": 0,
                    "amount": Decimal("0.00"),
                    "tax_amount": Decimal("0.00"),
                    "total": Decimal("0.00"),
                }
            )

            for expense in filtered_expenses:
                category = expense.get("category", "OTHER")
                category_summary[category]["count"] += 1
                category_summary[category]["amount"] += Decimal(
                    str(expense.get("amount", 0))
                )
                category_summary[category]["tax_amount"] += Decimal(
                    str(expense.get("tax_amount", 0))
                )
                category_summary[category]["total"] += Decimal(
                    str(expense.get("amount", 0))
                ) + Decimal(str(expense.get("tax_amount", 0)))

            category_summary_list = [
                {
                    "category": category,
                    "count": summary["count"],
                    "amount": str(summary["amount"]),
                    "tax_amount": str(summary["tax_amount"]),
                    "total": str(summary["total"]),
                }
                for category, summary in category_summary.items()
            ]
        else:
            category_summary_list = []

        # Calculate totals
        total_count = len(filtered_expenses)
        total_amount = sum(
            Decimal(str(exp.get("amount", 0))) for exp in filtered_expenses
        )
        total_tax = sum(
            Decimal(str(exp.get("tax_amount", 0))) for exp in filtered_expenses
        )
        total_all = total_amount + total_tax

        summary_data = {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "group_by": group_by,
            "by_date": date_summary_list,
            "by_category": category_summary_list,
            "totals": {
                "count": total_count,
                "amount": str(total_amount),
                "tax_amount": str(total_tax),
                "total": str(total_all),
            },
        }

        TransactionLogBase.log(
            transaction_type="EXPENSES_SUMMARY_RETRIEVED",
            user=user,
            message=f"Expenses summary retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"period": f"{start_date} to {end_date}"},
            request=request,
        )

        return ResponseProvider(
            data=summary_data,
            message="Expenses summary retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="EXPENSES_SUMMARY_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving expenses summary", code=500
        ).exception()
