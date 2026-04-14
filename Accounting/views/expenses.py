# expenses.py
import ast
import json
import re
import uuid
from collections import Counter
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.AccountingService import AccountingService
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.pagination import apply_search, paginate_queryset


@csrf_exempt
def create_expense(request):
    """
    Create a new expense entry and automatically create journal entry.

    Expected data:
    - date: Expense date (YYYY-MM-DD)
    - reference: Expense reference number
    - description: Expense description
    - category: Expense category (OPERATING, ADMINISTRATIVE, SELLING, FINANCIAL, OTHER)
    - amount: Expense amount (excluding tax)
    - expense_account_id: Account to debit for the expense
    - payment_account_id: Account to credit for payment (Cash/Bank)
    - vendor_id: Vendor ID (optional)
    - tax_rate_id: Tax rate ID (optional)
    - tax_amount: Tax amount (optional, calculated if tax_rate provided)
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
        accounting_service = AccountingService(registry)

        # Get corporate association
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

        # Validate required fields — reference is now optional (auto-generated)
        required_fields = ["date", "description", "category", "amount"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"{field.replace('_', ' ').title()} is required", code=400
                ).bad_request()

        # Auto-generate reference if not provided
        import uuid as _uuid
        reference = data.get("reference", "").strip()
        if not reference:
            from datetime import date as _date
            today = _date.today().strftime("%Y%m%d")
            short_id = str(_uuid.uuid4())[:6].upper()
            reference = f"EXP-{today}-{short_id}"

        # Validate reference uniqueness
        existing_expenses = registry.database(
            model_name="Expense",
            operation="filter",
            data={"reference": reference, "corporate_id": corporate_id},
        )
        if existing_expenses:
            # Append extra uniqueness if collision
            reference = f"{reference}-{str(_uuid.uuid4())[:4].upper()}"

        # Always auto-resolve expense and payment accounts via AccountingService
        # This ensures accounts exist (creates them if needed) and journal entries work
        default_accounts = accounting_service.get_or_create_default_accounts(
            corporate_id,
            required=["operating_expense", "cash", "vat_receivable"],
        )

        # Map category to the right expense account
        category = data.get("category", "OPERATING")
        category_account_map = {
            "OPERATING": "operating_expense",
            "ADMINISTRATIVE": "operating_expense",
            "SELLING": "operating_expense",
            "FINANCIAL": "operating_expense",
            "OTHER": "operating_expense",
        }
        expense_account_key = category_account_map.get(category, "operating_expense")

        # User can override with explicit account IDs
        expense_account_id = data.get("expense_account_id") or default_accounts.get(expense_account_key)
        payment_account_id = data.get("payment_account_id") or default_accounts.get("cash")

        if not expense_account_id or not payment_account_id:
            return ResponseProvider(
                message="Could not resolve expense or payment accounts. Please seed default accounts first.",
                code=400,
            ).bad_request()

        # Validate vendor if provided
        if data.get("vendor_id"):
            vendors = registry.database(
                model_name="Vendor",
                operation="filter",
                data={"id": data["vendor_id"], "corporate_id": corporate_id},
            )
            if not vendors:
                return ResponseProvider(message="Vendor not found", code=404).bad_request()

        # Calculate tax amount if tax rate provided
        tax_amount = Decimal(str(data.get("tax_amount", 0)))
        if data.get("tax_rate_id") and not tax_amount:
            tax_rates = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": data["tax_rate_id"]},
            )
            if tax_rates:
                tax_rate = tax_rates[0]
                if tax_rate["name"] == "general_rated":
                    tax_amount = Decimal(str(data["amount"])) * Decimal("0.16")

        with transaction.atomic():
            expense_data = {
                "corporate_id": corporate_id,
                "date": data["date"],
                "reference": reference,
                "description": data["description"],
                "category": data["category"],
                "amount": str(data["amount"]),
                "expense_account_id": expense_account_id,
                "payment_account_id": payment_account_id,
                "vendor_id": data.get("vendor_id"),
                "tax_amount": str(tax_amount),
                "tax_rate_id": data.get("tax_rate_id"),
                "created_by_id": user_id,
                "is_posted": True,
            }

            expense = registry.database(
                model_name="Expense", operation="create", data=expense_data
            )

            # Create journal entry — accounts are guaranteed to exist
            journal_entry = None
            try:
                journal_entry = accounting_service.create_expense_journal_entry(
                    expense["id"], user
                )
                registry.database(
                    model_name="Expense",
                    operation="update",
                    instance_id=expense["id"],
                    data={"journal_entry_id": journal_entry["id"]},
                )
            except Exception as je_err:
                TransactionLogBase.log(
                    transaction_type="EXPENSE_JOURNAL_ENTRY_FAILED",
                    user=user,
                    message=str(je_err),
                    state_name="Warning",
                    request=request,
                )

        TransactionLogBase.log(
            transaction_type="EXPENSE_CREATED",
            user=user,
            message=f"Expense {expense['reference']} created and posted",
            state_name="Completed",
            extra={"expense_id": expense["id"]},
            request=request,
        )

        serialized_expense = {
            "id": str(expense["id"]),
            "reference": expense["reference"],
            "description": expense["description"],
            "date": expense["date"],
            "category": expense["category"],
            "amount": float(expense["amount"]),
            "tax_amount": float(expense.get("tax_amount", 0)),
            "total_amount": float(
                Decimal(str(expense["amount"]))
                + Decimal(str(expense.get("tax_amount", 0)))
            ),
            "expense_account_id": str(expense["expense_account_id"]),
            "payment_account_id": str(expense["payment_account_id"]),
            "vendor_id": (
                str(expense["vendor_id"]) if expense.get("vendor_id") else None
            ),
            "is_posted": expense.get("is_posted", False),
            "journal_entry_id": str(journal_entry["id"]) if journal_entry else None,
        }

        return ResponseProvider(
            message="Expense created and posted successfully",
            data=serialized_expense,
            code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="EXPENSE_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating expense", code=500
        ).exception()


@csrf_exempt
def list_expenses(request):
    """
    List all expenses for the user's corporate.

    Returns:
    - 200: List of expenses with total count and category counts
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

        # Get expenses
        expenses = registry.database(
            model_name="Expense",
            operation="filter",
            data={"corporate_id": corporate_id},
        )

        # Serialize
        serialized_expenses = [
            {
                "id": str(expense["id"]),
                "reference": expense["reference"],
                "description": expense["description"],
                "date": str(expense["date"]) if expense.get("date") else "",
                "category": expense["category"],
                "amount": float(expense["amount"]),
                "tax_amount": float(expense.get("tax_amount", 0)),
                "total_amount": float(
                    Decimal(str(expense["amount"]))
                    + Decimal(str(expense.get("tax_amount", 0)))
                ),
                "expense_account_id": str(expense["expense_account_id"]),
                "payment_account_id": str(expense["payment_account_id"]),
                "vendor_id": (
                    str(expense["vendor_id"]) if expense.get("vendor_id") else None
                ),
                "is_posted": expense.get("is_posted", False),
            }
            for expense in expenses
        ]

        # Category counts on full unfiltered set
        categories = [exp["category"] for exp in expenses]
        category_counts = dict(Counter(categories))

        # Apply search
        search = request.GET.get("search", "").strip()
        if search:
            serialized_expenses = apply_search(
                serialized_expenses, search,
                fields=["reference", "description", "category"]
            )

        # Apply category filter
        category_filter = request.GET.get("category", "").strip().upper()
        if category_filter and category_filter != "ALL":
            serialized_expenses = [e for e in serialized_expenses if e["category"] == category_filter]

        # Paginate
        page_data = paginate_queryset(serialized_expenses, request)
        total = page_data["total"]

        TransactionLogBase.log(
            transaction_type="EXPENSE_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} expenses",
            state_name="Success",
            extra={"category_counts": category_counts},
            request=request,
        )

        return ResponseProvider(
            data={
                "expenses": page_data["results"],
                "total": page_data["total"],
                "page": page_data["page"],
                "page_size": page_data["page_size"],
                "total_pages": page_data["total_pages"],
                "category_counts": category_counts,
            },
            message="Expenses retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="EXPENSE_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving expenses", code=500
        ).exception()


