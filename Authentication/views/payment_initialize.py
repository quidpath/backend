"""
Payment initialization - server-side Paystack transaction initialization.
Secret key never leaves the server. Frontend gets back only the access_code.
"""
import logging
import os
import uuid

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.request_parser import get_data

logger = logging.getLogger(__name__)


@csrf_exempt
def initialize_payment(request):
    """
    Initialize a Paystack transaction server-side.
    Returns access_code to the frontend — secret key never exposed.

    Body:
        email        (str)  required
        amount       (int)  required  — in KES (whole units, e.g. 2500)
        payment_type (str)  required  — "individual" | "corporate"
        corporate_id (str)  optional  — for individual activation
        registration_id (str) optional — for corporate verification
        plan_id      (str)  optional
        plan_tier    (str)  optional
    """
    data, _ = get_data(request)

    email = data.get("email", "").strip()
    amount_kes = data.get("amount")
    payment_type = data.get("payment_type", "individual")
    corporate_id = data.get("corporate_id", "")
    registration_id = data.get("registration_id", "")
    plan_id = data.get("plan_id", "")
    plan_tier = data.get("plan_tier", "starter")

    if not email or not amount_kes:
        return JsonResponse({"error": "email and amount are required"}, status=400)

    try:
        amount_kobo = int(float(amount_kes) * 100)  # Paystack expects smallest unit
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid amount"}, status=400)

    secret_key = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not secret_key:
        # Fallback to Django settings
        from django.conf import settings
        secret_key = getattr(settings, "PAYSTACK_SECRET_KEY", "")
    if not secret_key:
        logger.error("PAYSTACK_SECRET_KEY not configured")
        return JsonResponse({"error": "Payment system not configured"}, status=500)

    reference = f"qp-{payment_type[:4]}-{uuid.uuid4().hex[:12]}"

    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": "KES",
        "reference": reference,
        "metadata": {
            "payment_type": payment_type,
            "corporate_id": corporate_id,
            "registration_id": registration_id,
            "plan_id": plan_id,
            "plan_tier": plan_tier,
        },
    }

    try:
        resp = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload,
            headers={
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp_data = resp.json()
    except Exception as e:
        logger.error(f"Paystack initialize error: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to reach payment provider"}, status=502)

    if not resp_data.get("status"):
        logger.error(f"Paystack init failed: {resp_data}")
        return JsonResponse(
            {"error": resp_data.get("message", "Payment initialization failed")},
            status=400,
        )

    return JsonResponse({
        "success": True,
        "access_code": resp_data["data"]["access_code"],
        "reference": resp_data["data"]["reference"],
    })
