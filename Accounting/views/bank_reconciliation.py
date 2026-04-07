"""
Bank Reconciliation Views
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from Accounting.models import BankReconciliation, ReconciliationItem
from quidpath_backend.core.helpers.data_helpers import get_clean_data
from quidpath_backend.core.helpers.response_provider import ResponseProvider
from quidpath_backend.core.helpers.service_registry import ServiceRegistry
from quidpath_backend.core.helpers.transaction_log import TransactionLogBase


@require_http_methods(["POST"])
def create_bank_reconciliation(request):
    """Create a new bank reconciliation"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        required_fields = ["bank_account_id", "period_start", "period_end", "opening_balance", "closing_balance", "statement_balance"]
        
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"Missing required field: {field}", code=400
                ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get bank account
        bank_account = registry.database(
            model_name="BankAccount",
            operation="get",
            data={"id": data["bank_account_id"]},
        )
        
        if not bank_account:
            return ResponseProvider(
                message="Bank account not found", code=404
            ).bad_request()
        
        # Create reconciliation
        recon_data = {
            "corporate": corporate,
            "bank_account": bank_account,
            "period_start": data["period_start"],
            "period_end": data["period_end"],
            "opening_balance": data["opening_balance"],
            "closing_balance": data["closing_balance"],
            "statement_balance": data["statement_balance"],
            "book_balance": data.get("book_balance", data["closing_balance"]),
            "notes": data.get("notes", ""),
            "reconciled_by": user,
        }
        
        reconciliation = registry.database(
            model_name="BankReconciliation",
            operation="create",
            data=recon_data,
        )
        
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_CREATED",
            user=user,
            message=f"Created bank reconciliation for {bank_account.get('account_name', '')}",
            state_name="Success",
            extra={"reconciliation_id": str(reconciliation["id"])},
            request=request,
        )
        
        return ResponseProvider(
            data={"reconciliation": reconciliation},
            message="Bank reconciliation created successfully",
            code=201,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_CREATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating bank reconciliation", code=500
        ).exception()


@require_http_methods(["GET"])
def list_bank_reconciliations(request):
    """List bank reconciliations"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        registry = ServiceRegistry()
        
        reconciliations = registry.database(
            model_name="BankReconciliation",
            operation="filter",
            data={"corporate": corporate},
        )
        
        serialized_reconciliations = [
            {
                "id": str(recon["id"]),
                "bank_account_id": str(recon["bank_account"]["id"]) if isinstance(recon.get("bank_account"), dict) else str(recon.get("bank_account").id) if hasattr(recon.get("bank_account"), "id") else "",
                "bank_account_name": recon["bank_account"]["account_name"] if isinstance(recon.get("bank_account"), dict) else recon.get("bank_account").account_name if hasattr(recon.get("bank_account"), "account_name") else "",
                "period_start": recon["period_start"].isoformat() if hasattr(recon.get("period_start"), "isoformat") else str(recon.get("period_start", "")),
                "period_end": recon["period_end"].isoformat() if hasattr(recon.get("period_end"), "isoformat") else str(recon.get("period_end", "")),
                "opening_balance": float(recon["opening_balance"]),
                "closing_balance": float(recon["closing_balance"]),
                "statement_balance": float(recon["statement_balance"]),
                "book_balance": float(recon["book_balance"]),
                "difference": float(recon["difference"]),
                "status": recon["status"],
                "created_at": recon["created_at"].isoformat() if hasattr(recon.get("created_at"), "isoformat") else str(recon.get("created_at", "")),
            }
            for recon in reconciliations
        ]
        
        return ResponseProvider(
            data={"reconciliations": serialized_reconciliations, "total": len(serialized_reconciliations)},
            message="Bank reconciliations retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving bank reconciliations", code=500
        ).exception()


@require_http_methods(["GET"])
def get_bank_reconciliation(request):
    """Get a specific bank reconciliation with items"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        reconciliation_id = data.get("id")
        if not reconciliation_id:
            return ResponseProvider(
                message="Missing reconciliation id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        reconciliation = registry.database(
            model_name="BankReconciliation",
            operation="get",
            data={"id": reconciliation_id},
        )
        
        if not reconciliation:
            return ResponseProvider(
                message="Reconciliation not found", code=404
            ).bad_request()
        
        # Get reconciliation items
        items = registry.database(
            model_name="ReconciliationItem",
            operation="filter",
            data={"reconciliation": reconciliation_id},
        )
        
        serialized_items = [
            {
                "id": str(item["id"]),
                "item_type": item["item_type"],
                "date": item["date"].isoformat() if hasattr(item.get("date"), "isoformat") else str(item.get("date", "")),
                "reference": item["reference"],
                "description": item["description"],
                "amount": float(item["amount"]),
                "is_cleared": item["is_cleared"],
                "cleared_date": item["cleared_date"].isoformat() if item.get("cleared_date") and hasattr(item["cleared_date"], "isoformat") else None,
            }
            for item in items
        ]
        
        reconciliation["items"] = serialized_items
        
        return ResponseProvider(
            data={"reconciliation": reconciliation},
            message="Bank reconciliation retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving bank reconciliation", code=500
        ).exception()


