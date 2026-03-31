"""
Individual user payment verification
Handles payment verification and account activation
"""
import logging
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def verify_individual_payment(request):
    """
    Verify individual payment and activate account
    Called after successful payment on custom payment page
    """
    data, metadata = get_clean_data(request)
    
    try:
        reference = data.get("reference")
        corporate_id = data.get("corporate_id")
        
        if not reference or not corporate_id:
            return JsonResponse({"error": "Reference and corporate_id required"}, status=400)
        
        # Verify with Paystack directly
        import requests
        
        secret_key = os.environ.get("PAYSTACK_SECRET_KEY", "")
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            return JsonResponse({"error": "Payment verification failed"}, status=400)
        
        response_data = response.json()
        if not response_data.get("status") or response_data.get("data", {}).get("status") != "success":
            return JsonResponse({"error": "Payment was not successful"}, status=400)
        
        # Get corporate and user
        try:
            corporate = Corporate.objects.get(id=corporate_id)
            user = CorporateUser.objects.get(corporate=corporate)
        except (Corporate.DoesNotExist, CorporateUser.DoesNotExist):
            return JsonResponse({"error": "Account not found"}, status=404)
        
        # Activate account
        user.is_active = True
        user.save(update_fields=["is_active"])
        
        corporate.is_active = True
        corporate.save(update_fields=["is_active"])
        
        # Create subscription in billing service
        try:
            from quidpath_backend.core.Services.billing_service import BillingServiceClient
            
            billing_client = BillingServiceClient()
            plan_tier = user.metadata.get("plan_tier", "starter") if hasattr(user, "metadata") and user.metadata else "starter"
            
            billing_client.create_subscription(
                corporate_id=str(corporate_id),
                corporate_name=corporate.name,
                plan_tier=plan_tier,
                billing_cycle="monthly",
            )
            
            logger.info(f"Subscription created for individual user: {user.username}")
        except Exception as e:
            logger.warning(f"Failed to create subscription: {e}")
        
        TransactionLogBase.log(
            "INDIVIDUAL_PAYMENT_VERIFIED",
            user=user,
            message=f"Payment verified and account activated: {user.username}",
            extra={"reference": reference, "corporate_id": str(corporate_id)},
        )
        
        return JsonResponse({
            "success": True,
            "message": "Payment verified. Your account is now active!",
            "username": user.username,
            "email": user.email,
        })
    
    except Exception as e:
        logger.error(f"Error verifying individual payment: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
