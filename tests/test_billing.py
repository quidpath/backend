"""
Test suite for Billing Service
Tests Plans, Subscriptions, Payments, Trials, Invoices
"""
import uuid
from decimal import Decimal

import pytest
import requests
from rest_framework import status


@pytest.mark.django_db
class TestBillingPlansEndpoints:
    """Test Billing Plans endpoints"""

    def test_list_plans(self, billing_url):
        """Test listing subscription plans"""
        response = requests.get(f"{billing_url}/api/billing/plans/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list) or "results" in response.json()

    def test_get_plan_detail(self, billing_url):
        """Test retrieving single plan"""
        # First get list of plans
        list_response = requests.get(f"{billing_url}/api/billing/plans/")
        plans = list_response.json()
        
        if isinstance(plans, dict) and "results" in plans:
            plans = plans["results"]
        
        if plans:
            plan_id = plans[0]["id"]
            response = requests.get(f"{billing_url}/api/billing/plans/{plan_id}/")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["id"] == plan_id


@pytest.mark.django_db
class TestBillingSubscriptionEndpoints:
    """Test Subscription endpoints"""

    def test_subscribe_requires_auth(self, billing_url):
        """Test subscription endpoint requires authentication"""
        data = {
            "plan_id": str(uuid.uuid4()),
            "payment_method": "paystack",
        }
        response = requests.post(f"{billing_url}/api/billing/subscribe/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_check_billing_status_requires_auth(self, billing_url):
        """Test billing status check requires authentication"""
        response = requests.get(f"{billing_url}/api/billing/status/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBillingPaymentEndpoints:
    """Test Payment endpoints"""

    def test_initiate_payment_requires_auth(self, billing_url):
        """Test payment initiation requires authentication"""
        data = {
            "amount": "1000.00",
            "payment_method": "paystack",
        }
        response = requests.post(
            f"{billing_url}/api/billing/payment/initiate/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBillingInvoiceEndpoints:
    """Test Billing Invoice endpoints"""

    def test_list_invoices_requires_auth(self, billing_url):
        """Test listing invoices requires authentication"""
        response = requests.get(f"{billing_url}/api/billing/invoices/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBillingPromotionEndpoints:
    """Test Promotion validation endpoints"""

    def test_validate_promotion_requires_auth(self, billing_url):
        """Test promotion validation requires authentication"""
        data = {"code": "TESTCODE"}
        response = requests.post(
            f"{billing_url}/api/billing/promotion/validate/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBillingAdminEndpoints:
    """Test Admin Billing endpoints"""

    def test_corporate_billing_status_requires_admin(self, billing_url):
        """Test corporate billing status requires admin auth"""
        corporate_id = str(uuid.uuid4())
        response = requests.get(
            f"{billing_url}/api/admin/billing/corporate/{corporate_id}/status/"
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.django_db
class TestBillingTrialEndpoints:
    """Test Trial endpoints"""

    def test_start_trial_requires_auth(self, billing_url):
        """Test starting trial requires authentication"""
        data = {"plan_id": str(uuid.uuid4())}
        response = requests.post(f"{billing_url}/api/billing/trial/start/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
