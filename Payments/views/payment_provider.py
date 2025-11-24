# Payment provider management views
from django.views.decorators.csrf import csrf_exempt
import logging

from Payments.models import PaymentProvider
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


@csrf_exempt
def get_payment_provider(request, provider_type='flutterwave'):
    """Get payment provider configuration."""
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
        
        providers = registry.database(
            model_name="PaymentProvider",
            operation="filter",
            data={"corporate_id": corporate_id, "provider_type": provider_type, "is_active": True}
        )
        
        if providers:
            provider = providers[0]
            return ResponseProvider(data=provider, message="Payment provider retrieved successfully", code=200).success()
        else:
            return ResponseProvider(message="Payment provider not found", code=404).bad_request()
        
    except Exception as e:
        logger.exception(f"Error getting payment provider: {e}")
        return ResponseProvider(message=f"Error getting payment provider: {str(e)}", code=500).exception()


@csrf_exempt
def create_or_update_payment_provider(request, provider_type='flutterwave'):
    """Create or update payment provider configuration."""
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
        
        # Check if provider exists
        existing_providers = registry.database(
            model_name="PaymentProvider",
            operation="filter",
            data={"corporate_id": corporate_id, "provider_type": provider_type}
        )
        
        provider_data = {
            "corporate_id": corporate_id,
            "provider_type": provider_type,
            "provider_name": data.get("provider_name", "Flutterwave"),
            "is_active": data.get("is_active", True),
            "test_mode": data.get("test_mode", False),
            "config_json": data.get("config_json", {}),
        }
        
        if existing_providers:
            # Update existing provider
            provider = registry.database(
                "PaymentProvider",
                "update",
                instance_id=existing_providers[0]["id"],
                data=provider_data
            )
            message = "Payment provider updated successfully"
        else:
            # Create new provider
            provider = registry.database("PaymentProvider", "create", data=provider_data)
            message = "Payment provider created successfully"
        
        return ResponseProvider(data=provider, message=message, code=200).success()
        
    except Exception as e:
        logger.exception(f"Error saving payment provider: {e}")
        return ResponseProvider(message=f"Error saving payment provider: {str(e)}", code=500).exception()








