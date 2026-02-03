# Organization billing views
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Payments.adapters.flutterwave import FlutterwaveAdapter
from Payments.models.organization_billing import (OrganizationInvoice,
                                                  OrganizationPayment,
                                                  OrganizationSubscription)
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def list_organization_invoices(request):
    """List organization billing invoices."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Build filter
        filter_kwargs = {"corporate_id": corporate_id}
        if data.get("status"):
            filter_kwargs["status"] = data.get("status")

        invoices = OrganizationInvoice.objects.filter(**filter_kwargs).order_by(
            "-created_at"
        )[:50]

        # Serialize invoices
        invoices_data = []
        for invoice in invoices:
            invoices_data.append(
                {
                    "id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "status": invoice.status,
                    "subtotal_usd": float(invoice.subtotal_usd),
                    "tax_usd": float(invoice.tax_usd),
                    "total_usd": float(invoice.total_usd),
                    "currency": invoice.currency,
                    "exchange_rate_to_usd": float(invoice.exchange_rate_to_usd),
                    "billing_period_start": (
                        invoice.billing_period_start.isoformat()
                        if invoice.billing_period_start
                        else None
                    ),
                    "billing_period_end": (
                        invoice.billing_period_end.isoformat()
                        if invoice.billing_period_end
                        else None
                    ),
                    "due_date": (
                        invoice.due_date.isoformat() if invoice.due_date else None
                    ),
                    "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
                    "payment_reference": invoice.payment_reference,
                    "created_at": (
                        invoice.created_at.isoformat() if invoice.created_at else None
                    ),
                }
            )

        return ResponseProvider(
            data={"invoices": invoices_data},
            message="Invoices retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error listing organization invoices: {e}")
        return ResponseProvider(
            message=f"Error listing invoices: {str(e)}", code=500
        ).exception()


@csrf_exempt
def list_organization_payments(request):
    """List organization payments."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Build filter
        filter_kwargs = {"corporate_id": corporate_id}
        if data.get("status"):
            filter_kwargs["status"] = data.get("status")

        payments = OrganizationPayment.objects.filter(**filter_kwargs).order_by(
            "-created_at"
        )[:50]

        # Serialize payments
        payments_data = []
        for payment in payments:
            payments_data.append(
                {
                    "id": str(payment.id),
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "exchange_rate_to_usd": float(payment.exchange_rate_to_usd),
                    "payment_method": payment.payment_method,
                    "status": payment.status,
                    "provider": payment.provider,
                    "provider_reference": payment.provider_reference,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    "invoice_id": str(payment.invoice.id) if payment.invoice else None,
                    "invoice_number": (
                        payment.invoice.invoice_number if payment.invoice else None
                    ),
                    "created_at": (
                        payment.created_at.isoformat() if payment.created_at else None
                    ),
                }
            )

        return ResponseProvider(
            data={"payments": payments_data},
            message="Payments retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error listing organization payments: {e}")
        return ResponseProvider(
            message=f"Error listing payments: {str(e)}", code=500
        ).exception()


