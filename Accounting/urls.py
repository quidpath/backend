from django.urls import path

from Accounting.views.analytics_views import get_analytics_overview
from Accounting.views.export_views import (export_expenses,
                                           export_financial_report,
                                           export_invoices,
                                           export_journal_entries,
                                           export_purchase_orders,
                                           export_quotations,
                                           export_vendor_bills)
from Accounting.views.import_views import (download_import_template,
                                           import_customers, import_expenses,
                                           import_products, import_vendors)
from Accounting.views.aged_invoices import (download_aged_invoices,
                                            get_aged_invoices)
from Accounting.views.aging_reports import (download_aging_report,
                                            get_aging_report)
from Accounting.views.attachments import (delete_attachment, list_attachments,
                                          upload_attachment)
from Accounting.views.audit import list_audit_logs
from Accounting.views.chart_of_accounts import (create_account,
                                                create_account_sub_type,
                                                create_account_type,
                                                delete_account,
                                                delete_account_sub_type,
                                                delete_account_type,
                                                get_account,
                                                get_account_sub_type,
                                                get_account_type,
                                                list_account_sub_types,
                                                list_account_types,
                                                list_accounts, update_account,
                                                update_account_sub_type,
                                                update_account_type)
from Accounting.views.currency import (get_currency_rates,
                                       refresh_currency_rates)
from Accounting.views.customer_view import (create_customer, delete_customer,
                                            get_tax_rate, list_customers,
                                            update_customer)
from Accounting.views.default_accounts import seed_default_accounts
from Accounting.views.document_sending import (send_invoice, send_lpo,
                                               send_quote)
from Accounting.views.expenses import (create_expense, delete_expense,
                                       get_expense, list_expenses,
                                       update_expense)
from Accounting.views.fetch_reports import (get_balance_sheet,
                                            get_cash_flow_statement,
                                            get_income_statement,
                                            get_profit_and_loss)
from Accounting.views.inventory import (create_inventory_item,
                                        create_stock_movement,
                                        create_warehouse,
                                        delete_inventory_item,
                                        delete_warehouse, list_inventory_items,
                                        list_stock_movements, list_warehouses,
                                        update_inventory_item,
                                        update_warehouse)
from Accounting.views.invoice import (create_and_post_invoice, delete_invoice,
                                      get_invoice, list_invoices,
                                      save_invoice_draft, update_invoice)
from Accounting.views.journal_actions import (duplicate_journal_entry,
                                              post_journal_entry,
                                              unpost_journal_entry)
from Accounting.views.journals import (create_journal_entry,
                                       delete_journal_entry, get_journal_entry,
                                       list_journal_entries,
                                       update_journal_entry)
from Accounting.views.ledger import download_ledger, list_ledger
from Accounting.views.lpo import (create_and_post_purchase_order,
                                  delete_purchase_order, get_purchase_order,
                                  list_purchase_orders,
                                  save_purchase_order_draft,
                                  update_purchase_order)
from Accounting.views.Quote import (convert_quotation_to_invoice,
                                    create_and_post_quotation,
                                    delete_quotation, get_quotation,
                                    list_quotations, save_quotation_draft,
                                    update_quotation)
from Accounting.views.quotation_draft_post import (
    post_quotation as post_quotation_new,
    auto_save_quotation,
    list_draft_quotations
)
from Accounting.views.invoice_draft_post import (
    post_invoice as post_invoice_new,
    auto_save_invoice,
    list_draft_invoices
)
from Accounting.views.purchase_order_draft_post import (
    post_purchase_order as post_purchase_order_new,
    auto_save_purchase_order,
    list_draft_purchase_orders
)
from Accounting.views.vendor_bill_draft_post import (
    post_vendor_bill as post_vendor_bill_new,
    auto_save_vendor_bill,
    list_draft_vendor_bills
)
from Accounting.views.recurring import (list_recurring_transactions,
                                        update_recurring_transaction)
from Accounting.views.reports import (download_financial_report,
                                      generate_balance_sheet_report,
                                      generate_cash_flow_report,
                                      generate_income_statement_report,
                                      generate_profit_loss_report,
                                      retrieve_financial_report)
from Accounting.views.summary_reports import (get_expenses_summary,
                                              get_purchases_summary,
                                              get_sales_summary)
