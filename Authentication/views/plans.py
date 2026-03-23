"""
Views for fetching subscription plans from billing service.
Uses get_clean_data_safe and ResponseProvider; method check inside view.
"""

import logging

from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.Services.billing_service import billing_service
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.rate_limit import rate_limit
from quidpath_backend.core.utils.request_parser import get_clean_data_safe

logger = logging.getLogger(__name__)


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="plans")
def get_subscription_plans(request):
    """
    Get subscription plans.
    Query params: type=individual or type=organization (default: individual)
    Falls back to local DB if billing service is unavailable.
    """
    data, err = get_clean_data_safe(request, allowed_methods=["GET"], require_json_body=False)
    if err is not None:
        return err
    try:
        plan_type = (data or {}).get("type", "individual")
        if plan_type not in ["individual", "organization"]:
            return ResponseProvider.error_response(
                "Invalid plan type. Use 'individual' or 'organization'", status=400
            )

        # Try billing service first
        plans = billing_service.get_plans(plan_type=plan_type)

        # Fall back to local DB if billing service is down
        if plans is None:
            plans = _get_local_plans(plan_type)

        if plans is None:
            return ResponseProvider.error_response(
                "Failed to fetch plans",
                status=500,
                data={"plans": []},
            )

        return ResponseProvider.success_response(
            data={"plans": plans, "count": len(plans)}
        )
    except Exception as e:
        logger.exception("Error in get_subscription_plans: %s", e)
        return ResponseProvider.error_response(str(e), status=500)


def _get_local_plans(plan_type: str):
    """Static fallback plans when billing service is unavailable."""
    if plan_type == "individual":
        return [
            {
                "id": "fallback-individual-starter",
                "tier": "starter",
                "name": "Starter",
                "description": "Basic individual plan",
                "price_monthly": 500.0,
                "max_transactions": 100,
                "max_invoices": 50,
                "features": {"invoicing": True, "reports": False, "api_access": False},
                "type": "individual",
            },
            {
                "id": "fallback-individual-professional",
                "tier": "professional",
                "name": "Professional",
                "description": "Professional individual plan",
                "price_monthly": 1500.0,
                "max_transactions": 500,
                "max_invoices": 200,
                "features": {"invoicing": True, "reports": True, "api_access": False},
                "type": "individual",
            },
        ]
    else:
        return [
            {
                "id": "fallback-org-basic",
                "tier": "basic",
                "name": "Basic",
                "description": "Basic organisation plan",
                "price_monthly": 3000.0,
                "max_users": 5,
                "features": {"invoicing": True, "reports": True, "api_access": False},
                "type": "organization",
            },
            {
                "id": "fallback-org-standard",
                "tier": "standard",
                "name": "Standard",
                "description": "Standard organisation plan",
                "price_monthly": 8000.0,
                "max_users": 20,
                "features": {"invoicing": True, "reports": True, "api_access": True},
                "type": "organization",
            },
        ]


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="initiate_payment")
def initiate_subscription_payment(request):
    """Initiate payment for a subscription."""
    data, err = get_clean_data_safe(request, allowed_methods=["POST"], require_json_body=True)
    if err is not None:
        return err
    try:
        entity_id = (data or {}).get("entity_id")
        entity_name = (data or {}).get("entity_name")
        plan_id = (data or {}).get("plan_id")
        phone_number = (data or {}).get("phone_number")
        payment_type = (data or {}).get("payment_type", "individual")

        if not all([entity_id, entity_name, plan_id, phone_number]):
            return ResponseProvider.error_response(
                "Missing required fields: entity_id, entity_name, plan_id, phone_number",
                status=400,
            )

        result = billing_service.initiate_payment(
            entity_id=entity_id,
            entity_name=entity_name,
            plan_id=plan_id,
            phone_number=phone_number,
            payment_type=payment_type,
        )

        if result and result.get("success"):
            return ResponseProvider.success_response(data=result)
        return ResponseProvider.error_response(
            (result or {}).get("message", "Payment initiation failed") or "Payment initiation failed",
            status=400,
        )
    except Exception as e:
        logger.exception("Error in initiate_subscription_payment: %s", e)
        return ResponseProvider.error_response(str(e), status=500)


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="sub_status")
def check_subscription_status(request):
    """Check subscription status. Query params: entity_id (required)."""
    data, err = get_clean_data_safe(request, allowed_methods=["GET"], require_json_body=False)
    if err is not None:
        return err
    try:
        entity_id = (data or {}).get("entity_id")
        if not entity_id:
            return ResponseProvider.error_response("entity_id is required", status=400)

        status = billing_service.get_subscription_status(entity_id)
        if status is None:
            return ResponseProvider.error_response(
                "Failed to fetch subscription status",
                status=500,
                data={"has_subscription": False},
            )

        return ResponseProvider.success_response(data=status)
    except Exception as e:
        logger.exception("Error in check_subscription_status: %s", e)
        return ResponseProvider.error_response(str(e), status=500)
