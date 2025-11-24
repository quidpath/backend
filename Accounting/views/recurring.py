# Recurring transaction views
from django.views.decorators.csrf import csrf_exempt
import logging
from datetime import datetime, timedelta

from Accounting.models.recurring import RecurringTransaction
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


@csrf_exempt
def list_recurring_transactions(request):
    """List recurring transactions for a corporate."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        # Build filter
        filter_data = {"corporate_id": corporate_id}
        if data.get("status"):
            filter_data["status"] = data.get("status")
        if data.get("transaction_type"):
            filter_data["transaction_type"] = data.get("transaction_type")
        
        transactions = registry.database(
            model_name="RecurringTransaction",
            operation="filter",
            data=filter_data
        )
        
        return ResponseProvider(data={"transactions": transactions}, message="Recurring transactions retrieved successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error listing recurring transactions: {e}")
        return ResponseProvider(message=f"Error listing recurring transactions: {str(e)}", code=500).exception()


@csrf_exempt
def update_recurring_transaction(request, transaction_id):
    """Update a recurring transaction."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        
        transaction = registry.database("RecurringTransaction", "get", data={"id": transaction_id})
        if not transaction:
            return ResponseProvider(message="Recurring transaction not found", code=404).bad_request()
        
        corporate_id = transaction.get("corporate_id")
        
        # Verify user has access
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="Recurring transaction not found", code=404).bad_request()
        
        # Update allowed fields
        update_data = {}
        allowed_fields = ["status", "frequency", "next_run_at", "auto_charge", "is_active"]
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        updated_transaction = registry.database("RecurringTransaction", "update", instance_id=transaction_id, data=update_data)
        
        return ResponseProvider(data=updated_transaction, message="Recurring transaction updated successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error updating recurring transaction: {e}")
        return ResponseProvider(message=f"Error updating recurring transaction: {str(e)}", code=500).exception()








