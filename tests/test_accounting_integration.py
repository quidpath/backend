"""
Comprehensive Integration Tests for Accounting Module
Tests mirror EXACT frontend data structure and flow
"""
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from OrgAuth.models import Corporate, CorporateUser
from Authentication.models.role import Role
from Accounting.models import Customer, Vendor, TaxRate, Account, AccountType
from Accounting.models.sales import Invoices, Quotation, PurchaseOrder, VendorBill

User = get_user_model()


class BaseAccountingTest(TestCase):
    """Base test class with common setup"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create corporate
        self.corporate = Corporate.objects.create(
            name="Test Corp",
            email="test@corp.com",
            phone="+254700000000"
        )
        
        # Create role
        self.role = Role.objects.create(
            name="ADMIN",
            corporate=self.corporate
        )
        
        # Create user properly - CorporateUser extends CustomUser
        self.user = CorporateUser.objects.create_user(
            username="testuser",
            email="test@user.com",
            password="testpass123",
            corporate=self.corporate,
            role=self.role
        )
        
        # Create customer
        self.customer = Customer.objects.create(
            corporate=self.corporate,
            category="company",
            company_name="Test Customer Ltd",
            email="customer@test.com",
            phone="+254700000001"
        )
        
        # Create vendor
        self.vendor = Vendor.objects.create(
            corporate=self.corporate,
            category="company",
            company_name="Test Vendor Ltd",
            email="vendor@test.com",
            phone="+254700000002"
        )
        
        # Create tax rates
        self.tax_exempt = TaxRate.objects.create(
            corporate=self.corporate,
            name="exempt",
            rate=Decimal("0.00")
        )
        self.tax_zero = TaxRate.objects.create(
            corporate=self.corporate,
            name="zero_rated",
            rate=Decimal("0.00")
        )
        self.tax_general = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated",
            rate=Decimal("16.00")
        )
        
        # Create accounts
        acc_type, _ = AccountType.objects.get_or_create(
            name="REVENUE",
            defaults={"description": "Revenue accounts"}
        )
        self.revenue_account = Account.objects.create(
            corporate=self.corporate,
            account_type=acc_type,
            name="Sales Revenue",
            code="4000"
        )
        
        expense_type, _ = AccountType.objects.get_or_create(
            name="EXPENSE",
            defaults={"description": "Expense accounts"}
        )
        self.expense_account = Account.objects.create(
            corporate=self.corporate,
            account_type=expense_type,
            name="Cost of Goods Sold",
            code="5000"
        )


class TestVendorBillCreation(BaseAccountingTest):
    """Test vendor bill creation with EXACT frontend data structure"""
    
    def test_create_bill_as_draft_with_null_taxable(self):
        """Test creating bill with taxable_id: null (as frontend sends)"""
        # This is EXACTLY how frontend sends data from PurchasesSection.tsx
        payload = {
            "vendor": str(self.vendor.id),
            "date": "2026-04-08",
            "due_date": "2026-05-08",
            "number": f"BILL-{1712500000}",
            "status": "DRAFT",
            "lines": [
                {
                    "description": "Professional Services",
                    "quantity": 5,
                    "unit_price": 200.00,
                    "discount": 0,
                    "taxable_id": None,  # Frontend sends null
                }
            ],
        }
        
        # Simulate authenticated request
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIn('vendor_bill', data['data'])
        
        # Verify bill was created
        bill = VendorBill.objects.get(number=payload['number'])
        self.assertEqual(bill.status, 'DRAFT')
        self.assertEqual(bill.vendor, self.vendor)
        self.assertEqual(bill.lines.count(), 1)
    
    def test_create_bill_with_multiple_lines(self):
        """Test creating bill with multiple line items"""
        payload = {
            "vendor": str(self.vendor.id),
            "date": "2026-04-08",
            "due_date": "2026-05-08",
            "number": f"BILL-{1712500001}",
            "status": "DRAFT",
            "lines": [
                {
                    "description": "Item 1",
                    "quantity": 10,
                    "unit_price": 50.00,
                    "discount": 0,
                    "taxable_id": None,
                },
                {
                    "description": "Item 2",
                    "quantity": 5,
                    "unit_price": 100.00,
                    "discount": 0,
                    "taxable_id": None,
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        bill = VendorBill.objects.get(number=payload['number'])
        self.assertEqual(bill.lines.count(), 2)
        # Total should be (10*50) + (5*100) = 1000
        self.assertEqual(bill.sub_total, Decimal("1000.00"))


class TestPurchaseOrderCreation(BaseAccountingTest):
    """Test PO creation with EXACT frontend data structure"""
    
    def test_create_po_with_null_taxable(self):
        """Test creating PO with taxable_id: null (as frontend sends)"""
        payload = {
            "vendor": str(self.vendor.id),
            "date": "2026-04-08",
            "expected_delivery": "2026-04-20",
            "number": f"PO-{1712500000}",
            "created_by": None,  # Frontend sends undefined which becomes None
            "lines": [
                {
                    "description": "Raw Materials",
                    "quantity": 100,
                    "unit_price": 10.00,
                    "discount": 0,
                    "taxable_id": None,  # Changed from 'exempt' to null
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/purchase-orders/save-draft/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        
        # Verify PO was created
        po = PurchaseOrder.objects.get(number=payload['number'])
        self.assertEqual(po.status, 'DRAFT')
        self.assertEqual(po.vendor, self.vendor)
        self.assertEqual(po.lines.count(), 1)


class TestInvoiceCreation(BaseAccountingTest):
    """Test invoice creation with EXACT frontend data structure"""
    
    def test_create_invoice_draft(self):
        """Test creating invoice as draft"""
        payload = {
            "customer": str(self.customer.id),
            "date": "2026-04-08",
            "due_date": "2026-05-08",
            "number": f"INV-{1712500000}",
            "salesperson": str(self.user.id),
            "terms": "net_30",
            "purchase_order": "",
            "comments": "",
            "lines": [
                {
                    "description": "Consulting Services",
                    "quantity": 10,
                    "unit_price": 150.00,
                    "discount": 0,
                    "taxable_id": None,
                    "account": str(self.revenue_account.id),
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/invoice/save-draft/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        
        # Verify invoice was created
        invoice = Invoices.objects.get(number=payload['number'])
        self.assertEqual(invoice.status, 'DRAFT')
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.lines.count(), 1)


class TestQuotationCreation(BaseAccountingTest):
    """Test quotation creation with EXACT frontend data structure"""
    
    def test_create_quotation_draft(self):
        """Test creating quotation as draft"""
        payload = {
            "customer": str(self.customer.id),
            "date": "2026-04-08",
            "valid_until": "2026-05-08",
            "number": f"QT-{1712500000}",
            "salesperson": str(self.user.id),
            "ship_date": "2026-04-15",
            "ship_via": "DHL",
            "terms": "net_30",
            "fob": "Origin",
            "comments": "",
            "T_and_C": "Standard terms",
            "lines": [
                {
                    "description": "Product A",
                    "quantity": 20,
                    "unit_price": 75.00,
                    "discount": 0,
                    "taxable_id": None,
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/quotation/save-draft/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        
        # Verify quotation was created
        quote = Quotation.objects.get(number=payload['number'])
        self.assertEqual(quote.status, 'DRAFT')
        self.assertEqual(quote.customer, self.customer)
        self.assertEqual(quote.lines.count(), 1)


class TestDraftStatusInTables(BaseAccountingTest):
    """Test that DRAFT documents appear in list endpoints"""
    
    def test_draft_bills_appear_in_list(self):
        """Test that draft bills appear in the list"""
        # Create a draft bill
        bill = VendorBill.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="BILL-DRAFT-001",
            status="DRAFT",
            created_by=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        self.client.force_login(self.user)
        response = self.client.get('/api/vendor-bill/list/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('vendor_bills', data['data'])
        
        # Find our draft bill in the list
        bills = data['data']['vendor_bills']
        draft_bill = next((b for b in bills if b['number'] == 'BILL-DRAFT-001'), None)
        self.assertIsNotNone(draft_bill)
        self.assertEqual(draft_bill['status'], 'DRAFT')
    
    def test_draft_invoices_appear_in_list(self):
        """Test that draft invoices appear in the list"""
        invoice = Invoices.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="INV-DRAFT-001",
            status="DRAFT",
            salesperson=self.user,
            sub_total=Decimal("1500.00"),
            total=Decimal("1500.00")
        )
        
        self.client.force_login(self.user)
        response = self.client.get('/api/invoice/list/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('invoices', data['data'])
        
        # Find our draft invoice
        invoices = data['data']['invoices']
        draft_invoice = next((i for i in invoices if i['number'] == 'INV-DRAFT-001'), None)
        self.assertIsNotNone(draft_invoice)
        self.assertEqual(draft_invoice['status'], 'DRAFT')


class TestStatCardExcludesDrafts(BaseAccountingTest):
    """Test that analytics exclude DRAFT documents"""
    
    def test_analytics_excludes_draft_bills(self):
        """Test that draft bills are excluded from analytics totals"""
        # Create one DRAFT and one POSTED bill
        VendorBill.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="BILL-DRAFT-002",
            status="DRAFT",
            created_by=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        VendorBill.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="BILL-POSTED-001",
            status="POSTED",
            created_by=self.user,
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        self.client.force_login(self.user)
        response = self.client.get('/api/analytics/overview/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Analytics should only include the POSTED bill (2000), not DRAFT (1000)
        total_bills = float(data['data'].get('total_bills', 0))
        self.assertEqual(total_bills, 2000.00, f"Expected 2000.00 but got {total_bills}")


class TestTaxCalculations(BaseAccountingTest):
    """Test tax calculations with different tax rates"""
    
    def test_bill_with_general_rated_tax(self):
        """Test bill creation with 16% VAT"""
        payload = {
            "vendor": str(self.vendor.id),
            "date": "2026-04-08",
            "due_date": "2026-05-08",
            "number": f"BILL-TAX-001",
            "status": "DRAFT",
            "lines": [
                {
                    "description": "Taxable Item",
                    "quantity": 10,
                    "unit_price": 100.00,
                    "discount": 0,
                    "taxable_id": str(self.tax_general.id),
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        bill = VendorBill.objects.get(number=payload['number'])
        
        # Subtotal: 10 * 100 = 1000
        # Tax: 1000 * 0.16 = 160
        # Total: 1000 + 160 = 1160
        self.assertEqual(bill.sub_total, Decimal("1000.00"))
        self.assertEqual(bill.tax_total, Decimal("160.00"))
        self.assertEqual(bill.total, Decimal("1160.00"))
    
    def test_bill_with_exempt_tax(self):
        """Test bill creation with exempt tax rate"""
        payload = {
            "vendor": str(self.vendor.id),
            "date": "2026-04-08",
            "due_date": "2026-05-08",
            "number": f"BILL-EXEMPT-001",
            "status": "DRAFT",
            "lines": [
                {
                    "description": "Exempt Item",
                    "quantity": 10,
                    "unit_price": 100.00,
                    "discount": 0,
                    "taxable_id": str(self.tax_exempt.id),
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        bill = VendorBill.objects.get(number=payload['number'])
        
        # No tax should be applied
        self.assertEqual(bill.sub_total, Decimal("1000.00"))
        self.assertEqual(bill.tax_total, Decimal("0.00"))
        self.assertEqual(bill.total, Decimal("1000.00"))


class TestDiscountCalculations(BaseAccountingTest):
    """Test discount calculations"""
    
    def test_bill_with_discount(self):
        """Test bill creation with line item discount"""
        payload = {
            "vendor": str(self.vendor.id),
            "date": "2026-04-08",
            "due_date": "2026-05-08",
            "number": f"BILL-DISCOUNT-001",
            "status": "DRAFT",
            "lines": [
                {
                    "description": "Discounted Item",
                    "quantity": 10,
                    "unit_price": 100.00,
                    "discount": 100.00,  # $100 discount
                    "taxable_id": None,
                }
            ],
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        bill = VendorBill.objects.get(number=payload['number'])
        
        # Subtotal: 10 * 100 = 1000
        # After discount: 1000 - 100 = 900
        self.assertEqual(bill.total_discount, Decimal("100.00"))
        self.assertEqual(bill.total, Decimal("900.00"))
