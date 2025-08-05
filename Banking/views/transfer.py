from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_internal_transfer(request):
    data, metadata = get_clean_data(request)
    required_fields = ["from_account_id", "to_account_id", "amount", "corporate"]

    # Check required fields
    for field in required_fields:
        if not data.get(field):
            return ResponseProvider(message=f"{field} is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        corporate_id = data["corporate"]
        from_account_id = data["from_account_id"]
        to_account_id = data["to_account_id"]

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found or inactive", code=404)
        corporate = corporates[0]

        # Validate from_account and to_account
        from_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": from_account_id, "corporate": corporate_id, "is_active": True}
        )
        to_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": to_account_id, "corporate": corporate_id, "is_active": True}
        )

        if not from_accounts:
            return ResponseProvider(message="From account not found or inactive", code=404)
        if not to_accounts:
            return ResponseProvider(message="To account not found or inactive", code=404)

        # Create Internal Transfer
        transfer = registry.database("InternalTransfer", "create", data={
            "from_account": from_account_id,
            "to_account": to_account_id,
            "amount": data["amount"],
            "reference": data.get("reference"),
            "reason": data.get("reason"),
            "transfer_date": data.get("transfer_date", timezone.now().date()),
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
                    A new internal transfer has been created:
                    <ul>
                        <li><strong>From Account:</strong> {from_accounts[0].get("account_name")}</li>
                        <li><strong>To Account:</strong> {to_accounts[0].get("account_name")}</li>
                        <li><strong>Amount:</strong> {transfer.amount}</li>
                        <li><strong>Date:</strong> {transfer.transfer_date}</li>
                    </ul>
                    <br/>Regards,<br/>ERP Team
                """,
            }]
            notif_response = NotificationServiceHandler().send_notification(notification_payload)
        else:
            notif_response = {"status": "skipped", "message": "No email on file"}

        # Log transfer creation
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_CREATED",
            user=metadata.get("user"),
            message=f"Transfer created for corporate {corporate['id']}",
            state_name="Completed",
            extra={"transfer_id": str(transfer.id)},
            notification_resp=notif_response,
            request=request
        )

        return ResponseProvider(
            message="Internal transfer created successfully",
            data={"id": str(transfer.id)},
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_CREATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating internal transfer", code=500)


@csrf_exempt
def list_internal_transfers(request):
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate")

    if not corporate_id:
        return ResponseProvider(message="corporate is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Fetch transfers with accounts belonging to the corporate
        bank_accounts = registry.database("BankAccount", "filter", {
            "corporate": corporate_id,
            "is_active": True
        })

        if not bank_accounts:
            return ResponseProvider(message="No bank accounts found for corporate", data=[], code=200).success()

        account_ids = [acct["id"] for acct in bank_accounts]

        transfers = registry.database("InternalTransfer", "filter_multiple_conditions", {
            "from_account__in": account_ids,
            "to_account__in": account_ids
        })

        return ResponseProvider(
            message="Transfers fetched successfully",
            data=transfers,
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(message="Error fetching transfers", code=500)

@csrf_exempt
def update_internal_transfer(request, transfer_id):
    data, metadata = get_clean_data(request)

    try:
        registry = ServiceRegistry()

        existing = registry.database("InternalTransfer", "get", {"id": transfer_id})
        if not existing:
            return ResponseProvider(message="Transfer not found", code=404)

        updated = registry.database("InternalTransfer", "update", data={
            "id": transfer_id,
            **data,
        })

        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_UPDATED",
            user=metadata.get("user"),
            message=f"Updated internal transfer {transfer_id}",
            state_name="Completed",
            request=request
        )

        return ResponseProvider(
            message="Internal transfer updated successfully",
            data={"id": str(updated.id)},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error updating transfer", code=500)

@csrf_exempt
def delete_internal_transfer(request, transfer_id):
    data, metadata = get_clean_data(request)

    try:
        registry = ServiceRegistry()

        existing = registry.database("InternalTransfer", "get", {"id": transfer_id})
        if not existing:
            return ResponseProvider(message="Transfer not found", code=404)

        registry.database("InternalTransfer", "delete", data={"id": transfer_id})

        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_DELETED",
            user=metadata.get("user"),
            message=f"Deleted internal transfer {transfer_id}",
            state_name="Completed",
            request=request
        )

        return ResponseProvider(
            message="Internal transfer deleted successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error deleting transfer", code=500).error()
