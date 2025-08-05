from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def add_bank_reconciliation(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    required_items = ["bank_account", "period_start", "period_end", "opening_balance", "closing_balance"]
    for item in required_items:
        if item not in data:
            return ResponseProvider(message=f"{item} is required", code=400).bad_request()

    try:
        bank_account_id = data["bank_account"]

        # ✅ Validate bank account
        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": bank_account_id, "is_active": True}
        )
        if not bank_accounts:
            return ResponseProvider(message="Bank account not found or inactive", code=404).not_found()

        bank_account = bank_accounts[0]

        # ✅ Create reconciliation record
        reconciliation = registry.database(
            model_name="BankReconciliation",
            operation="create",
            data={
                "bank_account_id": bank_account_id,
                "period_start": data["period_start"],
                "period_end": data["period_end"],
                "opening_balance": data["opening_balance"],
                "closing_balance": data["closing_balance"],
                "status": data.get("status", "open"),
            }
        )

        # ✅ Notify corporate via email
        corporate_id = bank_account.get("corporate_id")
        corporate = registry.database("Corporate", "get", data={"id": corporate_id})
        corporate_email = corporate.get("email") if corporate else None

        if corporate_email:
            message = f"""
                Dear {corporate.get("name", "Corporate")},
                <br/><br/>
                A bank reconciliation has been initiated:
                <ul>
                    <li><strong>Account:</strong> {bank_account['bank_name']} - {bank_account['account_number']}</li>
                    <li><strong>Period:</strong> {data['period_start']} to {data['period_end']}</li>
                    <li><strong>Opening Balance:</strong> {data['opening_balance']}</li>
                    <li><strong>Closing Balance:</strong> {data['closing_balance']}</li>
                    <li><strong>Status:</strong> {data.get('status', 'open')}</li>
                </ul>
                <br/>Regards,<br/>ERP Team
            """

            notification_payload = [{
                "message_type": "EMAIL",
                "organisation_id": corporate_id,
                "destination": corporate_email,
                "message": message,
            }]
            notif_response = NotificationServiceHandler().send_notification(notification_payload)
        else:
            notif_response = {"status": "skipped", "message": "No email on file"}

        # ✅ Log transaction
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
            transaction_type="BANK_RECONCILIATION_FAILED",
            user=metadata.get("user"),
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Error during reconciliation creation", code=500)

@csrf_exempt
def list_bank_reconciliations(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    corporate_id = data.get("corporate")
    if not corporate_id:
        return ResponseProvider(message="corporate is required", code=400).bad_request()

    try:
        corporate = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True}
        )
        if not corporate:
            return ResponseProvider(message="Corporate not found or inactive", code=404)

        bank_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        account_ids = [acct["id"] for acct in bank_accounts]
        if not account_ids:
            return ResponseProvider(message="No bank accounts found for this corporate", code=404).not_found()

        reconciliations = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"bank_account_id__in": account_ids}
        )

        return ResponseProvider(
            message="Reconciliations fetched successfully",
            data=reconciliations,
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
        return ResponseProvider(message="Error fetching reconciliations", code=500).server_error()

@csrf_exempt
def update_bank_reconciliation(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(message="Reconciliation ID is required", code=400).bad_request()

    try:
        rec_id = data["id"]

        existing = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"id": rec_id}
        )
        if not existing:
            return ResponseProvider(message="Reconciliation not found", code=404).not_found()

        update_fields = {
            key: value for key, value in data.items()
            if key in ["period_start", "period_end", "opening_balance", "closing_balance", "status"]
        }

        updated = registry.database(
            model_name="BankReconciliation",
            operation="update",
            data={"id": rec_id, **update_fields}
        )

        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_UPDATED",
            user=metadata.get("user"),
            message=f"Reconciliation {rec_id} updated",
            state_name="Completed",
            extra={"reconciliation_id": rec_id},
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
        return ResponseProvider(message="Error updating reconciliation", code=500).server_error()

@csrf_exempt
def delete_bank_reconciliation(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()

    if "id" not in data:
        return ResponseProvider(message="Reconciliation ID is required", code=400).bad_request()

    try:
        rec_id = data["id"]

        existing = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"id": rec_id}
        )
        if not existing:
            return ResponseProvider(message="Reconciliation not found", code=404).not_found()

        deleted = registry.database(
            model_name="BankReconciliation",
            operation="update",
            data={"id": rec_id, "is_active": False}
        )

        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_DELETED",
            user=metadata.get("user"),
            message=f"Reconciliation {rec_id} soft-deleted",
            state_name="Completed",
            extra={"reconciliation_id": rec_id},
            request=request
        )

        return ResponseProvider(
            message="Reconciliation deleted successfully",
            data=deleted,
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
        return ResponseProvider(message="Error deleting reconciliation", code=500).server_error()
