# Currency and exchange rate views
from django.views.decorators.csrf import csrf_exempt
import logging
import requests
from decimal import Decimal

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def get_currency_rates(request):
    """Get currency exchange rates."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        # Default rates (fallback)
        rates = [
            {
                "currency": "USD",
                "rate_to_usd": 1.0,
                "last_updated": datetime.now().isoformat(),
                "source": "Default"
            },
            {
                "currency": "KES",
                "rate_to_usd": 135.0,  # Approximate rate
                "last_updated": datetime.now().isoformat(),
                "source": "Default"
            }
        ]
        
        # TODO: Integrate with CBK API or other currency rate provider
        # For now, return default rates
        
        return ResponseProvider(data={"rates": rates}, message="Currency rates retrieved successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error getting currency rates: {e}")
        return ResponseProvider(message=f"Error getting currency rates: {str(e)}", code=500).exception()


@csrf_exempt
def refresh_currency_rates(request):
    """Refresh currency exchange rates from external API."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        # TODO: Implement actual CBK API integration
        # For now, return default rates
        
        rates = [
            {
                "currency": "USD",
                "rate_to_usd": 1.0,
                "last_updated": datetime.now().isoformat(),
                "source": "Default"
            },
            {
                "currency": "KES",
                "rate_to_usd": 135.0,
                "last_updated": datetime.now().isoformat(),
                "source": "Default"
            }
        ]
        
        return ResponseProvider(data={"rates": rates}, message="Currency rates refreshed successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error refreshing currency rates: {e}")
        return ResponseProvider(message=f"Error refreshing currency rates: {str(e)}", code=500).exception()