@csrf_exempt
def get_expense(request):
    """
    Get a single expense by ID.

    Expected data:
    - id: UUID of the expense

    Returns:
    - 200: Expense retrieved successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Expense not found
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

        expense_id = data.get("id")
        if not expense_id:
            return ResponseProvider(
                message="Expense ID is required", code=400
            ).bad_request()

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

        expenses = registry.database(
            model_name="Expense",
            operation="filter",
            data={"id": expense_id, "corporate_id": corporate_id},
        )
        if not expenses:
            return ResponseProvider(message="Expense not found", code=404).bad_request()

        expense = expenses[0]

        serialized_expense = {
            "id": str(expense["id"]),
            "reference": expense["reference"],
            "description": expense["description"],
            "date": expense["date"],
            "category": expense["category"],
            "amount": float(expense["amount"]),
            "tax_amount": float(expense.get("tax_amount", 0)),
            "total_amount": float(
                Decimal(str(expense["amount"]))
                + Decimal(str(expense.get("tax_amount", 0)))
            ),
            "expense_account_id": str(expense["expense_account_id"]),
            "payment_account_id": str(expense["payment_account_id"]),
            "vendor_id": (
                str(expense["vendor_id"]) if expense.get("vendor_id") else None
            ),
            "tax_rate_id": (
                str(expense["tax_rate_id"]) if expense.get("tax_rate_id") else None
            ),
            "is_posted": expense.get("is_posted", False),
            "journal_entry_id": (
                str(expense["journal_entry_id"])
                if expense.get("journal_entry_id")
                else None
            ),
        }

        TransactionLogBase.log(
            transaction_type="EXPENSE_GET_SUCCESS",
            user=user,
            message=f"Expense {expense_id} retrieved",
            state_name="Success",
            extra={"expense_id": expense_id},
            request=request,
        )

        return ResponseProvider(
            message="Expense retrieved successfully", data=serialized_expense, code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="EXPENSE_GET_FAILED",
            user=user if "user" in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving expense", code=500
        ).exception()


@csrf_exempt
def update_expense(request):
    """
    Update an existing expense entry.

    Expected data:
    - id: UUID of the expense
    - date: Expense date (YYYY-MM-DD)
    - reference: Expense reference number
    - description: Expense description
    - category: Expense category
    - amount: Expense amount (excluding tax)
    - expense_account_id: Account to debit for the expense
    - payment_account_id: Account to credit for payment
    - vendor_id: Vendor ID (optional)
    - tax_rate_id: Tax rate ID (optional)
    - tax_amount: Tax amount (optional)
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
        accounting_service = AccountingService(registry)

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

        # Validate required fields — account IDs are optional (auto-resolved)
        required_fields = ["id", "date", "description", "category", "amount"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"{field.replace('_', ' ').title()} is required", code=400
                ).bad_request()

        # Validate expense existence
        expenses = registry.database(
            model_name="Expense",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id},
        )
        if not expenses:
            return ResponseProvider(message="Expense not found", code=404).bad_request()

        expense_id = expenses[0]["id"]
        old_expense = expenses[0]

        # Auto-resolve accounts (use provided or fall back to defaults)
        default_accounts = accounting_service.get_or_create_default_accounts(
            corporate_id, required=["operating_expense", "cash"],
        )
        expense_account_id = data.get("expense_account_id") or old_expense.get("expense_account_id") or default_accounts.get("operating_expense")
        payment_account_id = data.get("payment_account_id") or old_expense.get("payment_account_id") or default_accounts.get("cash")

        # Auto-generate reference if not provided
        import uuid as _uuid
        reference = data.get("reference", "").strip() or old_expense.get("reference", "")
        if not reference:
            from datetime import date as _date
            reference = f"EXP-{_date.today().strftime('%Y%m%d')}-{str(_uuid.uuid4())[:6].upper()}"

        # Validate reference uniqueness if changed
        if reference != old_expense.get("reference", ""):
            existing_expenses = registry.database(
                model_name="Expense",
                operation="filter",
                data={"reference": reference, "corporate_id": corporate_id},
            )
            if existing_expenses:
                return ResponseProvider(
                    message="Expense reference already exists", code=400
                ).bad_request()

        # Calculate tax amount if tax rate provided
        tax_amount = Decimal(str(data.get("tax_amount", 0)))
        if data.get("tax_rate_id") and not tax_amount:
            tax_rates = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": data["tax_rate_id"]},
            )
            if tax_rates:
                tax_rate = tax_rates[0]
                if tax_rate["name"] == "general_rated":
                    tax_amount = Decimal(str(data["amount"])) * Decimal("0.16")

        with transaction.atomic():
            # Update expense
            expense_data = {
                "date": data["date"],
                "reference": reference,
                "description": data["description"],
                "category": data["category"],
                "amount": str(data["amount"]),
                "expense_account_id": expense_account_id,
                "payment_account_id": payment_account_id,
                "vendor_id": data.get("vendor_id"),
                "tax_amount": str(tax_amount),
                "tax_rate_id": data.get("tax_rate_id"),
            }

            expense = registry.database(
                model_name="Expense",
                operation="update",
                instance_id=expense_id,
                data=expense_data,
            )

            # Update related journal entry if it exists
            if old_expense.get("journal_entry_id"):
                # Delete old journal entry lines
                old_lines = registry.database(
                    model_name="JournalEntryLine",
                    operation="filter",
                    data={"journal_entry_id": old_expense["journal_entry_id"]},
                )
                for line in old_lines:
                    registry.database(
                        model_name="JournalEntryLine",
                        operation="delete",
                        instance_id=line["id"],
                    )

                # Recreate journal entry lines with new data
                journal_entry = accounting_service.create_expense_journal_entry(
                    expense["id"], user
                )

                # Update expense with new journal entry ID
                registry.database(
                    model_name="Expense",
                    operation="update",
                    instance_id=expense["id"],
                    data={"journal_entry_id": journal_entry["id"]},
                )

        TransactionLogBase.log(
            transaction_type="EXPENSE_UPDATED",
            user=user,
            message=f"Expense {expense['reference']} updated",
            state_name="Completed",
            extra={"expense_id": expense["id"]},
            request=request,
        )

        serialized_expense = {
            "id": str(expense["id"]),
            "reference": expense["reference"],
            "description": expense["description"],
            "date": expense["date"],
            "category": expense["category"],
            "amount": float(expense["amount"]),
            "tax_amount": float(expense.get("tax_amount", 0)),
            "total_amount": float(
                Decimal(str(expense["amount"]))
                + Decimal(str(expense.get("tax_amount", 0)))
            ),
            "expense_account_id": str(expense["expense_account_id"]),
            "payment_account_id": str(expense["payment_account_id"]),
            "vendor_id": (
                str(expense["vendor_id"]) if expense.get("vendor_id") else None
            ),
            "is_posted": expense.get("is_posted", False),
        }

        return ResponseProvider(
            message="Expense updated successfully", data=serialized_expense, code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="EXPENSE_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while updating expense", code=500
        ).exception()


