"""
Tax Rate Management Views
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase


def _get_corporate_id(user, registry):
    """Resolve corporate_id from user dict or object."""
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
def create_tax_rate(request):
    """Create a new tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()
        corporate_id, user_id = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        required_fields = ["name"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"Missing required field: {field}", code=400).bad_request()

        # Check for duplicate name within corporate
        existing = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"corporate_id": corporate_id, "name": data["name"]},
        )
        if existing:
            return ResponseProvider(message="A tax rate with this name already exists", code=400).bad_request()

        tax_rate_data = {
            "corporate_id": corporate_id,
            "name": data["name"],
        }
        if data.get("sales_account_id"):
            tax_rate_data["sales_account_id"] = data["sales_account_id"]
        if data.get("purchase_account_id"):
            tax_rate_data["purchase_account_id"] = data["purchase_account_id"]

        tax_rate = registry.database(model_name="TaxRate", operation="create", data=tax_rate_data)

        TransactionLogBase.log(
            transaction_type="TAX_RATE_CREATED", user=user,
            message=f"Created tax rate: {tax_rate['name']}",
            state_name="Success", extra={"tax_rate_id": str(tax_rate["id"])}, request=request,
        )

        return ResponseProvider(
            data={"tax_rate": {
                "id": str(tax_rate["id"]),
                "name": tax_rate["name"],
                "rate": float(tax_rate.get("rate", 0)),
                "created_at": str(tax_rate.get("created_at", "")),
            }},
            message="Tax rate created successfully", code=201,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TAX_RATE_CREATE_FAILED", user=user,
            message=str(e), state_name="Failed", request=request,
        )
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["GET"])
def list_tax_rates(request):
    """List all tax rates for the corporate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()
        corporate_id, _ = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        tax_rates = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"corporate_id": corporate_id},
        )

        def _safe_account(field):
            if not field:
                return None, None
            if isinstance(field, dict):
                return str(field.get("id", "")), field.get("name", "")
            if hasattr(field, "id"):
                return str(field.id), getattr(field, "name", "")
            return str(field), None

        serialized = []
        for rate in tax_rates:
            sales_id, sales_name = _safe_account(rate.get("sales_account"))
            purchase_id, purchase_name = _safe_account(rate.get("purchase_account"))
            serialized.append({
                "id": str(rate["id"]),
                "name": rate["name"],
                "rate": float(rate.get("rate", 0)),
                "sales_account_id": sales_id,
                "sales_account_name": sales_name,
                "purchase_account_id": purchase_id,
                "purchase_account_name": purchase_name,
                "created_at": str(rate.get("created_at", "")),
            })

        return ResponseProvider(
            data={"tax_rates": serialized, "total": len(serialized)},
            message="Tax rates retrieved successfully", code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["GET"])
def get_tax_rate_detail(request):
    """Get a specific tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        tax_rate_id = data.get("id")
        if not tax_rate_id:
            return ResponseProvider(message="Missing tax rate id", code=400).bad_request()

        registry = ServiceRegistry()
        corporate_id, _ = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        rates = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"id": tax_rate_id, "corporate_id": corporate_id},
        )
        if not rates:
            return ResponseProvider(message="Tax rate not found", code=404).bad_request()

        rate = rates[0]
        return ResponseProvider(
            data={"tax_rate": {
                "id": str(rate["id"]),
                "name": rate["name"],
                "rate": float(rate.get("rate", 0)),
            }},
            message="Tax rate retrieved successfully", code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["PUT"])
def update_tax_rate(request):
    """Update a tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        tax_rate_id = data.get("id")
        if not tax_rate_id:
            return ResponseProvider(message="Missing tax rate id", code=400).bad_request()

        registry = ServiceRegistry()
        corporate_id, _ = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        rates = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"id": tax_rate_id, "corporate_id": corporate_id},
        )
        if not rates:
            return ResponseProvider(message="Tax rate not found", code=404).bad_request()

        update_data = {}
        if "name" in data:
            update_data["name"] = data["name"]
        if "sales_account_id" in data:
            update_data["sales_account_id"] = data["sales_account_id"] or None
        if "purchase_account_id" in data:
            update_data["purchase_account_id"] = data["purchase_account_id"] or None

        updated = registry.database(
            model_name="TaxRate",
            operation="update",
            instance_id=tax_rate_id,
            data=update_data,
        )

        TransactionLogBase.log(
            transaction_type="TAX_RATE_UPDATED", user=user,
            message=f"Updated tax rate: {updated.get('name', tax_rate_id)}",
            state_name="Success", extra={"tax_rate_id": str(tax_rate_id)}, request=request,
        )

        return ResponseProvider(
            data={"tax_rate": {"id": str(updated["id"]), "name": updated["name"], "rate": float(updated.get("rate", 0))}},
            message="Tax rate updated successfully", code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TAX_RATE_UPDATE_FAILED", user=user,
            message=str(e), state_name="Failed", request=request,
        )
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_tax_rate(request):
    """Delete a tax rate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        tax_rate_id = data.get("id")
        if not tax_rate_id:
            return ResponseProvider(message="Missing tax rate id", code=400).bad_request()

        registry = ServiceRegistry()
        corporate_id, _ = _get_corporate_id(user, registry)
        if not corporate_id:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        rates = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"id": tax_rate_id, "corporate_id": corporate_id},
        )
        if not rates:
            return ResponseProvider(message="Tax rate not found", code=404).bad_request()

        registry.database(model_name="TaxRate", operation="delete", instance_id=tax_rate_id)

        TransactionLogBase.log(
            transaction_type="TAX_RATE_DELETED", user=user,
            message=f"Deleted tax rate: {tax_rate_id}",
            state_name="Success", extra={"tax_rate_id": str(tax_rate_id)}, request=request,
        )

        return ResponseProvider(message="Tax rate deleted successfully", code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="TAX_RATE_DELETE_FAILED", user=user,
            message=str(e), state_name="Failed", request=request,
        )
        return ResponseProvider(message=f"An error occurred: {str(e)}", code=500).exception()



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
