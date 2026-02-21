import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from os.path import basename
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from OrgAuth.templates.CorporateTempMgt import TemplateManagementEngine
from quidpath_backend.core.Services.notification_service import (
    NotificationService, NotificationTypeService)
from quidpath_backend.core.Services.organisation_service import \
    CorporateService
from quidpath_backend.core.Services.state_service import StateService

log = logging.getLogger(__name__)


class DocumentNotificationHandler(TemplateManagementEngine):
    """
    Handles sending document-related notifications (Email with details for quotations, invoices, etc.).
    Adapted from NotificationServiceHandler to fetch corporate email as from_address and send to customer/vendor.
    """

    def send_document_notification(
        self, notifications: List[Dict[str, Any]], trans=None, attachment=None, cc=None
    ):
        """
        Process and send a list of document notifications (e.g., quotation, invoice to customer; PO, bill to vendor).
        Each notification dict must include:
        - message_type: 'EMAIL' (SMS not supported for documents)
        - organisation_id: corporate_id
        - destination: customer/vendor email
        - message: HTML message body with document details
        - subject: Optional custom subject
        """
        if not notifications:
            return None

        try:
            for data in notifications:
                # Extract fields
                message_type = data.get("message_type")
                if message_type == "1":  # SMS not supported for documents
                    log.warning("SMS not supported for document notifications")
                    continue

                corporate_id = data.get("organisation_id")
                destination = data.get("destination", "")
                message = data.get("message", "")
                subject = data.get("subject", f"Document Notification - {corporate_id}")

                # Get NotificationType (EMAIL)
                notification_type = NotificationTypeService().get_or_create_type(
                    "EMAIL"
                )

                # Get Organisation (Corporate)
                organisation = CorporateService().get_or_default(corporate_id)
                from_email = (
                    organisation.email
                    if hasattr(organisation, "email") and organisation.email
                    else settings.DEFAULT_FROM_EMAIL
                )  # Fetch corporate email

                # Create notification record (state initially Completed)
                notification_obj = NotificationService().create_notification(
                    corporate=organisation,
                    title="Document Email Notification",
                    destination=destination,
                    message=message,
                    notification_type=notification_type,
                    state=StateService().get_completed(),
                )

                # Send actual email
                notification_response = self._send_email_without_attachment(
                    destination,
                    message,
                    organisation.name,
                    cc,
                    from_address=from_email,
                    subject=subject,
                )

                # Update Notification state if failed
                if notification_response.get("code") != "200.001.001":
                    NotificationService().mark_failed(notification_obj.id)

                # Optionally update transaction logs
                if trans:
                    NotificationService().update_transaction_notification_log(
                        trans, notification_response
                    )

            return "success"

        except Exception as e:
            log.exception("Error sending document notification: %s", e)
            return {"status": "failed", "message": f"Error: {e}"}

    def _send_email(
        self,
        recipient_email: str,
        subject: str,
        message: str,
        reply_to="noreply@example.com",
        cc=None,
        bcc=None,
        attachment=None,
        from_address=None,
        sender=None,
        password=None,
    ):
        """
        Low-level email sender (same as original)
        """
        from_address = from_address or settings.DEFAULT_FROM_EMAIL
        sender = sender or settings.SMTP_USER
        password = password or settings.SMTP_PASSWORD

        # Validate SMTP credentials
        if not sender or not password:
            log.error("SMTP credentials not configured. SMTP_USER or SMTP_PASSWORD is missing.")
            return {
                "status": "failed",
                "code": "400.001.008",
                "message": "SMTP credentials not configured",
            }

        try:
            # Validate email
            try:
                validate_email(recipient_email)
            except ValidationError:
                return {
                    "status": "failed",
                    "message": f"Invalid email: {recipient_email}",
                }

            msg = MIMEMultipart()
            msg["From"] = from_address
            msg["Reply-To"] = reply_to
            msg["To"] = recipient_email
            msg["Date"] = formatdate(localtime=True)
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "html"))

            # Add CC/BCC
            toaddrs = [recipient_email]
            if cc:
                if not isinstance(cc, list):
                    cc = cc.split(",")
                msg["Cc"] = ",".join(cc)
                toaddrs.extend(cc)
            if bcc:
                if not isinstance(bcc, list):
                    bcc = bcc.split(",")
                toaddrs.extend(bcc)

            # Attach files (e.g., PDF of document if generated)
            if attachment:
                for f in attachment:
                    with open(f, "rb") as fil:
                        part = MIMEApplication(fil.read(), Name=basename(f))
                    part["Content-Disposition"] = (
                        f'attachment; filename="{basename(f)}"'
                    )
                    msg.attach(part)

            # Connect SMTP
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(sender, password)
            server.sendmail(from_address, toaddrs, msg.as_string())
            server.quit()

            return {
                "status": "success",
                "code": "200.001.001",
                "message": "Email sent successfully",
            }
        except Exception as e:
            log.error("Error sending email: %s", e)
            return {"status": "failed", "code": "400.001.007", "message": str(e)}

    def _send_email_without_attachment(
        self,
        destination,
        message,
        corporate_name,
        cc=None,
        from_address=None,
        subject=None,
    ):
        """
        Email sender without attachments, with optional custom subject and from_address.
        """
        subject = subject or f"Notification - {corporate_name}"
        return self._send_email(
            destination, subject, message, cc=cc, from_address=from_address
        )
