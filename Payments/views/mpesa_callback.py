import json
import logging
from datetime import timedelta

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from OrgAuth.models import Corporate
from Payments.models.individual_billing import IndividualPayment, IndividualSubscription
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data_safe

logger = logging.getLogger(__name__)


@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return ResponseProvider.method_not_allowed(["POST"])
    data, err = get_clean_data_safe(request, allowed_methods=["POST"], require_json_body=True)
    if err is not None:
        return err
    payload = data
    try:
        
        TransactionLogBase.log(
            "MPESA_CALLBACK_RECEIVED",
            user=None,
            message="M-Pesa callback received",
            extra={"payload": payload},
        )
        
        body = payload.get("Body", {})
        stk_callback = body.get("stkCallback", {})
        
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")
        merchant_request_id = stk_callback.get("MerchantRequestID")
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        
        payment = IndividualPayment.objects.filter(
            mpesa_checkout_request_id=checkout_request_id
        ).first()
        
        if not payment:
            logger.warning("Payment not found for CheckoutRequestID: %s", checkout_request_id)
            return ResponseProvider.raw_response({"ResultCode": 0, "ResultDesc": "Accepted"})
        
        if result_code == 0:
            callback_metadata = stk_callback.get("CallbackMetadata", {})
            items = callback_metadata.get("Item", [])
            
            mpesa_receipt_number = None
            transaction_date = None
            phone_number = None
            amount = None
            
            for item in items:
                name = item.get("Name")
                value = item.get("Value")
                
                if name == "MpesaReceiptNumber":
                    mpesa_receipt_number = value
                elif name == "TransactionDate":
                    transaction_date = value
                elif name == "PhoneNumber":
                    phone_number = value
                elif name == "Amount":
                    amount = value
            
            if transaction_date:
                try:
                    from datetime import datetime
                    transaction_date = datetime.strptime(str(transaction_date), "%Y%m%d%H%M%S")
                    transaction_date = timezone.make_aware(transaction_date)
                except Exception as e:
                    logger.error(f"Failed to parse transaction date: {e}")
                    transaction_date = timezone.now()
            
            if payment.status == "success":
                TransactionLogBase.log(
                    "MPESA_DUPLICATE_CALLBACK",
                    user=payment.user,
                    message=f"Duplicate callback for payment {payment.id}. Idempotency key: {payment.idempotency_key}",
                    extra={
                        "payment_id": str(payment.id),
                        "idempotency_key": payment.idempotency_key,
                        "mpesa_receipt_number": mpesa_receipt_number,
                    },
                )
                return ResponseProvider.raw_response({
                    "ResultCode": 0,
                    "ResultDesc": "Accepted (Duplicate)",
                })
            
            payment.status = "success"
            payment.mpesa_receipt_number = mpesa_receipt_number
            payment.mpesa_transaction_date = transaction_date
            payment.metadata = {
                "result_desc": result_desc,
                "phone_number": phone_number,
                "amount": amount,
            }
            payment.save()
            
            if payment.subscription:
                subscription = payment.subscription
                subscription.status = "active"
                subscription.save()
                
                corporate = subscription.user.corporateuser.corporate
                corporate.is_active = True
                corporate.is_verified = True
                corporate.save()
                
                TransactionLogBase.log(
                    "INDIVIDUAL_SUBSCRIPTION_ACTIVATED",
                    user=payment.user,
                    message=f"Individual subscription activated for {payment.user.username}",
                    extra={
                        "subscription_id": str(subscription.id),
                        "payment_id": str(payment.id),
                        "mpesa_receipt_number": mpesa_receipt_number,
                        "amount": float(payment.amount_kes),
                    },
                )
                
                NotificationServiceHandler().send_notification([
                    {
                        "message_type": "2",
                        "organisation_id": str(corporate.id),
                        "destination": payment.user.email,
                        "message": f"""
                        <h3>Payment Successful!</h3>
                        <p>Hello {payment.user.username},</p>
                        <p>Your payment of KES {payment.amount_kes} has been received successfully.</p>
                        <p>M-Pesa Receipt: <b>{mpesa_receipt_number}</b></p>
                        <p>Your subscription is now active. You can now access all features.</p>
                        <p>Thank you for choosing Quidpath!</p>
                    """,
                    }
                ])
            
            TransactionLogBase.log(
                "MPESA_PAYMENT_SUCCESS",
                user=payment.user,
                message=f"Payment successful. Receipt: {mpesa_receipt_number}",
                extra={
                    "payment_id": str(payment.id),
                    "mpesa_receipt_number": mpesa_receipt_number,
                    "amount": float(payment.amount_kes),
                    "idempotency_key": payment.idempotency_key,
                },
            )
            
        else:
            payment.status = "failed"
            payment.metadata = {
                "result_code": result_code,
                "result_desc": result_desc,
            }
            payment.save()
            
            if payment.subscription:
                payment.subscription.status = "cancelled"
                payment.subscription.save()
            
            TransactionLogBase.log(
                "MPESA_PAYMENT_FAILED",
                user=payment.user,
                message=f"Payment failed. Reason: {result_desc}",
                extra={
                    "payment_id": str(payment.id),
                    "result_code": result_code,
                    "result_desc": result_desc,
                    "idempotency_key": payment.idempotency_key,
                },
            )
            
            NotificationServiceHandler().send_notification([
                {
                    "message_type": "2",
                    "organisation_id": str(payment.user.corporateuser.corporate.id) if hasattr(payment.user, 'corporateuser') else None,
                    "destination": payment.user.email,
                    "message": f"""
                    <h3>Payment Failed</h3>
                    <p>Hello {payment.user.username},</p>
                    <p>Your payment of KES {payment.amount_kes} could not be processed.</p>
                    <p>Reason: {result_desc}</p>
                    <p>Please try again or contact support if the issue persists.</p>
                """,
                }
            ])
        
        return ResponseProvider.raw_response({"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as e:
        logger.exception("M-Pesa callback error: %s", e)
        TransactionLogBase.log(
            "MPESA_CALLBACK_ERROR",
            user=None,
            message="M-Pesa callback processing error: %s" % str(e),
        )
        return ResponseProvider.raw_response(
            {"ResultCode": 1, "ResultDesc": "Error processing callback"}, status=500
        )
