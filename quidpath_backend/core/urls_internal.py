"""
Internal API URLs for inter-service communication.
These endpoints are used by microservices to communicate with the main backend.
All endpoints require a valid X-Service-Key header.
"""

from django.urls import path

from quidpath_backend.core.views import auth_verify
from quidpath_backend.core.views.internal_erp import (
    get_user,
    get_corporate,
    create_invoice,
    create_journal_entry,
    import_billable_hours,
)

urlpatterns = [
    # Auth
    path("auth/verify/", auth_verify.verify_credentials, name="verify_credentials"),

    # User & corporate data (used by all microservices for UserCacheService)
    path("users/<int:user_id>/", get_user, name="internal_get_user"),
    path("corporates/<int:corporate_id>/", get_corporate, name="internal_get_corporate"),

    # Accounting integration (used by CRM, HRM, Projects)
    path("invoices/", create_invoice, name="internal_create_invoice"),
    path("journal-entries/", create_journal_entry, name="internal_create_journal_entry"),
    path("billable-hours/", import_billable_hours, name="internal_billable_hours"),
]
