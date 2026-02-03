"""
Subscription Access Control Middleware
Enforces subscription-based access control
"""

import logging
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone

from OrgAuth.models import CorporateUser
from OrgAuth.models.subscription import CorporateSubscription

logger = logging.getLogger(__name__)


def get_corporate_subscription(corporate_id):
    """Get active subscription for a corporate"""
    try:
        subscription = CorporateSubscription.objects.filter(
            corporate_id=corporate_id
        ).first()

        if not subscription:
            return None

        # Check if subscription is active or in grace period
        if subscription.is_active or subscription.is_in_grace_period:
            return subscription

        return None

    except Exception as e:
        logger.error(f"Error fetching subscription for corporate {corporate_id}: {e}")
        return None


def require_subscription(plan_slug=None):
    """
    Decorator to require an active subscription

    Usage:
        @require_subscription()  # Any active subscription
        @require_subscription(plan_slug='premium')  # Specific plan required
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get corporate_id from request (set by JWT middleware)
            corporate_id = getattr(request, "corporate_id", None)

            if not corporate_id:
                return JsonResponse(
                    {
                        "error": "No corporate association found",
                        "code": "NO_CORPORATE",
                    },
                    status=403,
                )

            # Get subscription
            subscription = get_corporate_subscription(corporate_id)

            if not subscription:
                return JsonResponse(
                    {
                        "error": "No active subscription found",
                        "code": "NO_SUBSCRIPTION",
                        "message": "Please subscribe to a plan to access this feature",
                    },
                    status=403,
                )

            # Check specific plan if required
            if plan_slug and subscription.plan_slug != plan_slug:
                return JsonResponse(
                    {
                        "error": f"This feature requires {plan_slug} plan",
                        "code": "PLAN_REQUIRED",
                        "current_plan": subscription.plan_slug,
                        "required_plan": plan_slug,
                    },
                    status=403,
                )

            # Attach subscription to request for use in view
            request.subscription = subscription

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_feature(feature_name):
    """
    Decorator to require a specific feature

    Usage:
        @require_feature('advanced_analytics')
        @require_feature('api_access')
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get corporate_id from request
            corporate_id = getattr(request, "corporate_id", None)

            if not corporate_id:
                return JsonResponse(
                    {
                        "error": "No corporate association found",
                        "code": "NO_CORPORATE",
                    },
                    status=403,
                )

            # Get subscription
            subscription = get_corporate_subscription(corporate_id)

            if not subscription:
                return JsonResponse(
                    {
                        "error": "No active subscription found",
                        "code": "NO_SUBSCRIPTION",
                    },
                    status=403,
                )

            # Check if feature is enabled
            if not subscription.has_feature(feature_name):
                return JsonResponse(
                    {
                        "error": f"Feature '{feature_name}' not available in your plan",
                        "code": "FEATURE_NOT_AVAILABLE",
                        "current_plan": subscription.plan_slug,
                        "required_feature": feature_name,
                        "message": "Please upgrade your plan to access this feature",
                    },
                    status=403,
                )

            # Attach subscription to request
            request.subscription = subscription

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_plan_level(min_level):
    """
    Decorator to require minimum plan level

    Usage:
        @require_plan_level(2)  # Requires at least level 2 plan

    Plan levels:
        1 = Basic
        2 = Professional
        3 = Premium
        4 = Enterprise
    """

    PLAN_LEVELS = {
        "basic": 1,
        "professional": 2,
        "premium": 3,
        "enterprise": 4,
    }

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            corporate_id = getattr(request, "corporate_id", None)

            if not corporate_id:
                return JsonResponse(
                    {"error": "No corporate association found"}, status=403
                )

            subscription = get_corporate_subscription(corporate_id)

            if not subscription:
                return JsonResponse(
                    {"error": "No active subscription found"}, status=403
                )

            # Get current plan level
            current_level = PLAN_LEVELS.get(subscription.plan_slug, 0)

            if current_level < min_level:
                return JsonResponse(
                    {
                        "error": "Plan upgrade required",
                        "code": "PLAN_UPGRADE_REQUIRED",
                        "current_plan": subscription.plan_slug,
                        "current_level": current_level,
                        "required_level": min_level,
                    },
                    status=403,
                )

            request.subscription = subscription
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class SubscriptionMiddleware:
    """
    Middleware to attach subscription information to request
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get corporate_id from request (set by JWT middleware)
        corporate_id = getattr(request, "corporate_id", None)

        if corporate_id:
            # Attach subscription to request
            request.subscription = get_corporate_subscription(corporate_id)
        else:
            request.subscription = None

        response = self.get_response(request)
        return response
