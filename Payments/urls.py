# Payments/urls.py
from django.urls import path

from . import views
from .views.bill_payment import list_vendors, list_unpaid_bills, record_vendor_payment
from .views.invoice_payments import list_unpaid_invoices, record_payment, list_customers
from .views.payment_gateway import initiate_mpesa_stk, mpesa_webhook
from .views.card_gateway import initiate_card_payment, card_webhook
from .views.payment_status import get_payment_status
from .views.payment_provider import get_payment_provider, create_or_update_payment_provider
from .views.organization_billing import (
    list_organization_invoices, list_organization_payments,
    initiate_organization_payment, organization_payment_webhook,
    get_subscription_status, get_invoice_details
)

urlpatterns = [
    path("customers/", list_customers, name="list_customers"),
    path("invoices/unpaid/", list_unpaid_invoices, name="list_unpaid_invoices"),
    path("record/", record_payment, name="record_payment"),

    path('vendors/', list_vendors, name='list_vendors'),
    path('unpaid-bills/', list_unpaid_bills, name='list_unpaid_bills'),
    path('record-vendor-payment/', record_vendor_payment, name='record_vendor_payment'),
    
    # Payment Gateway Endpoints
    path('mpesa/stk-initiate/', initiate_mpesa_stk, name='initiate_mpesa_stk'),
    path('mpesa/webhook/', mpesa_webhook, name='mpesa_webhook'),
    path('card/initiate/', initiate_card_payment, name='initiate_card_payment'),
    path('card/webhook/', card_webhook, name='card_webhook'),
    path('payments/<uuid:payment_id>/status/', get_payment_status, name='get_payment_status'),
    
    # Payment Provider Management
    path('payment-providers/<str:provider_type>/', get_payment_provider, name='get_payment_provider'),
    path('payment-providers/<str:provider_type>/update/', create_or_update_payment_provider, name='create_or_update_payment_provider'),
    
    # Organization Billing
    path('organization/subscription/status/', get_subscription_status, name='get_subscription_status'),
    path('organization/invoices/', list_organization_invoices, name='list_organization_invoices'),
    path('organization/invoices/<uuid:invoice_id>/', get_invoice_details, name='get_invoice_details'),
    path('organization/payments/', list_organization_payments, name='list_organization_payments'),
    path('organization/payment/initiate/', initiate_organization_payment, name='initiate_organization_payment'),
    path('organization/payment/webhook/', organization_payment_webhook, name='organization_payment_webhook'),
]
