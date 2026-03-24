"""
Billing proxy endpoints - Frontend calls these, main backend proxies to billing service
This ensures proper authentication and authorization
"""
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.Services.billing_service import billing_service
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.rate_limit import rate_limit
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.token_utils import token_required

logger = logging.getLogger(__name__)


@csrf_exempt
@token_required
@rate_limit(max_requests=20, window_seconds=60, key_prefix="billing_subscription_status")
def get_subscription_status(request):
    """
    Get subscription status for the authenticated user's corporate.
    Proxies to billing service with service secret.
    """
    try:
        # Get corporate_id from authenticated user
        user_id = request.user_data.get("id")
        corporate_id = request.user_data.get("corporate_id")
        
        if not corporate_id:
            # Try to get from CorporateUser
            try:
                corp_user = CorporateUser.objects.select_related("corporate").get(id=user_id)
                corporate_id = str(corp_user.corporate.id)
            except CorporateUser.DoesNotExist:
                return JsonResponse({"error": "User not associated with any organization"}, status=404)
        
        # Call billing service
        result = billing_service.get_subscription_status(corporate_id)
        
        if result:
            return JsonResponse(result)
        else:
            return JsonResponse({"error": "Failed to fetch subscription status"}, status=500)
            
    except Exception as e:
        logger.error(f"Error fetching subscription status: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@token_required
@rate_limit(max_requests=20, window_seconds=60, key_prefix="billing_trial_status")
def get_trial_status(request):
    """
    Get trial status for the authenticated user's corporate.
    Proxies to billing service with service secret.
    """
    try:
        # Get corporate_id from authenticated user
        user_id = request.user_data.get("id")
        corporate_id = request.user_data.get("corporate_id")
        
        if not corporate_id:
            # Try to get from CorporateUser
            try:
                corp_user = CorporateUser.objects.select_related("corporate").get(id=user_id)
                corporate_id = str(corp_user.corporate.id)
            except CorporateUser.DoesNotExist:
                return JsonResponse({"error": "User not associated with any organization"}, status=404)
        
        # Call billing service
        result = billing_service.get_trial_status(corporate_id)
        
        if result:
            return JsonResponse(result)
        else:
            return JsonResponse({"error": "Failed to fetch trial status"}, status=500)
            
    except Exception as e:
        logger.error(f"Error fetching trial status: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@token_required
@rate_limit(max_requests=20, window_seconds=60, key_prefix="billing_invoices")
def list_invoices(request):
    """
    List invoices for the authenticated user's corporate.
    Proxies to billing service with service secret.
    """
    try:
        # Get corporate_id from authenticated user
        user_id = request.user_data.get("id")
        corporate_id = request.user_data.get("corporate_id")
        
        if not corporate_id:
            # Try to get from CorporateUser
            try:
                corp_user = CorporateUser.objects.select_related("corporate").get(id=user_id)
                corporate_id = str(corp_user.corporate.id)
            except CorporateUser.DoesNotExist:
                return JsonResponse({"error": "User not associated with any organization"}, status=404)
        
        # Call billing service
        result = billing_service.list_invoices(corporate_id)
        
        if result:
            return JsonResponse(result)
        else:
            return JsonResponse({"error": "Failed to fetch invoices"}, status=500)
            
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@token_required
@rate_limit(max_requests=20, window_seconds=60, key_prefix="billing_access_check")
def check_access(request):
    """
    Check if the authenticated user's corporate has active access.
    Proxies to billing service with service secret.
    """
    try:
        # Get corporate_id from authenticated user
        user_id = request.user_data.get("id")
        corporate_id = request.user_data.get("corporate_id")
        
        if not corporate_id:
            # Try to get from CorporateUser
            try:
                corp_user = CorporateUser.objects.select_related("corporate").get(id=user_id)
                corporate_id = str(corp_user.corporate.id)
            except CorporateUser.DoesNotExist:
                return JsonResponse({"error": "User not associated with any organization"}, status=404)
        
        # Call billing service
        result = billing_service.check_access(corporate_id)
        
        if result:
            return JsonResponse(result)
        else:
            return JsonResponse({"error": "Failed to check access"}, status=500)
            
    except Exception as e:
        logger.error(f"Error checking access: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@token_required
@rate_limit(max_requests=10, window_seconds=60, key_prefix="billing_plans")
def get_plans(request):
    """
    Get available billing plans.
    Proxies to billing service.
    """
    try:
        data, metadata = get_clean_data(request)
        plan_type = data.get("type", "individual")
        
        # Call billing service
        plans = billing_service.get_plans(plan_type)
        
        if plans is not None:
            return JsonResponse({"success": True, "plans": plans})
        else:
            return JsonResponse({"error": "Failed to fetch plans"}, status=500)
            
    except Exception as e:
        logger.error(f"Error fetching plans: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
