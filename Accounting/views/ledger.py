# ledger.py
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
def list_ledger(request):
    """
    List General Ledger transactions for accounts with running balances.

    Expected data (optional):
    - account_id: UUID of account to filter (optional)
    - start_date: Start date in YYYY-MM-DD format (optional)
    - end_date: End date in YYYY-MM-DD format (optional)
    - posted_only: Boolean (default: True)
    - page: Page number (default: 1)
    - limit: Items per page (default: 100)

    Returns:
    - 200: Ledger entries with running balances
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
        account_id = data.get("account_id")
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        posted_only = data.get("posted_only", True)
        page = int(data.get("page", 1))
        limit = int(data.get("limit", 100))
        offset = (page - 1) * limit

        start_date = _safe_parse_date(start_date_str) if start_date_str else None
        end_date = _safe_parse_date(end_date_str) if end_date_str else None

        # Build filter for journal entries
        je_filter = {"corporate_id": corporate_id}
        if posted_only:
            je_filter["is_posted"] = True

        # Filter by date range if provided
        if start_date or end_date:
            journal_entries = registry.database(
                model_name="JournalEntry", operation="filter", data=je_filter
            )
            filtered_je_ids = []
            for je in journal_entries:
                je_date = _safe_parse_date(je.get("date"))
                if je_date:
                    if start_date and je_date < start_date:
                        continue
                    if end_date and je_date > end_date:
                        continue
                    filtered_je_ids.append(je["id"])
            je_ids_set = set(filtered_je_ids)
        else:
            journal_entries = registry.database(
                model_name="JournalEntry", operation="filter", data=je_filter
            )
            je_ids_set = {je["id"] for je in journal_entries}

        # Get all journal entry lines
        all_lines = registry.database(
            model_name="JournalEntryLine", operation="filter", data={}
        )

        # Filter lines by journal entry IDs and account
        lines = []
        for line in all_lines:
            if line["journal_entry_id"] not in je_ids_set:
                continue
            if account_id and line["account_id"] != account_id:
                continue
            lines.append(line)

        # Get account information
        account_ids = {line["account_id"] for line in lines}
        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"id__in": list(account_ids), "corporate_id": corporate_id},
        )
        account_map = {acc["id"]: acc for acc in accounts}

        # Get journal entry information
        je_ids_list = list(je_ids_set)
        je_data_map = {
            je["id"]: je for je in journal_entries if je["id"] in je_ids_list
        }

        # Group by account and calculate running balances
        account_ledgers = defaultdict(list)
        for line in lines:
            account_id = line["account_id"]
            je_id = line["journal_entry_id"]
            je = je_data_map.get(je_id, {})
            account = account_map.get(account_id, {})

            account_ledgers[account_id].append(
                {"line": line, "journal_entry": je, "account": account}
            )

        # Build ledger entries with running balances
        ledger_entries = []
        for account_id, entries in account_ledgers.items():
            account = account_map.get(account_id, {})

            # Sort by date, then by journal entry ID
            entries.sort(
                key=lambda x: (
                    _safe_parse_date(x["journal_entry"].get("date")) or date.today(),
                    x["journal_entry"].get("id", ""),
                )
            )

            # Calculate opening balance (all transactions before start_date)
            opening_balance = Decimal("0.00")
            if start_date:
                opening_lines = []
                for entry in entries:
                    je_date = _safe_parse_date(entry["journal_entry"].get("date"))
                    if je_date and je_date < start_date:
                        opening_lines.append(entry["line"])

                for line in opening_lines:
                    debit = Decimal(str(line.get("debit", 0)))
                    credit = Decimal(str(line.get("credit", 0)))
                    opening_balance += debit - credit

            # Calculate running balance
            running_balance = opening_balance
            for entry in entries:
                line = entry["line"]
                je = entry["journal_entry"]
                debit = Decimal(str(line.get("debit", 0)))
                credit = Decimal(str(line.get("credit", 0)))
                running_balance += debit - credit

                je_date = _safe_parse_date(je.get("date"))
                if start_date and je_date and je_date < start_date:
                    continue
                if end_date and je_date and je_date > end_date:
                    continue

                ledger_entries.append(
                    {
                        "id": str(line["id"]),
                        "account_id": str(account_id),
                        "account_code": account.get("code", ""),
                        "account_name": account.get("name", ""),
                        "date": str(je_date) if je_date else "",
                        "journal_entry_reference": je.get("reference", ""),
                        "journal_entry_id": str(je_id),
                        "description": line.get("description", "")
                        or je.get("description", ""),
                        "debit": str(debit),
                        "credit": str(credit),
                        "balance": str(running_balance),
                        "status": "Posted" if je.get("is_posted", False) else "Draft",
                    }
                )

        # Sort by date and reference
        ledger_entries.sort(key=lambda x: (x["date"], x["journal_entry_reference"]))

        # Apply pagination
        total = len(ledger_entries)
        paginated_entries = ledger_entries[offset : offset + limit]

        TransactionLogBase.log(
            transaction_type="LEDGER_RETRIEVED",
            user=user,
            message=f"Ledger retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"total": total, "page": page, "limit": limit},
            request=request,
        )

        return ResponseProvider(
            data={
                "ledger_entries": paginated_entries,
                "total": total,
                "page": page,
                "limit": limit,
                "opening_balance": str(opening_balance) if account_id else None,
            },
            message="Ledger retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="LEDGER_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving ledger", code=500
        ).exception()


@csrf_exempt
def download_ledger(request):
    """
    Download General Ledger as CSV/XLS.

    Expected data (optional):
    - account_id: UUID of account to filter (optional)
    - start_date: Start date in YYYY-MM-DD format (optional)
    - end_date: End date in YYYY-MM-DD format (optional)
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
        account_id = data.get("account_id")
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        posted_only = data.get("posted_only", True)
        export_format = data.get("format", "csv").lower()

        start_date = _safe_parse_date(start_date_str) if start_date_str else None
        end_date = _safe_parse_date(end_date_str) if end_date_str else None

        # Build filter for journal entries
        je_filter = {"corporate_id": corporate_id}
        if posted_only:
            je_filter["is_posted"] = True

        # Get journal entries
        journal_entries = registry.database(
            model_name="JournalEntry", operation="filter", data=je_filter
        )

        # Filter by date range
        filtered_je_ids = []
        for je in journal_entries:
            je_date = _safe_parse_date(je.get("date"))
            if je_date:
                if start_date and je_date < start_date:
                    continue
                if end_date and je_date > end_date:
                    continue
                filtered_je_ids.append(je["id"])

        je_ids_set = set(filtered_je_ids)

        # Get journal entry lines
        all_lines = registry.database(
            model_name="JournalEntryLine", operation="filter", data={}
        )

        lines = [
            line
            for line in all_lines
            if line["journal_entry_id"] in je_ids_set
            and (not account_id or line["account_id"] == account_id)
        ]

        # Get account and journal entry info
        account_ids = {line["account_id"] for line in lines}
        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"id__in": list(account_ids), "corporate_id": corporate_id},
        )
        account_map = {acc["id"]: acc for acc in accounts}
        je_data_map = {je["id"]: je for je in journal_entries if je["id"] in je_ids_set}

        # Build ledger entries
        ledger_entries = []
        for line in lines:
            je = je_data_map.get(line["journal_entry_id"], {})
            account = account_map.get(line["account_id"], {})
            je_date = _safe_parse_date(je.get("date"))

            debit = Decimal(str(line.get("debit", 0)))
            credit = Decimal(str(line.get("credit", 0)))

            ledger_entries.append(
                {
                    "Date": str(je_date) if je_date else "",
                    "Account Code": account.get("code", ""),
                    "Account Name": account.get("name", ""),
                    "Reference": je.get("reference", ""),
                    "Description": line.get("description", "")
                    or je.get("description", ""),
                    "Debit": str(debit),
                    "Credit": str(credit),
                    "Status": "Posted" if je.get("is_posted", False) else "Draft",
                }
            )

        # Sort by date
        ledger_entries.sort(key=lambda x: x["Date"])

        # Generate CSV
        if export_format == "csv":
            response = HttpResponse(content_type="text/csv")
            filename = f"ledger_{corporate_id}_{date.today()}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            writer = csv.DictWriter(
                response,
                fieldnames=[
                    "Date",
                    "Account Code",
                    "Account Name",
                    "Reference",
                    "Description",
                    "Debit",
                    "Credit",
                    "Status",
                ],
            )
            writer.writeheader()
            writer.writerows(ledger_entries)

            TransactionLogBase.log(
                transaction_type="LEDGER_EXPORTED",
                user=user,
                message=f"Ledger exported as CSV for corporate {corporate_id}",
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
            transaction_type="LEDGER_EXPORT_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while exporting ledger", code=500
        ).exception()
