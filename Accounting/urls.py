from django.urls import path

from Accounting.views.Quote import list_quotations, get_quotation, update_quotation, delete_quotation, \
    create_and_send_quotation, save_quotation_draft
from Accounting.views.customer_view import create_customer, list_customers, update_customer, delete_customer, \
    get_tax_rate
from Accounting.views.invoice import save_invoice_draft, create_and_send_invoice, list_invoices, get_invoice, \
    update_invoice, delete_invoice
from Accounting.views.vendor_view import create_vendor, list_vendors, update_vendor, delete_vendor

urlpatterns = [
    path('customer/create/', create_customer, name='create_customer'),
    path('customer/list/', list_customers, name='list_customers'),
    path('customer/update/', update_customer, name='update_customer'),
    path('customer/delete/', delete_customer, name='delete_customer'),

    # Vendor Endpoints
    path('vendor/create/', create_vendor, name='create_vendor'),
    path('vendor/list/', list_vendors, name='list_vendors'),
    path('vendor/update/', update_vendor, name='update_vendor'),
    path('vendor/delete/', delete_vendor, name='delete_vendor'),

    path("quotation/save-draft/", save_quotation_draft, name="save_quotation_draft"),
    path("quotation/create-and-send/", create_and_send_quotation, name="create_and_send_quotation"),
    path("quotation/list/", list_quotations, name="list_quotations"),
    path("quotation/get/", get_quotation, name="get_quotation"),
    path("quotation/update/", update_quotation, name="update_quotation"),
    path("quotation/delete/", delete_quotation, name="delete_quotation"),

    path("invoice/save-draft/", save_invoice_draft, name="save_invoice_draft"),
    path("invoice/create-and-send/", create_and_send_invoice, name="create_and_send_invoice"),
    path("invoice/list/", list_invoices, name="list_invoices"),
    path("invoice/get/", get_invoice, name="get_invoice"),
    path("invoice/update/", update_invoice, name="update_invoice"),
    path("invoice/delete/", delete_invoice, name="delete_invoice"),

    path('get-tax-rate/', get_tax_rate, name='get_tax_rate'),
]