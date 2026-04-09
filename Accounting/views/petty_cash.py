"""
Petty Cash Management Views
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase


def _get_corporate_id(user, registry):
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return None, None
    corporate_users = registry.database(
        model_name="CorporateUser",
        operation="filter",
        data={"customuser_ptr_id": user_id, "is_active": True},
    )
    if not corporate_users:
        return None, None
    return corporate_users[0]["corporate_id"], user_id


@csrf_exempt
@require_http_methods(["POST"])
def create_petty_cash_fund(request):
    """Create a new petty cash fund"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()
        corporate_id, user_id = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        required_fields = ["name", "initial_amount", "custodian_id"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"Missing required field: {field}", code=400).bad_request()

        # Get custodian
        custodians = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": data["custodian_id"], "corporate_id": corporate_id},
        )
        if not custodians:
            return ResponseProvider(message="Custodian not found", code=404).bad_request()

        fund_data = {
            "corporate_id": corporate_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "custodian_id": data["custodian_id"],
            "initial_amount": data["initial_amount"],
            "current_balance": data["initial_amount"],
            "created_by_id": user_id,
        }

        fund = registry.database(model_name="PettyCashFund", operation="create", data=fund_data)

        TransactionLogBase.log(
            transaction_type="PETTY_CASH_FUND_CREATED", user=user,
            message=f"Created petty cash fund: {fund['name']}",
            state_name="Success", extra={"fund_id": str(fund["id"])}, request=request,
        )

        return ResponseProvider(
            data={"fund": {"id": str(fund["id"]), "name": fund["name"]}},
            message="Petty cash fund created successfully", code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_FUND_CREATE_FAILED", user=user,
            message=str(e), state_name="Failed", request=request,
        )
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["GET"])
def list_petty_cash_funds(request):
    """List all petty cash funds for the corporate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()
        corporate_id, _ = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        funds = registry.database(
            model_name="PettyCashFund",
            operation="filter",
            data={"corporate_id": corporate_id},
        )

        def _name(obj, field="username"):
            if isinstance(obj, dict):
                return obj.get(field, "")
            return getattr(obj, field, "") if obj else ""

        serialized = [
            {
                "id": str(f["id"]),
                "name": f["name"],
                "description": f.get("description", ""),
                "custodian": _name(f.get("custodian")),
                "custodian_id": str(_name(f.get("custodian"), "id") or f.get("custodian_id", "")),
                "initial_amount": float(f.get("initial_amount", 0)),
                "current_balance": float(f.get("current_balance", 0)),
                "is_active": f.get("is_active", True),
                "created_at": str(f.get("created_at", "")),
            }
            for f in funds
        ]

        return ResponseProvider(
            data={"funds": serialized, "total": len(serialized)},
            message="Petty cash funds retrieved successfully", code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["POST"])
def create_petty_cash_transaction(request):
    """Create a new petty cash transaction"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()
        corporate_id, user_id = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        required_fields = ["fund_id", "transaction_type", "date", "reference", "description", "amount"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"Missing required field: {field}", code=400).bad_request()

        # Verify fund belongs to this corporate
        funds = registry.database(
            model_name="PettyCashFund",
            operation="filter",
            data={"id": data["fund_id"], "corporate_id": corporate_id},
        )
        if not funds:
            return ResponseProvider(message="Petty cash fund not found", code=404).bad_request()

        transaction_data = {
            "fund_id": data["fund_id"],
            "transaction_type": data["transaction_type"],
            "date": data["date"],
            "reference": data["reference"],
            "description": data["description"],
            "category": data.get("category", ""),
            "amount": data["amount"],
            "recipient": data.get("recipient", ""),
            "receipt_number": data.get("receipt_number", ""),
            "requested_by_id": user_id,
            "status": "PENDING",
        }

        txn = registry.database(model_name="PettyCashTransaction", operation="create", data=transaction_data)

        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_CREATED", user=user,
            message=f"Created petty cash transaction: {txn['reference']}",
            state_name="Success", extra={"transaction_id": str(txn["id"])}, request=request,
        )

        return ResponseProvider(
            data={"transaction": {"id": str(txn["id"]), "reference": txn["reference"], "status": txn["status"]}},
            message="Petty cash transaction created successfully", code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_CREATE_FAILED", user=user,
            message=str(e), state_name="Failed", request=request,
        )
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["GET"])
def list_petty_cash_transactions(request):
    """List petty cash transactions"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()
        corporate_id, _ = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        # Get all funds for this corporate
        funds = registry.database(
            model_name="PettyCashFund",
            operation="filter",
            data={"corporate_id": corporate_id},
        )
        fund_ids = [f["id"] for f in funds]
        fund_names = {f["id"]: f["name"] for f in funds}

        all_transactions = []
        for fund_id in fund_ids:
            txns = registry.database(
                model_name="PettyCashTransaction",
                operation="filter",
                data={"fund_id": fund_id},
            )
            all_transactions.extend(txns)

        def _str_date(v):
            if hasattr(v, "isoformat"):
                return v.isoformat()
            return str(v or "")

        def _username(obj):
            if isinstance(obj, dict):
                return obj.get("username", "")
            return getattr(obj, "username", "") if obj else ""

        serialized = [
            {
                "id": str(t["id"]),
                "fund_id": str(t.get("fund_id", "")),
                "fund_name": fund_names.get(t.get("fund_id"), ""),
                "transaction_type": t["transaction_type"],
                "date": _str_date(t.get("date")),
                "reference": t["reference"],
                "description": t["description"],
                "category": t.get("category", ""),
                "amount": float(t["amount"]),
                "recipient": t.get("recipient", ""),
                "receipt_number": t.get("receipt_number", ""),
                "status": t["status"],
                "requested_by": _username(t.get("requested_by")),
                "created_at": _str_date(t.get("created_at")),
            }
            for t in all_transactions
        ]

        return ResponseProvider(
            data={"transactions": serialized, "total": len(serialized)},
            message="Petty cash transactions retrieved successfully", code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
@require_http_methods(["POST"])
def reverse_petty_cash_transaction(request):
    """Reverse an approved petty cash transaction"""
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
        
        from Accounting.models import PettyCashTransaction
        txn_obj = PettyCashTransaction.objects.get(id=transaction_id)
        txn_obj.reverse(user)
        
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_REVERSED",
            user=user,
            message=f"Reversed petty cash transaction: {txn_obj.reference}",
            state_name="Success",
            extra={"transaction_id": str(transaction_id)},
            request=request,
        )
        
        return ResponseProvider(
            data={"message": "Transaction reversed successfully"},
            message="Transaction reversed successfully",
            code=200,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PETTY_CASH_TRANSACTION_REVERSE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=str(e), code=500
        ).exception()