@require_http_methods(["POST"])
def add_reconciliation_item(request):
    """Add an item to a bank reconciliation"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        required_fields = ["reconciliation_id", "item_type", "date", "reference", "description", "amount"]
        
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"Missing required field: {field}", code=400
                ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get reconciliation
        reconciliation = registry.database(
            model_name="BankReconciliation",
            operation="get",
            data={"id": data["reconciliation_id"]},
        )
        
        if not reconciliation:
            return ResponseProvider(
                message="Reconciliation not found", code=404
            ).bad_request()
        
        # Create item
        item_data = {
            "reconciliation": reconciliation,
            "item_type": data["item_type"],
            "date": data["date"],
            "reference": data["reference"],
            "description": data["description"],
            "amount": data["amount"],
        }
        
        item = registry.database(
            model_name="ReconciliationItem",
            operation="create",
            data=item_data,
        )
        
        # Update reconciliation totals based on item type
        from Accounting.models import BankReconciliation
        from decimal import Decimal
        
        recon_obj = BankReconciliation.objects.get(id=data["reconciliation_id"])
        amount = Decimal(str(data["amount"]))
        
        if data["item_type"] == "DEPOSIT_IN_TRANSIT":
            recon_obj.total_deposits_in_transit += amount
        elif data["item_type"] == "OUTSTANDING_CHECK":
            recon_obj.total_outstanding_checks += amount
        elif data["item_type"] == "BANK_CHARGE":
            recon_obj.total_bank_charges += amount
        elif data["item_type"] in ["ADJUSTMENT", "BANK_ERROR", "BOOK_ERROR"]:
            recon_obj.total_adjustments += amount
        
        recon_obj.calculate_difference()
        recon_obj.save()
        
        TransactionLogBase.log(
            transaction_type="RECONCILIATION_ITEM_ADDED",
            user=user,
            message=f"Added reconciliation item: {item['reference']}",
            state_name="Success",
            extra={"item_id": str(item["id"])},
            request=request,
        )
        
        return ResponseProvider(
            data={"item": item},
            message="Reconciliation item added successfully",
            code=201,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="RECONCILIATION_ITEM_ADD_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while adding reconciliation item", code=500
        ).exception()


@require_http_methods(["POST"])
def complete_bank_reconciliation(request):
    """Complete a bank reconciliation"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        reconciliation_id = data.get("reconciliation_id")
        if not reconciliation_id:
            return ResponseProvider(
                message="Missing reconciliation_id", code=400
            ).bad_request()
        
        from Accounting.models import BankReconciliation
        
        recon_obj = BankReconciliation.objects.get(id=reconciliation_id)
        recon_obj.complete()
        
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_COMPLETED",
            user=user,
            message=f"Completed bank reconciliation for {recon_obj.bank_account.account_name}",
            state_name="Success",
            extra={"reconciliation_id": str(reconciliation_id)},
            request=request,
        )
        
        return ResponseProvider(
            data={"message": "Reconciliation completed successfully"},
            message="Reconciliation completed successfully",
            code=200,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_COMPLETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=str(e), code=500
        ).exception()


@require_http_methods(["DELETE"])
def delete_bank_reconciliation(request):
    """Delete a bank reconciliation"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        reconciliation_id = data.get("id")
        if not reconciliation_id:
            return ResponseProvider(
                message="Missing reconciliation id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get reconciliation to check status
        reconciliation = registry.database(
            model_name="BankReconciliation",
            operation="get",
            data={"id": reconciliation_id},
        )
        
        if not reconciliation:
            return ResponseProvider(
                message="Reconciliation not found", code=404
            ).bad_request()
        
        # Only allow deletion of in-progress reconciliations
        if reconciliation["status"] != "IN_PROGRESS":
            return ResponseProvider(
                message="Only in-progress reconciliations can be deleted", code=400
            ).bad_request()
        
        registry.database(
            model_name="BankReconciliation",
            operation="delete",
            data={"id": reconciliation_id},
        )
        
        TransactionLogBase.log(
            transaction_type="BANK_RECONCILIATION_DELETED",
            user=user,
            message=f"Deleted bank reconciliation",
            state_name="Success",
            extra={"reconciliation_id": str(reconciliation_id)},
            request=request,
        )
        
        return ResponseProvider(
            message="Reconciliation deleted successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while deleting reconciliation", code=500
        ).exception()
