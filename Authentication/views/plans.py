"""
Views for fetching subscription plans from billing service.
Uses get_clean_data_safe and ResponseProvider; method check inside view.
"""

import logging

from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.Services.billing_service import billing_service
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data_safe

logger = logging.getLogger(__name__)


@csrf_exempt
def get_subscription_plans(request):
    """
    Get subscription plans from billing service.
    Query params: type=individual or type=organization (default: individual)
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

        plans = billing_service.get_plans(plan_type=plan_type)
        if plans is None:
            return ResponseProvider.error_response(
                "Failed to fetch plans from billing service",
                status=500,
                data={"plans": []},
            )

        return ResponseProvider.success_response(
            data={"plans": plans, "count": len(plans)}
        )
    except Exception as e:
        logger.exception("Error in get_subscription_plans: %s", e)
        return ResponseProvider.error_response(str(e), status=500)


@csrf_exempt
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
