import traceback

from django.shortcuts import get_object_or_404

from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import uuid

from Banking.models import BankTransaction
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_transaction(request):
    """
    Create a new transaction for a bank account.

    Expected data:
    - bank_account_id: UUID of the bank account
    - transaction_type: Type of transaction (e.g., "deposit", "withdrawal")
    - amount: Transaction amount
    - corporate: UUID of the corporate entity
    - reference: Transaction reference (optional)
    - narration: Transaction description (optional)
    - transaction_date: Date of transaction (optional, defaults to current date)
    - status: Transaction status (optional, defaults to "pending")

    Returns:
    - 201: Transaction created successfully
    - 400: Bad request (missing required fields)
    - 404: Corporate or bank account not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    required_fields = ["bank_account_id", "transaction_type", "amount", "corporate"]

    # Validate required fields
    for field in required_fields:
        if not data.get(field):
            return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        corporate_id = data["corporate"]
        bank_account_id = data["bank_account_id"]

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found or inactive", code=404).bad_request()
        corporate = corporates[0]

        # Validate bank account
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": bank_account_id, "corporate": corporate_id, "is_active": True}
        )
        if not bank_accounts:
            return ResponseProvider(message="Bank account not found or inactive", code=404).bad_request()

        # Create transaction with corrected model name
        transaction = registry.database(
            model_name="BankTransaction",  # Corrected from "banktransaction"
            operation="create",
            data={
                "bank_account_id": bank_account_id,
                "transaction_type": data["transaction_type"],
                "amount": data["amount"],
                "reference": data.get("reference"),
                "narration": data.get("narration"),
                "transaction_date": data.get("transaction_date", timezone.now().date()),
                "status": data.get("status", "pending"),
                "created_by": metadata.get("user"),
            }
        )

        # Email Notification using dictionary access
        destination_email = corporate.get("email")
        if destination_email:
            notification_payload = [{
                "message_type": "EMAIL",
                "organisation_id": corporate["id"],
                "destination": destination_email,
                "message": f"""
                    Dear {corporate.get("name", "Corporate")},
                    <br/><br/>
                    A new transaction has been added:
                    <ul>
                        <li><strong>Type:</strong> {transaction["transaction_type"].title()}</li>
                        <li><strong>Amount:</strong> {transaction["amount"]}</li>
                        <li><strong>Date:</strong> {transaction["transaction_date"]}</li>
                    </ul>
                    <br/>Regards,<br/>ERP Team
                """,
            }]
            notif_response = NotificationServiceHandler().send_notification(notification_payload)
        else:
            notif_response = {"status": "skipped", "message": "No email on file"}

        # Log transaction using dictionary access
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_CREATED",
            user=metadata.get("user"),
            message=f"Transaction created for corporate {corporate['id']}",
            state_name="Completed",
            extra={"transaction_id": str(transaction["id"])},
            notification_resp=notif_response,
            request=request
        )

        return ResponseProvider(
            message="Transaction created successfully",
            data={"id": str(transaction["id"])},
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_CREATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating transaction", code=500).bad_request()

@csrf_exempt
def get_transaction(request, transaction_id):
    """
    Retrieve a specific transaction by ID.

    Args:
    - transaction_id: UUID of the transaction

    Returns:
    - 200: Transaction details
    - 404: Transaction not found
    - 500: Internal server error
    """
    try:
        _, metadata = get_clean_data(request)
        transaction = get_object_or_404(BankTransaction, id=transaction_id)

        # Log retrieval
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_RETRIEVED",
            user=metadata.get("user"),
            message=f"Transaction {transaction_id} retrieved",
            state_name="Success",
            extra={"transaction_id": str(transaction_id)},
            request=request
        )

        return ResponseProvider(
            message="Transaction retrieved successfully",
            data={
                "id": str(transaction.id),
                "bank_account": str(transaction.bank_account.id),
                "transaction_type": transaction.transaction_type,
                "amount": float(transaction.amount),
                "reference": transaction.reference,
                "narration": transaction.narration,
                "transaction_date": transaction.transaction_date,
                "status": transaction.status,
                "created_by": str(transaction.created_by_id) if transaction.created_by_id else None
            },
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_RETRIEVAL_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error retrieving transaction", code=500).server_error()

@csrf_exempt
def list_transactions(request):
    """
    Retrieve all transactions for a corporate's bank accounts based on the logged-in user's corporate.

    Returns:
    - 200: List of transactions
    - 400: Bad request (user not linked to a corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Corporate not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        # Get user_id safely
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        registry = ServiceRegistry()

        # Get corporate linked to this user
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0].get("corporate_id")
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Ensure corporate is active
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found or inactive", code=404).bad_request()

        # Get all active bank accounts for this corporate
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )
        bank_account_ids = [acc["id"] for acc in bank_accounts]

        # Get all transactions linked to those bank accounts
        transactions = registry.database(
            model_name="BankTransaction",
            operation="filter",
            data={"bank_account_id__in": bank_account_ids}
        )

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {len(transactions)} transactions for corporate {corporate_id}",
            state_name="Success",
            extra={"transaction_count": len(transactions)},
            request=request
        )

        return ResponseProvider(
            message="Transactions retrieved successfully",
            data={
                "transactions": transactions,
                "count": len(transactions),
                "corporate_id": corporate_id
            },
            code=200
        ).success()

    except ValueError as ve:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_LIST_VALIDATION_ERROR",
            user=metadata.get("user") if 'metadata' in locals() else None,
            message=f"Validation error: {str(ve)}",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message=f"Validation error: {str(ve)}", code=400).bad_request()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_LIST_FAILED",
            user=metadata.get("user") if 'metadata' in locals() else None,
            message=f"Unexpected error: {str(e)}",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving transactions", code=500).exception()

