"""
URL configuration for billing integration endpoints
"""

from django.urls import path

from quidpath_backend.core.views import billing_integration

app_name = "billing_integration"

urlpatterns = [
    path(
        "status/",
        billing_integration.get_subscription_status,
        name="subscription_status",
    ),
    path("invoices/", billing_integration.list_invoices, name="list_invoices"),
    path("plans/", billing_integration.list_plans, name="list_plans"),
    path(
        "subscribe/",
        billing_integration.create_subscription,
        name="create_subscription",
    ),
    path(
        "payment/initiate/",
        billing_integration.initiate_payment,
        name="initiate_payment",
    ),
    path(
        "promotion/validate/",
        billing_integration.validate_promotion,
        name="validate_promotion",
    ),
    path(
        "trials/status/",
        billing_integration.get_trial_status,
        name="trial_status",
    ),
    path(
        "access/check/",
        billing_integration.check_access,
        name="check_access",
    ),
]