@csrf_exempt
def initiate_organization_payment(request):
    """Initiate payment for organization billing invoice."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        corporate = registry.database("Corporate", "get", data={"id": corporate_id})

        # Get invoice
        invoice_id = data.get("invoice_id")
        if not invoice_id:
            return ResponseProvider(
                message="Invoice ID is required", code=400
            ).bad_request()

        invoice = OrganizationInvoice.objects.filter(
            id=invoice_id, corporate_id=corporate_id
        ).first()
        if not invoice:
            return ResponseProvider(message="Invoice not found", code=404).bad_request()

        if invoice.status == "paid":
            return ResponseProvider(
                message="Invoice already paid", code=400
            ).bad_request()

        # Get payment provider (Flutterwave)
        payment_providers = registry.database(
            model_name="PaymentProvider",
            operation="filter",
            data={
                "corporate_id": corporate_id,
                "provider_type": "flutterwave",
                "is_active": True,
            },
        )
        if not payment_providers:
            return ResponseProvider(
                message="Flutterwave payment provider not configured", code=400
            ).bad_request()

        provider = payment_providers[0]
        provider_config = provider.get("config_json", {})
        provider_config["test_mode"] = provider.get("test_mode", False)

        # Get payment method and details
        payment_method = data.get("payment_method", "card")  # card, mpesa, etc.
        invoice_amount = float(invoice.total_usd)
        invoice_currency = invoice.currency or "USD"

        # Convert to KES if needed for M-Pesa
        if payment_method == "mpesa":
            # M-Pesa requires KES, so convert from USD if needed
            if invoice_currency == "USD":
                # Use exchange rate to convert USD to KES (assuming 1 USD = exchange_rate_to_usd KES)
                # If exchange_rate_to_usd is for KES, then KES amount = USD * exchange_rate_to_usd
                amount_kes = float(invoice_amount * invoice.exchange_rate_to_usd)
            else:
                amount_kes = float(invoice_amount)
            payment_amount = Decimal(str(amount_kes))
            payment_currency = "KES"
        else:
            # For card payments, use original currency
            payment_amount = Decimal(str(invoice_amount))
            payment_currency = invoice_currency

        # Create payment record
        payment = OrganizationPayment.objects.create(
            corporate_id=corporate_id,
            invoice=invoice,
            amount=payment_amount,
            currency=payment_currency,
            exchange_rate_to_usd=invoice.exchange_rate_to_usd,
            payment_method=payment_method,
            status="pending",
            provider="flutterwave",
            metadata={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
            },
        )

        # Initialize Flutterwave adapter
        adapter = FlutterwaveAdapter(provider_config)

        # Initiate payment based on method
        if payment_method == "mpesa":
            msisdn = data.get("msisdn")
            if not msisdn:
                return ResponseProvider(
                    message="M-Pesa phone number is required", code=400
                ).bad_request()

            result = adapter.initiate_stk_push(
                msisdn=msisdn,
                amount=float(payment_amount),
                currency=payment_currency,
                account_reference=invoice.invoice_number,
                transaction_desc=f"Payment for invoice {invoice.invoice_number}",
                callback_url=provider_config.get("callback_url", ""),
            )

            if result.get("status") == "failed" or result.get("response_code") != "0":
                payment.status = "failed"
                payment.save()
                return ResponseProvider(
                    message=result.get("customer_message")
                    or result.get("response_description")
                    or "Failed to initiate payment",
                    code=400,
                ).bad_request()

            payment.provider_reference = result.get(
                "checkout_request_id"
            ) or result.get("provider_reference")
            payment.provider_metadata = result
            payment.save()

            return ResponseProvider(
                data={
                    "payment_id": str(payment.id),
                    "checkout_request_id": result.get("checkout_request_id"),
                    "status": "pending",
                    "message": result.get(
                        "customer_message", "Please check your phone for payment prompt"
                    ),
                },
                message="M-Pesa payment initiated successfully",
                code=200,
            ).success()

        else:  # card or other methods
            email = (
                data.get("email")
                or corporate.get("email")
                or user.get("email", "billing@quidpath.com")
            )

            # For card payments, use original currency (not converted to KES)
            card_amount = float(invoice.total_usd)
            card_currency = invoice.currency or "USD"

            result = adapter.initiate_card_payment(
                amount=float(card_amount),
                currency=card_currency,
                customer_email=email,
                callback_url=provider_config.get("callback_url", ""),
                metadata={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "corporate_id": str(corporate_id),
                },
            )

            if result["status"] == "failed":
                payment.status = "failed"
                payment.save()
                return ResponseProvider(
                    message=result.get("message", "Failed to initiate payment"),
                    code=400,
                ).bad_request()

            payment.provider_reference = result.get("provider_reference") or result.get(
                "tx_ref"
            )
            payment.provider_metadata = result
            payment.save()

            return ResponseProvider(
                data={
                    "payment_id": str(payment.id),
                    "checkout_url": result.get("checkout_url"),
                    "status": "pending",
                    "message": "Redirect to checkout URL to complete payment",
                },
                message="Payment initiated successfully",
                code=200,
            ).success()

    except Exception as e:
        logger.exception(f"Error initiating organization payment: {e}")
        return ResponseProvider(
            message=f"Error initiating payment: {str(e)}", code=500
        ).exception()


@csrf_exempt
def organization_payment_webhook(request):
    """Handle organization payment webhook from Flutterwave."""
    import json

    try:
        payload = json.loads(request.body) if request.body else {}
        headers = dict(request.headers)

        # Get payment reference from payload
        provider_reference = (
            payload.get("data", {}).get("tx_ref")
            or payload.get("data", {}).get("flw_ref")
            or payload.get("tx_ref")
        )

        if not provider_reference:
            logger.warning("Organization payment webhook: No payment reference found")
            return ResponseProvider(
                message="Invalid webhook payload", code=400
            ).bad_request()

        # Find payment
        payment = OrganizationPayment.objects.filter(
            provider_reference=provider_reference
        ).first()
        if not payment:
            logger.warning(
                f"Organization payment webhook: Payment not found for {provider_reference}"
            )
            return ResponseProvider(message="Payment not found", code=404).bad_request()

        # Get payment provider
        registry = ServiceRegistry()
        payment_providers = registry.database(
            model_name="PaymentProvider",
            operation="filter",
            data={
                "corporate_id": payment.corporate_id,
                "provider_type": "flutterwave",
                "is_active": True,
            },
        )
        if not payment_providers:
            logger.warning(f"Organization payment webhook: Payment provider not found")
            return ResponseProvider(
                message="Payment provider not found", code=404
            ).bad_request()

        provider = payment_providers[0]
        provider_config = provider.get("config_json", {})

        # Initialize Flutterwave adapter
        adapter = FlutterwaveAdapter(provider_config)

        # Verify webhook signature
        if not adapter.verify_webhook_signature(request.body, headers):
            logger.warning(
                f"Organization payment webhook: Invalid signature for {provider_reference}"
            )
            return ResponseProvider(
                message="Invalid webhook signature", code=401
            ).unauthorized()

        # Parse webhook
        webhook_data = (
            adapter.handle_card_webhook(payload, headers)
            if payment.payment_method == "card"
            else adapter.handle_stk_callback(payload, headers)
        )

        # Update payment status
        if webhook_data.get("status") == "successful":
            payment.status = "success"
            payment.paid_at = timezone.now()
            payment.provider_metadata = {**payment.provider_metadata, **webhook_data}
            payment.save()

            # Update invoice
            if payment.invoice:
                payment.invoice.status = "paid"
                payment.invoice.paid_at = timezone.now()
                payment.invoice.payment_reference = provider_reference
                payment.invoice.save()

            logger.info(f"Organization payment {payment.id} confirmed successfully")
        elif webhook_data.get("status") == "failed":
            payment.status = "failed"
            payment.provider_metadata = {**payment.provider_metadata, **webhook_data}
            payment.save()
            logger.warning(f"Organization payment {payment.id} failed")

        return ResponseProvider(
            message="Webhook processed successfully", code=200
        ).success()

    except Exception as e:
        logger.exception(f"Error processing organization payment webhook: {e}")
        return ResponseProvider(
            message=f"Error processing webhook: {str(e)}", code=500
        ).exception()


@csrf_exempt
def get_subscription_status(request):
    """Get organization subscription status including trial information."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Get active subscription
        subscription = (
            OrganizationSubscription.objects.filter(
                corporate_id=corporate_id, status__in=["trial", "active"]
            )
            .order_by("-created_at")
            .first()
        )

        if not subscription:
            # Check if organization is new (created within last 30 days)
            corporate = registry.database("Corporate", "get", data={"id": corporate_id})
            if corporate:
                created_at = corporate.get("created_at")
                if created_at:
                    from dateutil import parser

                    created_date = (
                        parser.parse(created_at).date()
                        if isinstance(created_at, str)
                        else created_at
                    )
                    days_since_creation = (timezone.now().date() - created_date).days

                    if days_since_creation <= 30:
                        # Create trial subscription
                        trial_end = created_date + timedelta(days=30)
                        subscription = OrganizationSubscription.objects.create(
                            corporate_id=corporate_id,
                            plan_type="basic",
                            status="trial",
                            monthly_price_usd=Decimal("0.00"),
                            start_date=created_date,
                            end_date=trial_end,
                            max_users=5,
                            current_users=1,
                        )

        if subscription:
            # Calculate days remaining in trial
            days_remaining = None
            is_trial = subscription.status == "trial"
            if is_trial:
                days_remaining = max(
                    0, (subscription.end_date - timezone.now().date()).days
                )

            subscription_data = {
                "id": str(subscription.id),
                "plan_type": subscription.plan_type,
                "status": subscription.status,
                "is_trial": is_trial,
                "days_remaining": days_remaining,
                "start_date": (
                    subscription.start_date.isoformat()
                    if subscription.start_date
                    else None
                ),
                "end_date": (
                    subscription.end_date.isoformat() if subscription.end_date else None
                ),
                "monthly_price_usd": float(subscription.monthly_price_usd),
                "currency": subscription.currency,
                "max_users": subscription.max_users,
                "current_users": subscription.current_users,
            }

            return ResponseProvider(
                data={"subscription": subscription_data},
                message="Subscription status retrieved successfully",
                code=200,
            ).success()
        else:
            return ResponseProvider(
                data={"subscription": None},
                message="No active subscription found",
                code=200,
            ).success()

    except Exception as e:
        logger.exception(f"Error getting subscription status: {e}")
        return ResponseProvider(
            message=f"Error getting subscription status: {str(e)}", code=500
        ).exception()


