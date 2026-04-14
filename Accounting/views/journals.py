# journals.py
import uuid
from decimal import Decimal

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.decorators import require_module_permission
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.pagination import apply_search, paginate_queryset


@csrf_exempt
def create_journal_entry(request):
    """
    Create a new journal entry with associated lines for the user's corporate.

    Expected data:
    - date: Date of the journal entry (YYYY-MM-DD)
    - reference: Unique reference number (e.g., 'JE-001')
    - description: Journal entry description (optional)
    - lines: List of line items, each with:
        - account_id: UUID of the account
        - debit: Decimal amount (optional, default 0.00)
        - credit: Decimal amount (optional, default 0.00)
        - description: Line description (optional)

    Returns:
    - 201: Journal entry created successfully
    - 400: Bad request (missing/invalid data, unbalanced entry)
    - 401: Unauthorized (user not authenticated)
    - 404: Account or corporate not found
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

        # Validate user corporate association
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

        # Validate required fields
        required_fields = ["date", "reference", "lines"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"{field.replace('_', ' ').title()} is required", code=400
                ).bad_request()

        # Validate lines
        if not isinstance(data["lines"], list) or not data["lines"]:
            return ResponseProvider(
                message="At least one line item is required", code=400
            ).bad_request()

        # Validate each line and account existence
        total_debit = Decimal(0)
        total_credit = Decimal(0)
        for line in data["lines"]:
            if "account_id" not in line:
                return ResponseProvider(
                    message="Account ID is required for each line", code=400
                ).bad_request()
            accounts = registry.database(
                model_name="Account",
                operation="filter",
                data={
                    "id": line["account_id"],
                    "corporate_id": corporate_id,
                    "is_active": True,
                },
            )
            if not accounts:
                return ResponseProvider(
                    message=f"Account {line['account_id']} not found or inactive",
                    code=404,
                ).bad_request()
            debit = Decimal(str(line.get("debit", 0.00)))
            credit = Decimal(str(line.get("credit", 0.00)))
            if debit < 0 or credit < 0:
                return ResponseProvider(
                    message="Debit and credit amounts cannot be negative", code=400
                ).bad_request()
            if debit > 0 and credit > 0:
                return ResponseProvider(
                    message="Line cannot have both debit and credit", code=400
                ).bad_request()
            total_debit += debit
            total_credit += credit

        # Validate balanced entry with tolerance for rounding
        if abs(total_debit - total_credit) > Decimal("0.01"):
            return ResponseProvider(
                message=f"Journal entry is unbalanced: total debit ({total_debit}) must equal total credit ({total_credit})",
                code=400,
            ).bad_request()

        # Create journal entry and lines within a transaction
        with transaction.atomic():
            journal_entry_data = {
                "corporate_id": corporate_id,
                "date": data["date"],
                "reference": data["reference"],
                "description": data.get("description", ""),
                "is_posted": False,
            }
            journal_entry = registry.database(
                model_name="JournalEntry", operation="create", data=journal_entry_data
            )

            # Create journal entry lines
            for line in data["lines"]:
                line_data = {
                    "journal_entry_id": journal_entry["id"],
                    "account_id": line["account_id"],
                    "debit": str(line.get("debit", 0.00)),
                    "credit": str(line.get("credit", 0.00)),
                    "description": line.get("description", ""),
                }
                registry.database(
                    model_name="JournalEntryLine", operation="create", data=line_data
                )

        # Log transaction
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_CREATED",
            user=user,
            message=f"Journal entry {journal_entry['reference']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={
                "journal_entry_id": journal_entry["id"],
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
            },
            request=request,
        )

        # Serialize response
        serialized_journal_entry = {
            "id": str(journal_entry["id"]),
            "date": journal_entry["date"],
            "reference": journal_entry["reference"],
            "description": journal_entry.get("description", ""),
            "is_posted": journal_entry.get("is_posted", False),
            "lines": [
                {
                    "id": str(line["id"]),
                    "account_id": str(line["account_id"]),
                    "debit": str(line["debit"]),
                    "credit": str(line["credit"]),
                    "description": line.get("description", ""),
                }
                for line in registry.database(
                    model_name="JournalEntryLine",
                    operation="filter",
                    data={"journal_entry_id": journal_entry["id"]},
                )
            ],
        }

        return ResponseProvider(
            message="Journal entry created successfully",
            data=serialized_journal_entry,
            code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating journal entry", code=500
        ).exception()


@csrf_exempt
@require_module_permission("finance")
def list_journal_entries(request):
    """
    List all journal entries for the user's corporate.

    Returns:
    - 200: List of journal entries with total count
    - 400: Bad request (missing corporate)
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

        # Check if user is superuser (works for both dict and model)
        if isinstance(user, dict):
            is_superuser = user.get("is_superuser", False)
        else:
            is_superuser = getattr(user, "is_superuser", False)

        # Validate user corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )

        if not corporate_users and not is_superuser:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        # For superusers, get all journal entries; for regular users, filter by corporate
        if is_superuser:
            journal_entries = registry.database(
                model_name="JournalEntry",
                operation="filter",
                data={},
            )
            corporate_id = None
        else:
            corporate_id = corporate_users[0]["corporate_id"]
            if not corporate_id:
                return ResponseProvider(
                    message="Corporate ID not found", code=400
                ).bad_request()

            journal_entries = registry.database(
                model_name="JournalEntry",
                operation="filter",
                data={"corporate_id": corporate_id},
            )

        # Serialize journal entries (without lines for performance)
        serialized_entries = []
        for entry in journal_entries:
            serialized_entries.append({
                "id": str(entry["id"]),
                "date": str(entry["date"]) if entry.get("date") else "",
                "reference": entry["reference"],
                "description": entry.get("description", ""),
                "is_posted": entry.get("is_posted", False),
                "lines": [],
            })

        # Apply search
        search = request.GET.get("search", "").strip()
        if search:
            serialized_entries = apply_search(
                serialized_entries, search,
                fields=["reference", "description"]
            )

        # Paginate
        page_data = paginate_queryset(serialized_entries, request)

        # Load lines only for current page
        for entry in page_data["results"]:
            lines = registry.database(
                model_name="JournalEntryLine",
                operation="filter",
                data={"journal_entry_id": entry["id"]},
            )
            entry["lines"] = [
                {
                    "id": str(line["id"]),
                    "account_id": str(line["account_id"]),
                    "debit": str(line["debit"]),
                    "credit": str(line["credit"]),
                    "description": line.get("description", ""),
                }
                for line in lines
            ]

        total = page_data["total"]

        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} journal entries for corporate {corporate_id}",
            state_name="Success",
            extra={"total": total},
            request=request,
        )

        return ResponseProvider(
            data={
                "journal_entries": page_data["results"],
                "total": page_data["total"],
                "page": page_data["page"],
                "page_size": page_data["page_size"],
                "total_pages": page_data["total_pages"],
            },
            message="Journal entries retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving journal entries", code=500
        ).exception()


