"""
Billing redirect handler for email links
When users click "Set Up Billing" in their approval email, they should be redirected to:
- Billing setup page if not paid
- Dashboard if already paid
"""
import logging

from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from OrgAuth.models import Corporate
from quidpath_backend.core.Services.billing_service import billing_service
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def billing_redirect_handler(request):
    """
    Handle billing redirect from email links.
    Smart redirect logic:
    1. If corporate has entered phone number + has active trial → Dashboard
    2. If corporate has entered phone number + has paid subscription → Dashboard
    3. If corporate has NOT entered phone number → Billing setup page
    
    Query params:
    - corporate_id: The corporate ID
    - redirect_to: Optional redirect destination after payment
    """
    corporate_id = request.GET.get("corporate_id")
    redirect_to = request.GET.get("redirect_to", "/dashboard")
    
    if not corporate_id:
        return JsonResponse(
            {"error": "corporate_id is required"},
            status=400
        )
    
    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except Corporate.DoesNotExist:
        return JsonResponse(
            {"error": "Organisation not found"},
            status=404
        )
    
    frontend_url = getattr(settings, "FRONTEND_URL", "https://stage.quidpath.com")
    
    # Check if corporate has entered phone number (billing details)
    if not corporate.phone or corporate.phone.strip() == "":
        # No phone number entered - redirect to billing setup
        billing_setup_url = f"{frontend_url}/settings/billing?corporate_id={corporate_id}"
        
        TransactionLogBase.log(
            "BILLING_REDIRECT_TO_SETUP",
            user=None,
            message=f"Corporate {corporate.name} redirected to billing setup (no phone number)",
            extra={"corporate_id": str(corporate.id), "reason": "no_phone_number"}
        )
        
        return HttpResponseRedirect(billing_setup_url)
    
    # Phone number entered - check if they have active trial or subscription
    if corporate.is_active:
        # Check billing service for active subscription or trial
        try:
            access_check = billing_service.check_access(str(corporate.id))
            
            if access_check and access_check.get("success") and access_check.get("has_access"):
                # User has active trial or paid subscription - redirect to dashboard
                redirect_url = f"{frontend_url}{redirect_to}"
                
                TransactionLogBase.log(
                    "BILLING_REDIRECT_TO_DASHBOARD",
                    user=None,
                    message=f"Corporate {corporate.name} redirected to dashboard (has access)",
                    extra={"corporate_id": str(corporate.id), "has_phone": True}
                )
                
                return HttpResponseRedirect(redirect_url)
        except Exception as e:
            logger.warning(f"Billing check failed for {corporate.name}: {e}")
    
    # Phone entered but no active trial/subscription - redirect to billing setup
    billing_setup_url = f"{frontend_url}/settings/billing?corporate_id={corporate_id}"
    
    TransactionLogBase.log(
        "BILLING_REDIRECT_TO_SETUP",
        user=None,
        message=f"Corporate {corporate.name} redirected to billing setup (no active access)",
        extra={"corporate_id": str(corporate.id), "has_phone": True, "is_active": corporate.is_active}
    )
    
    return HttpResponseRedirect(billing_setup_url)


@csrf_exempt
def check_billing_status(request):
    """
    API endpoint to check billing status and get redirect URL.
    Used by frontend to determine where to redirect user.
    
    Smart logic:
    1. No phone number → Redirect to billing setup
    2. Has phone + active trial → Has access (dashboard)
    3. Has phone + paid subscription → Has access (dashboard)
    4. Has phone but no active trial/subscription → Redirect to billing setup
    
    Returns:
    - has_access: boolean
    - redirect_url: where to redirect user
    - requires_payment: boolean
    - requires_phone: boolean (NEW)
    - trial_info: trial information if applicable
    """
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate_id")
    
    if not corporate_id:
        return JsonResponse(
            {"error": "corporate_id is required"},
            status=400
        )
    
    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except Corporate.DoesNotExist:
        return JsonResponse(
            {"error": "Organisation not found"},
            status=404
        )
    
    frontend_url = getattr(settings, "FRONTEND_URL", "https://stage.quidpath.com")
    
    # Check if phone number has been entered
    if not corporate.phone or corporate.phone.strip() == "":
        return JsonResponse({
            "success": True,
            "has_access": False,
            "requires_payment": False,
            "requires_phone": True,
            "redirect_url": f"{frontend_url}/settings/billing?corporate_id={corporate_id}",
            "message": "Please enter your billing details to start your trial"
        })
    
    # Phone number entered - check if corporate is active
    if not corporate.is_active:
        return JsonResponse({
            "success": True,
            "has_access": False,
            "requires_payment": False,
            "requires_phone": False,
            "redirect_url": f"{frontend_url}/settings/billing?corporate_id={corporate_id}",
            "message": "Please complete billing setup to activate your account"
        })
    
    # Check billing service for active trial or subscription
    try:
        access_check = billing_service.check_access(str(corporate.id))
        
        if access_check and access_check.get("success"):
            has_access = access_check.get("has_access", False)
            
            if has_access:
                # Get trial info if available
                trial_info = None
                try:
                    trial_status = billing_service.get_trial_status(str(corporate.id))
                    if trial_status and trial_status.get("success"):
                        trial_data = trial_status.get("data", {})
                        trial = trial_data.get("trial")
                        if trial and trial.get("status") == "active":
                            trial_info = {
                                "is_trial": True,
                                "end_date": trial.get("end_date"),
                                "days_remaining": trial.get("days_remaining"),
                                "trial_days": 30  # Updated to 30 days
                            }
                except Exception as e:
                    logger.warning(f"Failed to get trial info: {e}")
                
                return JsonResponse({
                    "success": True,
                    "has_access": True,
                    "requires_payment": False,
                    "requires_phone": False,
                    "redirect_url": f"{frontend_url}/dashboard",
                    "trial_info": trial_info,
                    "message": "Access granted" + (" - Trial active" if trial_info else "")
                })
            else:
                reason = access_check.get("reason", "no_active_subscription")
                return JsonResponse({
                    "success": True,
                    "has_access": False,
                    "requires_payment": True,
                    "requires_phone": False,
                    "redirect_url": f"{frontend_url}/settings/billing?corporate_id={corporate_id}",
                    "reason": reason,
                    "message": access_check.get("message", "Payment required to access the system")
                })
        else:
            # Billing service check failed - fail open (allow access)
            logger.warning(f"Billing service check failed for {corporate.name}")
            return JsonResponse({
                "success": True,
                "has_access": True,
                "requires_payment": False,
                "requires_phone": False,
                "redirect_url": f"{frontend_url}/dashboard",
                "message": "Access granted (billing service unavailable)"
            })
    
    except Exception as e:
        logger.error(f"Error checking billing status: {e}", exc_info=True)
        return JsonResponse(
            {"error": str(e)},
            status=500
        )
