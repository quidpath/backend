from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def add_bank_reconciliation(request):
    """
    Add a new bank reconciliation for a bank account.

    Expected data:
    - bank_account: UUID of the bank account
    - period_start: Start date of the reconciliation period
    - period_end: End date of the reconciliation period
    - opening_balance: Opening balance for the period
    - closing_balance: Closing balance for the period
    - status: Reconciliation status (optional, defaults to "open")

    Returns:
    - 201: Bank reconciliation created successfully
    - 400: Bad request (missing required fields or invalid dates)
    - 404: Bank account or corporate not found
    - 409: Overlapping reconciliation period
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    required_items = ["bank_account", "period_start", "period_end", "opening_balance", "closing_balance"]
    for item in required_items:
        if item not in data:
            return ResponseProvider(message=f"{item.replace('_', ' ').title()} is required", code=400).bad_request()

    try:
        bank_account_id = data["bank_account"]

        # Validate date range
        if data["period_end"] < data["period_start"]:
            return ResponseProvider(message="Period end date cannot be before period start date", code=400).bad_request()

        # Validate bank account
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": bank_account_id, "is_active": True}
        )
        if not bank_accounts:
            return ResponseProvider(message="Bank account not found or inactive", code=404).bad_request()
        bank_account = bank_accounts[0]

        # Check for overlapping reconciliation periods
        existing_reconciliations = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={
                "bank_account_id": bank_account_id,
                "period_start__lte": data["period_end"],
                "period_end__gte": data["period_start"]
            }
        )
        if existing_reconciliations:
            return ResponseProvider(message="A reconciliation already exists for this period", code=409).bad_request()

        # Create reconciliation record
        reconciliation = registry.database(
            model_name="BankReconciliation",
            operation="create",
            data={
                "bank_account_id": bank_account_id,  # Use _id for ForeignKey
                "period_start": data["period_start"],
                "period_end": data["period_end"],
                "opening_balance": data["opening_balance"],
                "closing_balance": data["closing_balance"],
                "status": data.get("status", "open")
            }
        )

        # Notify corporate via email
        corporate_id = bank_account.get("corporate_id")
        corporate_email = None
        if corporate_id:
            corporates = registry.database(
                model_name="Corporate",
                operation="filter",
                data={"id": corporate_id, "is_active": True}
            )
            if corporates:
                corporate_email = corporates[0].get("email")

        if corporate_email:
            message = f"""
                Dear {corporates[0].get("name", "Corporate")},
                <br/><br/>
                A bank reconciliation has been initiated:
                <ul>
                    <li><strong>Account:</strong> {bank_account['bank_name']} - {bank_account['account_number']}</li>
                    <li><strong>Period:</strong> {reconciliation['period_start']} to {reconciliation['period_end']}</li>
                    <li><strong>Opening Balance:</strong> {reconciliation['opening_balance']}</li>
                    <li><strong>Closing Balance:</strong> {reconciliation['closing_balance']}</li>
                    <li><strong>Status:</strong> {reconciliation['status']}</li>
                </ul>
                <br/>Regards,<br/>ERP Team
            """
            notification_payload = [{
                "message_type": "EMAIL",
                "organisation_id": corporate_id,
                "destination": corporate_email,
                "message": message,
            }]
            try:
                notif_response = NotificationServiceHandler().send_notification(notification_payload)
            except Exception as email_error:
                notif_response = {"status": "failed", "message": str(email_error)}
        else:
            notif_response = {"status": "skipped", "message": "No email on file"}

        # Log transaction
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_CREATED",
            user=metadata.get("user"),
            message=f"Bank reconciliation created for account {bank_account['id']}",
            state_name="Completed",
            extra={"reconciliation_id": reconciliation["id"]},
            notification_resp=notif_response,
            request=request
        )

        return ResponseProvider(
            message="Bank reconciliation added successfully",
            data=reconciliation,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_CREATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating bank reconciliation", code=500).exception()


@csrf_exempt
def list_bank_reconciliations(request):
    """
    List all bank reconciliations for a corporate's bank accounts.

    Expected data:
    - corporate: UUID of the corporate entity

    Returns:
    - 200: List of reconciliations
    - 400: Bad request (missing corporate)
    - 404: Corporate not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    corporate_id = data.get("corporate")
    if not corporate_id:
        return ResponseProvider(message="Corporate ID is required", code=400).bad_request()

    try:
        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found or inactive", code=404).bad_request()

        # Fetch bank accounts
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        account_ids = [acct["id"] for acct in bank_accounts]
        if not account_ids:
            return ResponseProvider(
                message="No active bank accounts found for this corporate",
                data={"reconciliations": [], "count": 0},
                code=200
            ).success()

        # Fetch reconciliations
        reconciliations = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"bank_account_id__in": account_ids}
        )

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_LIST_SUCCESS",
            user=metadata.get("user"),
            message=f"Retrieved {len(reconciliations)} bank reconciliations for corporate {corporate_id}",
            state_name="Success",
            request=request
        )

        return ResponseProvider(
            message="Bank reconciliations retrieved successfully",
            data={"reconciliations": reconciliations, "count": len(reconciliations)},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_LIST_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving bank reconciliations", code=500).exception()


@csrf_exempt
def update_bank_reconciliation(request):
    """
    Update an existing bank reconciliation.

    Expected data:
    - id: UUID of the reconciliation to update
    - period_start: Start date of the reconciliation period (optional)
    - period_end: End date of the reconciliation period (optional)
    - opening_balance: Opening balance for the period (optional)
    - closing_balance: Closing balance for the period (optional)
    - status: Reconciliation status (optional)

    Returns:
    - 200: Bank reconciliation updated successfully
    - 400: Bad request (missing ID or no valid fields)
    - 404: Reconciliation not found
    - 409: Overlapping reconciliation period
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(message="Reconciliation ID is required", code=400).bad_request()

    try:
        rec_id = data["id"]

        # Validate existence
        existing = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"id": rec_id}
        )
        if not existing:
            return ResponseProvider(message="Reconciliation not found", code=404).bad_request()

        # Prepare update fields
        allowed_fields = ["period_start", "period_end", "opening_balance", "closing_balance", "status"]
        update_fields = {key: value for key, value in data.items() if key in allowed_fields and value is not None}
        if not update_fields:
            return ResponseProvider(message="No valid fields provided for update", code=400).bad_request()

        # Validate date range if both period_start and period_end are provided
        if "period_start" in update_fields and "period_end" in update_fields:
            if update_fields["period_end"] < update_fields["period_start"]:
                return ResponseProvider(message="Period end date cannot be before period start date", code=400).bad_request()

        # Check for overlapping periods if period dates are updated
        if "period_start" in update_fields or "period_end" in update_fields:
            bank_account_id = existing[0]["bank_account"]
            period_start = update_fields.get("period_start", existing[0]["period_start"])
            period_end = update_fields.get("period_end", existing[0]["period_end"])
            overlapping = registry.database(
                model_name="BankReconciliation",
                operation="filter",
                data={
                    "bank_account": bank_account_id,
                    "period_start__lte": period_end,
                    "period_end__gte": period_start,
                }
            )
            overlapping = [item for item in overlapping if item["id"] != rec_id]

            if overlapping:
                return ResponseProvider(message="Updated period overlaps with an existing reconciliation", code=409).bad_request()

        update_fields["id"] = rec_id

        # Perform update
        updated = registry.database(
            model_name="BankReconciliation",
            operation="update",
            instance_id=rec_id,
            data=update_fields
        )

        # Log update
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_UPDATED",
            user=metadata.get("user"),
            message=f"Bank reconciliation {rec_id} updated",
            state_name="Completed",
            extra={"reconciliation_id": rec_id, "updated_fields": list(update_fields.keys())},
            request=request
        )

        return ResponseProvider(
            message="Bank reconciliation updated successfully",
            data=updated,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_UPDATE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating bank reconciliation", code=500).exception()


@csrf_exempt
def delete_bank_reconciliation(request):
    """
    Soft delete a bank reconciliation by setting is_active to False.

    Expected data:
    - id: UUID of the reconciliation to delete

    Returns:
    - 200: Bank reconciliation deleted successfully
    - 400: Bad request (missing ID)
    - 404: Reconciliation not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(message="Reconciliation ID is required", code=400).bad_request()

    try:
        rec_id = data["id"]

        # Check existence
        existing = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"id": rec_id}
        )
        if not existing:
            return ResponseProvider(message="Reconciliation not found", code=404).bad_request()

        # Perform soft delete
        deleted = registry.database(
            model_name="BankReconciliation",
            operation="delete",
            instance_id=rec_id,
            data={"id": rec_id, "is_active": False}
        )

        # Log deletion
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_DELETED",
            user=metadata.get("user"),
            message=f"Bank reconciliation {rec_id} soft-deleted",
            state_name="Completed",
            extra={"reconciliation_id": rec_id},
            request=request
        )

        return ResponseProvider(
            message="Bank reconciliation deleted successfully",
            data={"reconciliation_id": rec_id, "status": "inactive"},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_DELETE_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting bank reconciliation", code=500).exception()