# Card gateway views (Flutterwave)
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging
import json

from Payments.models import RecordPayment, PaymentProvider
from Payments.adapters import FlutterwaveAdapter
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase

logger = logging.getLogger(__name__)


@csrf_exempt
def initiate_card_payment(request):
    """
    Initiate card payment.
    
    POST /api/v1/payments/card/initiate/
    
    Request:
    {
        "org_id": "uuid",
        "invoice_id": "uuid",  # Optional
        "email": "customer@example.com",
        "amount": 125.00,
        "currency": "USD",
        "callback_url": "https://app.example.com/api/v1/payments/card/webhook/",
        "provider_type": "flutterwave"  # or "interswitch", "pesapal"
    }
    
    Response:
    {
        "code": 200,
        "message": "Payment initiated successfully",
        "data": {
            "payment_id": "uuid",
            "checkout_url": "https://...",
            "provider_reference": "..."
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
        required_fields = ["email", "amount", "currency"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()
        
        email = data["email"]
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
        
        # Get exchange rate if needed
        exchange_rate = Decimal("1.0")
        if currency != "USD":
            # TODO: Get exchange rate from CBK API
            exchange_rate = Decimal("135.0")  # Placeholder
        
        # Initialize Flutterwave adapter
        adapter = FlutterwaveAdapter(provider_config)
        
        # Prepare metadata
        import uuid
        transaction_ref = f"TXN-{uuid.uuid4().hex[:12]}"
        metadata_dict = {
            "invoice_id": str(invoice_id) if invoice_id else None,
            "transaction_reference": transaction_ref,
            "customer_name": customer.get("company_name", f"{customer.get('first_name', '')} {customer.get('last_name', '')}") if customer else email,
            "description": f"Payment for invoice {invoice.get('number', '')}" if invoice else "Payment",
            "phone_number": customer.get("phone", "") if customer else ""
        }
        
        # Initiate card payment via Flutterwave
        result = adapter.initiate_card_payment(
            amount=float(amount),
            currency=currency,
            customer_email=email,
            callback_url=callback_url,
            metadata=metadata_dict
        )
        
        if result["status"] == "failed":
            return ResponseProvider(
                message=result.get("message", "Failed to initiate payment"),
                code=400
            ).bad_request()
        
        # Create payment record
        with transaction.atomic():
            # Get customer
            if not customer:
                # Try to find customer by email
                customers = registry.database(
                    model_name="Customer",
                    operation="filter",
                    data={"corporate_id": corporate_id, "email": email}
                )
                if customers:
                    customer = customers[0]
            
            if not customer:
                return ResponseProvider(message="Customer not found", code=400).bad_request()
            
            # Get payment account
            accounts = registry.database(
                model_name="Account",
                operation="filter",
                data={"corporate_id": corporate_id, "name__icontains": "cash"}
            )
            if not accounts:
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
                "payment_method": "card",
                "payment_status": "pending",
                "account_id": account_id,
                "provider_reference": result.get("provider_reference"),
                "provider_metadata": {
                    "checkout_url": result.get("checkout_url"),
                    "provider_type": provider_type,
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
                transaction_type="CARD_PAYMENT_INITIATED",
                user=user,
                message=f"Card payment initiated for {amount} {currency}",
                state_name="Success",
                extra={"payment_id": payment.get("id"), "provider_reference": result.get("provider_reference")},
                request=request
            )
            
            return ResponseProvider(
                data={
                    "payment_id": payment.get("id"),
                    "checkout_url": result.get("redirect_url") or result.get("checkout_url"),
                    "provider_reference": result.get("transaction_reference") or result.get("transaction_id"),
                    "message": result.get("message") or "Payment initiated successfully"
                },
                message="Payment initiated successfully",
                code=200
            ).success()
            
    except Exception as e:
        logger.exception(f"Error initiating card payment: {e}")
        TransactionLogBase.log(
            transaction_type="CARD_PAYMENT_INITIATED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while initiating payment", code=500).exception()


@csrf_exempt
def card_webhook(request):
    """
    Handle card gateway webhook callback.
    
    POST /api/v1/payments/card/webhook/
    
    This endpoint receives callbacks from card gateways when payment status changes.
    """
    try:
        # Parse webhook payload
        payload = json.loads(request.body.decode('utf-8'))
        headers = dict(request.headers)
        
        # Get provider reference from payload (Flutterwave uses tx_ref)
        provider_reference = payload.get("data", {}).get("tx_ref") or payload.get("tx_ref")
        
        if not provider_reference:
            logger.warning("Flutterwave webhook missing tx_ref")
            return ResponseProvider(message="Invalid webhook payload", code=400).bad_request()
        
        # Find payment by provider_reference
        registry = ServiceRegistry()
        payments = registry.database(
            model_name="RecordPayment",
            operation="filter",
            data={"provider_reference": provider_reference}
        )
        
        if not payments:
            logger.warning(f"Flutterwave webhook: Payment not found for {provider_reference}")
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
        try:
            if not adapter.verify_webhook_signature(request.body, headers):
                logger.warning(f"Flutterwave webhook: Invalid signature for {provider_reference}")
                return ResponseProvider(message="Invalid webhook signature", code=401).unauthorized()
        except Exception as e:
            logger.warning(f"Flutterwave webhook signature verification error: {e}")
            # Continue processing if verification fails (for development)
        
        # Parse webhook
        webhook_data = adapter.handle_card_webhook(payload, headers)
        
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
                    invoices = registry.database(
                        model_name="Invoices",
                        operation="filter",
                        data={"id": payment["invoice_id"]}
                    )
                    if invoices:
                        invoice = invoices[0]
                        # Update invoice payment status
                        registry.database(
                            model_name="Invoices",
                            operation="update",
                            instance_id=invoice["id"],
                            data={
                                "payment_status": "paid",
                                "paid_at": timezone.now(),
                                "payment_reference": webhook_data.get("gateway_transaction_id") or provider_reference
                            }
                        )
                
                # Generate receipt PDF (TODO: Implement)
                # receipt_url = generate_receipt_pdf(payment["id"])
                
                # Send receipt email/SMS (TODO: Implement)
                # send_receipt_notification(payment["id"])
                
                logger.info(f"Card payment confirmed: {provider_reference}")
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
                logger.warning(f"Card payment failed: {provider_reference}")
        
        # Return 200 OK to acknowledge receipt
        return ResponseProvider(
            message="Webhook received successfully",
            code=200
        ).success()
        
    except Exception as e:
        logger.exception(f"Error processing card gateway webhook: {e}")
        # Still return 200 to prevent retries
        return ResponseProvider(message="Webhook processed", code=200).success()

