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


class NotificationServiceHandler(TemplateManagementEngine):
    """
    Handles sending notifications (Email, future SMS, etc.)
    """

    def send_notification(
        self, notifications: List[Dict[str, Any]], trans=None, attachment=None, cc=None
    ):
        """
        Process and send a list of notifications.
        """
        if not notifications:
            return None

        try:
            for data in notifications:
                # Extract fields
                message_type = data.get("message_type")  # '1'=SMS, else EMAIL
                corporate_id = data.get("organisation_id")
                destination = data.get("destination", "")
                message = data.get("message", "")
                confirmation_code = data.get("confirmation_code", "")

                # Get NotificationType (SMS or EMAIL)
                notif_type_name = "SMS" if message_type == "1" else "EMAIL"
                notification_type = NotificationTypeService().get_or_create_type(
                    notif_type_name
                )

                # Get Organisation
                organisation = CorporateService().get_or_default(corporate_id)

                # Create notification record with Pending state initially
                notification_obj = NotificationService().create_notification(
                    corporate=organisation,
                    title=f"{notif_type_name} Notification",
                    destination=destination,
                    message=message,
                    notification_type=notification_type,
                    state=StateService().get_pending(),
                )

                log.info(f"Attempting to send {notif_type_name} notification to {destination}")

                # Send actual notification
                if notif_type_name == "SMS":
                    # Placeholder for SMS sending
                    notification_response = self._send_sms(
                        destination, message, confirmation_code, organisation.id
                    )
                else:
                    notification_response = self._send_email_without_attachment(
                        destination, message, organisation.name, cc
                    )

                # Update Notification state based on response
                if notification_response.get("code") == "200.001.001":
                    # Mark as sent/completed
                    notification_obj.state = StateService().get_sent()
                    notification_obj.response_payload = notification_response
                    notification_obj.save()
                    log.info(f"Successfully sent {notif_type_name} notification to {destination}")
                else:
                    # Mark as failed
                    NotificationService().mark_failed(notification_obj.id)
                    notification_obj.response_payload = notification_response
                    notification_obj.save()
                    log.error(f"Failed to send {notif_type_name} notification to {destination}: {notification_response.get('message')}")

                # Optionally update transaction logs
                if trans:
                    NotificationService().update_transaction_notification_log(
                        trans, notification_response
                    )

            return "success"

        except Exception as e:
            log.exception("Error sending notification: %s", e)
            return {"status": "failed", "message": f"Error: {e}"}

    def _send_sms(self, destination, message, confirmation_code, corporate_id):
        """
        Future: Integrate with SMS provider.
        """
        log.info(
            f"[SMS] {destination} -> {message} (code: {confirmation_code}, org={corporate_id})"
        )
        return {"code": "200.001.001"}  # simulate success

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
        Low-level email sender
        """
        from_address = from_address or settings.DEFAULT_FROM_EMAIL
        sender = sender or settings.SMTP_USER
        password = password or settings.SMTP_PASSWORD

        # Validate SMTP credentials
        if not sender or not password:
            error_msg = f"SMTP credentials not configured. SMTP_USER={'set' if sender else 'missing'}, SMTP_PASSWORD={'set' if password else 'missing'}"
            log.error(error_msg)
            return {
                "status": "failed",
                "code": "400.001.008",
                "message": error_msg,
            }

        log.info(f"Preparing to send email to {recipient_email} with subject: {subject}")
        log.debug(f"SMTP Config: Host={settings.SMTP_HOST}, Port={settings.SMTP_PORT}, User={sender}")

        try:
            # Validate email
            try:
                validate_email(recipient_email)
            except ValidationError as ve:
                error_msg = f"Invalid email address: {recipient_email}"
                log.error(error_msg)
                return {
                    "status": "failed",
                    "code": "400.001.009",
                    "message": error_msg,
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

            # Attach files
            if attachment:
                for f in attachment:
                    with open(f, "rb") as fil:
                        part = MIMEApplication(fil.read(), Name=basename(f))
                    part["Content-Disposition"] = (
                        f'attachment; filename="{basename(f)}"'
                    )
                    msg.attach(part)

            # Connect SMTP
            log.info(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}")
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            server.set_debuglevel(0)  # Set to 1 for verbose SMTP debugging
            
            log.info("Starting TLS...")
            server.starttls()
            
            log.info(f"Logging in as {sender}...")
            server.login(sender, password)
            
            log.info(f"Sending email to {toaddrs}...")
            server.sendmail(from_address, toaddrs, msg.as_string())
            server.quit()

            log.info(f"Email sent successfully to {recipient_email}")
            return {
                "status": "success",
                "code": "200.001.001",
                "message": "Email sent successfully",
            }
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP Authentication failed: {str(e)}"
            log.error(error_msg)
            return {"status": "failed", "code": "400.001.010", "message": error_msg}
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error occurred: {str(e)}"
            log.error(error_msg)
            return {"status": "failed", "code": "400.001.011", "message": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error sending email: {str(e)}"
            log.exception(error_msg)
            return {"status": "failed", "code": "400.001.007", "message": error_msg}

    def _send_email_without_attachment(
        self, destination, message, corporate_name, cc=None
    ):
        """
        Email sender without attachments.
        """
        subject = f"Notification - {corporate_name}"
        return self._send_email(destination, subject, message, cc=cc)
