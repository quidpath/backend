"""
Subscription Webhook Handler
Receives subscription/payment events from the Billing Service and updates
the Corporate.is_active flag accordingly.
All subscription data lives in the billing service — we only mirror is_active here.
"""
import hashlib
import hmac
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data_safe

logger = logging.getLogger(__name__)


def _verify_signature(request) -> bool:
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        return False
    webhook_secret = getattr(settings, "BILLING_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.error("BILLING_WEBHOOK_SECRET not configured")
        return False
    # Billing service signs json.dumps(payload, sort_keys=True) — not raw request.body
    # We must re-serialize the parsed payload the same way to verify
    try:
        import json
        payload = json.loads(request.body)
        payload_json = json.dumps(payload, sort_keys=True).encode()
    except Exception:
        payload_json = request.body
    expected = hmac.new(webhook_secret.encode(), payload_json, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _set_corporate_active(corporate_id, active: bool):
    if not corporate_id:
        return
    try:
        corporate = Corporate.objects.get(id=corporate_id)
        if corporate.is_active != active:
            corporate.is_active = active
            corporate.save(update_fields=["is_active"])
            logger.info("Corporate %s is_active set to %s", corporate_id, active)
    except Corporate.DoesNotExist:
        logger.warning("Corporate %s not found in webhook", corporate_id)


@csrf_exempt
def subscription_webhook(request):
    """
    Handle subscription/payment webhooks from Billing Service.
    Updates Corporate.is_active based on payment and subscription events.
    """
    if request.method != "POST":
        return ResponseProvider.method_not_allowed(["POST"])

    if not _verify_signature(request):
        logger.warning("Invalid webhook signature")
        return ResponseProvider.error_response("Invalid signature", status=403)

    payload, err = get_clean_data_safe(request, allowed_methods=["POST"], require_json_body=True)
    if err is not None:
        return err

    try:
        event_type = (payload or {}).get("event")
        data = (payload or {}).get("data", {})
        corporate_id = data.get("corporate_id")

        logger.info("Received billing webhook: %s for corporate %s", event_type, corporate_id)

        # Events that mean the corporate should have access
        ACTIVATE_EVENTS = {
            "subscription.created",
            "subscription.activated",
            "subscription.upgraded",
            "subscription.downgraded",
            "payment.succeeded",
            "trial.created",
            "trial.activated",
        }

        # Events that mean the corporate should lose access
        DEACTIVATE_EVENTS = {
            "subscription.expired",
            "subscription.cancelled",
            "payment.failed",
            "trial.expired",
        }

        if event_type in ACTIVATE_EVENTS:
            _set_corporate_active(corporate_id, True)
        elif event_type in DEACTIVATE_EVENTS:
            _set_corporate_active(corporate_id, False)
        else:
            logger.info("Unhandled webhook event: %s", event_type)

        return ResponseProvider.success_response(data={"status": "ok", "event": event_type})

    except Exception as e:
        logger.exception("Error processing webhook: %s", e)
        return ResponseProvider.error_response(str(e), status=500)
