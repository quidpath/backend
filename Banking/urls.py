from django.urls import path

from Banking.views import bankAccount
from Banking.views.transfer import create_internal_transfer, list_internal_transfers, update_internal_transfer, \
    delete_internal_transfer

urlpatterns = [
    path("bank-account/add/", bankAccount.add_bank_account, name="add_bank_account"),
    path("bank-account/list/", bankAccount.list_bank_accounts, name="list_bank_accounts"),
    path("bank-account/update/", bankAccount.update_bank_account, name="update_bank_account"),
    path("bank-account/delete/", bankAccount.delete_bank_account, name="delete_bank_account"),

    path("internal-transfer/create/", create_internal_transfer, name="create_internal_transfer"),
    path("internal-transfer/list/", list_internal_transfers, name="list_internal_transfers"),
    path("internal-transfer/update/<uuid:transfer_id>/", update_internal_transfer, name="update_internal_transfer"),
    path("internal-transfer/delete/<uuid:transfer_id>/", delete_internal_transfer, name="delete_internal_transfer"),
]
