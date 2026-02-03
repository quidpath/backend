# aged_invoices.py
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
def get_aged_invoices(request):
    """
    Retrieve Aged Invoices Report with detailed invoice information.

    Expected data (optional):
    - as_of_date: Date in YYYY-MM-DD format (default: today)
    - aging_buckets: List of days [30, 60, 90, 120] (default: [30, 60, 90, 120])
    - customer_id: Filter by specific customer (optional)
    - include_paid: Boolean (default: False) - Include fully paid invoices

    Returns:
    - 200: Aged invoices data with detailed invoice information
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

        # Parse parameters
        as_of_date_raw = data.get("as_of_date")
        aging_buckets = data.get("aging_buckets", [30, 60, 90, 120])
        customer_id = data.get("customer_id")
        include_paid = data.get("include_paid", False)

        if isinstance(as_of_date_raw, str):
            as_of_date = _safe_parse_date(as_of_date_raw) or date.today()
        elif isinstance(as_of_date_raw, datetime):
            as_of_date = as_of_date_raw.date()
        elif isinstance(as_of_date_raw, date):
            as_of_date = as_of_date_raw
        else:
            as_of_date = date.today()

        # Get posted invoices
        invoice_filter = {"corporate_id": corporate_id, "status": "POSTED"}
        if customer_id:
            invoice_filter["customer_id"] = customer_id

        invoices = registry.database(
            model_name="Invoices", operation="filter", data=invoice_filter
        )

        # Get customer payments
        all_payments = registry.database(
            model_name="RecordPayment",
            operation="filter",
            data={"corporate_id": corporate_id},
        )

        # Calculate outstanding per invoice
        invoice_payments = defaultdict(Decimal)
        for payment in all_payments:
            inv_id = payment.get("invoice_id")
            if inv_id:
                amount = Decimal(
                    str(
                        payment.get(
                            "amount_received", payment.get("amount_disbursed", 0)
                        )
                    )
                )
                invoice_payments[inv_id] += amount

        # Get customer information
        customer_ids = {
            inv.get("customer_id") for inv in invoices if inv.get("customer_id")
        }
        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id__in": list(customer_ids), "corporate_id": corporate_id},
        )
        customer_map = {c["id"]: c for c in customers}

        # Process invoices and group by aging buckets
        aged_invoices = []
        aging_totals = {
            "current": Decimal("0.00"),
            "buckets": {bucket: Decimal("0.00") for bucket in aging_buckets},
            "over": Decimal("0.00"),
            "total": Decimal("0.00"),
        }

        for invoice in invoices:
            due_date_raw = invoice.get("due_date")
            due_date = _safe_parse_date(due_date_raw) if due_date_raw else None

            if not due_date:
                continue

            total_amount = Decimal(str(invoice.get("total", 0)))
            paid_amount = invoice_payments.get(invoice["id"], Decimal("0.00"))
            outstanding = total_amount - paid_amount

            if outstanding <= 0 and not include_paid:
                continue

            days_overdue = (as_of_date - due_date).days

            # Determine bucket
            if days_overdue <= 0:
                bucket = "current"
            elif days_overdue <= aging_buckets[0]:
                bucket = aging_buckets[0]
            elif len(aging_buckets) > 1 and days_overdue <= aging_buckets[1]:
                bucket = aging_buckets[1]
            elif len(aging_buckets) > 2 and days_overdue <= aging_buckets[2]:
                bucket = aging_buckets[2]
            elif len(aging_buckets) > 3 and days_overdue <= aging_buckets[3]:
                bucket = aging_buckets[3]
            else:
                bucket = "over"

            # Get customer details
            customer_id = invoice.get("customer_id")
            customer = customer_map.get(customer_id, {}) if customer_id else {}

            invoice_data = {
                "id": str(invoice["id"]),
                "number": invoice.get("number", ""),
                "invoice_date": str(invoice.get("date", "")),
                "due_date": str(due_date),
                "customer_id": str(customer_id) if customer_id else None,
                "customer_name": customer.get("name", ""),
                "customer_code": customer.get("code", ""),
                "customer_email": customer.get("email", ""),
                "customer_phone": customer.get("phone", ""),
                "sub_total": str(invoice.get("sub_total", 0)),
                "tax_total": str(invoice.get("tax_total", 0)),
                "total": str(total_amount),
                "paid": str(paid_amount),
                "outstanding": str(outstanding),
                "status": invoice.get("status", ""),
                "days_overdue": days_overdue,
                "aging_bucket": bucket,
                "comments": invoice.get("comments", ""),
                "terms": invoice.get("terms", ""),
            }

            aged_invoices.append(invoice_data)

            # Update totals
            if bucket == "current":
                aging_totals["current"] += outstanding
            elif bucket == "over":
                aging_totals["over"] += outstanding
            else:
                aging_totals["buckets"][bucket] += outstanding

            aging_totals["total"] += outstanding

        # Sort by days overdue (descending)
        aged_invoices.sort(key=lambda x: x["days_overdue"], reverse=True)

        # Group by customer
        customer_aging = defaultdict(
            lambda: {
                "current": Decimal("0.00"),
                "buckets": {bucket: Decimal("0.00") for bucket in aging_buckets},
                "over": Decimal("0.00"),
                "total": Decimal("0.00"),
                "invoices": [],
            }
        )

        for inv in aged_invoices:
            customer_id_key = inv.get("customer_id") or "unknown"
            customer_aging[customer_id_key]["invoices"].append(inv)
            outstanding = Decimal(inv["outstanding"])

            bucket = inv["aging_bucket"]
            if bucket == "current":
                customer_aging[customer_id_key]["current"] += outstanding
            elif bucket == "over":
                customer_aging[customer_id_key]["over"] += outstanding
            else:
                customer_aging[customer_id_key]["buckets"][bucket] += outstanding

            customer_aging[customer_id_key]["total"] += outstanding

        # Build customer summary
        customer_summary = []
        for cust_id, aging_data in customer_aging.items():
            if cust_id == "unknown":
                continue
            customer = customer_map.get(cust_id, {})
            customer_summary.append(
                {
                    "customer_id": cust_id,
                    "customer_name": customer.get("name", ""),
                    "customer_code": customer.get("code", ""),
                    "current": str(aging_data["current"]),
                    "buckets": {
                        str(k): str(v) for k, v in aging_data["buckets"].items()
                    },
                    "over": str(aging_data["over"]),
                    "total": str(aging_data["total"]),
                    "invoice_count": len(aging_data["invoices"]),
                }
            )

        # Sort by total outstanding (descending)
        customer_summary.sort(key=lambda x: Decimal(x["total"]), reverse=True)

        response_data = {
            "as_of_date": str(as_of_date),
            "aging_buckets": aging_buckets,
            "invoices": aged_invoices,
            "customer_summary": customer_summary,
            "totals": {
                "current": str(aging_totals["current"]),
                "buckets": {str(k): str(v) for k, v in aging_totals["buckets"].items()},
                "over": str(aging_totals["over"]),
                "total": str(aging_totals["total"]),
            },
            "statistics": {
                "total_invoices": len(aged_invoices),
                "total_customers": len(customer_summary),
                "average_days_overdue": (
                    sum(inv["days_overdue"] for inv in aged_invoices)
                    / len(aged_invoices)
                    if aged_invoices
                    else 0
                ),
            },
        }

        TransactionLogBase.log(
            transaction_type="AGED_INVOICES_RETRIEVED",
            user=user,
            message=f"Aged invoices retrieved for corporate {corporate_id} as of {as_of_date}",
            state_name="Success",
            extra={"as_of_date": str(as_of_date), "total_invoices": len(aged_invoices)},
            request=request,
        )

        return ResponseProvider(
            data=response_data,
            message="Aged invoices retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="AGED_INVOICES_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving aged invoices", code=500
        ).exception()


@csrf_exempt
def download_aged_invoices(request):
    """
    Download Aged Invoices Report as CSV.

    Expected data (optional):
    - as_of_date: Date in YYYY-MM-DD format (default: today)
    - aging_buckets: List of days [30, 60, 90, 120] (default: [30, 60, 90, 120])
    - customer_id: Filter by specific customer (optional)
    - format: "csv" (default: "csv")

    Returns:
    - CSV file download
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
        # Get aged invoices data
        aging_data = get_aged_invoices(request)
        if isinstance(aging_data, HttpResponse):
            return aging_data

        # Parse the response data
        from django.http import JsonResponse

        if hasattr(aging_data, "content"):
            import json

            response_data = json.loads(aging_data.content)
            invoices = response_data.get("data", {}).get("invoices", [])
        else:
            # Fallback: call get_aged_invoices logic directly
            registry = ServiceRegistry()
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
            invoices = []

        # Build CSV rows
        csv_rows = []
        for inv in invoices:
            csv_rows.append(
                {
                    "Invoice Number": inv.get("number", ""),
                    "Invoice Date": inv.get("invoice_date", ""),
                    "Due Date": inv.get("due_date", ""),
                    "Customer Name": inv.get("customer_name", ""),
                    "Customer Code": inv.get("customer_code", ""),
                    "Customer Email": inv.get("customer_email", ""),
                    "Sub Total": inv.get("sub_total", "0.00"),
                    "Tax Total": inv.get("tax_total", "0.00"),
                    "Total": inv.get("total", "0.00"),
                    "Paid": inv.get("paid", "0.00"),
                    "Outstanding": inv.get("outstanding", "0.00"),
                    "Days Overdue": inv.get("days_overdue", 0),
                    "Aging Bucket": inv.get("aging_bucket", ""),
                    "Status": inv.get("status", ""),
                }
            )

        # Sort by days overdue
        csv_rows.sort(key=lambda x: x.get("Days Overdue", 0), reverse=True)

        # Generate CSV
        response = HttpResponse(content_type="text/csv")
        as_of_date = data.get("as_of_date", date.today())
        filename = f"aged_invoices_{corporate_id}_{as_of_date}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.DictWriter(
            response,
            fieldnames=[
                "Invoice Number",
                "Invoice Date",
                "Due Date",
                "Customer Name",
                "Customer Code",
                "Customer Email",
                "Sub Total",
                "Tax Total",
                "Total",
                "Paid",
                "Outstanding",
                "Days Overdue",
                "Aging Bucket",
                "Status",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

        TransactionLogBase.log(
            transaction_type="AGED_INVOICES_EXPORTED",
            user=user,
            message=f"Aged invoices exported as CSV for corporate {corporate_id}",
            state_name="Success",
            request=request,
        )

        return response

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="AGED_INVOICES_EXPORT_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while exporting aged invoices", code=500
        ).exception()
