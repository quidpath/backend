# journal_actions.py
import uuid
from decimal import Decimal

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def post_journal_entry(request):
    """
    Post a journal entry (mark as posted after validation).

    Expected data:
    - id: UUID of the journal entry

    Returns:
    - 200: Journal entry posted successfully
    - 400: Bad request (missing ID, unbalanced entry, already posted)
    - 401: Unauthorized (user not authenticated)
    - 404: Journal entry not found
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

        journal_entry_id = data.get("id")
        if not journal_entry_id:
            return ResponseProvider(
                message="Journal entry ID is required", code=400
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

        journal_entry = journal_entries[0]

        # Check if already posted
        if journal_entry.get("is_posted", False):
            return ResponseProvider(
                message="Journal entry is already posted", code=400
            ).bad_request()

        # Get journal entry lines
        lines = registry.database(
            model_name="JournalEntryLine",
            operation="filter",
            data={"journal_entry_id": journal_entry_id},
        )

        if not lines:
            return ResponseProvider(
                message="Journal entry must have at least one line", code=400
            ).bad_request()

        # Validate balanced entry
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        for line in lines:
            total_debit += Decimal(str(line.get("debit", 0)))
            total_credit += Decimal(str(line.get("credit", 0)))

        if abs(total_debit - total_credit) > Decimal("0.01"):
            return ResponseProvider(
                message=f"Journal entry is unbalanced: total debit ({total_debit}) must equal total credit ({total_credit})",
                code=400,
            ).bad_request()

        # Post the journal entry
        with transaction.atomic():
            updated_entry = registry.database(
                model_name="JournalEntry",
                operation="update",
                instance_id=journal_entry_id,
                data={"is_posted": True},
            )

        # Serialize response
        serialized_journal_entry = {
            "id": str(updated_entry["id"]),
            "date": updated_entry["date"],
            "reference": updated_entry["reference"],
            "description": updated_entry.get("description", ""),
            "is_posted": updated_entry.get("is_posted", False),
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
            transaction_type="JOURNAL_ENTRY_POSTED",
            user=user,
            message=f"Journal entry {journal_entry['reference']} posted for corporate {corporate_id}",
            state_name="Completed",
            extra={
                "journal_entry_id": journal_entry_id,
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
            },
            request=request,
        )

        return ResponseProvider(
            message="Journal entry posted successfully",
            data=serialized_journal_entry,
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_POST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while posting journal entry", code=500
        ).exception()


@csrf_exempt
def unpost_journal_entry(request):
    """
    Unpost a journal entry (mark as draft).

    Expected data:
    - id: UUID of the journal entry

    Returns:
    - 200: Journal entry unposted successfully
    - 400: Bad request (missing ID, not posted)
    - 401: Unauthorized (user not authenticated)
    - 404: Journal entry not found
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

        journal_entry_id = data.get("id")
        if not journal_entry_id:
            return ResponseProvider(
                message="Journal entry ID is required", code=400
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

        journal_entry = journal_entries[0]

        # Check if not posted
        if not journal_entry.get("is_posted", False):
            return ResponseProvider(
                message="Journal entry is not posted", code=400
            ).bad_request()

        # Unpost the journal entry
        with transaction.atomic():
            updated_entry = registry.database(
                model_name="JournalEntry",
                operation="update",
                instance_id=journal_entry_id,
                data={"is_posted": False},
            )

        # Get lines
        lines = registry.database(
            model_name="JournalEntryLine",
            operation="filter",
            data={"journal_entry_id": journal_entry_id},
        )

        # Serialize response
        serialized_journal_entry = {
            "id": str(updated_entry["id"]),
            "date": updated_entry["date"],
            "reference": updated_entry["reference"],
            "description": updated_entry.get("description", ""),
            "is_posted": updated_entry.get("is_posted", False),
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
            transaction_type="JOURNAL_ENTRY_UNPOSTED",
            user=user,
            message=f"Journal entry {journal_entry['reference']} unposted for corporate {corporate_id}",
            state_name="Completed",
            extra={"journal_entry_id": journal_entry_id},
            request=request,
        )

        return ResponseProvider(
            message="Journal entry unposted successfully",
            data=serialized_journal_entry,
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_UNPOST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while unposting journal entry", code=500
        ).exception()


@csrf_exempt
def duplicate_journal_entry(request):
    """
    Duplicate a journal entry (create a new draft copy).

    Expected data:
    - id: UUID of the journal entry to duplicate

    Returns:
    - 201: Journal entry duplicated successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Journal entry not found
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

        journal_entry_id = data.get("id")
        if not journal_entry_id:
            return ResponseProvider(
                message="Journal entry ID is required", code=400
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

        journal_entry = journal_entries[0]

        # Get journal entry lines
        lines = registry.database(
            model_name="JournalEntryLine",
            operation="filter",
            data={"journal_entry_id": journal_entry_id},
        )

        if not lines:
            return ResponseProvider(
                message="Journal entry has no lines to duplicate", code=400
            ).bad_request()

        # Generate new reference
        original_reference = journal_entry.get("reference", "")
        new_reference = f"{original_reference}-COPY"

        # Check for existing reference
        existing = registry.database(
            model_name="JournalEntry",
            operation="filter",
            data={"corporate_id": corporate_id, "reference": new_reference},
        )
        if existing:
            # Add timestamp to make it unique
            import time

            new_reference = f"{original_reference}-COPY-{int(time.time())}"

        # Create duplicated journal entry
        with transaction.atomic():
            new_journal_entry_data = {
                "corporate_id": corporate_id,
                "date": journal_entry.get("date"),
                "reference": new_reference,
                "description": journal_entry.get("description", ""),
                "is_posted": False,  # Always create as draft
                "source_type": journal_entry.get("source_type", ""),
                "source_id": journal_entry.get("source_id"),
                "created_by_id": user_id,
            }
            new_journal_entry = registry.database(
                model_name="JournalEntry",
                operation="create",
                data=new_journal_entry_data,
            )

            # Duplicate lines
            new_lines = []
            for line in lines:
                line_data = {
                    "journal_entry_id": new_journal_entry["id"],
                    "account_id": line["account_id"],
                    "debit": str(line.get("debit", 0.00)),
                    "credit": str(line.get("credit", 0.00)),
                    "description": line.get("description", ""),
                }
                new_line = registry.database(
                    model_name="JournalEntryLine", operation="create", data=line_data
                )
                new_lines.append(new_line)

        # Serialize response
        serialized_journal_entry = {
            "id": str(new_journal_entry["id"]),
            "date": new_journal_entry["date"],
            "reference": new_journal_entry["reference"],
            "description": new_journal_entry.get("description", ""),
            "is_posted": new_journal_entry.get("is_posted", False),
            "lines": [
                {
                    "id": str(line["id"]),
                    "account_id": str(line["account_id"]),
                    "debit": str(line["debit"]),
                    "credit": str(line["credit"]),
                    "description": line.get("description", ""),
                }
                for line in new_lines
            ],
        }

        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_DUPLICATED",
            user=user,
            message=f"Journal entry {journal_entry['reference']} duplicated to {new_reference} for corporate {corporate_id}",
            state_name="Completed",
            extra={
                "original_journal_entry_id": journal_entry_id,
                "new_journal_entry_id": new_journal_entry["id"],
            },
            request=request,
        )

        return ResponseProvider(
            message="Journal entry duplicated successfully",
            data=serialized_journal_entry,
            code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="JOURNAL_ENTRY_DUPLICATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while duplicating journal entry", code=500
        ).exception()
