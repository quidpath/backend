import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from os.path import basename
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from quidpath_backend.core.Services.notification_service import NotificationTypeService, NotificationService
from quidpath_backend.core.Services.organisation_service import OrganisationService
from quidpath_backend.core.Services.state_service import StateService

log = logging.getLogger(__name__)


class NotificationServiceHandler:
    """
    Handles sending notifications (Email, future SMS, etc.)
    """

    def send_notification(self, notifications: List[Dict[str, Any]], trans=None, attachment=None, cc=None):
        """
        Process and send a list of notifications.
        """
        if not notifications:
            return None

        try:
            for data in notifications:
                # Extract fields
                message_type = data.get("message_type")   # '1'=SMS, else EMAIL
                corporate_id = data.get("organisation_id")
                destination = data.get("destination", "")
                message = data.get("message", "")
                confirmation_code = data.get("confirmation_code", "")

                # Get NotificationType (SMS or EMAIL)
                notif_type_name = "SMS" if message_type == "1" else "EMAIL"
                notification_type = NotificationTypeService().get_or_create_type(notif_type_name)

                # Get Organisation
                organisation = OrganisationService().get_or_default(corporate_id)

                # Create notification record (state initially Completed)
                notification_obj = NotificationService().create_notification(
                    corporate=organisation,
                    title=f"{notif_type_name} Notification",
                    destination=destination,
                    message=message,
                    notification_type=notification_type,
                    state=StateService().get_completed()
                )

                # Send actual notification
                if notif_type_name == "SMS":
                    # Placeholder for SMS sending
                    notification_response = self._send_sms(destination, message, confirmation_code, organisation.id)
                else:
                    notification_response = self._send_email_without_attachment(
                        destination, message, organisation.name, cc
                    )

                # Update Notification state if failed
                if notification_response.get("code") != "200.001.001":
                    NotificationService().mark_failed(notification_obj.id)

                # Optionally update transaction logs
                if trans:
                    NotificationService().update_transaction_notification_log(trans, notification_response)

            return "success"

        except Exception as e:
            log.exception("Error sending notification: %s", e)
            return {"status": "failed", "message": f"Error: {e}"}

    def _send_sms(self, destination, message, confirmation_code, corporate_id):
        """
        Future: Integrate with SMS provider.
        """
        log.info(f"[SMS] {destination} -> {message} (code: {confirmation_code}, org={corporate_id})")
        return {"code": "200.001.001"}  # simulate success

    def _send_email(self, recipient_email: str, subject: str, message: str,
                    reply_to="noreply@example.com", cc=None, bcc=None, attachment=None,
                    from_address=None, sender=None, password=None):
        """
        Low-level email sender
        """
        from_address = from_address or settings.DEFAULT_FROM_EMAIL
        sender = sender or settings.SMTP_USER
        password = password or settings.SMTP_PASS

        try:
            # Validate email
            try:
                validate_email(recipient_email)
            except ValidationError:
                return {"status": "failed", "message": f"Invalid email: {recipient_email}"}

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
                    part["Content-Disposition"] = f'attachment; filename="{basename(f)}"'
                    msg.attach(part)

            # Connect SMTP
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(sender, password)
            server.sendmail(from_address, toaddrs, msg.as_string())
            server.quit()

            return {"status": "success", "code": "200.001.001", "message": "Email sent successfully"}
        except Exception as e:
            log.error("Error sending email: %s", e)
            return {"status": "failed", "code": "400.001.007", "message": str(e)}

    def _send_email_without_attachment(self, destination, message, corporate_name, cc=None):
        """
        Email sender without attachments.
        """
        subject = f"Notification - {corporate_name}"
        return self._send_email(destination, subject, message, cc=cc)
