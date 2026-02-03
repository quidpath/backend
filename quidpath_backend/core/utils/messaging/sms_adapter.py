# SMS adapter (generic for Kenyan SMS providers)
import logging
from typing import Any, Dict, List, Optional

import requests

from .base import MessagingAdapter

logger = logging.getLogger(__name__)


class SMSAdapter(MessagingAdapter):
    """
    Generic SMS adapter for Kenyan SMS providers.
    Supports AfricasTalking, Twilio, and other SMS gateways.
    """

    PROVIDER_TYPES = {
        "africas_talking": {
            "base_url": {
                "test": "https://api.sandbox.africastalking.com",
                "live": "https://api.africastalking.com",
            },
            "send_endpoint": "/version1/messaging",
            "api_key_header": "apiKey",
            "username_header": "username",
        },
        "twilio": {
            "base_url": {
                "test": "https://api.twilio.com",
                "live": "https://api.twilio.com",
            },
            "send_endpoint": "/2010-04-01/Accounts/{account_sid}/Messages.json",
            "auth_type": "basic",
        },
        "sms_kenya": {
            "base_url": {
                "test": "https://api.smskenya.com",
                "live": "https://api.smskenya.com",
            },
            "send_endpoint": "/api/send",
            "api_key_header": "X-API-Key",
        },
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider_type = config.get("provider_type", "africas_talking")
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret", "")
        self.username = config.get("username", "")
        self.shortcode = config.get("shortcode", "")
        self.sender_id = config.get("sender_id", "QUIDPATH")

        # Get provider config
        provider_config = self.PROVIDER_TYPES.get(
            self.provider_type, self.PROVIDER_TYPES["africas_talking"]
        )
        base_urls = provider_config["base_url"]
        self.base_url = base_urls["test" if self.test_mode else "live"]
        self.send_endpoint = provider_config["send_endpoint"]
        self.api_key_header = provider_config.get("api_key_header", "apiKey")
        self.username_header = provider_config.get("username_header", "username")

    def format_phone(self, phone: str) -> str:
        """
        Format phone number for SMS.
        """
        # Remove spaces, dashes, parentheses
        phone = (
            phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        )

        # Add country code if missing (assume Kenya +254)
        if not phone.startswith("+") and not phone.startswith("254"):
            if phone.startswith("0"):
                phone = "254" + phone[1:]
            else:
                phone = "254" + phone

        # Remove + if present
        phone = phone.replace("+", "")

        return phone

    def send(
        self,
        to: str,
        message: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send SMS.

        Args:
            to: Recipient phone number
            message: SMS message content
            subject: Not used for SMS
            metadata: Additional metadata
        """
        # Format phone number
        phone = self.format_phone(to)

        # Send based on provider type
        if self.provider_type == "africas_talking":
            return self._send_africas_talking(phone, message, metadata)
        elif self.provider_type == "twilio":
            return self._send_twilio(phone, message, metadata)
        elif self.provider_type == "sms_kenya":
            return self._send_sms_kenya(phone, message, metadata)
        else:
            raise ValueError(f"Unsupported provider type: {self.provider_type}")

    def _send_africas_talking(
        self, phone: str, message: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send SMS via AfricasTalking."""
        url = f"{self.base_url}{self.send_endpoint}"

        headers = {
            self.api_key_header: self.api_key,
            self.username_header: self.username,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        payload = {
            "username": self.username,
            "to": phone,
            "message": message,
            "from": self.sender_id,
        }

        try:
            response = requests.post(url, data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse AfricasTalking response
            sms_message_data = data.get("SMSMessageData", {})
            recipients = sms_message_data.get("Recipients", [])

            if recipients:
                recipient = recipients[0]
                status = recipient.get("status", "")
                message_id = recipient.get("messageId", "")

                if status == "Success":
                    logger.info(f"SMS sent successfully: {message_id} to {phone}")
                    return {
                        "status": "success",
                        "provider_reference": message_id,
                        "message": "SMS sent successfully",
                    }
                else:
                    logger.error(f"SMS send failed: {status}")
                    return {
                        "status": "failed",
                        "provider_reference": message_id,
                        "message": f"SMS send failed: {status}",
                    }
            else:
                return {
                    "status": "failed",
                    "provider_reference": None,
                    "message": "No recipients in response",
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"AfricasTalking SMS send failed: {e}")
            return {
                "status": "failed",
                "provider_reference": None,
                "message": f"Request failed: {str(e)}",
            }

    def _send_twilio(
        self, phone: str, message: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send SMS via Twilio."""
        account_sid = self.api_key  # Twilio uses account_sid as API key
        auth_token = self.api_secret

        url = self.send_endpoint.format(account_sid=account_sid)
        full_url = f"{self.base_url}{url}"

        from_number = (
            metadata.get("from_number", self.shortcode) if metadata else self.shortcode
        )

        payload = {"To": f"+{phone}", "From": from_number, "Body": message}

        try:
            response = requests.post(
                full_url, data=payload, auth=(account_sid, auth_token), timeout=30
            )
            response.raise_for_status()
            data = response.json()

            message_id = data.get("sid", "")
            status = data.get("status", "")

            if status in ["queued", "sent", "delivered"]:
                logger.info(f"Twilio SMS sent successfully: {message_id} to {phone}")
                return {
                    "status": "success",
                    "provider_reference": message_id,
                    "message": "SMS sent successfully",
                }
            else:
                logger.error(f"Twilio SMS send failed: {status}")
                return {
                    "status": "failed",
                    "provider_reference": message_id,
                    "message": f"SMS send failed: {status}",
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Twilio SMS send failed: {e}")
            return {
                "status": "failed",
                "provider_reference": None,
                "message": f"Request failed: {str(e)}",
            }

    def _send_sms_kenya(
        self, phone: str, message: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send SMS via SMS Kenya."""
        url = f"{self.base_url}{self.send_endpoint}"

        headers = {
            self.api_key_header: self.api_key,
            "Content-Type": "application/json",
        }

        payload = {"to": phone, "message": message, "from": self.sender_id}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            message_id = data.get("message_id", "")
            status = data.get("status", "")

            if status == "success":
                logger.info(f"SMS Kenya SMS sent successfully: {message_id} to {phone}")
                return {
                    "status": "success",
                    "provider_reference": message_id,
                    "message": "SMS sent successfully",
                }
            else:
                logger.error(f"SMS Kenya SMS send failed: {status}")
                return {
                    "status": "failed",
                    "provider_reference": message_id,
                    "message": f"SMS send failed: {status}",
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"SMS Kenya SMS send failed: {e}")
            return {
                "status": "failed",
                "provider_reference": None,
                "message": f"Request failed: {str(e)}",
            }

    def send_bulk(
        self,
        recipients: List[str],
        message: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send bulk SMS.
        """
        # Format phone numbers
        phones = [self.format_phone(phone) for phone in recipients]

        # Send based on provider type
        if self.provider_type == "africas_talking":
            return self._send_bulk_africas_talking(phones, message, metadata)
        else:
            # For other providers, send individually
            results = []
            for phone in phones:
                result = self.send(phone, message, subject, metadata)
                results.append({"recipient": phone, **result})

            success_count = sum(1 for r in results if r["status"] == "success")
            failed_count = len(results) - success_count

            return {
                "status": "completed",
                "total": len(results),
                "success": success_count,
                "failed": failed_count,
                "results": results,
            }

    def _send_bulk_africas_talking(
        self, phones: List[str], message: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Send bulk SMS via AfricasTalking."""
        url = f"{self.base_url}{self.send_endpoint}"

        headers = {
            self.api_key_header: self.api_key,
            self.username_header: self.username,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        # Format recipients as comma-separated string
        recipients = ",".join(phones)

        payload = {
            "username": self.username,
            "to": recipients,
            "message": message,
            "from": self.sender_id,
        }

        try:
            response = requests.post(url, data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse response
            sms_message_data = data.get("SMSMessageData", {})
            recipients_data = sms_message_data.get("Recipients", [])

            results = []
            for recipient in recipients_data:
                phone = recipient.get("number", "")
                status = recipient.get("status", "")
                message_id = recipient.get("messageId", "")

                results.append(
                    {
                        "recipient": phone,
                        "status": "success" if status == "Success" else "failed",
                        "provider_reference": message_id,
                        "message": status,
                    }
                )

            success_count = sum(1 for r in results if r["status"] == "success")
            failed_count = len(results) - success_count

            return {
                "status": "completed",
                "total": len(results),
                "success": success_count,
                "failed": failed_count,
                "results": results,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"AfricasTalking bulk SMS send failed: {e}")
            return {
                "status": "failed",
                "total": len(phones),
                "success": 0,
                "failed": len(phones),
                "message": f"Request failed: {str(e)}",
            }

    def get_status(self, provider_reference: str) -> Dict[str, Any]:
        """
        Get SMS delivery status.
        Note: Not all providers support status queries.
        """
        # Most SMS providers don't support direct status queries
        # Status is available via webhook callbacks
        return {
            "provider_reference": provider_reference,
            "status": "unknown",
            "message": "SMS delivery status is available via webhook callbacks",
        }
