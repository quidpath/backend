import logging

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from OrgAuth.models import CorporateUser
from quidpath_backend.core.Services.billing_service import billing_service

logger = logging.getLogger(__name__)


class BillingAccessMiddleware(MiddlewareMixin):
    EXEMPT_PATHS = [
        "/api/auth/login/",
        "/api/auth/register/",
        "/api/auth/register-individual/",
        "/api/auth/register-individual-email/",
        "/api/auth/activate-account/",
        "/api/auth/resend-activation/",
        "/api/auth/verify-otp/",
        "/api/auth/token/refresh/",   # correct path
        "/api/auth/refresh/",          # legacy fallback
        "/api/auth/password-forgot/",
        "/api/auth/verify-pass-otp/",
        "/api/auth/reset-password/",
        "/api/auth/health/",
        "/api/auth/plans/",
        "/api/auth/payment/",          # payment init + verify
        "/api/auth/get_profile/",
        "/api/auth/menu/",
        "/api/auth/notifications/",
        "/api/auth/activity/",
        "/api/auth/settings/",
        "/api/auth/permissions/",
        "/api/auth/logo/",
        "/api/auth/subscription/",
        "/api/auth/roles/",            # all role management endpoints
        "/api/orgauth/roles/",
        "/api/orgauth/corporate/register/",
        "/api/orgauth/corporate/create",
        "/api/orgauth/webhooks/",
        "/api/orgauth/billing/",
        "/api/billing/",
        "/api/payments/",
        "/api/support/",
        "/api/internal/",
        "/admin/",
        "/static/",
        "/media/",
        "/health/",
        # Legacy bare paths (Banking/Accounting mount at root)
        "/get_profile/",
        "/menu/",
        "/notifications/",
        "/token/refresh/",
        "/login/",
        "/register/",
        "/health/",
        "/plans/",
        "/webhooks/",
        "/billing/setup/",
        "/billing/pay/",
    ]

    def process_request(self, request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        path = request.path
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return None

        # Only Django superusers bypass billing checks
        if request.user.is_superuser:
            return None

        try:
            corporate_user = CorporateUser.objects.select_related("corporate", "role").get(
                customuser_ptr_id=request.user.id
            )
            
            corporate = corporate_user.corporate

            # Corporate must be active
            if not corporate.is_active:
                return JsonResponse(
                    {
                        "error": "Account not activated",
                        "message": "Your account is not yet active. Please contact support.",
                        "requires_payment": False,
                        "requires_phone": False,
                        "corporate_id": str(corporate.id),
                    },
                    status=402,
                )

            # Check billing service for active trial or subscription
            billing_client = billing_service
            access_check = billing_client.check_access(str(corporate.id))

            if not access_check or not access_check.get("success"):
                logger.warning(
                    "Billing service check failed for corporate %s: %s",
                    corporate.id, (access_check or {}).get("message"),
                )
                # Fail open — don't block if billing service is unreachable
                return None

            # check_access returns has_access at top level
            has_access = access_check.get("has_access", True)

            if not has_access:
                reason = access_check.get("reason", "no_active_subscription")
                return JsonResponse(
                    {
                        "error": "Payment required",
                        "message": access_check.get(
                            "message",
                            "Your trial has expired. Please complete payment to continue.",
                        ),
                        "reason": reason,
                        "requires_payment": True,
                        "requires_phone": False,
                        "corporate_id": str(corporate.id),
                    },
                    status=402,
                )

        except CorporateUser.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Billing middleware error: {str(e)}", exc_info=True)

        return None
