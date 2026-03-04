"""
Service to interact with the billing microservice
"""

import logging
import requests
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class BillingServiceClient:
    """Client to interact with the billing microservice"""
    
    def __init__(self):
        self.base_url = getattr(settings, "BILLING_SERVICE_URL", "http://billing-backend-dev:8002")
        self.api_key = getattr(settings, "BILLING_SERVICE_API_KEY", "")
        self.timeout = 30
    
    def _get_headers(self) -> Dict:
        """Get headers for API requests"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def get_plans(self, plan_type: str = "individual") -> Optional[List[Dict]]:
        """
        Get subscription plans from billing service
        
        Args:
            plan_type: 'individual' or 'organization'
            
        Returns:
            List of plans or None if error
        """
        try:
            url = f"{self.base_url}/api/billing/unified/plans/"
            params = {"type": plan_type}
            
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Fetched {data.get('count', 0)} {plan_type} plans from billing service")
                return data.get("plans", [])
            else:
                logger.error(f"Failed to fetch plans: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching plans from billing service: {str(e)}", exc_info=True)
            return None
    
    def initiate_payment(
        self,
        entity_id: str,
        entity_name: str,
        plan_id: str,
        phone_number: str,
        payment_type: str = "individual"
    ) -> Optional[Dict]:
        """
        Initiate payment through billing service
        
        Args:
            entity_id: User or organization ID
            entity_name: User or organization name
            plan_id: Plan ID to subscribe to
            phone_number: M-Pesa phone number
            payment_type: 'individual' or 'organization'
            
        Returns:
            Payment response or None if error
        """
        try:
            url = f"{self.base_url}/api/billing/unified/payments/initiate/"
            
            payload = {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "plan_id": plan_id,
                "phone_number": phone_number,
                "payment_type": payment_type,
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payment initiated for {entity_name}: {data.get('payment_id')}")
                return data
            else:
                logger.error(f"Failed to initiate payment: {response.status_code} - {response.text}")
                return {"success": False, "message": response.text}
                
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
            return {"success": False, "message": str(e)}
    
    def get_subscription_status(self, entity_id: str) -> Optional[Dict]:
        """
        Get subscription status from billing service
        
        Args:
            entity_id: User or organization ID
            
        Returns:
            Subscription status or None if error
        """
        try:
            url = f"{self.base_url}/api/billing/unified/subscriptions/status/{entity_id}/"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Subscription status for {entity_id}: {data.get('status')}")
                return data
            else:
                logger.error(f"Failed to get subscription status: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting subscription status: {str(e)}", exc_info=True)
            return None
    
    def get_payment_status(self, payment_id: str) -> Optional[Dict]:
        """
        Get payment status from billing service
        
        Args:
            payment_id: Payment ID
            
        Returns:
            Payment status or None if error
        """
        try:
            url = f"{self.base_url}/api/billing/unified/payments/status/{payment_id}/"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payment status for {payment_id}: {data.get('status')}")
                return data
            else:
                logger.error(f"Failed to get payment status: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}", exc_info=True)
            return None


# Singleton instance
billing_service = BillingServiceClient()
