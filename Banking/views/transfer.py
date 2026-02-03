from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_internal_transfer(request):
    """
    Create a new internal transfer between two bank accounts.

    Expected data:
    - from_account_id: UUID of the source bank account
    - to_account_id: UUID of the destination bank account
    - amount: Transfer amount
    - corporate: UUID of the corporate entity
    - reference: Transfer reference (optional)
    - reason: Reason for the transfer (optional)
    - transfer_date: Date of the transfer (optional, defaults to current date)
    - status: Transfer status (optional, defaults to "pending")

    Returns:
    - 201: Internal transfer created successfully
    - 400: Bad request (missing required fields or same account)
    - 404: Corporate, from account, or to account not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    required_fields = ["from_account_id", "to_account_id", "amount", "corporate"]

    # Check required fields
    for field in required_fields:
        if not data.get(field):
            return ResponseProvider(
                message=f"{field.replace('_', ' ').title()} is required", code=400
            ).bad_request()

    try:
        registry = ServiceRegistry()
        corporate_id = data["corporate"]
        from_account_id = data["from_account_id"]
        to_account_id = data["to_account_id"]

        # Prevent transfer to the same account
        if from_account_id == to_account_id:
            return ResponseProvider(
                message="Cannot transfer to the same account", code=400
            ).bad_request()

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True},
        )
        if not corporates:
            return ResponseProvider(
                message="Corporate not found or inactive", code=404
            ).bad_request()
        corporate = corporates[0]

        # Validate from_account
        from_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={
                "id": from_account_id,
                "corporate_id": corporate_id,
                "is_active": True,
            },
        )
        if not from_accounts:
            return ResponseProvider(
                message="From account not found or inactive", code=404
            ).bad_request()

        # Validate to_account
        to_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": to_account_id, "corporate_id": corporate_id, "is_active": True},
        )
        if not to_accounts:
            return ResponseProvider(
                message="To account not found or inactive", code=404
            ).bad_request()

        # Create Internal Transfer
        transfer = registry.database(
            model_name="InternalTransfer",
            operation="create",
            data={
                "from_account_id": from_account_id,  # Use _id for ForeignKey
                "to_account_id": to_account_id,  # Use _id for ForeignKey
                "amount": data["amount"],
                "reference": data.get("reference"),
                "reason": data.get("reason"),
                "transfer_date": data.get("transfer_date", timezone.now().date()),
                "status": data.get("status", "pending"),
                "created_by": metadata.get("user"),
            },
        )

        # Email Notification
        destination_email = corporate.get("email")
        if destination_email:
            notification_payload = [
                {
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
                        <li><strong>Amount:</strong> {transfer["amount"]}</li>
                        <li><strong>Date:</strong> {transfer["transfer_date"]}</li>
                    </ul>
                    <br/>Regards,<br/>ERP Team
                """,
                }
            ]
            try:
                notif_response = NotificationServiceHandler().send_notification(
                    notification_payload
                )
            except Exception as email_error:
                notif_response = {"status": "failed", "message": str(email_error)}
        else:
            notif_response = {"status": "skipped", "message": "No email on file"}

        # Log transfer creation
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_CREATED",
            user=metadata.get("user"),
            message=f"Transfer created for corporate {corporate['id']}",
            state_name="Completed",
            extra={"transfer_id": str(transfer["id"])},
            notification_resp=notif_response,
            request=request,
        )

        return ResponseProvider(
            message="Internal transfer created successfully",
            data={
                "id": str(transfer["id"]),
                "amount": transfer["amount"],
                "status": transfer["status"],
            },
            code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_CREATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating internal transfer", code=500
        ).exception()


