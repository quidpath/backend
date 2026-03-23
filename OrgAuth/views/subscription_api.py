"""
Subscription API Views — proxies to the billing microservice.
No local subscription model queries; all data comes from billing service.
Uses resolve_user_from_token for JWT auth (plain Django views, not DRF).
"""
import logging

from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import CorporateUser
from quidpath_backend.core.Services.billing_service import billing_service
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data_safe, resolve_user_from_token

logger = logging.getLogger(__name__)


def _get_authenticated_corporate(request):
    """
    Resolve JWT token → user → corporate.
    Returns (corporate_id, corporate_name, error_response).
    error_response is non-None if auth or lookup failed.
    """
    user, corporate_user = resolve_user_from_token(request)
    if not user:
        return None, None, ResponseProvider.error_response("Authentication required", status=401)

    if corporate_user and hasattr(corporate_user, "corporate"):
        return str(corporate_user.corporate.id), str(corporate_user.corporate.name), None

    # Fallback: look up CorporateUser directly
    try:
        cu = CorporateUser.objects.select_related("corporate").get(customuser_ptr_id=user.id)
        return str(cu.corporate.id), str(cu.corporate.name), None
    except CorporateUser.DoesNotExist:
        return None, None, ResponseProvider.error_response("User is not associated with a corporate", status=404)


@csrf_exempt
def get_my_subscription(request):
    """Get current user's corporate subscription from billing service."""
    data, err = get_clean_data_safe(request, allowed_methods=["GET"], require_json_body=False)
    if err:
        return err

    corporate_id, corporate_name, err = _get_authenticated_corporate(request)
    if err:
        return err

    result = billing_service.get_subscription_status(corporate_id)
    if result is None:
        return ResponseProvider.success_response(data={"has_subscription": False, "corporate_id": corporate_id})

    return ResponseProvider.success_response(data=result)


@csrf_exempt
def check_feature_access(request, feature_name=None):
    """Check if current user's corporate has access to a specific feature."""
    data, err = get_clean_data_safe(request, allowed_methods=["GET"], require_json_body=False)
    if err:
        return err

    corporate_id, _, err = _get_authenticated_corporate(request)
    if err:
        return err

    feature_name = feature_name or (data or {}).get("feature_name")
    if not feature_name:
        return ResponseProvider.error_response("feature_name is required", status=400)

    result = billing_service.check_access(corporate_id)
    if result is None:
        return ResponseProvider.error_response("Billing service unavailable", status=503)

    has_access = result.get("has_access", False)
    subscription = result.get("subscription") or {}
    features = subscription.get("features", {})
    has_feature = features.get(feature_name, False) if has_access else False

    return ResponseProvider.success_response(data={
        "has_access": has_feature,
        "feature_name": feature_name,
        "subscription_active": has_access,
        "message": "Feature available" if has_feature else f"Feature '{feature_name}' not available in current plan",
    })


@csrf_exempt
def get_subscription_features(request):
    """Get all features available in current subscription."""
    data, err = get_clean_data_safe(request, allowed_methods=["GET"], require_json_body=False)
    if err:
        return err

    corporate_id, _, err = _get_authenticated_corporate(request)
    if err:
        return err

    result = billing_service.check_access(corporate_id)
    if result is None:
        return ResponseProvider.error_response("Billing service unavailable", status=503)

    subscription = result.get("subscription") or {}
    features = subscription.get("features", {})

    return ResponseProvider.success_response(data={
        "has_access": result.get("has_access", False),
        "features": features,
        "enabled_features": [k for k, v in features.items() if v],
    })


@csrf_exempt
def sync_subscription_from_billing(request):
    """Trigger a fresh subscription check from billing service."""
    data, err = get_clean_data_safe(request, allowed_methods=["POST"], require_json_body=False)
    if err:
        return err

    corporate_id, _, err = _get_authenticated_corporate(request)
    if err:
        return err

    result = billing_service.get_subscription_status(corporate_id)
    if result is None:
        return ResponseProvider.error_response("Billing service unavailable", status=503)

    return ResponseProvider.success_response(data={"message": "Subscription synced", **result})
