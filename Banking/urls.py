from django.urls import path

from Banking.views import bankAccount
from Banking.views.charge import (add_bank_charge, delete_bank_charge,
                                  list_bank_charges, update_bank_charge)
from Banking.views.reconciliation import (add_bank_reconciliation,
                                          delete_bank_reconciliation,
                                          list_bank_reconciliations,
                                          update_bank_reconciliation)
from Banking.views.Transactions import (create_transaction, delete_transaction,
                                        get_transaction, list_transactions,
                                        update_transaction)
from Banking.views.transfer import (create_internal_transfer,
                                    delete_internal_transfer,
                                    list_internal_transfers,
                                    update_internal_transfer)

urlpatterns = [
    # Bank Account endpoints
    path("bank-account/add/", bankAccount.add_bank_account, name="add_bank_account"),
    path(
        "bank-account/list/", bankAccount.list_bank_accounts, name="list_bank_accounts"
    ),
    path(
        "bank-account/update/",
        bankAccount.update_bank_account,
        name="update_bank_account",
    ),
    path(
        "bank-account/delete/",
        bankAccount.delete_bank_account,
        name="delete_bank_account",
    ),
    # Internal Transfer endpoints
    path(
        "internal-transfer/create/",
        create_internal_transfer,
        name="create_internal_transfer",
    ),
    path(
        "internal-transfer/list/",
        list_internal_transfers,
        name="list_internal_transfers",
    ),
    path(
        "internal-transfer/update/",
        update_internal_transfer,
        name="update_internal_transfer",
    ),
    path(
        "internal-transfer/delete/",
        delete_internal_transfer,
        name="delete_internal_transfer",
    ),
    path(
        "bank-reconciliation/create/",
        add_bank_reconciliation,
        name="add_bank_reconciliation",
    ),
    path(
        "bank-reconciliation/list/",
        list_bank_reconciliations,
        name="list_bank_reconciliations",
    ),
    path(
        "bank-reconciliation/update/",
        update_bank_reconciliation,
        name="update_bank_reconciliation",
    ),
    path(
        "bank-reconciliation/delete/",
        delete_bank_reconciliation,
        name="delete_bank_reconciliation",
    ),
    # Bank Charge endpoints
    path("bank-charge/add/", add_bank_charge, name="add_bank_charge"),
    path("bank-charge/list/", list_bank_charges, name="list_bank_charges"),
    path("bank-charge/update/", update_bank_charge, name="update_bank_charge"),
    path("bank-charge/delete/", delete_bank_charge, name="delete_bank_charge"),
    path("transaction/create/", create_transaction, name="create_transaction"),
    path("transaction/<uuid:transaction_id>/", get_transaction, name="get_transaction"),
    path("transaction/list/", list_transactions, name="list_transactions"),
    path("transaction/update/", update_transaction, name="update_transaction"),
    path("transaction/delete/", delete_transaction, name="delete_transaction"),
]