@csrf_exempt
def update_transaction(request):
    """
    Update an existing transaction.

    Expected data:
    - id: UUID of the transaction to update
    - transaction_type: Type of transaction (optional)
    - amount: Transaction amount (optional)
    - reference: Transaction reference (optional)
    - narration: Transaction description (optional)
    - transaction_date: Date of transaction (optional)
    - status: Transaction status (optional)

    Returns:
    - 200: Transaction updated successfully
    - 400: Bad request (missing ID or no valid fields)
    - 404: Transaction not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    transaction_id = data.get("id")

    if not transaction_id:
        return ResponseProvider(message="Transaction ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Check if transaction exists
        existing_transactions = registry.database(
            model_name="BankTransaction",
            operation="filter",
            data={"id": transaction_id}
        )
        if not existing_transactions:
            return ResponseProvider(message="Transaction not found", code=404).bad_request()

        # Prepare update fields
        allowed_fields = ["transaction_type", "amount", "reference", "narration", "transaction_date", "status"]
        update_fields = {key: value for key, value in data.items() if key in allowed_fields and value is not None}
        if not update_fields:
            return ResponseProvider(message="No valid fields provided for update", code=400).bad_request()

        # Include ID in update data
        update_fields["id"] = transaction_id

        # Perform update
        updated_transaction = registry.database(
            model_name="BankTransaction",
            operation="update",
            instance_id=transaction_id,
            data=update_fields
        )

        # Log update
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_UPDATED",
            user=metadata.get("user"),
            message=f"Transaction {transaction_id} updated",
            state_name="Completed",
            extra={"transaction_id": transaction_id, "updated_fields": list(update_fields.keys())},
            request=request
        )

        return ResponseProvider(
            message="Transaction updated successfully",
            data=updated_transaction,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Failed to update transaction", code=500).exception()

@csrf_exempt
def delete_transaction(request):
    """
    Delete a transaction.

    Expected data:
    - id: UUID of the transaction to delete

    Returns:
    - 200: Transaction deleted successfully
    - 400: Bad request (missing ID)
    - 404: Transaction not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    transaction_id = data.get("id")

    if not transaction_id:
        return ResponseProvider(message="Transaction ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Check if transaction exists
        existing_transactions = registry.database(
            model_name="BankTransaction",
            operation="filter",
            data={"id": transaction_id}
        )
        if not existing_transactions:
            return ResponseProvider(message="Transaction not found", code=404).bad_request()

        # Perform delete
        registry.database(
            model_name="BankTransaction",
            operation="delete",
            data={"id": transaction_id}
        )

        # Log delete
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_DELETED",
            user=metadata.get("user"),
            message=f"Transaction {transaction_id} deleted",
            state_name="Completed",
            extra={"transaction_id": transaction_id},
            request=request
        )

        return ResponseProvider(
            message="Transaction deleted successfully",
            data={"transaction_id": transaction_id},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Failed to delete transaction", code=500).exception()

