# Document sending views (invoices, quotes, LPOs)
import logging
from decimal import Decimal

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Accounting.models.audit import AuditLog
from quidpath_backend.core.utils.DocsEmail import DocumentNotificationHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.messaging import SESAdapter, SMSAdapter
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def send_invoice(request, invoice_id):
    """
    Send invoice via email and/or SMS.

    POST /api/v1/invoices/{id}/send/

    Request:
    {
        "via": ["email", "sms"],
        "to_emails": ["customer@example.com"],
        "to_msisdns": ["254712345678"],
        "message": "Custom message (optional)",
        "subject": "Custom subject (optional)"
    }

    Response:
    {
        "code": 200,
        "message": "Invoice sent successfully",
        "data": {
            "email_logs": [...],
            "sms_logs": [...]
        }
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate
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

        # Get invoice
        invoices = registry.database(
            model_name="Invoices",
            operation="filter",
            data={"id": invoice_id, "corporate_id": corporate_id},
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found", code=404).bad_request()

        invoice = invoices[0]

        # Get customer
        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": invoice["customer_id"]},
        )
        if not customers:
            return ResponseProvider(
                message="Customer not found", code=404
            ).bad_request()

        customer = customers[0]

        # Get corporate details
        corporates = registry.database(
            model_name="Corporate", operation="filter", data={"id": corporate_id}
        )
        if not corporates:
            return ResponseProvider(
                message="Corporate not found", code=404
            ).bad_request()

        corporate = corporates[0]

        # Validate send methods
        via = data.get("via", ["email"])
        if not isinstance(via, list):
            via = [via]

        to_emails = data.get("to_emails", [])
        to_msisdns = data.get("to_msisdns", [])

        # Default to customer email/phone if not provided
        if "email" in via and not to_emails:
            if customer.get("email"):
                to_emails = [customer["email"]]

        if "sms" in via and not to_msisdns:
            if customer.get("phone"):
                to_msisdns = [customer["phone"]]

        # Get messaging adapters configuration
        # TODO: Store messaging provider config in database
        # For now, use environment variables
        import os

        from django.conf import settings

        email_logs = []
        sms_logs = []

        # Send emails
        if "email" in via and to_emails:
            # Get SES adapter config
            ses_config = {
                "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
                "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
                "aws_region": os.environ.get("AWS_REGION", "us-east-1"),
                "from_email": corporate.get("email", settings.DEFAULT_FROM_EMAIL),
                "test_mode": os.environ.get("AWS_SES_TEST_MODE", "True").lower()
                == "true",
            }

            # Generate invoice HTML
            invoice_html = _generate_invoice_html(invoice, customer, corporate)

            subject = data.get(
                "subject",
                f"Invoice {invoice.get('number', '')} from {corporate.get('name', '')}",
            )
            custom_message = data.get("message", "")

            if custom_message:
                invoice_html = f"<p>{custom_message}</p><hr>{invoice_html}"

            # Send via SES
            ses_adapter = SESAdapter(ses_config)

            for email in to_emails:
                result = ses_adapter.send(
                    to=email,
                    message=invoice_html,
                    subject=subject,
                    metadata={
                        "invoice_id": str(invoice_id),
                        "corporate_id": str(corporate_id),
                    },
                )

                email_logs.append(
                    {
                        "recipient": email,
                        "status": result.get("status"),
                        "provider_reference": result.get("provider_reference"),
                        "message": result.get("message"),
                    }
                )

                # Log email send
                # TODO: Create EmailLog model and save logs

        # Send SMS
        if "sms" in via and to_msisdns:
            # Get SMS adapter config
            sms_config = {
                "provider_type": os.environ.get("SMS_PROVIDER_TYPE", "africas_talking"),
                "api_key": os.environ.get("SMS_API_KEY", ""),
                "api_secret": os.environ.get("SMS_API_SECRET", ""),
                "username": os.environ.get("SMS_USERNAME", ""),
                "sender_id": os.environ.get("SMS_SENDER_ID", "QUIDPATH"),
                "test_mode": os.environ.get("SMS_TEST_MODE", "True").lower() == "true",
            }

            # Generate SMS message
            sms_message = _generate_invoice_sms(
                invoice, customer, corporate, data.get("message", "")
            )

            # Send via SMS adapter
            sms_adapter = SMSAdapter(sms_config)

            for msisdn in to_msisdns:
                result = sms_adapter.send(
                    to=msisdn,
                    message=sms_message,
                    metadata={
                        "invoice_id": str(invoice_id),
                        "corporate_id": str(corporate_id),
                    },
                )

                sms_logs.append(
                    {
                        "recipient": msisdn,
                        "status": result.get("status"),
                        "provider_reference": result.get("provider_reference"),
                        "message": result.get("message"),
                    }
                )

                # Log SMS send
                # TODO: Create SmsLog model and save logs

        # Update invoice issued_at
        registry.database(
            model_name="Invoices",
            operation="update",
            instance_id=invoice_id,
            data={"issued_at": timezone.now()},
        )

        # Create audit log
        AuditLog.objects.create(
            user_id=user_id,
            corporate_id=corporate_id,
            action_type="send",
            model_name="Invoice",
            object_id_str=str(invoice_id),
            description=f"Invoice {invoice.get('number', '')} sent via {', '.join(via)}",
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        # Log transaction
        TransactionLogBase.log(
            transaction_type="INVOICE_SENT",
            user=user,
            message=f"Invoice {invoice.get('number', '')} sent successfully",
            state_name="Success",
            extra={"invoice_id": str(invoice_id), "via": via},
            request=request,
        )

        return ResponseProvider(
            data={"email_logs": email_logs, "sms_logs": sms_logs},
            message="Invoice sent successfully",
            code=200,
        ).success()

    except Exception as e:
        logger.exception(f"Error sending invoice: {e}")
        TransactionLogBase.log(
            transaction_type="INVOICE_SENT",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while sending invoice", code=500
        ).exception()


def _generate_invoice_html(invoice, customer, corporate):
    """Generate HTML email body for invoice."""
    # Simple HTML template - in production, use Jinja2 templates
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .invoice-header {{ background-color: #f0f0f0; padding: 20px; }}
            .invoice-details {{ margin: 20px 0; }}
            .invoice-table {{ width: 100%; border-collapse: collapse; }}
            .invoice-table th, .invoice-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .invoice-table th {{ background-color: #f0f0f0; }}
            .invoice-total {{ text-align: right; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="invoice-header">
            <h2>Invoice {invoice.get('number', '')}</h2>
            <p><strong>{corporate.get('name', '')}</strong></p>
        </div>
        
        <div class="invoice-details">
            <p><strong>Bill To:</strong></p>
            <p>
                {customer.get('company_name', f"{customer.get('first_name', '')} {customer.get('last_name', '')}")}<br>
                {customer.get('email', '')}<br>
                {customer.get('phone', '')}
            </p>
            
            <p><strong>Invoice Date:</strong> {invoice.get('date', '')}</p>
            <p><strong>Due Date:</strong> {invoice.get('due_date', '')}</p>
        </div>
        
        <table class="invoice-table">
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit Price</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
                <!-- Invoice lines would go here -->
            </tbody>
        </table>
        
        <div class="invoice-total">
            <p>Subtotal: {invoice.get('sub_total', '0.00')}</p>
            <p>Tax: {invoice.get('tax_total', '0.00')}</p>
            <p><strong>Total: {invoice.get('total', '0.00')} {invoice.get('currency', 'USD')}</strong></p>
        </div>
        
        <p>Thank you for your business!</p>
    </body>
    </html>
    """
    return html


def _generate_invoice_sms(invoice, customer, corporate, custom_message=""):
    """Generate SMS message for invoice."""
    if custom_message:
        return custom_message

    message = f"Invoice {invoice.get('number', '')} from {corporate.get('name', '')} - Amount: {invoice.get('total', '0.00')} {invoice.get('currency', 'USD')}. Due: {invoice.get('due_date', '')}. Pay: https://app.quidpath.com/pay/{invoice.get('id', '')}"
    return message


def _get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# Similar functions for quotes and LPOs
@csrf_exempt
def send_quote(request, quote_id):
    """Send quote via email and/or SMS."""
    # Similar implementation to send_invoice
    # TODO: Implement
    pass


@csrf_exempt
def send_lpo(request, lpo_id):
    """Send LPO via email and/or SMS."""
    # Similar implementation to send_invoice
    # TODO: Implement
    pass
