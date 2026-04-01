"""
Corporate registration with custom payment page - V2
Payment verification happens on custom frontend page, then backend creates corporate
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

logger = logging.getLogger(__name__)


@csrf_exempt
def initiate_corporate_registration(request):
    """
    Step 1: Store corporate data and return registration ID
    No payment initiated yet - that happens on custom payment page
    """
    from quidpath_backend.core.utils.request_parser import get_data
    data, metadata = get_data(request)
    
    try:
        required_fields = ['name', 'email', 'phone', 'address', 'city', 'country']
        missing_fields = [f for f in required_fields if not data.get(f)]
        
        if missing_fields:
            return JsonResponse({
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }, status=400)
        
        corporate_name = data.get("name")
        email = data.get("email")
        
        if Corporate.objects.filter(name=corporate_name).exists():
            return JsonResponse({
                "error": f"An organization with the name '{corporate_name}' already exists."
            }, status=400)
        
        if Corporate.objects.filter(email=email).exists():
            return JsonResponse({
                "error": f"An organization with the email '{email}' already exists."
            }, status=400)
        
        registration_id = str(uuid.uuid4())
        cache_key = f"corporate_reg_{registration_id}"
        cache.set(cache_key, data, timeout=7200)
        
        TransactionLogBase.log(
            "CORPORATE_REGISTRATION_INITIATED",
            user=None,
            message=f"Registration initiated: {corporate_name}",
            request=request,
        )
        
        return JsonResponse({
            "success": True,
            "registration_id": registration_id,
            "email": email,
            "corporate_name": corporate_name,
            "message": "Registration data saved. Please complete payment verification."
        })
    
    except Exception as e:
        logger.error(f"Error initiating registration: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def verify_corporate_payment_v2(request):
    """
    Step 2: Verify payment and CREATE corporate record
    Called after successful payment on custom payment page
    """
    from quidpath_backend.core.utils.request_parser import get_data
    data, metadata = get_data(request)
    
    try:
        registration_id = data.get("registration_id")
        payment_reference = data.get("reference")
        
        if not registration_id or not payment_reference:
            return JsonResponse({"error": "Registration ID and payment reference required"}, status=400)
        
        # Verify with Paystack directly
        import requests
        
        secret_key = os.environ.get("PAYSTACK_SECRET_KEY", "")
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{payment_reference}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            return JsonResponse({"error": "Payment verification failed"}, status=400)
        
        response_data = response.json()
        if not response_data.get("status") or response_data.get("data", {}).get("status") != "success":
            return JsonResponse({"error": "Payment was not successful"}, status=400)
        
        # Get corporate data from cache
        cache_key = f"corporate_reg_{registration_id}"
        corporate_data = cache.get(cache_key)
        
        if not corporate_data:
            return JsonResponse({"error": "Registration data expired. Please start again."}, status=400)
        
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
        from quidpath_backend.core.utils.registry import ServiceRegistry
        corporate = ServiceRegistry().database("corporate", "create", data=filtered_data)
        
        corporate_id = corporate.get("id") if isinstance(corporate, dict) else corporate.id
        corporate_name = corporate.get("name") if isinstance(corporate, dict) else corporate.name
        corporate_email = corporate.get("email") if isinstance(corporate, dict) else corporate.email
        
        # Clear cache
        cache.delete(cache_key)
        
        # Create 30-day trial in billing service
        try:
            from quidpath_backend.core.Services.billing_service import BillingServiceClient
            
            billing_client = BillingServiceClient()
            billing_client.create_trial(
                corporate_id=str(corporate_id),
                corporate_name=corporate_name,
                plan_tier="starter",
            )
            logger.info(f"Trial created for corporate: {corporate_name}")
        except Exception as e:
            logger.warning(f"Failed to create trial: {e}")
        
        # Log creation
        TransactionLogBase.log(
            "CORPORATE_CREATED_AFTER_PAYMENT",
            user=None,
            message=f"Corporate created: {corporate_name}",
            request=request,
        )
        
        # Send pending approval email
        notification_service = NotificationServiceHandler()
        
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
                    <li>You'll get a 30-day free trial once approved</li>
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
        })
    
    except Exception as e:
        logger.error(f"Error verifying payment: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
