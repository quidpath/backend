from datetime import timedelta
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser
from Payments.models.individual_billing import (
    IndividualPayment,
    IndividualSubscription,
    IndividualSubscriptionPlan,
)
from Payments.services.mpesa_daraja import MpesaDarajaService
from quidpath_backend.core.utils.decorators import require_authenticated
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def list_individual_plans(request):
    try:
        plans = IndividualSubscriptionPlan.objects.filter(is_active=True)
        
        plans_data = []
        for plan in plans:
            plans_data.append({
                "id": str(plan.id),
                "tier": plan.tier,
                "name": plan.name,
                "description": plan.description,
                "monthly_price_kes": float(plan.monthly_price_kes),
                "features": plan.features,
                "max_transactions": plan.max_transactions,
                "max_invoices": plan.max_invoices,
            })
        
        return JsonResponse({
            "success": True,
            "plans": plans_data,
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)


@csrf_exempt
@require_authenticated
def create_individual_subscription(request):
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return JsonResponse({"error": "User not authenticated"}, status=401)
    
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return JsonResponse({"error": "User ID not found"}, status=400)
    
    try:
        user_obj = CustomUser.objects.get(id=user_id)
        
        corporate_user = CorporateUser.objects.filter(customuser_ptr_id=user_id).first()
        if not corporate_user:
            return JsonResponse({
                "error": "Only individual users can subscribe to individual plans"
            }, status=400)
        
        plan_tier = data.get("plan_tier", "starter")
        phone_number = data.get("phone_number")
        
        if not phone_number:
            return JsonResponse({"error": "Phone number is required"}, status=400)
        
        plan = IndividualSubscriptionPlan.objects.filter(tier=plan_tier, is_active=True).first()
        if not plan:
            return JsonResponse({"error": "Invalid plan tier"}, status=400)
        
        active_subscription = IndividualSubscription.objects.filter(
            user=user_obj,
            status="active"
        ).first()
        
        if active_subscription and active_subscription.is_active:
            return JsonResponse({
                "error": "You already have an active subscription"
            }, status=400)
        
        start_date = timezone.now()
        end_date = start_date + timedelta(days=30)
        
        subscription = IndividualSubscription.objects.create(
            user=user_obj,
            plan=plan,
            status="pending",
            start_date=start_date,
            end_date=end_date,
            auto_renew=True,
        )
        
        mpesa_service = MpesaDarajaService()
        payment_result = mpesa_service.initiate_stk_push(
            phone_number=phone_number,
            amount=float(plan.monthly_price_kes),
            account_reference=f"SUB-{subscription.id}",
            transaction_desc=f"Subscription: {plan.name}",
            user_id=str(user_id),
        )
        
        if payment_result.get("success"):
            payment = IndividualPayment.objects.create(
                user=user_obj,
                subscription=subscription,
                amount_kes=plan.monthly_price_kes,
                phone_number=phone_number,
                status="processing",
                mpesa_checkout_request_id=payment_result.get("checkout_request_id"),
                mpesa_merchant_request_id=payment_result.get("merchant_request_id"),
                idempotency_key=payment_result.get("idempotency_key"),
            )
            
            TransactionLogBase.log(
                "INDIVIDUAL_SUBSCRIPTION_CREATED",
                user=user_obj,
                message=f"Individual subscription created for {user_obj.username}, Plan: {plan.name}",
                extra={
                    "subscription_id": str(subscription.id),
                    "plan_tier": plan_tier,
                    "amount": float(plan.monthly_price_kes),
                    "payment_id": str(payment.id),
                },
            )
            
            return JsonResponse({
                "success": True,
                "message": "Payment initiated. Please check your phone for M-Pesa prompt.",
                "subscription_id": str(subscription.id),
                "payment_id": str(payment.id),
                "checkout_request_id": payment_result.get("checkout_request_id"),
            })
        else:
            subscription.delete()
            return JsonResponse({
                "success": False,
                "error": payment_result.get("message", "Failed to initiate payment"),
            }, status=400)
            
    except Exception as e:
        TransactionLogBase.log(
            "INDIVIDUAL_SUBSCRIPTION_CREATION_FAILED",
            user=None,
            message=f"Failed to create individual subscription: {str(e)}",
        )
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_authenticated
def get_individual_subscription_status(request):
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return JsonResponse({"error": "User not authenticated"}, status=401)
    
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return JsonResponse({"error": "User ID not found"}, status=400)
    
    try:
        user_obj = CustomUser.objects.get(id=user_id)
        
        subscription = IndividualSubscription.objects.filter(
            user=user_obj
        ).order_by("-created_at").first()
        
        if not subscription:
            return JsonResponse({
                "success": True,
                "has_subscription": False,
                "message": "No subscription found",
            })
        
        return JsonResponse({
            "success": True,
            "has_subscription": True,
            "subscription": {
                "id": str(subscription.id),
                "plan_name": subscription.plan.name,
                "plan_tier": subscription.plan.tier,
                "status": subscription.status,
                "is_active": subscription.is_active,
                "start_date": subscription.start_date.isoformat(),
                "end_date": subscription.end_date.isoformat(),
                "days_until_expiry": subscription.days_until_expiry,
                "auto_renew": subscription.auto_renew,
                "monthly_price_kes": float(subscription.plan.monthly_price_kes),
            },
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_authenticated
def get_individual_payment_history(request):
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return JsonResponse({"error": "User not authenticated"}, status=401)
    
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return JsonResponse({"error": "User ID not found"}, status=400)
    
    try:
        user_obj = CustomUser.objects.get(id=user_id)
        
        payments = IndividualPayment.objects.filter(user=user_obj).order_by("-created_at")
        
        payments_data = []
        for payment in payments:
            payments_data.append({
                "id": str(payment.id),
                "amount_kes": float(payment.amount_kes),
                "phone_number": payment.phone_number,
                "status": payment.status,
                "mpesa_receipt_number": payment.mpesa_receipt_number,
                "mpesa_transaction_date": payment.mpesa_transaction_date.isoformat() if payment.mpesa_transaction_date else None,
                "created_at": payment.created_at.isoformat(),
                "subscription_plan": payment.subscription.plan.name if payment.subscription else None,
            })
        
        return JsonResponse({
            "success": True,
            "payments": payments_data,
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
