"""
Petty Cash Management Views
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from Accounting.models import PettyCashFund, PettyCashTransaction
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase


@require_http_methods(["POST"])
def create_petty_cash_fund(request):
    """Create a new petty cash fund"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        required_fields = ["name", "initial_amount", "custodian_id"]
        
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"Missing required field: {field}", code=400
                ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get custodian
        custodian = registry.database(
            model_name="CorporateUser",
            operation="get",
            data={"id": data["custodian_id"]},
        )
        
        if not custodian:
            return ResponseProvider(
                message="Custodian not found", code=404
            ).bad_request()
        
        # Create fund
        fund_data = {
            "corporate": corporate,
            "name": data["name"],
            "description": data.get("description", ""),
            "custodian": custodian,
            "initial_amount": data["initial_amount"],
            "created_by": user,
        }
        
        fund = registry.database(
            model_name="PettyCashFund",
            operation="create",
            data=fund_data,
        )
        
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_FUND_CREATED",
            user=user,
            message=f"Created petty cash fund: {fund['name']}",
            state_name="Success",
            extra={"fund_id": str(fund["id"])},
            request=request,
        )
        
        return ResponseProvider(
            data={"fund": fund},
            message="Petty cash fund created successfully",
            code=201,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_FUND_CREATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating petty cash fund", code=500
        ).exception()


@require_http_methods(["GET"])
def list_petty_cash_funds(request):
    """List all petty cash funds for the corporate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        registry = ServiceRegistry()
        
        funds = registry.database(
            model_name="PettyCashFund",
            operation="filter",
            data={"corporate": corporate},
        )
        
        serialized_funds = [
            {
                "id": str(fund["id"]),
                "name": fund["name"],
                "description": fund.get("description", ""),
                "custodian": fund["custodian"]["username"] if isinstance(fund.get("custodian"), dict) else fund.get("custodian").username if hasattr(fund.get("custodian"), "username") else "",
                "custodian_id": str(fund["custodian"]["id"]) if isinstance(fund.get("custodian"), dict) else str(fund.get("custodian").id) if hasattr(fund.get("custodian"), "id") else "",
                "initial_amount": float(fund["initial_amount"]),
                "current_balance": float(fund["current_balance"]),
                "is_active": fund["is_active"],
                "created_at": fund["created_at"].isoformat() if hasattr(fund.get("created_at"), "isoformat") else str(fund.get("created_at", "")),
            }
            for fund in funds
        ]
        
        return ResponseProvider(
            data={"funds": serialized_funds, "total": len(serialized_funds)},
            message="Petty cash funds retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving petty cash funds", code=500
        ).exception()


@require_http_methods(["POST"])
def create_petty_cash_transaction(request):
    """Create a new petty cash transaction"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        required_fields = ["fund_id", "transaction_type", "date", "reference", "description", "amount"]
        
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"Missing required field: {field}", code=400
                ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get fund
        fund = registry.database(
            model_name="PettyCashFund",
            operation="get",
            data={"id": data["fund_id"]},
        )
        
        if not fund:
            return ResponseProvider(
                message="Petty cash fund not found", code=404
            ).bad_request()
        
        # Create transaction
        transaction_data = {
            "fund": fund,
            "transaction_type": data["transaction_type"],
            "date": data["date"],
            "reference": data["reference"],
            "description": data["description"],
            "category": data.get("category", ""),
            "amount": data["amount"],
            "recipient": data.get("recipient", ""),
            "receipt_number": data.get("receipt_number", ""),
            "requested_by": user,
            "status": "PENDING",
        }
        
        transaction = registry.database(
            model_name="PettyCashTransaction",
            operation="create",
            data=transaction_data,
        )
        
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_CREATED",
            user=user,
            message=f"Created petty cash transaction: {transaction['reference']}",
            state_name="Success",
            extra={"transaction_id": str(transaction["id"])},
            request=request,
        )
        
        return ResponseProvider(
            data={"transaction": transaction},
            message="Petty cash transaction created successfully",
            code=201,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_CREATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating petty cash transaction", code=500
        ).exception()