@csrf_exempt
def get_journal_entry(request):
    """
    Get a single journal entry by ID for the user's corporate.

    Expected data:
    - id: UUID of the journal entry

    Returns:
    - 200: Journal entry retrieved successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Journal entry not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        journal_entry_id = data.get("id")
        if not journal_entry_id:
            return ResponseProvider(
                message="Journal entry ID is required", code=400
            ).bad_request()

        registry = ServiceRegistry()

        # Validate user corporate association
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

        # Fetch journal entry
        journal_entries = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"id": journal_entry_id, "corporate_id": corporate_id},
        )
        if not journal_entries:
            return ResponseProvider(
                message="Journal entry not found for this corporate", code=404
            ).bad_request()

        journal_entry = journal_entries[0]

        # Fetch lines
        lines = registry.database(
            model_name="JournalEntryLine",
            operation="filter",
            data={"journal_entry_id": journal_entry["id"]},
        )

        serialized_journal_entry = {
            "id": str(journal_entry["id"]),
            "date": journal_entry["date"],
            "reference": journal_entry["reference"],
            "description": journal_entry.get("description", ""),
            "is_posted": journal_entry.get("is_posted", False),
            "lines": [
                {
                    "id": str(line["id"]),
                    "account_id": str(line["account_id"]),
                    "debit": str(line["debit"]),
                    "credit": str(line["credit"]),
                    "description": line.get("description", ""),
                }
                for line in lines
            ],
        }

        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_GET_SUCCESS",
            user=user,
            message=f"Journal entry {journal_entry['reference']} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"journal_entry_id": journal_entry["id"]},
            request=request,
        )

        return ResponseProvider(
            message="Journal entry retrieved successfully",
            data=serialized_journal_entry,
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_GET_FAILED",
            user=user if "user" in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving journal entry", code=500
        ).exception()


@csrf_exempt
def update_journal_entry(request):
    """
    Update an existing journal entry for the user's corporate.

    Expected data:
    - id: UUID of the journal entry
    - date: Date of the journal entry (YYYY-MM-DD)
    - reference: Unique reference number (e.g., 'JE-001')
    - description: Journal entry description (optional)
    - lines: List of line items, each with:
        - id: UUID of the line (optional for new lines)
        - account_id: UUID of the account
        - debit: Decimal amount (optional, default 0.00)
        - credit: Decimal amount (optional, default 0.00)
        - description: Line description (optional)

    Returns:
    - 200: Journal entry updated successfully
    - 400: Bad request (missing/invalid data, unbalanced entry)
    - 401: Unauthorized (user not authenticated)
    - 404: Journal entry or account not found
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

        # Validate user corporate association
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

        # Validate required fields
        required_fields = ["id", "date", "reference", "lines"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"{field.replace('_', ' ').title()} is required", code=400
                ).bad_request()

        # Validate journal entry existence
        journal_entries = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id},
        )
        if not journal_entries:
            return ResponseProvider(
                message="Journal entry not found for this corporate", code=404
            ).bad_request()
        journal_entry_id = journal_entries[0]["id"]

        # Validate lines
        if not isinstance(data["lines"], list) or not data["lines"]:
            return ResponseProvider(
                message="At least one line item is required", code=400
            ).bad_request()

        # Validate each line and account existence
        total_debit = Decimal(0)
        total_credit = Decimal(0)
        for line in data["lines"]:
            if "account_id" not in line:
                return ResponseProvider(
                    message="Account ID is required for each line", code=400
                ).bad_request()
            accounts = registry.database(
                model_name="Account",
                operation="filter",
                data={
                    "id": line["account_id"],
                    "corporate_id": corporate_id,
                    "is_active": True,
                },
            )
            if not accounts:
                return ResponseProvider(
                    message=f"Account {line['account_id']} not found or inactive",
                    code=404,
                ).bad_request()
            debit = Decimal(str(line.get("debit", 0.00)))
            credit = Decimal(str(line.get("credit", 0.00)))
            if debit < 0 or credit < 0:
                return ResponseProvider(
                    message="Debit and credit amounts cannot be negative", code=400
                ).bad_request()
            if debit > 0 and credit > 0:
                return ResponseProvider(
                    message="Line cannot have both debit and credit", code=400
                ).bad_request()
            total_debit += debit
            total_credit += credit

        # Validate balanced entry with tolerance for rounding
        if abs(total_debit - total_credit) > Decimal("0.01"):
            return ResponseProvider(
                message=f"Journal entry is unbalanced: total debit ({total_debit}) must equal total credit ({total_credit})",
                code=400,
            ).bad_request()

        # Update journal entry and lines within a transaction
        with transaction.atomic():
            # Update journal entry
            journal_entry_data = {
                "date": data["date"],
                "reference": data["reference"],
                "description": data.get("description", ""),
                "is_posted": journal_entries[0].get(
                    "is_posted", False
                ),  # Preserve posting status
            }
            journal_entry = registry.database(
                model_name="JournalEntry",
                operation="update",
                instance_id=journal_entry_id,
                data=journal_entry_data,
            )

            # Delete existing lines
            registry.database(
                model_name="JournalEntryLine",
                operation="delete",
                data={"journal_entry_id": journal_entry_id},
            )

            # Create new lines
            for line in data["lines"]:
                line_data = {
                    "journal_entry_id": journal_entry_id,
                    "account_id": line["account_id"],
                    "debit": str(line.get("debit", 0.00)),
                    "credit": str(line.get("credit", 0.00)),
                    "description": line.get("description", ""),
                }
                registry.database(
                    model_name="JournalEntryLine", operation="create", data=line_data
                )

        # Log transaction
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_UPDATED",
            user=user,
            message=f"Journal entry {journal_entry['reference']} updated for corporate {corporate_id}",
            state_name="Completed",
            extra={
                "journal_entry_id": journal_entry["id"],
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
            },
            request=request,
        )

        # Serialize response
        serialized_journal_entry = {
            "id": str(journal_entry["id"]),
            "date": journal_entry["date"],
            "reference": journal_entry["reference"],
            "description": journal_entry.get("description", ""),
            "is_posted": journal_entry.get("is_posted", False),
            "lines": [
                {
                    "id": str(line["id"]),
                    "account_id": str(line["account_id"]),
                    "debit": str(line["debit"]),
                    "credit": str(line["credit"]),
                    "description": line.get("description", ""),
                }
                for line in registry.database(
                    model_name="JournalEntryLine",
                    operation="filter",
                    data={"journal_entry_id": journal_entry["id"]},
                )
            ],
        }

        return ResponseProvider(
            message="Journal entry updated successfully",
            data=serialized_journal_entry,
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while updating journal entry", code=500
        ).exception()


