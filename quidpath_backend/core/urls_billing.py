"""
URL configuration for billing integration endpoints.
All billing calls from the frontend go through here — the gateway
authenticates the user JWT and forwards to the billing microservice
using X-Service-Key (server-to-server), eliminating direct frontend→billing calls.
"""

from django.urls import path

from quidpath_backend.core.views import billing_integration

app_name = "billing_integration"

urlpatterns = [
    # Plans — public, no auth required
    path("plans/", billing_integration.list_plans, name="list_plans"),

    # Access & trial
    path("access/check/", billing_integration.check_access, name="check_access"),
    path("trials/status/", billing_integration.get_trial_status, name="trial_status"),
    path("trials/create/", billing_integration.create_trial, name="create_trial"),

    # Subscription
    path("subscriptions/status/", billing_integration.get_subscription_status, name="subscription_status"),
    path("subscriptions/create/", billing_integration.create_subscription, name="create_subscription"),

    # Payments
    path("payments/initiate/", billing_integration.initiate_payment, name="initiate_payment"),
    path("payments/status/", billing_integration.check_payment_status, name="payment_status"),
    path("payments/history/", billing_integration.payment_history, name="payment_history"),

    # Invoices
    path("invoices/", billing_integration.list_invoices, name="list_invoices"),

    # Promotions
    path("promotions/validate/", billing_integration.validate_promotion, name="validate_promotion"),
]