@require_http_methods(["GET"])
def list_petty_cash_transactions(request):
    """List petty cash transactions"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        registry = ServiceRegistry()
        
        # Get all funds for this corporate
        funds = registry.database(
            model_name="PettyCashFund",
            operation="filter",
            data={"corporate": corporate},
        )
        
        fund_ids = [fund["id"] if isinstance(fund, dict) else fund.id for fund in funds]
        
        # Get transactions for these funds
        all_transactions = []
        for fund_id in fund_ids:
            transactions = registry.database(
                model_name="PettyCashTransaction",
                operation="filter",
                data={"fund": fund_id},
            )
            all_transactions.extend(transactions)
        
        serialized_transactions = [
            {
                "id": str(txn["id"]),
                "fund_id": str(txn["fund"]["id"]) if isinstance(txn.get("fund"), dict) else str(txn.get("fund").id) if hasattr(txn.get("fund"), "id") else "",
                "fund_name": txn["fund"]["name"] if isinstance(txn.get("fund"), dict) else txn.get("fund").name if hasattr(txn.get("fund"), "name") else "",
                "transaction_type": txn["transaction_type"],
                "date": txn["date"].isoformat() if hasattr(txn.get("date"), "isoformat") else str(txn.get("date", "")),
                "reference": txn["reference"],
                "description": txn["description"],
                "category": txn.get("category", ""),
                "amount": float(txn["amount"]),
                "recipient": txn.get("recipient", ""),
                "receipt_number": txn.get("receipt_number", ""),
                "status": txn["status"],
                "requested_by": txn["requested_by"]["username"] if isinstance(txn.get("requested_by"), dict) else txn.get("requested_by").username if hasattr(txn.get("requested_by"), "username") else "",
                "created_at": txn["created_at"].isoformat() if hasattr(txn.get("created_at"), "isoformat") else str(txn.get("created_at", "")),
            }
            for txn in all_transactions
        ]
        
        return ResponseProvider(
            data={"transactions": serialized_transactions, "total": len(serialized_transactions)},
            message="Petty cash transactions retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving petty cash transactions", code=500
        ).exception()


@require_http_methods(["POST"])
def approve_petty_cash_transaction(request):
    """Approve a petty cash transaction"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        transaction_id = data.get("transaction_id")
        if not transaction_id:
            return ResponseProvider(
                message="Missing transaction_id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get transaction
        transaction = registry.database(
            model_name="PettyCashTransaction",
            operation="get",
            data={"id": transaction_id},
        )
        
        if not transaction:
            return ResponseProvider(
                message="Transaction not found", code=404
            ).bad_request()
        
        # Approve transaction (this will update fund balance)
        from Accounting.models import PettyCashTransaction
        txn_obj = PettyCashTransaction.objects.get(id=transaction_id)
        txn_obj.approve(user)
        
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_APPROVED",
            user=user,
            message=f"Approved petty cash transaction: {txn_obj.reference}",
            state_name="Success",
            extra={"transaction_id": str(transaction_id)},
            request=request,
        )
        
        return ResponseProvider(
            data={"message": "Transaction approved successfully"},
            message="Transaction approved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_APPROVE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=str(e), code=500
        ).exception()


@require_http_methods(["DELETE"])
def delete_petty_cash_transaction(request):
    """Delete a petty cash transaction"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        transaction_id = data.get("id")
        if not transaction_id:
            return ResponseProvider(
                message="Missing transaction id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get transaction to check status
        transaction = registry.database(
            model_name="PettyCashTransaction",
            operation="get",
            data={"id": transaction_id},
        )
        
        if not transaction:
            return ResponseProvider(
                message="Transaction not found", code=404
            ).bad_request()
        
        # Only allow deletion of pending transactions
        if transaction["status"] != "PENDING":
            return ResponseProvider(
                message="Only pending transactions can be deleted", code=400
            ).bad_request()
        
        registry.database(
            model_name="PettyCashTransaction",
            operation="delete",
            data={"id": transaction_id},
        )
        
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_DELETED",
            user=user,
            message=f"Deleted petty cash transaction: {transaction['reference']}",
            state_name="Success",
            extra={"transaction_id": str(transaction_id)},
            request=request,
        )
        
        return ResponseProvider(
            message="Transaction deleted successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while deleting transaction", code=500
        ).exception()
