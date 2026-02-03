# trial_balance.py
import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
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
def get_trial_balance(request):
    """
    Retrieve Trial Balance for the user's corporate as of a specific date.

    Expected data (optional):
    - as_of_date: Date in YYYY-MM-DD format (default: today)
    - posted_only: Boolean (default: True)

    Returns:
    - 200: Trial balance data with debit/credit totals per account + grand totals
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

        # Parse as_of_date
        as_of_date_raw = data.get("as_of_date")
        posted_only = data.get("posted_only", True)

        if isinstance(as_of_date_raw, str):
            as_of_date = _safe_parse_date(as_of_date_raw) or date.today()
        elif isinstance(as_of_date_raw, datetime):
            as_of_date = as_of_date_raw.date()
        elif isinstance(as_of_date_raw, date):
            as_of_date = as_of_date_raw
        else:
            as_of_date = date.today()

        # Get all journal entries up to as_of_date
        je_filter = {"corporate_id": corporate_id}
        if posted_only:
            je_filter["is_posted"] = True

        journal_entries = registry.database(
            model_name="JournalEntry", operation="filter", data=je_filter
        )

        # Filter journal entries by date
        relevant_je = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date and je_date <= as_of_date:
                relevant_je.append(je)

        je_ids = {je["id"] for je in relevant_je}

        # Get journal entry lines
        all_lines = registry.database(
            model_name="JournalEntryLine", operation="filter", data={}
        )
        lines = [line for line in all_lines if line["journal_entry_id"] in je_ids]

        # Calculate balances per account
        account_balances = defaultdict(
            lambda: {"debit": Decimal("0.00"), "credit": Decimal("0.00")}
        )

        for line in lines:
            account_id = line["account_id"]
            debit = Decimal(str(line.get("debit", 0)))
            credit = Decimal(str(line.get("credit", 0)))
            account_balances[account_id]["debit"] += debit
            account_balances[account_id]["credit"] += credit

        # Get account information
        account_ids = list(account_balances.keys())
        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={
                "id__in": account_ids,
                "corporate_id": corporate_id,
                "is_active": True,
            },
        )
        account_map = {acc["id"]: acc for acc in accounts}

        # Build trial balance entries
        tb_entries = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for account_id, balances in account_balances.items():
            account = account_map.get(account_id)
            if not account:
                continue

            debit = balances["debit"]
            credit = balances["credit"]
            total_debit += debit
            total_credit += credit

            # Get account type for normal balance adjustment
            account_type = registry.database(
                model_name="AccountType",
                operation="filter",
                data={"id": account.get("account_type_id")},
            )
            normal_balance = "DEBIT"
            if account_type:
                normal_balance = account_type[0].get("normal_balance", "DEBIT")

            # For credit-normal accounts, show credit as positive
            if normal_balance == "CREDIT":
                # Swap for display if needed
                pass

            tb_entries.append(
                {
                    "id": str(account_id),
                    "account_code": account.get("code", ""),
                    "account_name": account.get("name", ""),
                    "debit": str(debit),
                    "credit": str(credit),
                    "balance": (
                        str(debit - credit)
                        if normal_balance == "DEBIT"
                        else str(credit - debit)
                    ),
                }
            )

        # Sort by account code
        tb_entries.sort(key=lambda x: x["account_code"])

        # Verify totals balance
        is_balanced = abs(total_debit - total_credit) < Decimal("0.01")

        tb_data = {
            "as_of_date": str(as_of_date),
            "entries": tb_entries,
            "totals": {
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
                "difference": str(total_debit - total_credit),
                "is_balanced": is_balanced,
            },
        }

        TransactionLogBase.log(
            transaction_type="TRIAL_BALANCE_RETRIEVED",
            user=user,
            message=f"Trial balance retrieved for corporate {corporate_id} as of {as_of_date}",
            state_name="Success",
            extra={"as_of_date": str(as_of_date), "is_balanced": is_balanced},
            request=request,
        )

        return ResponseProvider(
            data=tb_data,
            message="Trial balance retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TRIAL_BALANCE_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving trial balance", code=500
        ).exception()


@csrf_exempt
def download_trial_balance(request):
    """
    Download Trial Balance as CSV/XLS.

    Expected data (optional):
    - as_of_date: Date in YYYY-MM-DD format (default: today)
    - posted_only: Boolean (default: True)
    - format: "csv" or "xls" (default: "csv")

    Returns:
    - CSV/XLS file download
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
        posted_only = data.get("posted_only", True)
        export_format = data.get("format", "csv").lower()

        if isinstance(as_of_date_raw, str):
            as_of_date = _safe_parse_date(as_of_date_raw) or date.today()
        elif isinstance(as_of_date_raw, datetime):
            as_of_date = as_of_date_raw.date()
        elif isinstance(as_of_date_raw, date):
            as_of_date = as_of_date_raw
        else:
            as_of_date = date.today()

        # Get trial balance data (reuse logic from get_trial_balance)
        je_filter = {"corporate_id": corporate_id}
        if posted_only:
            je_filter["is_posted"] = True

        journal_entries = registry.database(
            model_name="JournalEntry", operation="filter", data=je_filter
        )

        relevant_je = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date and je_date <= as_of_date:
                relevant_je.append(je)

        je_ids = {je["id"] for je in relevant_je}

        all_lines = registry.database(
            model_name="JournalEntryLine", operation="filter", data={}
        )
        lines = [line for line in all_lines if line["journal_entry_id"] in je_ids]

        account_balances = defaultdict(
            lambda: {"debit": Decimal("0.00"), "credit": Decimal("0.00")}
        )
        for line in lines:
            account_id = line["account_id"]
            debit = Decimal(str(line.get("debit", 0)))
            credit = Decimal(str(line.get("credit", 0)))
            account_balances[account_id]["debit"] += debit
            account_balances[account_id]["credit"] += credit

        account_ids = list(account_balances.keys())
        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={
                "id__in": account_ids,
                "corporate_id": corporate_id,
                "is_active": True,
            },
        )
        account_map = {acc["id"]: acc for acc in accounts}

        # Build CSV rows
        csv_rows = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for account_id, balances in account_balances.items():
            account = account_map.get(account_id)
            if not account:
                continue

            debit = balances["debit"]
            credit = balances["credit"]
            total_debit += debit
            total_credit += credit

            csv_rows.append(
                {
                    "Account Code": account.get("code", ""),
                    "Account Name": account.get("name", ""),
                    "Debit": str(debit),
                    "Credit": str(credit),
                }
            )

        csv_rows.sort(key=lambda x: x["Account Code"])

        # Add totals row
        csv_rows.append(
            {
                "Account Code": "",
                "Account Name": "TOTAL",
                "Debit": str(total_debit),
                "Credit": str(total_credit),
            }
        )

        # Generate CSV
        if export_format == "csv":
            response = HttpResponse(content_type="text/csv")
            filename = f"trial_balance_{corporate_id}_{as_of_date}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            writer = csv.DictWriter(
                response, fieldnames=["Account Code", "Account Name", "Debit", "Credit"]
            )
            writer.writeheader()
            writer.writerows(csv_rows)

            TransactionLogBase.log(
                transaction_type="TRIAL_BALANCE_EXPORTED",
                user=user,
                message=f"Trial balance exported as CSV for corporate {corporate_id}",
                state_name="Success",
                request=request,
            )

            return response
        else:
            return ResponseProvider(
                message=f"Export format '{export_format}' not supported. Use 'csv'.",
                code=400,
            ).bad_request()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TRIAL_BALANCE_EXPORT_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while exporting trial balance", code=500
        ).exception()
