# Payments/urls.py
from django.urls import path

from . import views
from .views.bill_payment import list_vendors, list_unpaid_bills, record_vendor_payment
from .views.invoice_payments import list_unpaid_invoices, record_payment, list_customers

urlpatterns = [
    path("customers/", list_customers, name="list_customers"),
    path("invoices/unpaid/", list_unpaid_invoices, name="list_unpaid_invoices"),
    path("record/", record_payment, name="record_payment"),

    path('vendors/', list_vendors, name='list_vendors'),
    path('unpaid-bills/', list_unpaid_bills, name='list_unpaid_bills'),
    path('record-vendor-payment/', record_vendor_payment, name='record_vendor_payment'),
]
