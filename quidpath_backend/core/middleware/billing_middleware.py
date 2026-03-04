import logging

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from OrgAuth.models import CorporateUser
from quidpath_backend.core.billing_client import BillingServiceClient

logger = logging.getLogger(__name__)


class BillingAccessMiddleware(MiddlewareMixin):
    EXEMPT_PATHS = [
        "/api/auth/login/",
        "/api/auth/register/",
        "/api/auth/register-individual/",
        "/api/auth/verify-otp/",
        "/api/auth/password-forgot/",
        "/api/auth/verify-pass-otp/",
        "/api/auth/reset-password/",
        "/api/auth/health/",
        "/api/billing/",
        "/api/payments/",
        "/api/orgauth/webhooks/",
        "/admin/",
        "/static/",
        "/media/",
    ]

    def process_request(self, request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        path = request.path
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return None

        if request.user.is_superuser:
            return None

        try:
            corporate_user = CorporateUser.objects.select_related("corporate").get(
                customuser_ptr_id=request.user.id
            )
            corporate = corporate_user.corporate

            if not corporate.is_active:
                return JsonResponse(
                    {
                        "error": "Account suspended",
                        "message": "Your account has been suspended. Please contact support.",
                        "requires_payment": True,
                    },
                    status=403,
                )

            billing_client = BillingServiceClient()
            access_check = billing_client.check_access(str(corporate.id))

            if not access_check.get("success"):
                logger.warning(
                    f"Billing service check failed for corporate {corporate.id}: {access_check.get('message')}"
                )
                return None

            has_access = access_check.get("data", {}).get("has_access", False)
            status = access_check.get("data", {}).get("status", "unknown")

            if not has_access:
                return JsonResponse(
                    {
                        "error": "Payment required",
                        "message": "Your subscription has expired or payment is pending. Please complete payment to continue.",
                        "status": status,
                        "requires_payment": True,
                        "corporate_id": str(corporate.id),
                    },
                    status=402,
                )

        except CorporateUser.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Billing middleware error: {str(e)}", exc_info=True)

        return None
