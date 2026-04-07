"""
Tax Rate Management Views
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from Accounting.models import TaxRate
from quidpath_backend.core.helpers.data_helpers import get_clean_data
from quidpath_backend.core.helpers.response_provider import ResponseProvider
from quidpath_backend.core.helpers.service_registry import ServiceRegistry
from quidpath_backend.core.helpers.transaction_log import TransactionLogBase


@require_http_methods(["POST"])
def create_tax_rate(request):
    """Create a new tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        required_fields = ["name", "rate"]
        
        for field in required_fields:
            if field not in data:
                return ResponseProvider(
                    message=f"Missing required field: {field}", code=400
                ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get accounts if provided
        sales_account = None
        purchase_account = None
        
        if data.get("sales_account_id"):
            sales_account = registry.database(
                model_name="Account",
                operation="get",
                data={"id": data["sales_account_id"]},
            )
        
        if data.get("purchase_account_id"):
            purchase_account = registry.database(
                model_name="Account",
                operation="get",
                data={"id": data["purchase_account_id"]},
            )
        
        # Create tax rate
        tax_rate_data = {
            "corporate": corporate,
            "name": data["name"],
            "rate": data["rate"],
        }
        
        if sales_account:
            tax_rate_data["sales_account"] = sales_account
        if purchase_account:
            tax_rate_data["purchase_account"] = purchase_account
        
        tax_rate = registry.database(
            model_name="TaxRate",
            operation="create",
            data=tax_rate_data,
        )
        
        TransactionLogBase.log(
            transaction_type="TAX_RATE_CREATED",
            user=user,
            message=f"Created tax rate: {tax_rate['name']}",
            state_name="Success",
            extra={"tax_rate_id": str(tax_rate["id"])},
            request=request,
        )
        
        return ResponseProvider(
            data={"tax_rate": tax_rate},
            message="Tax rate created successfully",
            code=201,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TAX_RATE_CREATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating tax rate", code=500
        ).exception()


@require_http_methods(["GET"])
def list_tax_rates(request):
    """List all tax rates for the corporate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        corporate = user.corporate
        registry = ServiceRegistry()
        
        tax_rates = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"corporate": corporate},
        )
        
        serialized_tax_rates = [
            {
                "id": str(rate["id"]),
                "name": rate["name"],
                "rate": float(rate["rate"]),
                "sales_account_id": str(rate["sales_account"]["id"]) if rate.get("sales_account") and isinstance(rate["sales_account"], dict) else str(rate["sales_account"].id) if rate.get("sales_account") and hasattr(rate["sales_account"], "id") else None,
                "sales_account_name": rate["sales_account"]["name"] if rate.get("sales_account") and isinstance(rate["sales_account"], dict) else rate["sales_account"].name if rate.get("sales_account") and hasattr(rate["sales_account"], "name") else None,
                "purchase_account_id": str(rate["purchase_account"]["id"]) if rate.get("purchase_account") and isinstance(rate["purchase_account"], dict) else str(rate["purchase_account"].id) if rate.get("purchase_account") and hasattr(rate["purchase_account"], "id") else None,
                "purchase_account_name": rate["purchase_account"]["name"] if rate.get("purchase_account") and isinstance(rate["purchase_account"], dict) else rate["purchase_account"].name if rate.get("purchase_account") and hasattr(rate["purchase_account"], "name") else None,
                "created_at": rate["created_at"].isoformat() if hasattr(rate.get("created_at"), "isoformat") else str(rate.get("created_at", "")),
            }
            for rate in tax_rates
        ]
        
        return ResponseProvider(
            data={"tax_rates": serialized_tax_rates, "total": len(serialized_tax_rates)},
            message="Tax rates retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving tax rates", code=500
        ).exception()


@require_http_methods(["GET"])
def get_tax_rate_detail(request):
    """Get a specific tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        tax_rate_id = data.get("id")
        if not tax_rate_id:
            return ResponseProvider(
                message="Missing tax rate id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        tax_rate = registry.database(
            model_name="TaxRate",
            operation="get",
            data={"id": tax_rate_id},
        )
        
        if not tax_rate:
            return ResponseProvider(
                message="Tax rate not found", code=404
            ).bad_request()
        
        return ResponseProvider(
            data={"tax_rate": tax_rate},
            message="Tax rate retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving tax rate", code=500
        ).exception()


@require_http_methods(["PUT"])
def update_tax_rate(request):
    """Update a tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        tax_rate_id = data.get("id")
        if not tax_rate_id:
            return ResponseProvider(
                message="Missing tax rate id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get existing tax rate
        tax_rate = registry.database(
            model_name="TaxRate",
            operation="get",
            data={"id": tax_rate_id},
        )
        
        if not tax_rate:
            return ResponseProvider(
                message="Tax rate not found", code=404
            ).bad_request()
        
        # Prepare update data
        update_data = {"id": tax_rate_id}
        
        if "name" in data:
            update_data["name"] = data["name"]
        if "rate" in data:
            update_data["rate"] = data["rate"]
        if "sales_account_id" in data:
            if data["sales_account_id"]:
                sales_account = registry.database(
                    model_name="Account",
                    operation="get",
                    data={"id": data["sales_account_id"]},
                )
                update_data["sales_account"] = sales_account
            else:
                update_data["sales_account"] = None
        if "purchase_account_id" in data:
            if data["purchase_account_id"]:
                purchase_account = registry.database(
                    model_name="Account",
                    operation="get",
                    data={"id": data["purchase_account_id"]},
                )
                update_data["purchase_account"] = purchase_account
            else:
                update_data["purchase_account"] = None
        
        # Update tax rate
        updated_tax_rate = registry.database(
            model_name="TaxRate",
            operation="update",
            data=update_data,
        )
        
        TransactionLogBase.log(
            transaction_type="TAX_RATE_UPDATED",
            user=user,
            message=f"Updated tax rate: {updated_tax_rate.get('name', tax_rate_id)}",
            state_name="Success",
            extra={"tax_rate_id": str(tax_rate_id)},
            request=request,
        )
        
        return ResponseProvider(
            data={"tax_rate": updated_tax_rate},
            message="Tax rate updated successfully",
            code=200,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TAX_RATE_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while updating tax rate", code=500
        ).exception()


@require_http_methods(["DELETE"])
def delete_tax_rate(request):
    """Delete a tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()
    
    try:
        tax_rate_id = data.get("id")
        if not tax_rate_id:
            return ResponseProvider(
                message="Missing tax rate id", code=400
            ).bad_request()
        
        registry = ServiceRegistry()
        
        # Get tax rate
        tax_rate = registry.database(
            model_name="TaxRate",
            operation="get",
            data={"id": tax_rate_id},
        )
        
        if not tax_rate:
            return ResponseProvider(
                message="Tax rate not found", code=404
            ).bad_request()
        
        # Delete tax rate
        registry.database(
            model_name="TaxRate",
            operation="delete",
            data={"id": tax_rate_id},
        )
        
        TransactionLogBase.log(
            transaction_type="TAX_RATE_DELETED",
            user=user,
            message=f"Deleted tax rate: {tax_rate.get('name', tax_rate_id)}",
            state_name="Success",
            extra={"tax_rate_id": str(tax_rate_id)},
            request=request,
        )
        
        return ResponseProvider(
            message="Tax rate deleted successfully",
            code=200,
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TAX_RATE_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while deleting tax rate", code=500
        ).exception()