@csrf_exempt
def delete_expense(request):
    """
    Delete an expense by ID.

    Expected data:
    - id: UUID of the expense

    Returns:
    - 200: Expense deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Expense not found
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

        expense_id = data.get("id")
        if not expense_id:
            return ResponseProvider(
                message="Expense ID is required", code=400
            ).bad_request()

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

        expenses = registry.database(
            model_name="Expense",
            operation="filter",
            data={"id": expense_id, "corporate_id": corporate_id},
        )
        if not expenses:
            return ResponseProvider(message="Expense not found", code=404).bad_request()

        expense = expenses[0]

        with transaction.atomic():
            # Delete related journal entry and its lines if they exist
            if expense.get("journal_entry_id"):
                # Delete journal entry lines first
                je_lines = registry.database(
                    model_name="JournalEntryLine",
                    operation="filter",
                    data={"journal_entry_id": expense["journal_entry_id"]},
                )
                for line in je_lines:
                    registry.database(
                        model_name="JournalEntryLine",
                        operation="delete",
                        instance_id=line["id"],
                    )

                # Delete journal entry
                registry.database(
                    model_name="JournalEntry",
                    operation="delete",
                    instance_id=expense["journal_entry_id"],
                )

            # Delete expense
            registry.database(
                model_name="Expense", operation="delete", instance_id=expense_id
            )

        TransactionLogBase.log(
            transaction_type="EXPENSE_DELETED",
            user=user,
            message=f"Expense {expense_id} deleted",
            state_name="Completed",
            extra={"expense_id": expense_id},
            request=request,
        )

        return ResponseProvider(
            message="Expense deleted successfully",
            data={"expense_id": expense_id},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="EXPENSE_DELETE_FAILED",
            user=user if "user" in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while deleting expense", code=500
        ).exception()
