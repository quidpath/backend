from django.urls import path

from OrgAuth.views import (corporate_registration, corporate_users,
                           subscription_api, subscription_webhook)
from OrgAuth.views.corporate_users import get_corporate_user, list_roles

urlpatterns = [
    # Corporate
    path("corporate/create", corporate_registration.create_corporate),
    path("corporate/list", corporate_registration.list_corporates),
    path("corporate/update", corporate_registration.update_corporate),
    path("corporate/delete", corporate_registration.delete_corporate),
    path("corporate/approve", corporate_registration.approve_corporate),
    path("corporate/suspend", corporate_registration.suspend_corporate),
    # Corporate Users (admin only)
    path("corporate-users/create", corporate_users.create_corporate_user),
    path("corporate-users/list", corporate_users.list_corporate_users),
    path("corporate-users/get", corporate_users.get_corporate_user),
    path("corporate-users/update", corporate_users.update_corporate_user),
    path("corporate-users/delete", corporate_users.delete_corporate_user),
    path("corporate-users/suspend", corporate_users.suspend_corporate_user),
    path("corporate-users/unsuspend", corporate_users.unsuspend_corporate_user),
    path("roles/", list_roles, name="list_roles"),
    # Subscription Webhooks (from Billing Service)
    path(
        "webhooks/subscription",
        subscription_webhook.handle_subscription_webhook,
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
