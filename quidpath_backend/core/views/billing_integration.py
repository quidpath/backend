"""
Billing Integration Views for Main Backend
Provides endpoints for frontend to interact with billing service
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.billing_client import BillingServiceClient

logger = logging.getLogger(__name__)


def get_corporate_id_from_request(request) -> str:
    """Extract corporate_id from authenticated user"""
    if hasattr(request.user, "corporateuser") and hasattr(
        request.user.corporateuser, "corporate"
    ):
        return str(request.user.corporateuser.corporate.id)

    if hasattr(request.user, "corporate") and hasattr(request.user.corporate, "id"):
        return str(request.user.corporate.id)

    return None


@csrf_exempt
@login_required
def get_subscription_status(request):
    """Get current subscription status for authenticated user's corporate"""
    try:
        corporate_id = get_corporate_id_from_request(request)
        if not corporate_id:
            return JsonResponse(
                {"success": False, "message": "No corporate associated with user"},
                status=400,
            )

        billing_client = BillingServiceClient()
        result = billing_client.check_access(corporate_id)

        return JsonResponse(result, status=200)
    except Exception as e:
        logger.error(f"Error getting subscription status: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@login_required
def list_invoices(request):
    """List invoices for authenticated user's corporate"""
    try:
        corporate_id = get_corporate_id_from_request(request)
        if not corporate_id:
            return JsonResponse(
                {"success": False, "message": "No corporate associated with user"},
                status=400,
            )

        billing_client = BillingServiceClient()
        result = billing_client.list_invoices(corporate_id)

        return JsonResponse(result, status=200)
    except Exception as e:
        logger.error(f"Error listing invoices: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@login_required
def list_plans(request):
    """List available subscription plans"""
    try:
        billing_client = BillingServiceClient()
        result = billing_client.list_plans()

        return JsonResponse(result, status=200)
    except Exception as e:
        logger.error(f"Error listing plans: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@login_required
def create_subscription(request):
    """Create new subscription for authenticated user's corporate"""
    try:
        corporate_id = get_corporate_id_from_request(request)
        if not corporate_id:
            return JsonResponse(
                {"success": False, "message": "No corporate associated with user"},
                status=400,
            )

        data = json.loads(request.body) if request.body else {}
        plan_tier = data.get("plan_tier")
        billing_cycle = data.get("billing_cycle", "monthly")
        additional_users = data.get("additional_users", 0)
        promotion_code = data.get("promotion_code")

        if not plan_tier:
            return JsonResponse(
                {"success": False, "message": "Plan tier is required"}, status=400
            )

        # Get corporate name
        corporate_name = ""
        if hasattr(request.user, "corporateuser"):
            corporate_name = request.user.corporateuser.corporate.name
        elif hasattr(request.user, "corporate"):
            corporate_name = request.user.corporate.name

        billing_client = BillingServiceClient()
        result = billing_client.create_subscription(
            corporate_id=corporate_id,
            corporate_name=corporate_name,
            plan_tier=plan_tier,
            billing_cycle=billing_cycle,
            additional_users=additional_users,
            promotion_code=promotion_code,
        )

        return JsonResponse(result, status=201 if result.get("success") else 400)
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@login_required
def initiate_payment(request):
    """Initiate payment for an invoice"""
    try:
        corporate_id = get_corporate_id_from_request(request)
        if not corporate_id:
            return JsonResponse(
                {"success": False, "message": "No corporate associated with user"},
                status=400,
            )

        data = json.loads(request.body) if request.body else {}
        invoice_id = data.get("invoice_id")
        invoice_number = data.get("invoice_number")
        payment_method = data.get("payment_method", "mpesa")
        customer_phone = data.get("customer_phone")

        if not invoice_id and not invoice_number:
            return JsonResponse(
                {"success": False, "message": "Invoice ID or invoice number required"},
                status=400,
            )

        billing_client = BillingServiceClient()
        result = billing_client.initiate_payment(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            payment_method=payment_method,
            customer_email=request.user.email,
            customer_phone=customer_phone,
        )

        return JsonResponse(result, status=200 if result.get("success") else 400)
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@csrf_exempt
@login_required
def validate_promotion(request):
    """Validate a promotion code"""
    try:
        data = json.loads(request.body) if request.body else {}
        promotion_code = data.get("promotion_code")
        amount = data.get("amount", 0)
        plan_tier = data.get("plan_tier", "starter")

        if not promotion_code:
            return JsonResponse(
                {"success": False, "message": "Promotion code required"}, status=400
            )

        billing_client = BillingServiceClient()
        result = billing_client.validate_promotion(
            promotion_code=promotion_code, amount=float(amount), plan_tier=plan_tier
        )

        return JsonResponse(result, status=200 if result.get("success") else 400)
    except Exception as e:
        logger.error(f"Error validating promotion: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)