from Accounting.views.trial_balance import (download_trial_balance,
                                            get_trial_balance)
from Accounting.views.vendor_bill import (
    convert_purchase_order_to_vendor_bill, create_vendor_bill,
    delete_vendor_bill, get_vendor_bill, list_po, list_vendor_bills,
    update_vendor_bill)
from Accounting.views.vendor_view import (create_vendor, delete_vendor,
                                          get_vendor, list_vendors,
                                          search_vendors, update_vendor)
from Accounting.views.petty_cash import (
    create_petty_cash_fund,
    list_petty_cash_funds,
    create_petty_cash_transaction,
    list_petty_cash_transactions,
    approve_petty_cash_transaction,
    delete_petty_cash_transaction,
)
from Accounting.views.bank_reconciliation import (
    create_bank_reconciliation,
    list_bank_reconciliations,
    get_bank_reconciliation,
    add_reconciliation_item,
    complete_bank_reconciliation,
    delete_bank_reconciliation,
)
from Accounting.views.tax_rate import (
    create_tax_rate,
    list_tax_rates,
    get_tax_rate_detail,
    update_tax_rate,
    delete_tax_rate,
)
from Accounting.views.seed_tax_rates import seed_default_tax_rates
from Accounting.views.document_pdf import (
    download_invoice_pdf,
    download_quotation_pdf,
    download_po_pdf,
    download_bill_pdf,
)

