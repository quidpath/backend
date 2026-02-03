"""
Subscription Webhook Handler
Receives and processes subscription events from Billing Service
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from OrgAuth.models import Corporate
from OrgAuth.models.subscription import CorporateSubscription

logger = logging.getLogger(__name__)


def verify_webhook_signature(request):
    """Verify webhook signature from Billing Service"""
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        return False

    # Get webhook secret from settings
    webhook_secret = getattr(settings, "BILLING_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.error("BILLING_WEBHOOK_SECRET not configured")
        return False

    # Calculate expected signature
    payload = request.body
    expected_signature = hmac.new(
        webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@csrf_exempt
@require_http_methods(["POST"])
def subscription_webhook(request):
    """
    Handle subscription webhooks from Billing Service

    Events:
    - subscription.created
    - subscription.activated
    - subscription.cancelled
    - subscription.expired
    - subscription.upgraded
    - subscription.downgraded
    - payment.succeeded
    - payment.failed
    """

    # Verify webhook signature
    if not verify_webhook_signature(request):
        logger.warning("Invalid webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=403)

    try:
        payload = json.loads(request.body)
        event_type = payload.get("event")
        data = payload.get("data", {})

        logger.info(f"Received webhook: {event_type}")

        # Route to appropriate handler
        handlers = {
            "subscription.created": handle_subscription_created,
            "subscription.activated": handle_subscription_activated,
            "subscription.cancelled": handle_subscription_cancelled,
            "subscription.expired": handle_subscription_expired,
            "subscription.upgraded": handle_subscription_upgraded,
            "subscription.downgraded": handle_subscription_downgraded,
            "payment.succeeded": handle_payment_succeeded,
            "payment.failed": handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if not handler:
            logger.warning(f"Unknown event type: {event_type}")
            return JsonResponse({"error": "Unknown event type"}, status=400)

        # Process the event
        result = handler(data)

        return JsonResponse({"status": "success", "message": result})

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


def handle_subscription_created(data):
    """Handle subscription.created event"""
    corporate_id = data.get("corporate_id")
    subscription_id = data.get("subscription_id")
    plan = data.get("plan", {})

    # Create or update subscription
    subscription, created = CorporateSubscription.objects.update_or_create(
        billing_subscription_id=subscription_id,
        defaults={
            "corporate_id": corporate_id,
            "plan_id": plan.get("id"),
            "plan_name": plan.get("name"),
            "plan_slug": plan.get("slug"),
            "status": data.get("status", "trial"),
            "start_date": timezone.now(),
            "end_date": parse_datetime(data.get("end_date")),
            "trial_end_date": parse_datetime(data.get("trial_end_date")),
            "features": plan.get("features", {}),
            "auto_renew": data.get("auto_renew", True),
            "sync_source": "webhook",
        },
    )

    action = "created" if created else "updated"
    logger.info(f"Subscription {action} for corporate {corporate_id}")

    return f"Subscription {action}"


def handle_subscription_activated(data):
    """Handle subscription.activated event"""
    subscription_id = data.get("subscription_id")

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )
        subscription.status = "active"
        subscription.start_date = parse_datetime(data.get("start_date"))
        subscription.end_date = parse_datetime(data.get("end_date"))
        subscription.save()

        logger.info(f"Subscription {subscription_id} activated")
        return "Subscription activated"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        # Create it if it doesn't exist
        return handle_subscription_created(data)


def handle_subscription_cancelled(data):
    """Handle subscription.cancelled event"""
    subscription_id = data.get("subscription_id")

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )
        subscription.status = "cancelled"
        subscription.auto_renew = False
        subscription.save()

        logger.info(f"Subscription {subscription_id} cancelled")
        return "Subscription cancelled"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return "Subscription not found"


def handle_subscription_expired(data):
    """Handle subscription.expired event"""
    subscription_id = data.get("subscription_id")

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )
        subscription.status = "expired"
        subscription.save()

        logger.info(f"Subscription {subscription_id} expired")
        return "Subscription expired"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return "Subscription not found"


def handle_subscription_upgraded(data):
    """Handle subscription.upgraded event"""
    subscription_id = data.get("subscription_id")
    new_plan = data.get("new_plan", {})

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )
        subscription.plan_id = new_plan.get("id")
        subscription.plan_name = new_plan.get("name")
        subscription.plan_slug = new_plan.get("slug")
        subscription.features = new_plan.get("features", {})
        subscription.end_date = parse_datetime(data.get("end_date"))
        subscription.save()

        logger.info(
            f"Subscription {subscription_id} upgraded to {new_plan.get('name')}"
        )
        return "Subscription upgraded"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return "Subscription not found"


def handle_subscription_downgraded(data):
    """Handle subscription.downgraded event"""
    subscription_id = data.get("subscription_id")
    new_plan = data.get("new_plan", {})

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )
        subscription.plan_id = new_plan.get("id")
        subscription.plan_name = new_plan.get("name")
        subscription.plan_slug = new_plan.get("slug")
        subscription.features = new_plan.get("features", {})
        subscription.end_date = parse_datetime(data.get("end_date"))
        subscription.save()

        logger.info(
            f"Subscription {subscription_id} downgraded to {new_plan.get('name')}"
        )
        return "Subscription downgraded"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return "Subscription not found"


def handle_payment_succeeded(data):
    """Handle payment.succeeded event"""
    subscription_id = data.get("subscription_id")

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )

        # If subscription was expired, reactivate it
        if subscription.status == "expired":
            subscription.status = "active"
            subscription.end_date = parse_datetime(data.get("new_end_date"))
            subscription.save()
            logger.info(f"Subscription {subscription_id} reactivated after payment")

        return "Payment processed"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return "Subscription not found"


def handle_payment_failed(data):
    """Handle payment.failed event"""
    subscription_id = data.get("subscription_id")

    try:
        subscription = CorporateSubscription.objects.get(
            billing_subscription_id=subscription_id
        )

        # Mark subscription as suspended if payment fails
        subscription.status = "suspended"
        subscription.save()

        logger.warning(
            f"Subscription {subscription_id} suspended due to payment failure"
        )
        return "Subscription suspended"

    except CorporateSubscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return "Subscription not found"


def parse_datetime(date_string):
    """Parse datetime string to datetime object"""
    if not date_string:
        return timezone.now()

    try:
        # Try ISO format first
        return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # Fallback to current time
        return timezone.now()