@csrf_exempt
def list_internal_transfers(request):
    """
    List all internal transfers for a corporate's bank accounts.

    Expected data:
    - corporate: UUID of the corporate entity

    Returns:
    - 200: List of internal transfers
    - 400: Bad request (missing corporate)
    - 404: Corporate not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate")

    if not corporate_id:
        return ResponseProvider(
            message="Corporate ID is required", code=400
        ).bad_request()

    try:
        registry = ServiceRegistry()

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True},
        )
        if not corporates:
            return ResponseProvider(
                message="Corporate not found or inactive", code=404
            ).bad_request()

        # Fetch bank accounts
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True},
        )

        account_ids = [acct["id"] for acct in bank_accounts]
        if not account_ids:
            return ResponseProvider(
                message="No active bank accounts found for this corporate",
                data={"transfers": [], "count": 0},
                code=200,
            ).success()

        # Fetch transfers
        transfers = registry.database(
            model_name="InternalTransfer",
            operation="filter",
            data={"from_account_id__in": account_ids, "to_account_id__in": account_ids},
        )

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_LIST_SUCCESS",
            user=metadata.get("user"),
            message=f"Retrieved {len(transfers)} internal transfers for corporate {corporate_id}",
            state_name="Success",
            request=request,
        )

        return ResponseProvider(
            message="Internal transfers retrieved successfully",
            data={"transfers": transfers, "count": len(transfers)},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_LIST_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving internal transfers", code=500
        ).exception()


@csrf_exempt
def update_internal_transfer(request):
    """
    Update an existing internal transfer.

    Expected data:
    - id: UUID of the internal transfer to update
    - amount: Transfer amount (optional)
    - reference: Transfer reference (optional)
    - reason: Reason for the transfer (optional)
    - transfer_date: Date of the transfer (optional)
    - status: Transfer status (optional)

    Returns:
    - 200: Internal transfer updated successfully
    - 400: Bad request (missing ID or no valid fields)
    - 404: Internal transfer not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    transfer_id = data.get("id")

    if not transfer_id:
        return ResponseProvider(
            message="Internal transfer ID is required", code=400
        ).bad_request()

    try:
        registry = ServiceRegistry()

        # Validate existence
        existing = registry.database(
            model_name="InternalTransfer", operation="filter", data={"id": transfer_id}
        )
        if not existing:
            return ResponseProvider(
                message="Internal transfer not found", code=404
            ).bad_request()

        # Prepare update fields
        allowed_fields = ["amount", "reference", "reason", "transfer_date", "status"]
        update_fields = {
            key: value
            for key, value in data.items()
            if key in allowed_fields and value is not None
        }
        if not update_fields:
            return ResponseProvider(
                message="No valid fields provided for update", code=400
            ).bad_request()

        update_fields["id"] = transfer_id

        # Perform update
        updated = registry.database(
            model_name="InternalTransfer",
            operation="update",
            instance_id=transfer_id,
            data=update_fields,
        )

        # Log update
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_UPDATED",
            user=metadata.get("user"),
            message=f"Internal transfer {transfer_id} updated",
            state_name="Completed",
            extra={
                "transfer_id": transfer_id,
                "updated_fields": list(update_fields.keys()),
            },
            request=request,
        )

        return ResponseProvider(
            message="Internal transfer updated successfully", data=updated, code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while updating internal transfer", code=500
        ).exception()


@csrf_exempt
def delete_internal_transfer(request):
    """
    Soft delete an internal transfer by setting is_active to False.

    Expected data:
    - id: UUID of the internal transfer to delete

    Returns:
    - 200: Internal transfer deleted successfully
    - 400: Bad request (missing ID)
    - 404: Internal transfer not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    transfer_id = data.get("id")

    if not transfer_id:
        return ResponseProvider(
            message="Internal transfer ID is required", code=400
        ).bad_request()

    try:
        registry = ServiceRegistry()

        # Check existence
        existing = registry.database(
            model_name="InternalTransfer", operation="filter", data={"id": transfer_id}
        )
        if not existing:
            return ResponseProvider(
                message="Internal transfer not found", code=404
            ).bad_request()

        # Perform soft delete
        deleted = registry.database(
            model_name="InternalTransfer",
            operation="update",
            instance_id=transfer_id,
            data={"id": transfer_id, "is_active": False},
        )

        # Log deletion
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_DELETED",
            user=metadata.get("user"),
            message=f"Internal transfer {transfer_id} soft-deleted",
            state_name="Completed",
            extra={"transfer_id": transfer_id},
            request=request,
        )

        return ResponseProvider(
            message="Internal transfer deleted successfully",
            data={"transfer_id": transfer_id, "status": "inactive"},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INTERNAL_TRANSFER_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while deleting internal transfer", code=500
        ).exception()