@csrf_exempt
def delete_journal_entry(request):
    """
    Delete a journal entry by ID for the user's corporate.

    Expected data:
    - id: UUID of the journal entry

    Returns:
    - 200: Journal entry deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Journal entry not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        journal_entry_id = data.get("id")
        if not journal_entry_id:
            return ResponseProvider(
                message="Journal entry ID is required", code=400
            ).bad_request()

        registry = ServiceRegistry()

        # Validate user corporate association
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

        # Validate journal entry existence
        journal_entries = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"id": journal_entry_id, "corporate_id": corporate_id},
        )
        if not journal_entries:
            return ResponseProvider(
                message="Journal entry not found for this corporate", code=404
            ).bad_request()

        # Delete journal entry and its lines within a transaction
        with transaction.atomic():
            # Delete lines first
            registry.database(
                model_name="JournalEntryLine",
                operation="delete",
                data={"journal_entry_id": journal_entry_id},
            )
            # Delete journal entry
            registry.database(
                model_name="JournalEntry",
                operation="delete",
                instance_id=journal_entry_id,
            )

            TransactionLogBase.log(
                transaction_type="JOURNAL_ENTRY_DELETED",
                user=user,
                message=f"Journal entry {journal_entry_id} deleted for corporate {corporate_id}",
                state_name="Completed",
                extra={"journal_entry_id": journal_entry_id},
                request=request,
            )

        return ResponseProvider(
            message="Journal entry deleted successfully",
            data={"journal_entry_id": journal_entry_id},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while deleting journal entry", code=500
        ).exception()
