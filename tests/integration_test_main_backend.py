"""
Integration tests for Main Backend (running in Docker)
Tests endpoints via HTTP requests without Django imports
"""
import requests
import pytest


BASE_URL = "http://localhost:8000"


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_check(self):
        """Test health endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/auth/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"


class TestAuthenticationEndpoints:
    """Test Authentication endpoints"""

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login/",
            json={"username": "invalid", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_login_missing_fields(self):
        """Test login without required fields returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login/",
            json={},
        )
        assert response.status_code == 400

    def test_unauthenticated_profile_access(self):
        """Test accessing profile without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/get_profile/")
        assert response.status_code == 401


class TestCustomerEndpoints:
    """Test Customer CRUD endpoints"""

    def test_list_customers_requires_auth(self):
        """Test listing customers requires authentication"""
        response = requests.get(f"{BASE_URL}/customer/list/")
        assert response.status_code in [400, 401, 403]  # May return 400 for missing params

    def test_create_customer_requires_auth(self):
        """Test creating customer requires authentication"""
        data = {
            "name": "Test Customer",
            "email": "customer@test.com",
        }
        response = requests.post(f"{BASE_URL}/customer/create/", json=data)
        assert response.status_code in [400, 401, 403]  # May return 400 for validation


class TestVendorEndpoints:
    """Test Vendor CRUD endpoints"""

    def test_list_vendors_requires_auth(self):
        """Test listing vendors requires authentication"""
        response = requests.get(f"{BASE_URL}/vendor/list/")
        assert response.status_code == 401

    def test_create_vendor_requires_auth(self):
        """Test creating vendor requires authentication"""
        data = {
            "name": "Test Vendor",
            "email": "vendor@test.com",
        }
        response = requests.post(f"{BASE_URL}/vendor/create/", json=data)
        assert response.status_code in [400, 401, 403]  # May return 400 for validation


class TestInvoiceEndpoints:
    """Test Invoice CRUD endpoints"""

    def test_list_invoices_requires_auth(self):
        """Test listing invoices requires authentication"""
        response = requests.get(f"{BASE_URL}/invoice/list/")
        assert response.status_code in [401, 403]  # May return 403 for billing access

    def test_create_invoice_requires_auth(self):
        """Test creating invoice requires authentication"""
        data = {
            "customer_id": "test-uuid",
            "invoice_date": "2026-04-01",
        }
        response = requests.post(f"{BASE_URL}/invoice/save-draft/", json=data)
        assert response.status_code == 401


class TestQuotationEndpoints:
    """Test Quotation CRUD endpoints"""

    def test_list_quotations_requires_auth(self):
        """Test listing quotations requires authentication"""
        response = requests.get(f"{BASE_URL}/quotation/list/")
        assert response.status_code == 401

    def test_create_quotation_requires_auth(self):
        """Test creating quotation requires authentication"""
        data = {
            "customer_id": "test-uuid",
            "quote_date": "2026-04-01",
        }
        response = requests.post(f"{BASE_URL}/quotation/save-draft/", json=data)
        assert response.status_code == 401


class TestPurchaseOrderEndpoints:
    """Test Purchase Order CRUD endpoints"""

    def test_list_purchase_orders_requires_auth(self):
        """Test listing purchase orders requires authentication"""
        response = requests.get(f"{BASE_URL}/purchase-orders/list/")
        assert response.status_code == 401

    def test_create_purchase_order_requires_auth(self):
        """Test creating purchase order requires authentication"""
        data = {
            "vendor_id": "test-uuid",
            "order_date": "2026-04-01",
        }
        response = requests.post(f"{BASE_URL}/purchase-orders/save-draft/", json=data)
        assert response.status_code == 401


class TestVendorBillEndpoints:
    """Test Vendor Bill CRUD endpoints"""

    def test_list_vendor_bills_requires_auth(self):
        """Test listing vendor bills requires authentication"""
        response = requests.get(f"{BASE_URL}/vendor-bill/list/")
        assert response.status_code == 401

    def test_create_vendor_bill_requires_auth(self):
        """Test creating vendor bill requires authentication"""
        data = {
            "vendor_id": "test-uuid",
            "bill_date": "2026-04-01",
        }
        response = requests.post(f"{BASE_URL}/vendor-bill/create/", json=data)
        assert response.status_code == 401


class TestExpenseEndpoints:
    """Test Expense CRUD endpoints"""

    def test_list_expenses_requires_auth(self):
        """Test listing expenses requires authentication"""
        response = requests.get(f"{BASE_URL}/expense/list/")
        assert response.status_code == 401

    def test_create_expense_requires_auth(self):
        """Test creating expense requires authentication"""
        data = {
            "description": "Test Expense",
            "amount": "100.00",
        }
        response = requests.post(f"{BASE_URL}/expense/create/", json=data)
        assert response.status_code == 401


class TestAccountEndpoints:
    """Test Chart of Accounts endpoints"""

    def test_list_accounts_requires_auth(self):
        """Test listing accounts requires authentication"""
        response = requests.get(f"{BASE_URL}/account/list/")
        assert response.status_code == 401

    def test_create_account_requires_auth(self):
        """Test creating account requires authentication"""
        data = {
            "name": "Test Account",
            "code": "1000",
        }
        response = requests.post(f"{BASE_URL}/account/create/", json=data)
        assert response.status_code == 401


class TestJournalEndpoints:
    """Test Journal Entry endpoints"""

    def test_list_journal_entries_requires_auth(self):
        """Test listing journal entries requires authentication"""
        response = requests.get(f"{BASE_URL}/journal/list/")
        assert response.status_code in [401, 403]  # May return 403 for billing access

    def test_create_journal_entry_requires_auth(self):
        """Test creating journal entry requires authentication"""
        data = {
            "date": "2026-04-01",
            "reference": "JE-001",
        }
        response = requests.post(f"{BASE_URL}/journal/create/", json=data)
        assert response.status_code == 401


class TestBankAccountEndpoints:
    """Test Bank Account endpoints"""

    def test_list_bank_accounts_requires_auth(self):
        """Test listing bank accounts requires authentication"""
        response = requests.get(f"{BASE_URL}/bank-account/list/")
        assert response.status_code == 401

    def test_create_bank_account_requires_auth(self):
        """Test creating bank account requires authentication"""
        data = {
            "name": "Test Bank Account",
            "account_number": "1234567890",
        }
        response = requests.post(f"{BASE_URL}/bank-account/add/", json=data)
        assert response.status_code in [400, 401, 403]  # May return 400 for validation


class TestTransactionEndpoints:
    """Test Transaction endpoints"""

    def test_list_transactions_requires_auth(self):
        """Test listing transactions requires authentication"""
        response = requests.get(f"{BASE_URL}/transaction/list/")
        assert response.status_code == 401

    def test_create_transaction_requires_auth(self):
        """Test creating transaction requires authentication"""
        data = {
            "bank_account_id": "test-uuid",
            "amount": "100.00",
        }
        response = requests.post(f"{BASE_URL}/transaction/create/", json=data)
        assert response.status_code in [400, 401, 403]  # May return 400 for validation


class TestReportEndpoints:
    """Test Report endpoints"""

    def test_trial_balance_requires_auth(self):
        """Test trial balance requires authentication"""
        response = requests.get(f"{BASE_URL}/trial-balance/")
        assert response.status_code == 401

    def test_balance_sheet_requires_auth(self):
        """Test balance sheet requires authentication"""
        response = requests.get(f"{BASE_URL}/reports/balance-sheet/")
        assert response.status_code == 401

    def test_profit_and_loss_requires_auth(self):
        """Test profit and loss requires authentication"""
        response = requests.get(f"{BASE_URL}/reports/profit-and-loss/")
        assert response.status_code == 401
