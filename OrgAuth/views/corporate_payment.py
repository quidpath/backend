"""
Corporate registration with Paystack payment - COMPLETE IMPLEMENTATION
Payment MUST be successful before corporate record is created in database.
"""
import json
import logging
import os
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase, logger
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


@csrf_exempt
def initiate_corporate_payment(request):
    """
    Step 1: Validate data and initiate Paystack payment (KES 1 card verification)
    Corporate is NOT created yet - only after successful payment
    """
    data, metadata = get_clean_data(request)
    
    try:
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'address', 'city', 'country']
        missing_fields = [f for f in required_fields if not data.get(f)]
        
        if missing_fields:
            return JsonResponse({
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }, status=400)
        
        corporate_name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        
        # Check if corporate already exists
        if Corporate.objects.filter(name=corporate_name).exists():
            return JsonResponse({
                "error": f"An organization with the name '{corporate_name}' already exists."
            }, status=400)
        
        if Corporate.objects.filter(email=email).exists():
            return JsonResponse({
                "error": f"An organization with the email '{email}' already exists."
            }, status=400)
        
        # Generate unique registration ID
        registration_id = str(uuid.uuid4())
        
        # Store corporate data in cache (expires in 2 hours)
        cache_key = f"corporate_reg_{registration_id}"
        cache.set(cache_key, data, timeout=7200)
        
        # Initialize Paystack payment
        from billing_service.billing.services.paystack_service import PaystackService
        
        paystack = PaystackService()
        frontend_url = os.environ.get("FRONTEND_URL", "https://stage.quidpath.com")
        callback_url = f"{frontend_url}/signup/corporate/verify?reg_id={registration_id}"
        
        payment_result = paystack.initialize_transaction(
            amount=Decimal("1.00"),  # KES 1 for card verification
            email=email,
            currency="KES",
            callback_url=callback_url,
            metadata={
                "type": "corporate_registration",
                "registration_id": registration_id,
                "corporate_name": corporate_name,
                "email": email,
                "phone": phone,
            },
            channels=["card"]
        )
        
        if payment_result.get("success"):
            cache.set(f"pay_ref_{registration_id}", payment_result.get("reference"), timeout=7200)
            
            TransactionLogBase.log(
                "CORPORATE_PAYMENT_INITIATED",
                user=None,
                message=f"Payment initiated: {corporate_name}",
                request=request,
            )
            
            return JsonResponse({
                "success": True,
                "registration_id": registration_id,
                "payment_reference": payment_result.get("reference"),
                "authorization_url": payment_result.get("authorization_url"),
                "message": "Please complete payment to continue"
            })
        else:
            return JsonResponse({
                "error": payment_result.get("message", "Payment initiation failed")
            }, status=400)
    
    except Exception as e:
        logger.error(f"Error initiating payment: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def verify_corporate_payment(request):
    """
    Step 2: Verify payment and CREATE corporate record
    Only called after successful payment
    """
    data, metadata = get_clean_data(request)
    
    try:
        registration_id = data.get("registration_id") or data.get("reg_id")
        payment_reference = data.get("reference")
        
        if not registration_id:
            return JsonResponse({"error": "Registration ID required"}, status=400)
        
        if not payment_reference:
            payment_reference = cache.get(f"pay_ref_{registration_id}")
        
        if not payment_reference:
            return JsonResponse({"error": "Payment reference not found"}, status=400)
        
        # Verify with Paystack
        from billing_service.billing.services.paystack_service import PaystackService
        
        paystack = PaystackService()
        result = paystack.verify_transaction(payment_reference)
        
        if not result.get("success") or result.get("status") != "success":
            return JsonResponse({
                "error": f"Payment not successful: {result.get('status', 'failed')}"
            }, status=400)
        
        # Get corporate data from cache
        cache_key = f"corporate_reg_{registration_id}"
        corporate_data = cache.get(cache_key)
        
        if not corporate_data:
            return JsonResponse({"error": "Registration data expired"}, status=400)
        
        # Extract card info
        auth = result.get("authorization", {})
        card_last4 = auth.get("last4", "")
        card_brand = auth.get("brand", "")
        auth_code = auth.get("authorization_code", "")
        
        # Filter valid fields
        valid_fields = {
            'name', 'industry', 'company_size', 'message', 'registration_number',
            'tax_id', 'description', 'website', 'logo', 'address', 'city', 'state',
            'country', 'zip_code', 'phone', 'email'
        }
        filtered_data = {k: v for k, v in corporate_data.items() if k in valid_fields}
        
        # Set status - pending approval
        filtered_data['is_approved'] = False
        filtered_data['is_active'] = False
        filtered_data['is_seen'] = False
        
        # CREATE CORPORATE NOW
        corporate = ServiceRegistry().database("corporate", "create", data=filtered_data)
        
        corporate_id = corporate.get("id") if isinstance(corporate, dict) else corporate.id
        corporate_name = corporate.get("name") if isinstance(corporate, dict) else corporate.name
        corporate_email = corporate.get("email") if isinstance(corporate, dict) else corporate.email
        
        # Clear cache
        cache.delete(cache_key)
        cache.delete(f"pay_ref_{registration_id}")
        
        # Log creation
        TransactionLogBase.log(
            "CORPORATE_CREATED_AFTER_PAYMENT",
            user=None,
            message=f"Corporate created: {corporate_name}",
            request=request,
        )
        
        # Send pending approval email
        notification_service = NotificationServiceHandler()
        
        # Create simple HTML email
        email_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Application Received</h2>
                <p>Dear {corporate_name},</p>
                <p>Thank you for registering with Quidpath! Your application has been received and is currently being reviewed by our team.</p>
                <p><strong>What happens next?</strong></p>
                <ul>
                    <li>Our team will review your application within 24-48 hours</li>
                    <li>You will receive an email with your login credentials once approved</li>
                    <li>Your card has been verified and saved securely</li>
                </ul>
                <p>If you have any questions, please don't hesitate to contact our support team.</p>
                <p>Best regards,<br>The Quidpath Team</p>
            </div>
        </body>
        </html>
        """
        
        notification_service.send_notification([{
            "message_type": "2",
            "organisation_id": corporate_id,
            "destination": corporate_email,
            "message": email_message,
        }])
        
        return JsonResponse({
            "success": True,
            "message": "Registration successful! Your application is being reviewed.",
            "corporate_id": str(corporate_id),
            "status": "pending_approval",
            "card_last4": card_last4,
            "card_brand": card_brand,
        })
    
    except Exception as e:
        logger.error(f"Error verifying payment: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def check_payment_status(request):
    """
    Check payment status - for frontend polling
    """
    data, metadata = get_clean_data(request)
    registration_id = data.get("registration_id") or data.get("reg_id")
    
    if not registration_id:
        return JsonResponse({"error": "Registration ID required"}, status=400)
    
    try:
        payment_reference = cache.get(f"pay_ref_{registration_id}")
        
        if not payment_reference:
            return JsonResponse({"status": "pending", "message": "Waiting for payment..."})
        
        from billing_service.billing.services.paystack_service import PaystackService
        
        paystack = PaystackService()
        result = paystack.verify_transaction(payment_reference)
        
        if not result.get("success"):
            return JsonResponse({"status": "error", "message": result.get("message")})
        
        status = result.get("status")
        
        if status == "success":
            return JsonResponse({
                "status": "completed",
                "message": "Payment successful!"
            })
        elif status == "failed":
            return JsonResponse({
                "status": "failed",
                "message": "Payment failed"
            })
        else:
            return JsonResponse({
                "status": "pending",
                "message": "Processing..."
            })
    
    except Exception as e:
        logger.error(f"Error checking status: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
