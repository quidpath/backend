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
    data, metadata = get_clean_data(request)
    required_fields = ["bank_account_id", "transaction_type", "amount", "corporate"]

    for field in required_fields:
        if not data.get(field):
            return ResponseProvider(message=f"{field} is required", code=400).bad_request()

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
            return ResponseProvider(message="Corporate not found or inactive", code=404)
        corporate = corporates[0]

        # Validate bank account
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": bank_account_id, "corporate": corporate_id, "is_active": True}
        )
        if not bank_accounts:
            return ResponseProvider(message="Bank account not found or inactive", code=404)

        # Create transaction
        transaction = registry.database("banktransaction", "create", data={
            "bank_account_id": bank_account_id,
            "transaction_type": data["transaction_type"],
            "amount": data["amount"],
            "reference": data.get("reference"),
            "narration": data.get("narration"),
            "transaction_date": data.get("transaction_date", timezone.now().date()),
            "status": data.get("status", "pending"),
            "created_by": metadata.get("user"),
        })

        # Email Notification
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
                        <li><strong>Type:</strong> {transaction.transaction_type.title()}</li>
                        <li><strong>Amount:</strong> {transaction.amount}</li>
                        <li><strong>Date:</strong> {transaction.transaction_date}</li>
                    </ul>
                    <br/>Regards,<br/>ERP Team
                """,
            }]
            notif_response = NotificationServiceHandler().send_notification(notification_payload)
        else:
            notif_response = {"status": "skipped", "message": "No email on file"}

        # Log transaction
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_CREATED",
            user=metadata.get("user"),
            message=f"Transaction created for corporate {corporate['id']}",
            state_name="Completed",
            extra={"transaction_id": str(transaction.id)},
            notification_resp=notif_response,
            request=request
        )

        return ResponseProvider(
            message="Transaction created successfully",
            data={"id": str(transaction.id)},
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
        return ResponseProvider(message="An error occurred while creating transaction", code=500)



@csrf_exempt
def get_transaction(request, transaction_id):
    transaction = get_object_or_404(BankTransaction, id=transaction_id)
    return ResponseProvider(data={
        "id": str(transaction.id),
        "bank_account": str(transaction.bank_account.id),
        "transaction_type": transaction.transaction_type,
        "amount": float(transaction.amount),
        "reference": transaction.reference,
        "narration": transaction.narration,
        "transaction_date": transaction.transaction_date,
        "status": transaction.status,
        "created_by": str(transaction.created_by_id) if transaction.created_by_id else None
    }).success()


@csrf_exempt
def list_transactions(request):
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate")

    if not corporate_id:
        return ResponseProvider(message="corporate is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found or inactive", code=404)

        # Get all bank accounts for the corporate
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate": corporate_id, "is_active": True}
        )
        bank_account_ids = [acc["id"] for acc in bank_accounts]

        # Get transactions for those accounts
        transactions = registry.database(
            model_name="BankTransaction",
            operation="filter",
            data={"bank_account_id__in": bank_account_ids}
        )

        return ResponseProvider(message="Transactions retrieved", data=transactions).success()

    except Exception as e:
        return ResponseProvider(message="Error retrieving transactions", code=500)

@csrf_exempt
def update_transaction(request):
    data, metadata = get_clean_data(request)
    transaction_id = data.get("id")

    if not transaction_id:
        return ResponseProvider(message="Transaction ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        updated_transaction = registry.database(
            model_name="BankTransaction",
            operation="update",
            data=data

        )

        # Log update
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_UPDATED",
            user=metadata.get("user"),
            message=f"Transaction {transaction_id} updated",
            state_name="Completed",
            extra={"transaction_id": transaction_id},
            request=request
        )

        return ResponseProvider(message="Transaction updated", data=updated_transaction).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Failed to update transaction", code=500).server_error()

@csrf_exempt
def delete_transaction(request):
    data, metadata = get_clean_data(request)
    transaction_id = data.get("id")

    if not transaction_id:
        return ResponseProvider(message="Transaction ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

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

        return ResponseProvider(message="Transaction deleted successfully").success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_TRANSACTION_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Failed to delete transaction", code=500).server_error()


