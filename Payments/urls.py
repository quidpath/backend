"""
Payments URL configuration — ERP customer/vendor payment processing only.
Subscription billing routes live in Authentication/urls.py and OrgAuth/urls.py.
"""
from django.urls import path

from Payments.views import payment_gateway

urlpatterns = [
    path("payments/mpesa/stk-initiate/", payment_gateway.initiate_mpesa_stk, name="mpesa-stk-initiate"),
    path("payments/mpesa/webhook/", payment_gateway.mpesa_webhook, name="mpesa-webhook"),
]
