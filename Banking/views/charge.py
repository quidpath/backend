from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def add_bank_charge(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    required_items = ["bank_account", "charge_type", "amount"]
    for item in required_items:
        if item not in data:
            return ResponseProvider(message=f"{item} is required", code=400).bad_request()

    try:
        bank_account_id = data["bank_account"]

        # Validate Bank Account
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": bank_account_id, "is_active": True}
        )

        if not bank_accounts:
            return ResponseProvider(message="Bank account not found or inactive", code=404)

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
                "charge_date": data.get("charge_date"),  # Optional; default used if None
                "linked_transaction_id": data.get("linked_transaction")
            }
        )

        # Prepare email notification
        corporate_id = bank_account.get("corporate_id")
        corporate = registry.database("Corporate", "get", data={"id": corporate_id})
        corporate_email = corporate.get("email") if corporate else None

        if corporate_email:
            notification_payload = [{
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
            }]
            notif_response = NotificationServiceHandler().send_notification(notification_payload)
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
            request=request
        )

        return ResponseProvider(
            message="Bank charge recorded successfully",
            data=new_charge,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_CREATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error while creating bank charge", code=500)

@csrf_exempt
def list_bank_charges(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    corporate_id = data.get("corporate")
    if not corporate_id:
        return ResponseProvider(message="corporate is required", code=400).bad_request()

    try:
        # Ensure the corporate exists
        corporate = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporate:
            return ResponseProvider(message="Corporate not found", code=404).not_found()

        # Get all active bank accounts for this corporate
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        account_ids = [acct["id"] for acct in bank_accounts]
        if not account_ids:
            return ResponseProvider(message="No active bank accounts found for this corporate", code=404).not_found()

        # Fetch charges for those bank accounts
        charges = registry.database(
            model_name="BankCharge",
            operation="filter",
            data={"bank_account_id__in": account_ids}
        )

        return ResponseProvider(
            message="Bank charges retrieved successfully",
            data=charges,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_LIST_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error retrieving bank charges", code=500).server_error()

@csrf_exempt
def update_bank_charge(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(message="Bank charge ID is required", code=400).bad_request()

    try:
        charge_id = data["id"]

        # Validate existence
        charge = registry.database(
            model_name="BankCharge",
            operation="filter",
            data={"id": charge_id}
        )
        if not charge:
            return ResponseProvider(message="Bank charge not found", code=404).not_found()

        # Update
        update_fields = {key: value for key, value in data.items() if key in [
            "charge_type", "amount", "description", "charge_date", "linked_transaction"
        ]}

        updated_charge = registry.database(
            model_name="BankCharge",
            operation="update",
            data={"id": charge_id, **update_fields}
        )

        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_UPDATED",
            user=metadata.get("user"),
            message=f"Bank charge {charge_id} updated",
            state_name="Completed",
            extra={"charge_id": charge_id},
            request=request
        )

        return ResponseProvider(
            message="Bank charge updated successfully",
            data=updated_charge,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error updating bank charge", code=500).server_error()

@csrf_exempt
def delete_bank_charge(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(message="Bank charge ID is required", code=400).bad_request()

    try:
        charge_id = data["id"]

        # Check existence
        existing = registry.database(
            model_name="BankCharge",
            operation="filter",
            data={"id": charge_id}
        )
        if not existing:
            return ResponseProvider(message="Bank charge not found", code=404).not_found()

        # Mark as inactive
        deleted = registry.database(
            model_name="BankCharge",
            operation="update",
            data={"id": charge_id, "is_active": False}
        )

        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_DELETED",
            user=metadata.get("user"),
            message=f"Bank charge {charge_id} deleted (soft)",
            state_name="Completed",
            extra={"charge_id": charge_id},
            request=request
        )

        return ResponseProvider(
            message="Bank charge deleted successfully",
            data=deleted,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_CHARGE_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error deleting bank charge", code=500).server_error()
