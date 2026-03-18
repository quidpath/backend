from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.corporate_helper import get_corporate_id_from_data


@csrf_exempt
def add_bank_charge(request):
    """
    Add a new bank charge to a bank account.

    Expected data:
    - bank_account: UUID of the bank account
    - charge_type: Type of the charge
    - amount: Amount of the charge
    - description: Description of the charge (optional)
    - charge_date: Date of the charge (optional)
    - linked_transaction: UUID of the linked transaction (optional)

    Returns:
    - 201: Bank charge created successfully
    - 400: Bad request (missing required fields)
    - 404: Bank account not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    required_items = ["bank_account", "charge_type", "amount"]
    for item in required_items:
        if item not in data:
            return ResponseProvider(
                message=f"{item.replace('_', ' ').title()} is required", code=400
            ).bad_request()

    try:
        bank_account_id = data["bank_account"]

        # Validate Bank Account
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": bank_account_id, "is_active": True},
        )

        if not bank_accounts:
            return ResponseProvider(
                message="Bank account not found or inactive", code=404
            ).bad_request()

        bank_account = bank_accounts[0]

        # Create Bank Charge
        new_charge = registry.database(
            model_name="BankCharge",
            operation="create",
            data={
                "bank_account_id": bank_account_id,
                "charge_type": data["charge_type"],
                "amount": data["amount"],
                "description": data.get("description"),
                "charge_date": data.get("charge_date"),
                "linked_transaction_id": data.get("linked_transaction"),
            },
        )

        # Retrieve corporate and send notification
        corporate_id = bank_account.get("corporate_id")
        corporate_email = None
        if corporate_id:
            corporate = registry.database(
                model_name="Corporate", operation="get", data={"id": corporate_id}
            )
            corporate_email = corporate.get("email") if corporate else None

        if corporate_email:
            notification_payload = [
                {
                    "message_type": "EMAIL",
                    "organisation_id": corporate_id,
                    "destination": corporate_email,
                    "message": f"""
                    Dear {corporate.get("name", "Corporate")},
                    <br/><br/>
                    A new bank charge has been recorded on your account:
                    <ul>
                        <li><strong>Charge Type:</strong> {new_charge["charge_type"]}</li>
                        <li><strong>Amount:</strong> {new_charge["amount"]}</li>
                        <li><strong>Date:</strong> {new_charge["charge_date"]}</li>
                        <li><strong>Description:</strong> {new_charge.get("description", 'N/A')}</li>
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

        # Log the transaction
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_CREATED",
            user=metadata.get("user"),
            message=f"Bank charge of {new_charge['amount']} created on account {bank_account['id']}",
            state_name="Completed",
            extra={"charge_id": new_charge["id"]},
            notification_resp=notif_response,
            request=request,
        )

        return ResponseProvider(
            message="Bank charge recorded successfully", data=new_charge, code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_CREATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating bank charge", code=500
        ).exception()


