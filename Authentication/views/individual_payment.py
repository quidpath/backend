"""
Individual user payment verification — activates account after Paystack payment.
"""
import logging
import os

import requests as http_requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_data

logger = logging.getLogger(__name__)


def _get_paystack_secret() -> str:
    key = os.environ.get("PAYSTACK_SECRET_KEY", "") or getattr(settings, "PAYSTACK_SECRET_KEY", "")
    return key


@csrf_exempt
def verify_individual_payment(request):
    """
    Verify Paystack payment reference and activate the individual account.
    Called by the frontend after Paystack's onSuccess callback.
    """
    data, _ = get_data(request)

    reference = data.get("reference", "").strip()
    corporate_id = data.get("corporate_id", "").strip()
    plan_id = data.get("plan_id", "").strip()

    if not reference or not corporate_id:
        return JsonResponse({"error": "reference and corporate_id are required"}, status=400)

    # ── 1. Verify with Paystack ───────────────────────────────────────────────
    secret_key = _get_paystack_secret()
    if not secret_key:
        logger.error("PAYSTACK_SECRET_KEY not configured")
        return JsonResponse({"error": "Payment system not configured"}, status=500)

    try:
        ps_resp = http_requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {secret_key}"},
            timeout=30,
        )
        ps_data = ps_resp.json()
    except Exception as e:
        logger.error(f"Paystack verify request failed: {e}", exc_info=True)
        return JsonResponse({"error": "Could not reach payment provider"}, status=502)

    if not ps_data.get("status") or ps_data.get("data", {}).get("status") != "success":
        msg = ps_data.get("data", {}).get("gateway_response") or ps_data.get("message", "Payment not successful")
        return JsonResponse({"error": msg}, status=400)

    # ── 2. Load account ───────────────────────────────────────────────────────
    try:
        corporate = Corporate.objects.get(id=corporate_id)
        user = CorporateUser.objects.get(corporate=corporate)
    except (Corporate.DoesNotExist, CorporateUser.DoesNotExist):
        return JsonResponse({"error": "Account not found"}, status=404)

    # ── 3. Activate ───────────────────────────────────────────────────────────
    user.is_active = True
    user.save(update_fields=["is_active"])
    corporate.is_active = True
    corporate.save(update_fields=["is_active"])

    # ── 4. Create subscription in billing service ─────────────────────────────
    try:
        from quidpath_backend.core.Services.billing_service import BillingServiceClient
        plan_tier = (
            (user.metadata or {}).get("plan_tier", "starter")
            if hasattr(user, "metadata") else "starter"
        )
        BillingServiceClient().create_subscription(
            corporate_id=str(corporate_id),
            corporate_name=corporate.name,
            plan_tier=plan_tier,
            billing_cycle="monthly",
        )
    except Exception as e:
        logger.warning(f"Subscription creation failed (non-fatal): {e}")

    TransactionLogBase.log(
        "INDIVIDUAL_PAYMENT_VERIFIED",
        user=user,
        message=f"Payment verified, account activated: {user.username}",
        extra={"reference": reference, "corporate_id": str(corporate_id), "plan_id": plan_id},
    )

    return JsonResponse({
        "success": True,
        "message": "Payment verified. Your account is now active!",
        "username": user.username,
        "email": user.email,
    })
