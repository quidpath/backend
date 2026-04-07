"""
Test suite for POS Service
Tests Stores, Terminals, Sessions, Orders, Payments, Returns, Promotions, Loyalty
"""
import uuid

import pytest
import requests
from rest_framework import status


@pytest.mark.django_db
class TestStoreEndpoints:
    """Test Store CRUD endpoints"""

    def test_list_stores_requires_auth(self, pos_url):
        """Test listing stores requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/stores/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_store_requires_auth(self, pos_url):
        """Test creating store requires authentication"""
        data = {
            "name": "Test Store",
            "location": "Test Location",
        }
        response = requests.post(f"{pos_url}/api/pos/stores/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_store_detail_requires_auth(self, pos_url):
        """Test retrieving store detail requires authentication"""
        store_id = str(uuid.uuid4())
        response = requests.get(f"{pos_url}/api/pos/stores/{store_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_store_requires_auth(self, pos_url):
        """Test updating store requires authentication"""
        store_id = str(uuid.uuid4())
        data = {"name": "Updated Store"}
        response = requests.patch(f"{pos_url}/api/pos/stores/{store_id}/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_store_requires_auth(self, pos_url):
        """Test deleting store requires authentication"""
        store_id = str(uuid.uuid4())
        response = requests.delete(f"{pos_url}/api/pos/stores/{store_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTerminalEndpoints:
    """Test Terminal endpoints"""

    def test_list_terminals_requires_auth(self, pos_url):
        """Test listing terminals requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/terminals/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_terminal_requires_auth(self, pos_url):
        """Test creating terminal requires authentication"""
        data = {
            "name": "Terminal 1",
            "store_id": str(uuid.uuid4()),
        }
        response = requests.post(f"{pos_url}/api/pos/terminals/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestSessionEndpoints:
    """Test POS Session endpoints"""

    def test_list_sessions_requires_auth(self, pos_url):
        """Test listing sessions requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/sessions/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_session_requires_auth(self, pos_url):
        """Test creating session requires authentication"""
        data = {
            "terminal_id": str(uuid.uuid4()),
            "opening_balance": "1000.00",
        }
        response = requests.post(f"{pos_url}/api/pos/sessions/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_close_session_requires_auth(self, pos_url):
        """Test closing session requires authentication"""
        session_id = str(uuid.uuid4())
        data = {"closing_balance": "1500.00"}
        response = requests.post(
            f"{pos_url}/api/pos/sessions/{session_id}/close/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrderEndpoints:
    """Test POS Order endpoints"""

    def test_list_orders_requires_auth(self, pos_url):
        """Test listing orders requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/orders/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_order_requires_auth(self, pos_url):
        """Test creating order requires authentication"""
        data = {
            "session_id": str(uuid.uuid4()),
            "items": [
                {
                    "product_id": str(uuid.uuid4()),
                    "quantity": 1,
                    "price": "100.00",
                }
            ],
        }
        response = requests.post(f"{pos_url}/api/pos/orders/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_order_detail_requires_auth(self, pos_url):
        """Test retrieving order detail requires authentication"""
        order_id = str(uuid.uuid4())
        response = requests.get(f"{pos_url}/api/pos/orders/{order_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_pay_order_requires_auth(self, pos_url):
        """Test paying order requires authentication"""
        order_id = str(uuid.uuid4())
        data = {
            "payment_method": "cash",
            "amount": "100.00",
        }
        response = requests.post(f"{pos_url}/api/pos/orders/{order_id}/pay/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestReturnEndpoints:
    """Test Return endpoints"""

    def test_list_returns_requires_auth(self, pos_url):
        """Test listing returns requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/returns/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_return_requires_auth(self, pos_url):
        """Test creating return requires authentication"""
        data = {
            "order_id": str(uuid.uuid4()),
            "items": [
                {
                    "product_id": str(uuid.uuid4()),
                    "quantity": 1,
                }
            ],
        }
        response = requests.post(f"{pos_url}/api/pos/returns/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPromotionEndpoints:
    """Test Promotion endpoints"""

    def test_list_promotions_requires_auth(self, pos_url):
        """Test listing promotions requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/promotions/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_promotion_requires_auth(self, pos_url):
        """Test creating promotion requires authentication"""
        data = {
            "name": "Test Promotion",
            "discount_type": "percentage",
            "discount_value": "10.00",
        }
        response = requests.post(f"{pos_url}/api/pos/promotions/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLoyaltyProgramEndpoints:
    """Test Loyalty Program endpoints"""

    def test_list_loyalty_programs_requires_auth(self, pos_url):
        """Test listing loyalty programs requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/loyalty-programs/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_loyalty_program_requires_auth(self, pos_url):
        """Test creating loyalty program requires authentication"""
        data = {
            "name": "Test Loyalty Program",
            "points_per_currency": "1.00",
        }
        response = requests.post(f"{pos_url}/api/pos/loyalty-programs/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLoyaltyCardEndpoints:
    """Test Loyalty Card endpoints"""

    def test_list_loyalty_cards_requires_auth(self, pos_url):
        """Test listing loyalty cards requires authentication"""
        response = requests.get(f"{pos_url}/api/pos/loyalty-cards/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_loyalty_card_requires_auth(self, pos_url):
        """Test creating loyalty card requires authentication"""
        data = {
            "program_id": str(uuid.uuid4()),
            "customer_id": str(uuid.uuid4()),
            "card_number": "CARD-001",
        }
        response = requests.post(f"{pos_url}/api/pos/loyalty-cards/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
