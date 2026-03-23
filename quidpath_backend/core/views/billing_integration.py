"""
Billing integration views — thin proxies to the billing microservice.
All billing logic lives in the billing service; these views just forward requests.
Uses resolve_user_from_token for JWT auth (plain Django views, not DRF).
"""
import json
import logging

from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.Services.billing_service import billing_service
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import resolve_user_from_token

logger = logging.getLogger(__name__)


def _get_authenticated_corporate(request):
    """Resolve JWT → user → corporate. Returns (corporate_id, corporate_name, error_response)."""
    user, corporate_user = resolve_user_from_token(request)
    if not user:
        return None, None, ResponseProvider.error_response("Authentication required", status=401)

    if corporate_user and hasattr(corporate_user, "corporate"):
        c = corporate_user.corporate
        return str(c.id), getattr(c, "name", ""), None

    # Fallback via related manager
    from OrgAuth.models import CorporateUser
    try:
        cu = CorporateUser.objects.select_related("corporate").get(customuser_ptr_id=user.id)
        return str(cu.corporate.id), str(cu.corporate.name), None
    except CorporateUser.DoesNotExist:
        return None, None, ResponseProvider.error_response("No corporate associated with user", status=400)


@csrf_exempt
def get_subscription_status(request):
    corporate_id, _, err = _get_authenticated_corporate(request)
    if err:
        return err
    result = billing_service.check_access(corporate_id)
    if result is None:
        return ResponseProvider.error_response("Billing service unavailable", status=503)
    return ResponseProvider.success_response(data=result)


@csrf_exempt
def list_invoices(request):
    corporate_id, _, err = _get_authenticated_corporate(request)
    if err:
        return err
    result = billing_service.list_invoices(corporate_id)
    if result is None:
        return ResponseProvider.error_response("Billing service unavailable", status=503)
    return ResponseProvider.success_response(data=result)


@csrf_exempt
def list_plans(request):
    plan_type = request.GET.get("type", "organization")
    plans = billing_service.get_plans(plan_type=plan_type)
    if plans is None:
        return ResponseProvider.error_response("Billing service unavailable", status=503)
    return ResponseProvider.success_response(data={"plans": plans, "count": len(plans)})


@csrf_exempt
def create_subscription(request):
    corporate_id, corporate_name, err = _get_authenticated_corporate(request)
    if err:
        return err
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return ResponseProvider.error_response("Invalid JSON", status=400)
    plan_tier = data.get("plan_tier")
    if not plan_tier:
        return ResponseProvider.error_response("plan_tier is required", status=400)
    result = billing_service.create_subscription(
        corporate_id=corporate_id,
        corporate_name=corporate_name,
        plan_tier=plan_tier,
        billing_cycle=data.get("billing_cycle", "monthly"),
        additional_users=data.get("additional_users", 0),
        promotion_code=data.get("promotion_code"),
    )
    if result and result.get("success"):
        return ResponseProvider.success_response(data=result)
    return ResponseProvider.error_response((result or {}).get("message", "Subscription creation failed"), status=400)


@csrf_exempt
def initiate_payment(request):
    corporate_id, _, err = _get_authenticated_corporate(request)
    if err:
        return err
    user, _ = resolve_user_from_token(request)
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return ResponseProvider.error_response("Invalid JSON", status=400)
    invoice_id = data.get("invoice_id")
    invoice_number = data.get("invoice_number")
    if not invoice_id and not invoice_number:
        return ResponseProvider.error_response("invoice_id or invoice_number required", status=400)
    result = billing_service.initiate_invoice_payment(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        payment_method=data.get("payment_method", "mpesa"),
        customer_email=user.email if user else "",
        customer_phone=data.get("customer_phone"),
    )
    if result and result.get("success"):
        return ResponseProvider.success_response(data=result)
    return ResponseProvider.error_response((result or {}).get("message", "Payment initiation failed"), status=400)


@csrf_exempt
def validate_promotion(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return ResponseProvider.error_response("Invalid JSON", status=400)
    promotion_code = data.get("promotion_code")
    if not promotion_code:
        return ResponseProvider.error_response("promotion_code is required", status=400)
    result = billing_service.validate_promotion(
        promotion_code=promotion_code,
        amount=float(data.get("amount", 0)),
        plan_tier=data.get("plan_tier", "starter"),
    )
    if result and result.get("success"):
        return ResponseProvider.success_response(data=result)
    return ResponseProvider.error_response((result or {}).get("message", "Invalid promotion code"), status=400)
