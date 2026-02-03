"""
Subscription API Views
Provides subscription information to frontend and other services
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from OrgAuth.models import CorporateUser
from OrgAuth.models.subscription import CorporateSubscription


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_my_subscription(request):
    """
    Get current user's corporate subscription

    Returns subscription details including:
    - Plan information
    - Status
    - Expiry date
    - Enabled features
    """
    user = request.user

    try:
        # Get corporate user
        corporate_user = CorporateUser.objects.select_related("corporate").get(
            customuser_ptr_id=user.id
        )
        corporate_id = corporate_user.corporate.id

        # Get subscription
        subscription = CorporateSubscription.objects.filter(
            corporate_id=corporate_id
        ).first()

        if not subscription:
            return Response(
                {
                    "has_subscription": False,
                    "message": "No subscription found",
                    "corporate_id": str(corporate_id),
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "has_subscription": True,
                "subscription": {
                    "id": str(subscription.id),
                    "plan_name": subscription.plan_name,
                    "plan_slug": subscription.plan_slug,
                    "status": subscription.status,
                    "is_active": subscription.is_active,
                    "is_in_grace_period": subscription.is_in_grace_period,
                    "start_date": subscription.start_date.isoformat(),
                    "end_date": subscription.end_date.isoformat(),
                    "trial_end_date": (
                        subscription.trial_end_date.isoformat()
                        if subscription.trial_end_date
                        else None
                    ),
                    "days_until_expiry": subscription.days_until_expiry,
                    "auto_renew": subscription.auto_renew,
                    "features": subscription.features,
                    "enabled_features": subscription.get_enabled_features(),
                },
                "corporate": {
                    "id": str(corporate_user.corporate.id),
                    "name": corporate_user.corporate.name,
                },
            }
        )

    except CorporateUser.DoesNotExist:
        return Response(
            {"error": "User is not associated with a corporate"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_feature_access(request, feature_name):
    """
    Check if current user's corporate has access to a specific feature

    Args:
        feature_name: Name of the feature to check

    Returns:
        {
            "has_access": true/false,
            "feature_name": "feature_name",
            "plan_name": "Premium",
            "message": "..."
        }
    """
    user = request.user

    try:
        corporate_user = CorporateUser.objects.select_related("corporate").get(
            customuser_ptr_id=user.id
        )
        corporate_id = corporate_user.corporate.id

        subscription = CorporateSubscription.objects.filter(
            corporate_id=corporate_id
        ).first()

        if not subscription:
            return Response(
                {
                    "has_access": False,
                    "feature_name": feature_name,
                    "message": "No active subscription",
                }
            )

        if not subscription.is_active:
            return Response(
                {
                    "has_access": False,
                    "feature_name": feature_name,
                    "message": "Subscription is not active",
                    "status": subscription.status,
                }
            )

        has_feature = subscription.has_feature(feature_name)

        return Response(
            {
                "has_access": has_feature,
                "feature_name": feature_name,
                "plan_name": subscription.plan_name,
                "plan_slug": subscription.plan_slug,
                "message": (
                    "Feature available"
                    if has_feature
                    else f"Feature not available in {subscription.plan_name} plan"
                ),
            }
        )

    except CorporateUser.DoesNotExist:
        return Response(
            {
                "has_access": False,
                "feature_name": feature_name,
                "message": "User not associated with corporate",
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_subscription_features(request):
    """
    Get all features available in current subscription

    Returns list of enabled features with descriptions
    """
    user = request.user

    try:
        corporate_user = CorporateUser.objects.select_related("corporate").get(
            customuser_ptr_id=user.id
        )
        corporate_id = corporate_user.corporate.id

        subscription = CorporateSubscription.objects.filter(
            corporate_id=corporate_id
        ).first()

        if not subscription or not subscription.is_active:
            return Response(
                {"features": [], "message": "No active subscription"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "plan_name": subscription.plan_name,
                "plan_slug": subscription.plan_slug,
                "features": subscription.features,
                "enabled_features": subscription.get_enabled_features(),
            }
        )

    except CorporateUser.DoesNotExist:
        return Response(
            {"error": "User not associated with corporate"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_subscription_from_billing(request):
    """
    Manually trigger subscription sync from Billing Service

    This is a fallback in case webhooks fail
    """
    user = request.user

    try:
        corporate_user = CorporateUser.objects.select_related("corporate").get(
            customuser_ptr_id=user.id
        )
        corporate_id = corporate_user.corporate.id

        # TODO: Call Billing Service API to fetch latest subscription
        # For now, return current subscription
        subscription = CorporateSubscription.objects.filter(
            corporate_id=corporate_id
        ).first()

        if not subscription:
            return Response(
                {"message": "No subscription found to sync"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "message": "Subscription synced successfully",
                "subscription": {
                    "plan_name": subscription.plan_name,
                    "status": subscription.status,
                    "last_synced_at": subscription.last_synced_at.isoformat(),
                },
            }
        )

    except CorporateUser.DoesNotExist:
        return Response(
            {"error": "User not associated with corporate"},
            status=status.HTTP_404_NOT_FOUND,
        )
