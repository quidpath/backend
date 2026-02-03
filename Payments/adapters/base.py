# Base payment adapter interface
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, Optional


class PaymentAdapter(ABC):
    """
    Base interface for payment gateway adapters.
    All payment adapters must implement this interface.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.

        Args:
            config: Dictionary containing provider-specific configuration
                   (API keys, secrets, endpoints, etc.)
        """
        self.config = config
        self.test_mode = config.get("test_mode", False)

    @abstractmethod
    def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        customer_reference: str,
        callback_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Initiate a payment request.

        Args:
            amount: Payment amount
            currency: Currency code (USD, KES, etc.)
            customer_reference: Customer reference (phone number for M-Pesa, email for card, etc.)
            callback_url: Webhook URL to receive payment status updates
            metadata: Additional metadata (invoice_id, customer_id, etc.)

        Returns:
            Dictionary with:
            - provider_reference: Provider's transaction ID
            - checkout_url: URL for redirect (if applicable)
            - status: Initial status
            - message: Status message
        """
        pass

    @abstractmethod
    def verify_webhook(
        self, payload: Dict[str, Any], headers: Dict[str, str], secret: str
    ) -> bool:
        """
        Verify webhook signature/authenticity.

        Args:
            payload: Webhook payload (JSON dict)
            headers: HTTP headers from webhook request
            secret: Webhook secret for verification

        Returns:
            True if webhook is valid, False otherwise
        """
        pass

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse webhook payload into standardized format.

        Args:
            payload: Raw webhook payload

        Returns:
            Dictionary with:
            - provider_reference: Provider's transaction ID
            - status: Payment status (success, failed, pending)
            - amount: Payment amount
            - currency: Currency code
            - metadata: Additional provider-specific data
        """
        pass

    @abstractmethod
    def get_payment_status(self, provider_reference: str) -> Dict[str, Any]:
        """
        Query payment status from provider.

        Args:
            provider_reference: Provider's transaction ID

        Returns:
            Dictionary with payment status information
        """
        pass

    def format_amount(self, amount: Decimal, currency: str) -> str:
        """
        Format amount according to provider requirements.
        Some providers require amounts in cents/smallest currency unit.

        Args:
            amount: Payment amount
            currency: Currency code

        Returns:
            Formatted amount string
        """
        # Default: return as string with 2 decimal places
        return str(amount.quantize(Decimal("0.01")))

    def format_phone(self, phone: str) -> str:
        """
        Format phone number according to provider requirements.

        Args:
            phone: Phone number (various formats)

        Returns:
            Formatted phone number
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
