"""
Billing setup view for organisations.
After approval, the org admin enters their M-Pesa number here to start the 14-day trial.
After the trial, an STK push is sent automatically via process_trial_expirations command.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.rate_limit import rate_limit
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="billing_setup")
def setup_org_billing(request):
    """
    Called when an approved organisation enters their billing details (M-Pesa number).
    - Validates the corporate is approved
    - Saves the phone number
    - Activates the corporate (starts the 14-day trial)
    - Returns trial end date
    """
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate_id")
    phone_number = data.get("phone_number")

    if not corporate_id or not phone_number:
        return JsonResponse({"error": "corporate_id and phone_number are required"}, status=400)

    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except Corporate.DoesNotExist:
        return JsonResponse({"error": "Organisation not found"}, status=404)

    if not corporate.is_approved:
        return JsonResponse(
            {"error": "Organisation has not been approved yet. Please wait for admin approval."},
            status=403,
        )

    if corporate.is_active:
        # Already active — check trial status via billing service
        try:
            from quidpath_backend.core.Services.billing_service import billing_service as bs
            trial_status = bs.get_trial_status(str(corporate.id))
            if trial_status and trial_status.get("success"):
                trial = trial_status.get("data", {}).get("trial") or {}
                return JsonResponse({
                    "message": "Billing already set up.",
                    "status": trial.get("status"),
                    "trial_end_date": trial.get("end_date"),
                })
        except Exception:
            pass
        return JsonResponse({"message": "Organisation is already active."})

    # Save phone number and activate corporate
    corporate.phone = phone_number
    corporate.is_active = True
    corporate.save(update_fields=["phone", "is_active"])

    # Ensure billing service has a trial record (idempotent — safe to call again)
    try:
        from quidpath_backend.core.Services.billing_service import billing_service as bs
        bs.create_trial(
            corporate_id=str(corporate.id),
            corporate_name=corporate.name,
            plan_tier="starter",
        )
    except Exception as e:
        logger.warning(f"Billing service trial ensure failed for {corporate.name}: {e}")

    # Get trial end date from billing service
    trial_end_date = None
    try:
        from quidpath_backend.core.Services.billing_service import billing_service as bs
        trial_status = bs.get_trial_status(str(corporate.id))
        if trial_status and trial_status.get("success"):
            trial = trial_status.get("data", {}).get("trial") or {}
            trial_end_date = trial.get("end_date")
    except Exception as e:
        logger.warning(f"Could not fetch trial status for {corporate.name}: {e}")

    TransactionLogBase.log(
        "ORG_BILLING_SETUP",
        user=None,
        message=f"Organisation {corporate.name} entered billing details and started trial",
        extra={"corporate_id": str(corporate.id), "phone": phone_number},
    )

    return JsonResponse({
        "message": "Billing set up successfully. Your 14-day free trial has started.",
        "corporate_id": str(corporate.id),
        "trial_end_date": trial_end_date,
        "phone_number": phone_number,
    })


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="org_pay")
def initiate_org_payment(request):
    """
    Initiate M-Pesa STK push for an organisation subscription payment.
    Used both after trial expiry and for manual payment.
    """
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate_id")
    phone_number = data.get("phone_number")
    plan_tier = data.get("plan_tier", "basic")

    if not corporate_id or not phone_number:
        return JsonResponse({"error": "corporate_id and phone_number are required"}, status=400)

    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except Corporate.DoesNotExist:
        return JsonResponse({"error": "Organisation not found"}, status=404)

    try:
        from quidpath_backend.core.Services.billing_service import billing_service

        result = billing_service.initiate_payment(
            entity_id=str(corporate.id),
            entity_name=corporate.name,
            plan_id=plan_tier,
            phone_number=phone_number,
            payment_type="organization",
        )

        if result and result.get("success"):
            TransactionLogBase.log(
                "ORG_PAYMENT_INITIATED",
                user=None,
                message=f"STK push initiated for {corporate.name}",
                extra={"corporate_id": str(corporate.id), "plan_tier": plan_tier},
            )
            return JsonResponse({
                "message": "Payment request sent to your phone. Please enter your M-Pesa PIN to complete.",
                "payment_id": result.get("payment_id"),
                "corporate_id": str(corporate.id),
            })
        else:
            return JsonResponse(
                {"error": (result or {}).get("message", "Payment initiation failed")},
                status=400,
            )

    except Exception as e:
        logger.error(f"Payment initiation error for {corporate.name}: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
