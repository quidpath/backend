"""
Service to interact with the billing microservice.
All URLs match billing/billing_service/billing/urls.py exactly.
"""

import logging
from typing import Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BillingServiceClient:
    """Thin client to interact with the billing microservice"""

    def __init__(self):
        base = getattr(settings, "BILLING_SERVICE_URL", "http://billing-backend-dev:8002")
        self.base_url = base.rstrip("/") + "/api/billing"
        self.service_secret = getattr(settings, "BILLING_SERVICE_SECRET", "")
        self.timeout = 30

    def _get_headers(self) -> Dict:
        headers = {"Content-Type": "application/json"}
        if self.service_secret:
            headers["X-Service-Key"] = self.service_secret
        return headers

    def get_plans(self, plan_type: str = "individual") -> Optional[List[Dict]]:
        """
        Fetch plans from billing service.
        plan_type: 'individual' or 'organization'
        """
        try:
            response = requests.get(
                f"{self.base_url}/plans/",
                params={"type": plan_type},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("plans") or data.get("plans", [])
            logger.error("Failed to fetch plans: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error fetching plans: %s", e, exc_info=True)
            return None

    def initiate_payment(
        self,
        entity_id: str,
        entity_name: str,
        plan_id: str,
        phone_number: str,
        payment_type: str = "individual",
    ) -> Optional[Dict]:
        """
        Initiate M-Pesa payment via billing service simplified endpoint.
        Accepts plan_id directly — billing service creates subscription + invoice internally.
        """
        try:
            response = requests.post(
                f"{self.base_url}/payments/initiate/",
                json={
                    "corporate_id": entity_id,
                    "corporate_name": entity_name,
                    "plan_id": plan_id,
                    "phone_number": phone_number,
                    "subscription_type": payment_type,
                },
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("data") or data
            logger.error("Payment initiation failed: %s %s", response.status_code, response.text)
            return {"success": False, "message": response.text}
        except Exception as e:
            logger.error("Error initiating payment: %s", e, exc_info=True)
            return {"success": False, "message": str(e)}

    def get_subscription_status(self, entity_id: str) -> Optional[Dict]:
        """Get subscription status from billing service."""
        try:
            response = requests.post(
                f"{self.base_url}/subscriptions/status/",
                json={"corporate_id": entity_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Subscription status failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error getting subscription status: %s", e, exc_info=True)
            return None

    def check_access(self, entity_id: str) -> Optional[Dict]:
        """Check if entity has active trial or subscription."""
        try:
            response = requests.post(
                f"{self.base_url}/access/check/",
                json={"corporate_id": entity_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Access check failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error checking access: %s", e, exc_info=True)
            return None

    def create_trial(
        self, corporate_id: str, corporate_name: str = "", plan_tier: str = "starter",
        phone_number: str = "",
    ) -> Optional[Dict]:
        """Create a trial subscription in billing service."""
        try:
            payload = {
                "corporate_id": corporate_id,
                "corporate_name": corporate_name,
                "plan_tier": plan_tier,
            }
            if phone_number:
                payload["phone_number"] = phone_number
            response = requests.post(
                f"{self.base_url}/trials/create/",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code in (200, 201):
                return response.json()
            logger.error("Trial creation failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error creating trial: %s", e, exc_info=True)
            return None

    def get_payment_status(self, payment_id: str, corporate_id: str) -> Optional[Dict]:
        """Get payment status from billing service."""
        try:
            response = requests.post(
                f"{self.base_url}/payments/status/",
                json={"payment_id": payment_id, "corporate_id": corporate_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Payment status failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error getting payment status: %s", e, exc_info=True)
            return None

    def get_trial_status(self, corporate_id: str) -> Optional[Dict]:
        """Get trial status from billing service."""
        try:
            response = requests.post(
                f"{self.base_url}/trials/status/",
                json={"corporate_id": corporate_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Trial status failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error getting trial status: %s", e, exc_info=True)
            return None

    def list_invoices(self, corporate_id: str) -> Optional[Dict]:
        """List invoices for a corporate from billing service."""
        try:
            response = requests.post(
                f"{self.base_url}/invoices/",
                json={"corporate_id": corporate_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("List invoices failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error listing invoices: %s", e, exc_info=True)
            return None

    def create_subscription(
        self,
        corporate_id: str,
        corporate_name: str,
        plan_tier: str,
        billing_cycle: str = "monthly",
        additional_users: int = 0,
        promotion_code: Optional[str] = None,
    ) -> Optional[Dict]:
        """Create a paid subscription in billing service."""
        try:
            response = requests.post(
                f"{self.base_url}/subscriptions/create/",
                json={
                    "corporate_id": corporate_id,
                    "corporate_name": corporate_name,
                    "plan_tier": plan_tier,
                    "billing_cycle": billing_cycle,
                    "additional_users": additional_users,
                    "promotion_code": promotion_code,
                },
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code in (200, 201):
                return response.json()
            logger.error("Subscription creation failed: %s %s", response.status_code, response.text)
            return {"success": False, "message": response.text}
        except Exception as e:
            logger.error("Error creating subscription: %s", e, exc_info=True)
            return {"success": False, "message": str(e)}

    def initiate_invoice_payment(
        self,
        invoice_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        payment_method: str = "mpesa",
        customer_email: str = "",
        customer_phone: Optional[str] = None,
    ) -> Optional[Dict]:
        """Initiate payment for an existing invoice."""
        try:
            data: Dict = {"payment_method": payment_method, "customer_email": customer_email}
            if invoice_id:
                data["invoice_id"] = invoice_id
            if invoice_number:
                data["invoice_number"] = invoice_number
            if customer_phone:
                data["customer_phone"] = customer_phone
            response = requests.post(
                f"{self.base_url}/payments/initiate/",
                json=data,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Invoice payment initiation failed: %s %s", response.status_code, response.text)
            return {"success": False, "message": response.text}
        except Exception as e:
            logger.error("Error initiating invoice payment: %s", e, exc_info=True)
            return {"success": False, "message": str(e)}

    def get_payment_history(self, corporate_id: str) -> Optional[Dict]:
        """Get payment history for a corporate from billing service."""
        try:
            response = requests.post(
                f"{self.base_url}/payments/history/",
                json={"corporate_id": corporate_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Payment history failed: %s %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.error("Error getting payment history: %s", e, exc_info=True)
            return None

    def validate_promotion(self, promotion_code: str, amount: float, plan_tier: str) -> Optional[Dict]:
        """Validate a promotion code."""
        try:
            response = requests.post(
                f"{self.base_url}/promotions/validate/",
                json={"promotion_code": promotion_code, "amount": amount, "plan_tier": plan_tier},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Promotion validation failed: %s %s", response.status_code, response.text)
            return {"success": False, "message": response.text}
        except Exception as e:
            logger.error("Error validating promotion: %s", e, exc_info=True)
            return {"success": False, "message": str(e)}

    def admin_get_corporate_summary(self, corporate_id: str) -> Optional[Dict]:
        """Get comprehensive billing summary for admin panel."""
        try:
            response = requests.post(
                f"{self.base_url}/admin/corporate-summary/",
                json={"corporate_id": corporate_id},
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Admin corporate summary failed: %s %s", response.status_code, response.text)
            return {"success": False, "message": response.text}
        except Exception as e:
            logger.error("Error getting admin corporate summary: %s", e, exc_info=True)
            return {"success": False, "message": str(e)}


# Singleton instance
billing_service = BillingServiceClient()