@csrf_exempt
def list_bank_charges(request):
    """
    List all bank charges for a corporate's bank accounts.

    Expected data:
    - corporate: UUID of the corporate entity

    Returns:
    - 200: List of bank charges
    - 400: Bad request (missing corporate)
    - 404: Corporate not found or no active bank accounts
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    # Extract corporate_id using helper
    corporate_id = get_corporate_id_from_data(data)
    if not corporate_id:
        return ResponseProvider(
            message="Corporate ID is required", code=400
        ).bad_request()

    try:
        # Ensure the corporate exists
        corporate = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True},
        )
        if not corporate:
            return ResponseProvider(
                message="Corporate not found or inactive", code=404
            ).bad_request()

        # Get all active bank accounts
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True},
        )

        account_ids = [acct["id"] for acct in bank_accounts]
        if not account_ids:
            return ResponseProvider(
                message="No active bank accounts found for this corporate", code=404
            ).bad_request()

        # Fetch charges
        charges = registry.database(
            model_name="BankCharge",
            operation="filter",
            data={"bank_account_id__in": account_ids},
        )

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_LIST_SUCCESS",
            user=metadata.get("user"),
            message=f"Retrieved {len(charges)} bank charges for corporate {corporate_id}",
            state_name="Success",
            request=request,
        )

        return ResponseProvider(
            message="Bank charges retrieved successfully",
            data={"charges": charges, "count": len(charges)},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_LIST_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving bank charges", code=500
        ).exception()


@csrf_exempt
def update_bank_charge(request):
    """
    Update an existing bank charge.

    Expected data:
    - id: UUID of the bank charge to update
    - charge_type: Type of the charge (optional)
    - amount: Amount of the charge (optional)
    - description: Description of the charge (optional)
    - charge_date: Date of the charge (optional)
    - linked_transaction: UUID of the linked transaction (optional)

    Returns:
    - 200: Bank charge updated successfully
    - 400: Bad request (missing ID or no valid fields)
    - 404: Bank charge or linked transaction not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(
            message="Bank charge ID is required", code=400
        ).bad_request()

    try:
        charge_id = data["id"]

        # Validate existence of bank charge
        charge = registry.database(
            model_name="BankCharge", operation="filter", data={"id": charge_id}
        )
        if not charge:
            return ResponseProvider(
                message="Bank charge not found", code=404
            ).bad_request()

        # Prepare update fields
        allowed_fields = [
            "charge_type",
            "amount",
            "description",
            "charge_date",
            "linked_transaction",
        ]
        update_fields = {
            key: value
            for key, value in data.items()
            if key in allowed_fields and value is not None
        }
        if not update_fields:
            return ResponseProvider(
                message="No valid fields provided for update", code=400
            ).bad_request()

        # Handle linked_transaction ForeignKey
        if "linked_transaction" in update_fields:
            linked_transaction_id = update_fields.pop(
                "linked_transaction"
            )  # Remove from update_fields
            if linked_transaction_id:
                # Validate linked transaction exists
                linked_transaction = registry.database(
                    model_name="BankTransaction",
                    operation="filter",
                    data={"id": linked_transaction_id},
                )
                if not linked_transaction:
                    return ResponseProvider(
                        message="Linked transaction not found", code=404
                    ).bad_request()
                update_fields["linked_transaction_id"] = (
                    linked_transaction_id  # Use _id for ForeignKey
                )
            else:
                update_fields["linked_transaction_id"] = None

        update_fields["id"] = charge_id

        # Perform update
        updated_charge = registry.database(
            model_name="BankCharge",
            operation="update",
            instance_id=charge_id,
            data=update_fields,
        )

        # Log update
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_UPDATED",
            user=metadata.get("user"),
            message=f"Bank charge {charge_id} updated",
            state_name="Completed",
            extra={
                "charge_id": charge_id,
                "updated_fields": list(update_fields.keys()),
            },
            request=request,
        )

        return ResponseProvider(
            message="Bank charge updated successfully", data=updated_charge, code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while updating bank charge", code=500
        ).exception()


@csrf_exempt
def delete_bank_charge(request):
    """
    Soft delete a bank charge by setting is_active to False.

    Expected data:
    - id: UUID of the bank charge to delete

    Returns:
    - 200: Bank charge deleted successfully
    - 400: Bad request (missing ID)
    - 404: Bank charge not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(
            message="Bank charge ID is required", code=400
        ).bad_request()

    try:
        charge_id = data["id"]

        # Check existence
        existing = registry.database(
            model_name="BankCharge", operation="filter", data={"id": charge_id}
        )
        if not existing:
            return ResponseProvider(
                message="Bank charge not found", code=404
            ).bad_request()

        # Mark as inactive
        deleted = registry.database(
            model_name="BankCharge",
            operation="delete",
            instance_id=charge_id,
            data={"id": charge_id, "is_active": False},
        )

        # Log deletion
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_DELETED",
            user=metadata.get("user"),
            message=f"Bank charge {charge_id} soft-deleted",
            state_name="Completed",
            extra={"charge_id": charge_id},
            request=request,
        )

        return ResponseProvider(
            message="Bank charge deleted successfully",
            data={"charge_id": charge_id, "status": "inactive"},
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while deleting bank charge", code=500
        ).exception()
