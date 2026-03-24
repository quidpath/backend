from django.urls import path

from OrgAuth.views import (corporate_registration, corporate_users,
                           subscription_api, subscription_webhook)
from OrgAuth.views.billing_setup import setup_org_billing, initiate_org_payment
from OrgAuth.views.corporate_users import get_corporate_user, get_available_roles
from OrgAuth.views.corporate_user_approval import (
    approve_corporate_user,
    ban_corporate_user,
    unban_corporate_user,
)
from OrgAuth.views.corporate_management import (
    unsuspend_corporate,
    ban_corporate,
    unban_corporate,
)

urlpatterns = [
    # Corporate
    path("corporate/create", corporate_registration.create_corporate),
    path("corporate/list", corporate_registration.list_corporates),
    path("corporate/update", corporate_registration.update_corporate),
    path("corporate/delete", corporate_registration.delete_corporate),
    path("corporate/approve", corporate_registration.approve_corporate),
    path("corporate/suspend", corporate_registration.suspend_corporate),
    path("corporate/unsuspend", unsuspend_corporate),
    path("corporate/ban", ban_corporate),
    path("corporate/unban", unban_corporate),
    # Corporate Users (admin only)
    path("corporate-users/create", corporate_users.create_corporate_user),
    path("corporate-users/list", corporate_users.list_corporate_users),
    path("corporate-users/get", corporate_users.get_corporate_user),
    path("corporate-users/update", corporate_users.update_corporate_user),
    path("corporate-users/delete", corporate_users.delete_corporate_user),
    path("corporate-users/suspend", corporate_users.suspend_corporate_user),
    path("corporate-users/unsuspend", corporate_users.unsuspend_corporate_user),
    # Corporate User Approval & Ban (superuser only)
    path("corporate-users/approve", approve_corporate_user),
    path("corporate-users/ban", ban_corporate_user),
    path("corporate-users/unban", unban_corporate_user),
    path("roles/", get_available_roles, name="get_available_roles"),
    # Billing setup for approved organisations
    path("billing/setup/", setup_org_billing, name="org-billing-setup"),
    path("billing/pay/", initiate_org_payment, name="org-billing-pay"),
    # Subscription Webhooks (from Billing Service)
    path(
        "webhooks/subscription",
        subscription_webhook.subscription_webhook,
        name="subscription_webhook",
    ),
    # Subscription API (for corporates)
    path(
        "subscription/my-subscription",
        subscription_api.get_my_subscription,
        name="get_my_subscription",
    ),
    path(
        "subscription/check-feature",
        subscription_api.check_feature_access,
        name="check_feature_access",
    ),
    path(
        "subscription/features",
        subscription_api.get_subscription_features,
        name="get_subscription_features",
    ),
    path(
        "subscription/sync",
        subscription_api.sync_subscription_from_billing,
        name="sync_subscription",
    ),
]
