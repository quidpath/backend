"""
Billing Service Client for ERP Integration
"""

import os
from typing import Any, Dict, Optional

import requests


def _get_billing_base_url(base_url: Optional[str] = None) -> str:
    """Resolve billing service base URL (with /api/billing) from arg, Django settings, or env."""
    if base_url:
        url = base_url
    else:
        try:
            from django.conf import settings
            url = getattr(settings, "BILLING_SERVICE_URL", None) or ""
        except Exception:
            url = ""
        if not url:
            url = os.environ.get("BILLING_SERVICE_URL", "http://localhost:8002/api/billing")
    url = url.rstrip("/")
    if not url.endswith("api/billing"):
        url = url + "/api/billing"
    return url


class BillingServiceClient:
    """
    Client to communicate with the billing microservice
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = _get_billing_base_url(base_url)

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to billing service"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {}
        service_secret = os.environ.get("BILLING_SERVICE_SECRET")
        if service_secret:
            headers["X-Service-Key"] = service_secret
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=data, headers=headers, timeout=30)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=30)

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Billing service error: {str(e)}"}

    def create_trial(
        self, corporate_id: str, corporate_name: str = "", plan_tier: str = "starter"
    ) -> Dict:
        """Create 30-day free trial"""
        return self._make_request(
            "POST",
            "trials/create/",
            {
                "corporate_id": corporate_id,
                "corporate_name": corporate_name,
                "plan_tier": plan_tier,
            },
        )

    def get_trial_status(self, corporate_id: str) -> Dict:
        """Get trial status"""
        return self._make_request(
            "POST",
            "trials/status/",
            {
                "corporate_id": corporate_id,
            },
        )

    def create_subscription(
        self,
        corporate_id: str,
        corporate_name: str,
        plan_tier: str,
        billing_cycle: str = "monthly",
        additional_users: int = 0,
        promotion_code: Optional[str] = None,
    ) -> Dict:
        """Create subscription"""
        return self._make_request(
            "POST",
            "subscriptions/create/",
            {
                "corporate_id": corporate_id,
                "corporate_name": corporate_name,
                "plan_tier": plan_tier,
                "billing_cycle": billing_cycle,
                "additional_users": additional_users,
                "promotion_code": promotion_code,
            },
        )

    def get_subscription_status(self, corporate_id: str) -> Dict:
        """Get subscription status"""
        return self._make_request(
            "POST",
            "subscriptions/status/",
            {
                "corporate_id": corporate_id,
            },
        )

    def validate_promotion(
        self, promotion_code: str, amount: float, plan_tier: str
    ) -> Dict:
        """Validate promotion code"""
        return self._make_request(
            "POST",
            "promotions/validate/",
            {
                "promotion_code": promotion_code,
                "amount": amount,
                "plan_tier": plan_tier,
            },
        )

    def list_invoices(self, corporate_id: str) -> Dict:
        """List invoices"""
        return self._make_request(
            "POST",
            "invoices/",
            {
                "corporate_id": corporate_id,
            },
        )

    def initiate_payment(
        self,
        invoice_id: Optional[str] = None,
        invoice_number: Optional[str] = None,
        payment_method: str = "mpesa",
        customer_email: str = "",
        customer_phone: Optional[str] = None,
    ) -> Dict:
        """Initiate payment"""
        data = {
            "payment_method": payment_method,
            "customer_email": customer_email,
        }
        if invoice_id:
            data["invoice_id"] = invoice_id
        if invoice_number:
            data["invoice_number"] = invoice_number
        if customer_phone:
            data["customer_phone"] = customer_phone

        return self._make_request("POST", "payments/initiate/", data)

    def list_plans(self) -> Dict:
        """List all available plans"""
        return self._make_request("GET", "plans/", {})

    def check_access(self, corporate_id: str) -> Dict:
        """Check if corporate has access to Quidpath (active trial/subscription)"""
        return self._make_request(
            "POST",
            "access/check/",
            {
                "corporate_id": corporate_id,
            },
        )

    # Admin methods
    def admin_list_trials(self, status: Optional[str] = None, limit: int = 100) -> Dict:
        """List all trials (admin only)"""
        admin_base = self.base_url.replace("/api/billing", "/api/admin/billing")
        url = f"{admin_base}/trials/"
        params = {"limit": limit}
        if status:
            params["status"] = status
        try:
            import requests

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def admin_list_subscriptions(
        self, status: Optional[str] = None, limit: int = 100
    ) -> Dict:
        """List all subscriptions (admin only)"""
        admin_base = self.base_url.replace("/api/billing", "/api/admin/billing")
        url = f"{admin_base}/subscriptions/"
        params = {"limit": limit}
        if status:
            params["status"] = status
        try:
            import requests

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def admin_list_invoices(
        self, status: Optional[str] = None, limit: int = 100
    ) -> Dict:
        """List all invoices (admin only)"""
        admin_base = self.base_url.replace("/api/billing", "/api/admin/billing")
        url = f"{admin_base}/invoices/"
        params = {"limit": limit}
        if status:
            params["status"] = status
        try:
            import requests

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def admin_list_payments(
        self, status: Optional[str] = None, limit: int = 100
    ) -> Dict:
        """List all payments (admin only)"""
        admin_base = self.base_url.replace("/api/billing", "/api/admin/billing")
        url = f"{admin_base}/payments/"
        params = {"limit": limit}
        if status:
            params["status"] = status
        try:
            import requests

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def admin_get_stats(self) -> Dict:
        """Get billing statistics (admin only)"""
        admin_base = self.base_url.replace("/api/billing", "/api/admin/billing")
        url = f"{admin_base}/stats/"
        try:
            import requests

            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def admin_get_corporate_summary(self, corporate_id: str) -> Dict:
        """Get billing summary for a corporate (admin only)"""
        admin_base = self.base_url.replace("/api/billing", "/api/admin/billing")
        url = f"{admin_base}/corporate/{corporate_id}/summary/"
        headers = {}
        service_secret = os.environ.get("BILLING_SERVICE_SECRET")
        if service_secret:
            headers["X-Service-Key"] = service_secret
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Error: {str(e)}"}
