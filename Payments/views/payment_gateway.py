# Payment gateway views (Flutterwave - supports M-Pesa, Card, Mobile Money)
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from Payments.models import RecordPayment, PaymentProvider
from Payments.adapters import FlutterwaveAdapter
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase

logger = logging.getLogger(__name__)


@csrf_exempt
def initiate_mpesa_stk(request):
    """
    Initiate M-Pesa STK Push payment.
    
    POST /api/v1/payments/mpesa/stk-initiate/
    
    Request:
    {
        "org_id": "uuid",
        "invoice_id": "uuid",  # Optional
        "msisdn": "254712345678",
        "amount": 125.00,
        "currency": "USD",  # Will be converted to KES
        "callback_url": "https://app.example.com/api/v1/payments/mpesa/webhook/"
    }
    
    Response:
    {
        "code": 200,
        "message": "STK Push initiated successfully",
        "data": {
            "checkout_request_id": "...",
            "merchant_request_id": "...",
            "timestamp": "..."
        }
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()
    
    try:
        registry = ServiceRegistry()
        
        # Get corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        # Validate required fields
        required_fields = ["msisdn", "amount", "currency"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()
        
        msisdn = data["msisdn"]
        amount = Decimal(str(data["amount"]))
        currency = data["currency"]
        invoice_id = data.get("invoice_id")
        callback_url = data.get("callback_url", "")
        
        # Get payment provider (Flutterwave)
        payment_providers = registry.database(
            model_name="PaymentProvider",
            operation="filter",
            data={"corporate_id": corporate_id, "provider_type": "flutterwave", "is_active": True}
        )
        if not payment_providers:
            return ResponseProvider(message="Flutterwave payment provider not configured", code=400).bad_request()
        
        provider = payment_providers[0]
        provider_config = provider.get("config_json", {})
        provider_config["test_mode"] = provider.get("test_mode", False)
        provider_config["callback_url"] = callback_url or provider_config.get("callback_url", "")
        
        # Add required Flutterwave config fields
        if not provider_config.get("client_id"):
            return ResponseProvider(message="Flutterwave client_id not configured", code=400).bad_request()
        if not provider_config.get("client_secret"):
            return ResponseProvider(message="Flutterwave client_secret not configured", code=400).bad_request()
        if not provider_config.get("encryption_key"):
            return ResponseProvider(message="Flutterwave encryption_key not configured", code=400).bad_request()
        
        # Get invoice if provided
        invoice = None
        customer = None
        if invoice_id:
            invoices = registry.database(
                model_name="Invoices",
                operation="filter",
                data={"id": invoice_id, "corporate_id": corporate_id}
            )
            if invoices:
                invoice = invoices[0]
                # Get customer
                customers = registry.database(
                    model_name="Customer",
                    operation="filter",
                    data={"id": invoice["customer_id"]}
                )
                if customers:
                    customer = customers[0]
        
        # Convert currency to KES if needed
        if currency != "KES":
            # Get exchange rate (simplified - in production, use CBK rate lookup)
            exchange_rate = Decimal("135.0")  # Placeholder - should fetch from CBK API
            amount_kes = amount * exchange_rate
        else:
            exchange_rate = Decimal("1.0")
            amount_kes = amount
        
        # Initialize Flutterwave adapter
        adapter = FlutterwaveAdapter(provider_config)
        
        # Prepare metadata
        metadata_dict = {
            "invoice_id": str(invoice_id) if invoice_id else None,
            "account_reference": invoice.get("number", "QUIDPATH") if invoice else "QUIDPATH",
            "description": f"Payment for invoice {invoice.get('number', '')}" if invoice else "Payment",
            "transaction_reference": f"INV-{invoice_id}" if invoice_id else None
        }
        
        # Initiate M-Pesa STK Push via Flutterwave
        result = adapter.initiate_stk_push(
            msisdn=msisdn,
            amount=float(amount_kes),
            currency="KES",
            account_reference=metadata_dict["account_reference"],
            transaction_desc=metadata_dict["description"],
            callback_url=callback_url
        )
        
        if result.get("status") == "failed" or result.get("response_code") != "0":
            return ResponseProvider(
                message=result.get("customer_message") or result.get("response_description") or "Failed to initiate STK Push",
                code=400
            ).bad_request()
        
        # Create payment record
        with transaction.atomic():
            # Get customer
            if not customer and invoice:
                customers = registry.database(
                    model_name="Customer",
                    operation="filter",
                    data={"id": invoice["customer_id"]}
                )
                if customers:
                    customer = customers[0]
            
            if not customer:
                return ResponseProvider(message="Customer not found", code=400).bad_request()
            
            # Get payment account (default cash account)
            accounts = registry.database(
                model_name="Account",
                operation="filter",
                data={"corporate_id": corporate_id, "name__icontains": "cash"}
            )
            if not accounts:
                # Get any asset account
                accounts = registry.database(
                    model_name="Account",
                    operation="filter",
                    data={"corporate_id": corporate_id}
                )
            
            if not accounts:
                return ResponseProvider(message="Payment account not found", code=400).bad_request()
            
            account_id = accounts[0]["id"]
            
            # Create payment record
            payment_data = {
                "customer_id": customer["id"],
                "corporate_id": corporate_id,
                "invoice_id": invoice_id,
                "amount_received": amount,
                "currency": currency,
                "exchange_rate_to_usd": exchange_rate,
                "payment_date": timezone.now().date(),
                "payment_method": "mpesa",
                "payment_status": "pending",
                "account_id": account_id,
                "provider_reference": result.get("checkout_request_id") or result.get("merchant_request_id") or result.get("provider_reference"),
                "provider_metadata": {
                    "merchant_request_id": result.get("merchant_request_id"),
                    "checkout_request_id": result.get("checkout_request_id"),
                    **result
                },
                "created_by_id": user_id
            }
            
            payment = registry.database(
                model_name="RecordPayment",
                operation="create",
                data=payment_data
            )
            
            # Log transaction
            TransactionLogBase.log(
                transaction_type="MPESA_STK_INITIATED",
                user=user,
                message=f"STK Push initiated for {amount} {currency}",
                state_name="Success",
                extra={"payment_id": payment.get("id"), "provider_reference": result.get("provider_reference")},
                request=request
            )
            
            return ResponseProvider(
                data={
                    "payment_id": payment.get("id"),
                    "checkout_request_id": result.get("checkout_request_id") or result.get("merchant_request_id"),
                    "merchant_request_id": result.get("merchant_request_id"),
                    "timestamp": timezone.now().isoformat(),
                    "message": result.get("customer_message") or result.get("response_description") or "STK Push initiated successfully"
                },
                message="STK Push initiated successfully",
                code=200
            ).success()
            
    except Exception as e:
        logger.exception(f"Error initiating M-Pesa STK Push: {e}")
        TransactionLogBase.log(
            transaction_type="MPESA_STK_INITIATED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while initiating STK Push", code=500).exception()


@csrf_exempt
def mpesa_webhook(request):
    """
    Handle M-Pesa webhook callback.
    
    POST /api/v1/payments/mpesa/webhook/
    
    This endpoint receives callbacks from M-Pesa when payment status changes.
    """
    try:
        # Parse webhook payload
        import json
        payload = json.loads(request.body.decode('utf-8'))
        
        # Get transaction reference from Flutterwave payload
        # Flutterwave M-Pesa webhook uses different structure
        checkout_request_id = payload.get("data", {}).get("flw_ref") or payload.get("data", {}).get("tx_ref") or payload.get("tx_ref")
        
        if not checkout_request_id:
            logger.warning("Flutterwave M-Pesa webhook missing transaction reference")
            return ResponseProvider(message="Invalid webhook payload", code=400).bad_request()
        
        # Find payment by provider_reference
        registry = ServiceRegistry()
        payments = registry.database(
            model_name="RecordPayment",
            operation="filter",
            data={"provider_reference": checkout_request_id}
        )
        
        if not payments:
            logger.warning(f"Flutterwave M-Pesa webhook: Payment not found for {checkout_request_id}")
            return ResponseProvider(message="Payment not found", code=404).bad_request()
        
        payment = payments[0]
        
        # Get payment provider (Flutterwave)
        payment_providers = registry.database(
            model_name="PaymentProvider",
            operation="filter",
            data={"corporate_id": payment["corporate_id"], "provider_type": "flutterwave", "is_active": True}
        )
        if not payment_providers:
            logger.error(f"Flutterwave webhook: Provider not found for corporate {payment['corporate_id']}")
            return ResponseProvider(message="Payment provider not found", code=400).bad_request()
        
        provider = payment_providers[0]
        provider_config = provider.get("config_json", {})
        provider_config["test_mode"] = provider.get("test_mode", False)
        
        # Initialize Flutterwave adapter
        adapter = FlutterwaveAdapter(provider_config)
        
        # Verify webhook signature
        if not adapter.verify_webhook_signature(request.body, dict(request.headers)):
            logger.warning(f"Flutterwave M-Pesa webhook: Invalid signature for {checkout_request_id}")
            return ResponseProvider(message="Invalid webhook signature", code=401).unauthorized()
        
        # Parse webhook (Flutterwave M-Pesa callback)
        webhook_data = adapter.handle_stk_callback(payload, dict(request.headers))
        
        # Update payment status
        with transaction.atomic():
            if webhook_data["status"] == "success":
                # Update payment
                registry.database(
                    model_name="RecordPayment",
                    operation="update",
                    instance_id=payment["id"],
                    data={
                        "payment_status": "success",
                        "confirmed_at": timezone.now(),
                        "provider_metadata": {
                            **payment.get("provider_metadata", {}),
                            **webhook_data.get("metadata", {})
                        }
                    }
                )
                
                # Update invoice if linked
                if payment.get("invoice_id"):
                    # Get invoice
                    invoices = registry.database(
                        model_name="Invoices",
                        operation="filter",
                        data={"id": payment["invoice_id"]}
                    )
                    if invoices:
                        invoice = invoices[0]
                        # Update invoice payment status
                        # TODO: Calculate paid amount and update invoice
                        registry.database(
                            model_name="Invoices",
                            operation="update",
                            instance_id=invoice["id"],
                            data={
                                "payment_status": "paid",
                                "paid_at": timezone.now(),
                                "payment_reference": webhook_data.get("mpesa_receipt_number") or webhook_data.get("checkout_request_id")
                            }
                        )
                
                # Generate receipt PDF (TODO: Implement)
                # receipt_url = generate_receipt_pdf(payment["id"])
                
                # Send receipt email/SMS (TODO: Implement)
                # send_receipt_notification(payment["id"])
                
                logger.info(f"M-Pesa payment confirmed: {checkout_request_id}")
            else:
                # Payment failed
                registry.database(
                    model_name="RecordPayment",
                    operation="update",
                    instance_id=payment["id"],
                    data={
                        "payment_status": "failed",
                        "provider_metadata": {
                            **payment.get("provider_metadata", {}),
                            **webhook_data.get("metadata", {})
                        }
                    }
                )
                logger.warning(f"M-Pesa payment failed: {checkout_request_id}")
        
        # Return 200 OK to acknowledge receipt
        return ResponseProvider(
            message="Webhook received successfully",
            code=200
        ).success()
        
    except Exception as e:
        logger.exception(f"Error processing M-Pesa webhook: {e}")
        # Still return 200 to prevent retries
        return ResponseProvider(message="Webhook processed", code=200).success()

