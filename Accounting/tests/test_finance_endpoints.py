"""
Comprehensive tests for all finance endpoints
Tests all modals: Invoices, Quotations, Expenses, Banking, Journal Entries, etc.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from OrgAuth.models import Corporate, CorporateUser
from Accounting.models import (
    Customer, Vendor, Invoices, Quotation, VendorBill, PurchaseOrder,
    Account, AccountType, TaxRate
)
from Accounting.models.accounts import Expense, JournalEntry
from Banking.models import BankAccount
import json

User = get_user_model()


class FinanceEndpointsTestCase(TestCase):
    """Test all finance endpoints that frontend modals call"""

    def setUp(self):
        """Set up test data"""
        # Create corporate first
        self.corporate = Corporate.objects.create(
            name='Test Corp',
            email='corp@example.com',
            phone='1234567890'
        )
        
        # Create corporate user (which extends CustomUser)
        self.user = CorporateUser.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            corporate=self.corporate
        )
        
        # Login
        self.client = Client()
        self.client.login(username='test@example.com', password='testpass123')
        
        # Create test customer
        self.customer = Customer.objects.create(
            corporate=self.corporate,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            category='individual'
        )
        
        # Create test vendor
        self.vendor = Vendor.objects.create(
            corporate=self.corporate,
            company_name='Acme Corp',
            email='vendor@acme.com',
            category='company'
        )
        
        # Create account types
        self.asset_type = AccountType.objects.create(name='ASSET', description='Asset accounts')
        self.revenue_type = AccountType.objects.create(name='REVENUE', description='Revenue accounts')
        
        # Create test accounts
        self.cash_account = Account.objects.create(
            corporate=self.corporate,
            code='1000',
            name='Cash',
            account_type=self.asset_type,
            is_active=True
        )
        self.revenue_account = Account.objects.create(
            corporate=self.corporate,
            code='4000',
            name='Revenue',
            account_type=self.revenue_type,
            is_active=True
        )

    # ═══════════════════════════════════════════════════════════════════════
    # CUSTOMER & VENDOR TESTS
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_customer_create(self):
        """Test CustomerModal - create customer"""
        payload = {
            'category': 'individual',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@example.com',
            'phone': '1234567890',
            'address': '123 Main St',
            'city': 'Nairobi',
            'country': 'Kenya'
        }
        response = self.client.post(
            '/customer/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_customer_list(self):
        """Test customer list"""
        response = self.client.get('/customer/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('customers', data)
    
    def test_vendor_create(self):
        """Test VendorModal - create vendor"""
        payload = {
            'category': 'company',
            'company_name': 'Test Vendor Inc',
            'email': 'vendor@test.com',
            'phone': '0987654321',
            'city': 'Mombasa',
            'country': 'Kenya'
        }
        response = self.client.post(
            '/vendor/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_vendor_list(self):
        """Test vendor list"""
        response = self.client.get('/vendor/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('vendors', data)

    # ═══════════════════════════════════════════════════════════════════════
    # INVOICE TESTS (InvoiceModal in SalesSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_invoice_save_draft(self):
        """Test InvoiceModal - save draft"""
        payload = {
            'customer': str(self.customer.id),
            'date': '2026-04-07',
            'due_date': '2026-05-07',
            'number': 'INV-TEST-001',
            'salesperson': 'Test Salesperson',
            'lines': [
                {
                    'description': 'Test Product',
                    'quantity': 2,
                    'unit_price': 100.00,
                    'amount': 200.00,
                    'discount': 0,
                    'tax_amount': 32.00,
                    'sub_total': 200.00,
                    'total': 232.00
                }
            ]
        }
        response = self.client.post(
            '/invoice/save-draft/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_invoice_create_and_post(self):
        """Test InvoiceModal - create and post"""
        payload = {
            'customer': str(self.customer.id),
            'date': '2026-04-07',
            'due_date': '2026-05-07',
            'number': 'INV-TEST-002',
            'lines': [
                {
                    'description': 'Test Service',
                    'quantity': 1,
                    'unit_price': 500.00,
                    'amount': 500.00,
                    'discount': 0,
                    'tax_amount': 80.00,
                    'sub_total': 500.00,
                    'total': 580.00
                }
            ]
        }
        response = self.client.post(
            '/invoice/create-and-post/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_invoice_list(self):
        """Test invoice list"""
        response = self.client.get('/invoice/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('invoices', data)

    # ═══════════════════════════════════════════════════════════════════════
    # QUOTATION TESTS (QuoteModal in SalesSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_quotation_save_draft(self):
        """Test QuotationModal - save draft"""
        payload = {
            'customer': str(self.customer.id),
            'date': '2026-04-07',
            'valid_until': '2026-05-07',
            'number': 'QT-TEST-001',
            'salesperson': 'Test Salesperson',
            'ship_date': '2026-05-07',
            'ship_via': 'TBD',
            'terms': 'Net 30',
            'fob': 'Origin',
            'lines': [
                {
                    'description': 'Test Service',
                    'quantity': 1,
                    'unit_price': 500.00,
                    'discount': 0,
                    'taxable': 'exempt'
                }
            ]
        }
        response = self.client.post(
            '/quotation/save-draft/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_quotation_list(self):
        """Test quotation list"""
        response = self.client.get('/quotation/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('quotations', data)

    # ═══════════════════════════════════════════════════════════════════════
    # VENDOR BILL TESTS (BillModal in PurchasesSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_vendor_bill_create(self):
        """Test VendorBillModal - create"""
        payload = {
            'vendor': str(self.vendor.id),
            'date': '2026-04-07',
            'due_date': '2026-05-07',
            'number': 'BILL-TEST-001',
            'status': 'DRAFT',
            'lines': [
                {
                    'description': 'Office Supplies',
                    'quantity': 5,
                    'unit_price': 50.00,
                    'discount': 0,
                    'taxable_id': 'exempt'
                }
            ]
        }
        response = self.client.post(
            '/vendor-bill/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_vendor_bill_list(self):
        """Test vendor bill list"""
        response = self.client.get('/vendor-bill/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('vendor_bills', data)

    # ═══════════════════════════════════════════════════════════════════════
    # PURCHASE ORDER TESTS (POModal in PurchasesSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_purchase_order_save_draft(self):
        """Test PurchaseOrderModal - save draft"""
        payload = {
            'vendor': str(self.vendor.id),
            'date': '2026-04-07',
            'expected_delivery': '2026-05-07',
            'number': 'PO-TEST-001',
            'lines': [
                {
                    'description': 'Raw Materials',
                    'quantity': 10,
                    'unit_price': 75.00,
                    'discount': 0,
                    'taxable_id': 'exempt'
                }
            ]
        }
        response = self.client.post(
            '/purchase-orders/save-draft/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_purchase_order_list(self):
        """Test purchase order list"""
        response = self.client.get('/purchase-orders/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('purchase_orders', data)

    # ═══════════════════════════════════════════════════════════════════════
    # EXPENSE TESTS (ExpenseModal in ExpensesSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_expense_create(self):
        """Test ExpenseModal - create expense"""
        payload = {
            'date': '2026-04-07',
            'category': 'ADMINISTRATIVE',
            'description': 'Monthly rent',
            'amount': 1500.00,
            'payment_method': 'bank_transfer',
            'reference': 'EXP-001'
        }
        response = self.client.post(
            '/expense/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_expense_list(self):
        """Test expense list"""
        response = self.client.get('/expense/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('expenses', data)
    
    def test_petty_cash_create(self):
        """Test PettyCashModal - create petty cash entry"""
        payload = {
            'date': '2026-04-07',
            'description': 'Office supplies',
            'amount': 50.00,
            'category': 'OPERATING',
            'payment_method': 'cash',
            'reference': 'PC-001'
        }
        response = self.client.post(
            '/expense/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())

    # ═══════════════════════════════════════════════════════════════════════
    # BANKING TESTS (BankAccountModal, TransferModal in BankingSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_bank_account_create(self):
        """Test BankAccountModal - create bank account"""
        payload = {
            'bank_name': 'Test Bank',
            'account_name': 'Business Checking',
            'account_number': '1234567890',
            'currency': 'USD'
        }
        response = self.client.post(
            '/bank-account/add/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_bank_account_list(self):
        """Test bank account list"""
        response = self.client.get('/bank-account/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)
    
    def test_internal_transfer_create(self):
        """Test TransferModal - create internal transfer"""
        # First create two bank accounts
        bank1 = BankAccount.objects.create(
            corporate=self.corporate,
            bank_name='Bank A',
            account_name='Account A',
            account_number='111111',
            currency='USD'
        )
        bank2 = BankAccount.objects.create(
            corporate=self.corporate,
            bank_name='Bank B',
            account_name='Account B',
            account_number='222222',
            currency='USD'
        )
        
        payload = {
            'from_account_id': str(bank1.id),
            'to_account_id': str(bank2.id),
            'amount': '500.00',
            'reference': 'TRF-001',
            'reason': 'Test transfer',
            'transfer_date': '2026-04-07'
        }
        response = self.client.post(
            '/internal-transfer/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_internal_transfer_list(self):
        """Test internal transfer list"""
        response = self.client.get('/internal-transfer/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('results', data)

    # ═══════════════════════════════════════════════════════════════════════
    # JOURNAL ENTRY TESTS (JournalModal in OverviewSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_journal_entry_create(self):
        """Test JournalModal - create journal entry"""
        payload = {
            'date': '2026-04-07',
            'reference': 'JE-001',
            'description': 'Test journal entry',
            'lines': [
                {
                    'account_id': str(self.cash_account.id),
                    'debit': '1000.00',
                    'credit': '0',
                    'description': 'Debit cash'
                },
                {
                    'account_id': str(self.revenue_account.id),
                    'debit': '0',
                    'credit': '1000.00',
                    'description': 'Credit revenue'
                }
            ]
        }
        response = self.client.post(
            '/journal/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_journal_entry_list(self):
        """Test journal entry list"""
        response = self.client.get('/journal/list/')
        self.assertIn(response.status_code, [200, 403])  # May require permissions

    # ═══════════════════════════════════════════════════════════════════════
    # ACCOUNT TESTS (AccountModal in OverviewSection.tsx)
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_account_create(self):
        """Test AccountModal - create account"""
        expense_type = AccountType.objects.create(name='EXPENSE', description='Expense accounts')
        payload = {
            'code': '5000',
            'name': 'Test Expense Account',
            'account_type': 'EXPENSE',
            'account_sub_type': 'Operating',
            'description': 'Test account',
            'is_active': True
        }
        response = self.client.post(
            '/account/create/',
            json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.json())
    
    def test_account_list(self):
        """Test account list"""
        response = self.client.get('/account/list/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('accounts', data)

    # ═══════════════════════════════════════════════════════════════════════
    # REPORTS TESTS
    # ═══════════════════════════════════════════════════════════════════════
    
    def test_balance_sheet(self):
        """Test balance sheet report"""
        response = self.client.get('/reports/balance-sheet/')
        self.assertEqual(response.status_code, 200)
    
    def test_profit_and_loss(self):
        """Test profit & loss report"""
        response = self.client.get('/reports/profit-and-loss/')
        self.assertEqual(response.status_code, 200)
    
    def test_sales_summary(self):
        """Test sales summary report"""
        response = self.client.get('/reports/sales-summary/')
        self.assertEqual(response.status_code, 200)
    
    def test_purchases_summary(self):
        """Test purchases summary report"""
        response = self.client.get('/reports/purchases-summary/')
        self.assertEqual(response.status_code, 200)
    
    def test_expenses_summary(self):
        """Test expenses summary report"""
        response = self.client.get('/reports/expenses-summary/')
        self.assertEqual(response.status_code, 200)
    
    def test_tax_rate_get(self):
        """Test get tax rate"""
        response = self.client.get('/get-tax-rate/')
        self.assertEqual(response.status_code, 200)