@csrf_exempt
def get_invoice_details(request, invoice_id=None):
    """Get detailed invoice information."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    try:
        # Get invoice_id from URL parameter or request data
        invoice_id = invoice_id or data.get("invoice_id")
        if not invoice_id:
            return ResponseProvider(
                message="Invoice ID is required", code=400
            ).bad_request()

        registry = ServiceRegistry()
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        invoice = OrganizationInvoice.objects.filter(
            id=invoice_id, corporate_id=corporate_id
        ).first()
        if not invoice:
            return ResponseProvider(message="Invoice not found", code=404).not_found()

        # Get related payments
        payments = OrganizationPayment.objects.filter(invoice=invoice).order_by(
            "-created_at"
        )
        payments_data = []
        for payment in payments:
            payments_data.append(
                {
                    "id": str(payment.id),
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "payment_method": payment.payment_method,
                    "status": payment.status,
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    "provider_reference": payment.provider_reference,
                }
            )

        invoice_data = {
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "subtotal_usd": float(invoice.subtotal_usd),
            "tax_usd": float(invoice.tax_usd),
            "total_usd": float(invoice.total_usd),
            "currency": invoice.currency,
            "exchange_rate_to_usd": float(invoice.exchange_rate_to_usd),
            "billing_period_start": (
                invoice.billing_period_start.isoformat()
                if invoice.billing_period_start
                else None
            ),
            "billing_period_end": (
                invoice.billing_period_end.isoformat()
                if invoice.billing_period_end
                else None
            ),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            "payment_reference": invoice.payment_reference,
            "line_items": invoice.line_items or [],
            "payments": payments_data,
            "created_at": (
                invoice.created_at.isoformat() if invoice.created_at else None
            ),
        }

        return ResponseProvider(
            data={"invoice": invoice_data},
            message="Invoice details retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error getting invoice details: {e}")
        return ResponseProvider(
            message=f"Error getting invoice details: {str(e)}", code=500
        ).exception()