urlpatterns = [
    # Customer Endpoints
    path("customer/create/", create_customer, name="create_customer"),
    path("customer/list/", list_customers, name="list_customers"),
    path("customer/update/", update_customer, name="update_customer"),
    path("customer/delete/", delete_customer, name="delete_customer"),
    # Vendor Endpoints
    path("vendor/create/", create_vendor, name="create_vendor"),
    path("vendor/list/", list_vendors, name="list_vendors"),
    path("vendor/get/", get_vendor, name="get_vendor"),
    path("vendor/update/", update_vendor, name="update_vendor"),
    path("vendor/delete/", delete_vendor, name="delete_vendor"),
    path("vendor/search/", search_vendors, name="search_vendors"),
    # Quotation Endpoints
    path("quotation/save-draft/", save_quotation_draft, name="save_quotation_draft"),
    path(
        "quotation/create-and-post/",
        create_and_post_quotation,
        name="create_and_send_quotation",
    ),
    path("quotation/list/", list_quotations, name="list_quotations"),
    path("quotation/get/", get_quotation, name="get_quotation"),
    path("quotation/update/", update_quotation, name="update_quotation"),
    path("quotation/delete/", delete_quotation, name="delete_quotation"),
    path(
        "quotation/invoice-quote/",
        convert_quotation_to_invoice,
        name="convert_quote_to_invoice",
    ),
    path("quotation/<uuid:quote_id>/send/", send_quote, name="send_quote"),
    # New Draft/Post Endpoints
    path("quotation/<uuid:quotation_id>/post/", post_quotation_new, name="post_quotation"),
    path("quotation/<uuid:quotation_id>/auto-save/", auto_save_quotation, name="auto_save_quotation"),
    path("quotation/drafts/", list_draft_quotations, name="list_draft_quotations"),
    # Invoice Draft/Post Endpoints
    path("invoice/<uuid:invoice_id>/post/", post_invoice_new, name="post_invoice"),
    path("invoice/<uuid:invoice_id>/auto-save/", auto_save_invoice, name="auto_save_invoice"),
    path("invoice/drafts/", list_draft_invoices, name="list_draft_invoices"),
    # Invoice Endpoints
    path("invoice/save-draft/", save_invoice_draft, name="save_invoice_draft"),
    path(
        "invoice/create-and-post/",
        create_and_post_invoice,
        name="create_and_post_invoice",
    ),
    path("invoice/list/", list_invoices, name="list_invoices"),
    path("invoice/get/", get_invoice, name="get_invoice"),
    path("invoice/update/", update_invoice, name="update_invoice"),
    path("invoice/delete/", delete_invoice, name="delete_invoice"),
    path("invoice/<uuid:invoice_id>/send/", send_invoice, name="send_invoice"),
    # Purchase Order Endpoints
    path(
        "purchase-orders/save-draft/",
        save_purchase_order_draft,
        name="save_purchase_order_draft",
    ),
    path(
        "purchase-orders/create-and-post/",
        create_and_post_purchase_order,
        name="create_and_send_purchase_order",
    ),
    path("purchase-orders/list/", list_purchase_orders, name="list_purchase_orders"),
    path("purchase-orders/get/", get_purchase_order, name="get_purchase_order"),
    path(
        "purchase-orders/update/", update_purchase_order, name="update_purchase_order"
    ),
    path(
        "purchase-orders/delete/", delete_purchase_order, name="delete_purchase_order"
    ),
    path("purchase-orders/<uuid:lpo_id>/send/", send_lpo, name="send_lpo"),
    # Purchase Order Draft/Post Endpoints
    path("purchase-orders/<uuid:po_id>/post/", post_purchase_order_new, name="post_purchase_order"),
    path("purchase-orders/<uuid:po_id>/auto-save/", auto_save_purchase_order, name="auto_save_purchase_order"),
    path("purchase-orders/drafts/", list_draft_purchase_orders, name="list_draft_purchase_orders"),
    # Vendor Bill Endpoints
    path("vendor-bill/create/", create_vendor_bill, name="create_vendor_bill"),
    path("vendor-bill/update/", update_vendor_bill, name="update_vendor_bill"),
    path("vendor-bill/list/", list_vendor_bills, name="list_vendor_bills"),
    path("vendor-bill/po/list/", list_po, name="list_vendor_bill_po"),
    path("vendor-bill/get/", get_vendor_bill, name="get_vendor_bill"),
    path("vendor-bill/delete/", delete_vendor_bill, name="delete_vendor_bill"),
    path(
        "vendor-bill/convert-purchase-order/",
        convert_purchase_order_to_vendor_bill,
        name="convert_purchase_order_to_vendor_bill",
    ),
    # Vendor Bill Draft/Post Endpoints
    path("vendor-bill/<uuid:bill_id>/post/", post_vendor_bill_new, name="post_vendor_bill"),
    path("vendor-bill/<uuid:bill_id>/auto-save/", auto_save_vendor_bill, name="auto_save_vendor_bill"),
    path("vendor-bill/drafts/", list_draft_vendor_bills, name="list_draft_vendor_bills"),
    # Expense Endpoints
    path("expense/create/", create_expense, name="create_expense"),
    path("expense/list/", list_expenses, name="list_expenses"),
    path("expense/get/", get_expense, name="get_expense"),
    path("expense/update/", update_expense, name="update_expense"),
    path("expense/delete/", delete_expense, name="delete_expense"),
    # Tax Rate Endpoint
    path("get-tax-rate/", get_tax_rate, name="get_tax_rate"),
    path("account/create/", create_account, name="create_account"),
    path("account/list/", list_accounts, name="list_accounts"),
    path("account/get/", get_account, name="get_account"),
    path("account/update/", update_account, name="update_account"),
    path("account/delete/", delete_account, name="delete_account"),
    # AccountType URLs
    path("account-types/create/", create_account_type, name="create_account_type"),
    path("account-types/list/", list_account_types, name="list_account_types"),
    path("account-types/get/", get_account_type, name="get_account_type"),
    path("account-types/update/", update_account_type, name="update_account_type"),
    path("account-types/delete/", delete_account_type, name="delete_account_type"),
    # AccountSubType URLs
    path(
        "account-sub-types/create/",
        create_account_sub_type,
        name="create_account_sub_type",
    ),
    path(
        "account-sub-types/list/", list_account_sub_types, name="list_account_sub_types"
    ),
    path("account-sub-types/get/", get_account_sub_type, name="get_account_sub_type"),
    path(
        "account-sub-types/update/",
        update_account_sub_type,
        name="update_account_sub_type",
    ),
    path(
        "account-sub-types/delete/",
        delete_account_sub_type,
        name="delete_account_sub_type",
    ),
    # Journal Entry URLs
    path("journal/create/", create_journal_entry, name="create_journal_entry"),
    path("journal/list/", list_journal_entries, name="list_journal_entries"),
    path("journal/get/", get_journal_entry, name="get_journal_entry"),
    path("journal/update/", update_journal_entry, name="update_journal_entry"),
    path("journal/delete/", delete_journal_entry, name="delete_journal_entry"),
    path("journal/post/", post_journal_entry, name="post_journal_entry"),
    path("journal/unpost/", unpost_journal_entry, name="unpost_journal_entry"),
    path("journal/duplicate/", duplicate_journal_entry, name="duplicate_journal_entry"),
    # General Ledger URLs
    path("ledger/list/", list_ledger, name="list_ledger"),
    path("ledger/download/", download_ledger, name="download_ledger"),
    # Trial Balance URLs
    path("trial-balance/", get_trial_balance, name="get_trial_balance"),
    path(
        "trial-balance/download/", download_trial_balance, name="download_trial_balance"
    ),
    # Aging Reports URLs
    path("reports/aging/", get_aging_report, name="get_aging_report"),
    path(
        "reports/aging/download/", download_aging_report, name="download_aging_report"
    ),
    # Aged Invoices URLs (detailed invoice aging)
    path("reports/aged-invoices/", get_aged_invoices, name="get_aged_invoices"),
    path(
        "reports/aged-invoices/download/",
        download_aged_invoices,
        name="download_aged_invoices",
    ),
    # Summary Reports URLs
    path("reports/sales-summary/", get_sales_summary, name="get_sales_summary"),
    path(
        "reports/purchases-summary/",
        get_purchases_summary,
        name="get_purchases_summary",
    ),
    path(
        "reports/expenses-summary/", get_expenses_summary, name="get_expenses_summary"
    ),
    # Default Accounts URLs
    path(
        "accounts/seed-defaults/", seed_default_accounts, name="seed_default_accounts"
    ),
    # Financial Reports URLs (existing)
    path("generate-pl/", generate_profit_loss_report, name="generate-pl"),
    path(
        "generate-income-statement/",
        generate_income_statement_report,
        name="generate-income-statement",
    ),
    path("generate-bs/", generate_balance_sheet_report, name="generate-bs"),
    path("generate-cash-flow/", generate_cash_flow_report, name="generate-cash-flow"),
    path("retrieve-report/", retrieve_financial_report, name="retrieve-report"),
    path("download-report/", download_financial_report, name="download-report"),
    # Financial Reports Aliases (for frontend compatibility)
    path(
        "generate-profit-loss-report/",
        generate_profit_loss_report,
        name="generate-profit-loss-report",
    ),
    path(
        "generate-balance-sheet-report/",
        generate_balance_sheet_report,
        name="generate-balance-sheet-report",
    ),
    path(
        "generate-cash-flow-report/",
        generate_cash_flow_report,
        name="generate-cash-flow-report",
    ),
    # Financial Reports Direct Access URLs
    path("reports/balance-sheet/", get_balance_sheet, name="get_balance_sheet"),
    path(
        "reports/income-statement/", get_income_statement, name="get_income_statement"
    ),
    path("reports/profit-and-loss/", get_profit_and_loss, name="get_profit_and_loss"),
    path(
        "reports/cash-flow-statement/",
        get_cash_flow_statement,
        name="get_cash_flow_statement",
    ),
    # Document Attachments
    path("attachments/upload/", upload_attachment, name="upload_attachment"),
    path("attachments/list/", list_attachments, name="list_attachments"),
    path(
        "attachments/<uuid:attachment_id>/delete/",
        delete_attachment,
        name="delete_attachment",
    ),
    # Inventory Management
    # Warehouses
    path("warehouses/create/", create_warehouse, name="create_warehouse"),
    path("warehouses/list/", list_warehouses, name="list_warehouses"),
    path(
        "warehouses/<uuid:warehouse_id>/update/",
        update_warehouse,
        name="update_warehouse",
    ),
    path(
        "warehouses/<uuid:warehouse_id>/delete/",
        delete_warehouse,
        name="delete_warehouse",
    ),
    # Inventory Items
    path(
        "inventory-items/create/", create_inventory_item, name="create_inventory_item"
    ),
    path("inventory-items/list/", list_inventory_items, name="list_inventory_items"),
    path(
        "inventory-items/<uuid:item_id>/update/",
        update_inventory_item,
        name="update_inventory_item",
    ),
    path(
        "inventory-items/<uuid:item_id>/delete/",
        delete_inventory_item,
        name="delete_inventory_item",
    ),
    # Stock Movements
    path(
        "stock-movements/create/", create_stock_movement, name="create_stock_movement"
    ),
    path("stock-movements/list/", list_stock_movements, name="list_stock_movements"),
    # Audit Logs
    path("audit-logs/list/", list_audit_logs, name="list_audit_logs"),
    # Recurring Transactions
    path(
        "recurring-transactions/list/",
        list_recurring_transactions,
        name="list_recurring_transactions",
    ),
    path(
        "recurring-transactions/<uuid:transaction_id>/update/",
        update_recurring_transaction,
        name="update_recurring_transaction",
    ),
    # Currency Rates
    path("currency/rates/", get_currency_rates, name="get_currency_rates"),
    path(
        "currency/rates/refresh/", refresh_currency_rates, name="refresh_currency_rates"
    ),
    # ── Export Endpoints ──────────────────────────────────────────────────────
    path("export/invoices/", export_invoices, name="export_invoices"),
    path("export/vendor-bills/", export_vendor_bills, name="export_vendor_bills"),
    path("export/expenses/", export_expenses, name="export_expenses"),
    path("export/quotations/", export_quotations, name="export_quotations"),
    path("export/purchase-orders/", export_purchase_orders, name="export_purchase_orders"),
    path("export/journal-entries/", export_journal_entries, name="export_journal_entries"),
    path("export/financial-report/", export_financial_report, name="export_financial_report"),
    # ── Import Endpoints ──────────────────────────────────────────────────────
    path("import/customers/", import_customers, name="import_customers"),
    path("import/vendors/", import_vendors, name="import_vendors"),
    path("import/expenses/", import_expenses, name="import_expenses"),
    path("import/products/", import_products, name="import_products"),
    path("import/template/", download_import_template, name="download_import_template"),
    # ── Analytics ─────────────────────────────────────────────────────────────
    path("analytics/overview/", get_analytics_overview, name="analytics_overview"),
    # ── Petty Cash ────────────────────────────────────────────────────────────
    path("petty-cash/funds/create/", create_petty_cash_fund, name="create_petty_cash_fund"),
    path("petty-cash/funds/list/", list_petty_cash_funds, name="list_petty_cash_funds"),
    path("petty-cash/transactions/create/", create_petty_cash_transaction, name="create_petty_cash_transaction"),
    path("petty-cash/transactions/list/", list_petty_cash_transactions, name="list_petty_cash_transactions"),
    path("petty-cash/transactions/approve/", approve_petty_cash_transaction, name="approve_petty_cash_transaction"),
    path("petty-cash/transactions/delete/", delete_petty_cash_transaction, name="delete_petty_cash_transaction"),
    # ── Bank Reconciliation ───────────────────────────────────────────────────
    path("bank-reconciliation/create/", create_bank_reconciliation, name="create_bank_reconciliation"),
    path("bank-reconciliation/list/", list_bank_reconciliations, name="list_bank_reconciliations"),
    path("bank-reconciliation/get/", get_bank_reconciliation, name="get_bank_reconciliation"),
    path("bank-reconciliation/add-item/", add_reconciliation_item, name="add_reconciliation_item"),
    path("bank-reconciliation/complete/", complete_bank_reconciliation, name="complete_bank_reconciliation"),
    path("bank-reconciliation/delete/", delete_bank_reconciliation, name="delete_bank_reconciliation"),
    # ── Tax Rate Management ───────────────────────────────────────────────────
    path("tax-rates/create/", create_tax_rate, name="create_tax_rate"),
    path("tax-rates/list/", list_tax_rates, name="list_tax_rates"),
    path("tax-rates/get/", get_tax_rate_detail, name="get_tax_rate_detail"),
    path("tax-rates/update/", update_tax_rate, name="update_tax_rate"),
    path("tax-rates/delete/", delete_tax_rate, name="delete_tax_rate"),
    path("tax-rates/seed-defaults/", seed_default_tax_rates, name="seed_default_tax_rates"),
    # ── Document PDF Downloads ────────────────────────────────────────────────
    path("invoice/download-pdf/", download_invoice_pdf, name="download_invoice_pdf"),
    path("quotation/download-pdf/", download_quotation_pdf, name="download_quotation_pdf"),
    path("purchase-orders/download-pdf/", download_po_pdf, name="download_po_pdf"),
    path("vendor-bill/download-pdf/", download_bill_pdf, name="download_bill_pdf"),
]
