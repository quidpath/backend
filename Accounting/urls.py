from django.urls import path

from Accounting.views.Quote import list_quotations, get_quotation, update_quotation, delete_quotation, \
    create_and_send_quotation, save_quotation_draft, convert_quotation_to_invoice
from Accounting.views.customer_view import create_customer, list_customers, update_customer, delete_customer, \
    get_tax_rate
from Accounting.views.invoice import save_invoice_draft, create_and_send_invoice, list_invoices, get_invoice, \
    update_invoice, delete_invoice
from Accounting.views.lpo import list_purchase_orders, get_purchase_order, update_purchase_order, \
    delete_purchase_order, save_purchase_order_draft, create_and_send_purchase_order
from Accounting.views.vendor_view import create_vendor, list_vendors, update_vendor, delete_vendor
from Accounting.views.vendor_bill import create_vendor_bill, update_vendor_bill, list_vendor_bills, \
    get_vendor_bill, delete_vendor_bill, convert_purchase_order_to_vendor_bill

urlpatterns = [
    # Customer Endpoints
    path('customer/create/', create_customer, name='create_customer'),
    path('customer/list/', list_customers, name='list_customers'),
    path('customer/update/', update_customer, name='update_customer'),
    path('customer/delete/', delete_customer, name='delete_customer'),

    # Vendor Endpoints
    path('vendor/create/', create_vendor, name='create_vendor'),
    path('vendor/list/', list_vendors, name='list_vendors'),
    path('vendor/update/', update_vendor, name='update_vendor'),
    path('vendor/delete/', delete_vendor, name='delete_vendor'),

    # Quotation Endpoints
    path("quotation/save-draft/", save_quotation_draft, name="save_quotation_draft"),
    path("quotation/create-and-send/", create_and_send_quotation, name="create_and_send_quotation"),
    path("quotation/list/", list_quotations, name="list_quotations"),
    path("quotation/get/", get_quotation, name="get_quotation"),
    path("quotation/update/", update_quotation, name="update_quotation"),
    path("quotation/delete/", delete_quotation, name="delete_quotation"),
    path("quotation/invoice-quote/", convert_quotation_to_invoice, name="convert_quote_to_invoice"),

    # Invoice Endpoints
    path("invoice/save-draft/", save_invoice_draft, name="save_invoice_draft"),
    path("invoice/create-and-send/", create_and_send_invoice, name="create_and_send_invoice"),
    path("invoice/list/", list_invoices, name="list_invoices"),
    path("invoice/get/", get_invoice, name="get_invoice"),
    path("invoice/update/", update_invoice, name="update_invoice"),
    path("invoice/delete/", delete_invoice, name="delete_invoice"),

    # Purchase Order Endpoints
    path('purchase-orders/save-draft/', save_purchase_order_draft, name='save_purchase_order_draft'),
    path('purchase-orders/create-and-send/', create_and_send_purchase_order, name='create_and_send_purchase_order'),
    path('purchase-orders/list/', list_purchase_orders, name='list_purchase_orders'),
    path('purchase-orders/get/', get_purchase_order, name='get_purchase_order'),
    path('purchase-orders/update/', update_purchase_order, name='update_purchase_order'),
    path('purchase-orders/delete/', delete_purchase_order, name='delete_purchase_order'),

    # Vendor Bill Endpoints
    path('vendor-bill/create/', create_vendor_bill, name='create_vendor_bill'),
    path('vendor-bill/update/', update_vendor_bill, name='update_vendor_bill'),
    path('vendor-bill/list/', list_vendor_bills, name='list_vendor_bills'),
    path('vendor-bill/get/', get_vendor_bill, name='get_vendor_bill'),
    path('vendor-bill/delete/', delete_vendor_bill, name='delete_vendor_bill'),
    path('vendor-bill/convert-purchase-order/', convert_purchase_order_to_vendor_bill, name='convert_purchase_order_to_vendor_bill'),

    # Tax Rate Endpoint
    path('get-tax-rate/', get_tax_rate, name='get_tax_rate'),
]