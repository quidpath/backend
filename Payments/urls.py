from django.urls import path

from Payments.views import individual_billing, mpesa_callback

urlpatterns = [
    path("individual/plans/", individual_billing.list_individual_plans, name="list-individual-plans"),
    path("individual/subscribe/", individual_billing.create_individual_subscription, name="create-individual-subscription"),
    path("individual/subscription/status/", individual_billing.get_individual_subscription_status, name="get-individual-subscription-status"),
    path("individual/payment-history/", individual_billing.get_individual_payment_history, name="get-individual-payment-history"),
    path("mpesa/callback/", mpesa_callback.mpesa_callback, name="mpesa-callback"),
]
