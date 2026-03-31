"""
Payments URL configuration — ERP customer/vendor payment processing only.
Subscription billing routes live in Authentication/urls.py and OrgAuth/urls.py.

Note: M-Pesa/Daraja integration has been removed. All payments now go through Paystack.
"""
from django.urls import path

urlpatterns = [
    # All payment endpoints have been migrated to the billing service
    # This module is reserved for future ERP-specific payment processing
]
