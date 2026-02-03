# Payment status views
import logging

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Payments.models import RecordPayment
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def get_payment_status(request, payment_id):
    """
    Get payment status.

    GET /api/v1/payments/{payment_id}/status/

    Response:
    {
        "code": 200,
        "message": "Payment status retrieved successfully",
        "data": {
            "payment_id": "uuid",
            "payment_status": "pending|processing|success|failed|cancelled",
            "provider_reference": "...",
            "confirmed_at": "...",
            "receipt_pdf_url": "..."
        }
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        registry = ServiceRegistry()

        # Get payment
        payment = registry.database(
            model_name="RecordPayment", operation="get", data={"id": payment_id}
        )

        if not payment:
            return ResponseProvider(message="Payment not found", code=404).bad_request()

        # Check if user has access to this payment (same corporate)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={
                "customuser_ptr_id": (
                    user.get("id")
                    if isinstance(user, dict)
                    else getattr(user, "id", None)
                ),
                "is_active": True,
            },
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if payment.get("corporate_id") != corporate_id:
            return ResponseProvider(message="Payment not found", code=404).bad_request()

        return ResponseProvider(
            data={
                "payment_id": payment.get("id"),
                "payment_status": payment.get("payment_status", "pending"),
                "provider_reference": payment.get("provider_reference"),
                "confirmed_at": payment.get("confirmed_at"),
                "receipt_pdf_url": payment.get("receipt_pdf_url"),
                "amount_received": str(payment.get("amount_received", "0")),
                "currency": payment.get("currency", "USD"),
            },
            message="Payment status retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error getting payment status: {e}")
        return ResponseProvider(
            message="An error occurred while retrieving payment status", code=500
        ).exception()
