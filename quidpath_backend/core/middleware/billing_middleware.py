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
        "/api/auth/refresh/",
        "/api/auth/password-forgot/",
        "/api/auth/verify-pass-otp/",
        "/api/auth/reset-password/",
        "/api/auth/health/",
        "/api/auth/plans/",
        "/api/auth/subscription/initiate-payment/",
        "/api/auth/subscription/status/",
        "/api/orgauth/roles/",
        "/api/billing/",
        "/api/payments/",
        "/api/orgauth/webhooks/",
        "/admin/",
        "/static/",
        "/media/",
        # Direct paths (no prefix)
        "/login/",
        "/register/",
        "/register-individual/",
        "/register-individual-email/",
        "/activate-account/",
        "/resend-activation/",
        "/verify-otp/",
        "/token/refresh/",
        "/password-forgot/",
        "/verify-pass-otp/",
        "/reset-password/",
        "/health/",
        "/plans/",
        "/payments/initiate/",
        "/subscription/status/",
        "/corporate/create",
        "/webhooks/",
        "/billing/setup/",
        "/billing/pay/",
        # Profile endpoint — must be accessible so AuthGuard can load user data
        "/get_profile/",
        "/menu/",
        # Notifications — must not block authenticated users
        "/notifications/",
    ]

    def process_request(self, request):
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        path = request.path
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return None

        # Allow superusers and SUPERADMIN role to bypass all billing checks
        if request.user.is_superuser:
            return None

        try:
            corporate_user = CorporateUser.objects.select_related("corporate", "role").get(
                customuser_ptr_id=request.user.id
            )
            
            # Allow SUPERADMIN role to bypass billing checks
            if corporate_user.role and corporate_user.role.name == "SUPERADMIN":
                return None
            
            corporate = corporate_user.corporate

            if not corporate.is_active:
                return JsonResponse(
                    {
                        "error": "Payment required",
                        "message": "Please complete your subscription payment to access the system.",
                        "requires_payment": True,
                        "corporate_id": str(corporate.id),
                    },
                    status=402,
                )

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
                            "Your subscription has expired. Please complete payment to continue.",
                        ),
                        "reason": reason,
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
