# Flutterwave payment adapter (supports Card, M-Pesa, Mobile Money, Bank Transfer)
import hashlib
import hmac
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import requests

from .base import PaymentAdapter

logger = logging.getLogger(__name__)


class FlutterwaveAdapter(PaymentAdapter):
    """
    Flutterwave payment adapter.
    Supports Card, M-Pesa, Mobile Money, Bank Transfer, and other payment methods.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.encryption_key = config.get("encryption_key")
        self.public_key = config.get("public_key")  # Optional, for client-side
        self.secret_key = config.get("secret_key")  # Use client_secret as secret_key
        self.callback_url = config.get("callback_url", "")
        self.test_mode = config.get("test_mode", False)

        # Flutterwave API base URL
        self.base_url = "https://api.flutterwave.com/v3"

        if not self.client_id or not self.client_secret:
            raise ValueError("Flutterwave client_id and client_secret are required")

    def initiate_stk_push(
        self,
        msisdn: str,
        amount: float,
        currency: str,
        account_reference: str,
        transaction_desc: str,
        callback_url: str,
    ) -> Dict[str, Any]:
        """
        Initiate M-Pesa STK Push via Flutterwave.
        Flutterwave handles M-Pesa payments through their mobile money API.
        """
        try:
            # Format phone number (ensure it starts with country code)
            phone = self._format_phone(msisdn)

            # Convert amount to integer (Flutterwave uses smallest currency unit)
            amount_int = int(float(amount) * 100)

            # Generate unique transaction reference
            import uuid

            tx_ref = f"QUIDPATH-{uuid.uuid4().hex[:12]}"

            url = f"{self.base_url}/charges?type=mobile_money_mpesa"

            headers = {
                "Authorization": f"Bearer {self.client_secret}",
                "Content-Type": "application/json",
            }

            payload = {
                "phone_number": phone,
                "amount": amount_int,
                "currency": currency.upper(),
                "tx_ref": tx_ref,
                "email": "customer@quidpath.com",  # Required by Flutterwave
                "fullname": "Customer",  # Optional
                "meta": {
                    "invoice_id": account_reference,
                    "description": transaction_desc,
                    "account_reference": account_reference[:12],
                },
            }

            # Add callback URL if provided
            if callback_url:
                payload["callback_url"] = callback_url

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                response_data = data.get("data", {})
                return {
                    "checkout_request_id": response_data.get("flw_ref", tx_ref),
                    "merchant_request_id": tx_ref,
                    "response_code": "0",
                    "response_description": "STK Push initiated successfully",
                    "customer_message": "Please check your phone for payment prompt",
                    "full_response": data,
                    "provider_reference": tx_ref,
                    "status": "pending",
                }
            else:
                error_message = data.get("message", "Failed to initiate STK Push")
                logger.error(f"Flutterwave M-Pesa initiation failed: {error_message}")
                return {
                    "checkout_request_id": None,
                    "merchant_request_id": None,
                    "response_code": "1",
                    "response_description": error_message,
                    "customer_message": error_message,
                    "full_response": data,
                    "status": "failed",
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Flutterwave M-Pesa STK Push request failed: {e}")
            return {
                "checkout_request_id": None,
                "merchant_request_id": None,
                "response_code": "1",
                "response_description": str(e),
                "customer_message": "Failed to initiate payment. Please try again.",
                "status": "failed",
            }

    def handle_stk_callback(
        self, payload: Dict[str, Any], headers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle Flutterwave M-Pesa callback.
        """
        logger.info(f"Flutterwave M-Pesa callback received: {json.dumps(payload)}")

        event = payload.get("event", "")
        data = payload.get("data", {})

        if event == "charge.completed":
            status = data.get("status", "")
            if status == "successful":
                return {
                    "status": "success",
                    "checkout_request_id": data.get("flw_ref", ""),
                    "merchant_request_id": data.get("tx_ref", ""),
                    "amount": float(data.get("amount", 0)) / 100,
                    "mpesa_receipt_number": data.get("processor_response", {}).get(
                        "ReceiptNumber", ""
                    ),
                    "transaction_date": data.get("created_at", ""),
                    "phone_number": data.get("customer", {}).get("phone_number", ""),
                    "result_desc": "Payment successful",
                    "full_payload": payload,
                }
            else:
                return {
                    "status": "failed",
                    "checkout_request_id": data.get("flw_ref", ""),
                    "merchant_request_id": data.get("tx_ref", ""),
                    "result_code": "1",
                    "result_desc": data.get("processor_response", {}).get(
                        "ResponseDescription", "Payment failed"
                    ),
                    "full_payload": payload,
                }
        else:
            return {
                "status": "pending",
                "checkout_request_id": data.get("flw_ref", ""),
                "merchant_request_id": data.get("tx_ref", ""),
                "result_desc": f"Event: {event}",
                "full_payload": payload,
            }

    def initiate_card_payment(
        self,
        amount: float,
        currency: str,
        customer_email: str,
        callback_url: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Initiate card payment via Flutterwave.
        """
        try:
            # Convert amount to integer
            amount_int = int(float(amount) * 100)

            # Generate unique transaction reference
            import uuid

            tx_ref = metadata.get(
                "transaction_reference", f"QUIDPATH-{uuid.uuid4().hex[:12]}"
            )

            url = f"{self.base_url}/payments"

            headers = {
                "Authorization": f"Bearer {self.client_secret}",
                "Content-Type": "application/json",
            }

            payload = {
                "tx_ref": tx_ref,
                "amount": amount_int,
                "currency": currency.upper(),
                "redirect_url": callback_url,
                "payment_options": "card",
                "customer": {
                    "email": customer_email,
                    "name": metadata.get("customer_name", "Customer"),
                    "phone_number": metadata.get("phone_number", ""),
                },
                "customizations": {
                    "title": "Quidpath ERP Payment",
                    "description": metadata.get("description", "Payment"),
                    "logo": metadata.get("logo_url", ""),
                },
                "meta": metadata,
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                response_data = data.get("data", {})
                return {
                    "status": "success",
                    "redirect_url": response_data.get("link", ""),
                    "transaction_id": response_data.get("id", ""),
                    "transaction_reference": tx_ref,
                    "message": "Payment initiated successfully",
                    "full_response": data,
                }
            else:
                error_message = data.get("message", "Failed to initiate payment")
                logger.error(
                    f"Flutterwave card payment initiation failed: {error_message}"
                )
                return {
                    "status": "failed",
                    "redirect_url": None,
                    "transaction_id": None,
                    "transaction_reference": tx_ref,
                    "message": error_message,
                    "full_response": data,
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Flutterwave card payment request failed: {e}")
            return {
                "status": "failed",
                "redirect_url": None,
                "transaction_id": None,
                "message": f"Request failed: {str(e)}",
            }

    def handle_card_webhook(
        self, payload: Dict[str, Any], headers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle Flutterwave card payment webhook.
        """
        logger.info(f"Flutterwave card webhook received: {json.dumps(payload)}")

        # Verify webhook signature
        if not self.verify_webhook_signature(
            json.dumps(payload, sort_keys=True).encode("utf-8"), headers
        ):
            logger.error("Flutterwave webhook signature verification failed")
            raise ValueError("Webhook signature verification failed")

        event = payload.get("event", "")
        data = payload.get("data", {})

        tx_ref = data.get("tx_ref", "")
        transaction_id = str(data.get("id", ""))

        if event == "charge.completed":
            status = data.get("status", "")
            if status == "successful":
                return {
                    "status": "success",
                    "transaction_reference": tx_ref,
                    "gateway_transaction_id": transaction_id,
                    "amount": float(data.get("amount", 0)) / 100,
                    "currency": data.get("currency", "USD"),
                    "full_payload": payload,
                }
            else:
                return {
                    "status": "failed",
                    "transaction_reference": tx_ref,
                    "gateway_transaction_id": transaction_id,
                    "message": f"Transaction {status}",
                    "full_payload": payload,
                }
        else:
            return {
                "status": "pending",
                "transaction_reference": tx_ref,
                "gateway_transaction_id": transaction_id,
                "message": f"Event: {event}",
                "full_payload": payload,
            }

    def verify_webhook_signature(self, payload: bytes, headers: Dict[str, Any]) -> bool:
        """
        Verify Flutterwave webhook signature.
        Flutterwave uses SHA256 HMAC with the secret hash.
        """
        if not self.encryption_key:
            logger.warning(
                "No encryption key configured for Flutterwave webhook verification"
            )
            return True  # Skip verification if no key configured

        signature = headers.get("verif-hash") or headers.get("x-flw-signature")
        if not signature:
            logger.error("Flutterwave webhook signature header not found")
            return False

        # Generate expected signature
        expected_signature = hmac.new(
            self.encryption_key.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        if hmac.compare_digest(expected_signature, signature):
            return True
        else:
            logger.error(
                f"Flutterwave webhook signature mismatch. Expected: {expected_signature}, Got: {signature}"
            )
            return False

    def _format_phone(self, phone: str) -> str:
        """
        Format phone number for Flutterwave (254XXXXXXXXX format).
        """
        # Remove spaces, dashes, parentheses
        cleaned = (
            phone.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
            .replace("+", "")
        )

        # Add country code if missing (assume Kenya +254)
        if not cleaned.startswith("254"):
            if cleaned.startswith("0"):
                cleaned = "254" + cleaned[1:]
            else:
                cleaned = "254" + cleaned

        return cleaned

    def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        customer_reference: str,  # Phone for M-Pesa, email for card
        callback_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        payment_method: str = "card",  # 'card' or 'mpesa'
    ) -> Dict[str, Any]:
        """
        Unified payment initiation method.
        """
        if payment_method == "mpesa":
            return self.initiate_stk_push(
                msisdn=customer_reference,
                amount=float(amount),
                currency=currency,
                account_reference=(
                    metadata.get("invoice_id", "QUIDPATH") if metadata else "QUIDPATH"
                ),
                transaction_desc=(
                    metadata.get("description", "Payment") if metadata else "Payment"
                ),
                callback_url=callback_url,
            )
        else:
            return self.initiate_card_payment(
                amount=float(amount),
                currency=currency,
                customer_email=customer_reference,
                callback_url=callback_url,
                metadata=metadata or {},
            )
