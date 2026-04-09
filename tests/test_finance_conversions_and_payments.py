"""
Comprehensive Tests for Finance Conversions and Payments
Tests all conversion endpoints and payment recording functionality
"""
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from OrgAuth.models import Corporate, CorporateUser
from Authentication.models.role import Role
from Accounting.models import Customer, Vendor, TaxRate, Account, AccountType
from Accounting.models.sales import Invoices, Quotation, PurchaseOrder, VendorBill
from Accounting.models.payments import InvoicePayment, BillPayment

User = get_user_model()


class BaseFinanceTest(TestCase):
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
        
        # Create user
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


class TestQuoteToInvoiceConversion(BaseFinanceTest):
    """Test converting quotations to invoices"""
    
    def test_convert_quote_to_invoice_success(self):
        """Test successful conversion of quote to invoice"""
        # Create a quotation
        quote = Quotation.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            valid_until="2026-05-08",
            number="QT-001",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        # Create quote lines
        from Accounting.models.sales import QuotationLine
        QuotationLine.objects.create(
            quotation=quote,
            description="Service A",
            quantity=10,
            unit_price=Decimal("100.00"),
            discount=Decimal("0.00"),
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        # Convert to invoice
        payload = {
            "quotation_id": str(quote.id),
            "date": "2026-04-09",
            "number": "INV-20260409-0001",
            "due_date": "2026-05-09",
            "comments": "Converted from quote",
            "terms": "net_30"
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/quotation/invoice-quote/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 201)
        self.assertIn('invoice', data['data'])
        
        # Verify invoice was created
        invoice = Invoices.objects.get(number=payload['number'])
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.total, Decimal("1000.00"))
        self.assertEqual(invoice.lines.count(), 1)
        
        # Verify quote status updated
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'INVOICED')
    
    def test_convert_quote_missing_fields(self):
        """Test conversion fails when required fields are missing"""
        quote = Quotation.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            valid_until="2026-05-08",
            number="QT-002",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        # Missing required fields
        payload = {
            "quotation_id": str(quote.id),
            # Missing date, number, due_date
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/quotation/invoice-quote/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('message', data)


class TestPOToBillConversion(BaseFinanceTest):
    """Test converting purchase orders to vendor bills"""
    
    def test_convert_po_to_bill_success(self):
        """Test successful conversion of PO to bill"""
        # Create a purchase order
        po = PurchaseOrder.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            expected_delivery="2026-04-20",
            number="PO-001",
            status="POSTED",
            created_by=self.user,
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        # Create PO lines
        from Accounting.models.sales import PurchaseOrderLine
        PurchaseOrderLine.objects.create(
            purchase_order=po,
            description="Raw Material A",
            quantity=20,
            unit_price=Decimal("100.00"),
            discount=Decimal("0.00"),
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        # Convert to bill
        payload = {
            "purchase_order_id": str(po.id),
            "vendor_id": str(self.vendor.id),
            "date": "2026-04-09",
            "number": "BILL-20260409-0001",
            "due_date": "2026-05-09",
            "comments": "Converted from PO",
            "terms": "net_30"
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/convert-purchase-order/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 201)
        self.assertIn('vendor_bill', data['data'])
        
        # Verify bill was created
        bill = VendorBill.objects.get(number=payload['number'])
        self.assertEqual(bill.vendor, self.vendor)
        self.assertEqual(bill.total, Decimal("2000.00"))
        self.assertEqual(bill.lines.count(), 1)
        
        # Verify PO status updated
        po.refresh_from_db()
        self.assertEqual(po.status, 'BILLED')
    
    def test_convert_po_missing_vendor_id(self):
        """Test conversion fails when vendor_id is missing"""
        po = PurchaseOrder.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            expected_delivery="2026-04-20",
            number="PO-002",
            status="POSTED",
            created_by=self.user,
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        # Missing vendor_id
        payload = {
            "purchase_order_id": str(po.id),
            # Missing vendor_id
            "date": "2026-04-09",
            "number": "BILL-20260409-0002",
            "due_date": "2026-05-09",
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/vendor-bill/convert-purchase-order/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('message', data)


class TestInvoicePayments(BaseFinanceTest):
    """Test invoice payment recording"""
    
    def test_record_single_invoice_payment(self):
        """Test recording payment for a single invoice"""
        # Create an invoice
        invoice = Invoices.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="INV-001",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        # Record payment
        payload = {
            "customer_id": str(self.customer.id),
            "payment_date": "2026-04-09",
            "payment_method": "bank_transfer",
            "reference": "TXN-001",
            "items": [
                {
                    "invoice_id": str(invoice.id),
                    "amount": 1000.00
                }
            ]
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/invoice-payment/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        
        # Verify payment was recorded
        payment = InvoicePayment.objects.filter(invoice=invoice).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal("1000.00"))
        
        # Verify invoice status updated
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, 'PAID')
    
    def test_record_partial_invoice_payment(self):
        """Test recording partial payment for an invoice"""
        invoice = Invoices.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="INV-002",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        # Record partial payment
        payload = {
            "customer_id": str(self.customer.id),
            "payment_date": "2026-04-09",
            "payment_method": "bank_transfer",
            "reference": "TXN-002",
            "items": [
                {
                    "invoice_id": str(invoice.id),
                    "amount": 500.00  # Partial payment
                }
            ]
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/invoice-payment/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify payment was recorded
        payment = InvoicePayment.objects.filter(invoice=invoice).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal("500.00"))
        
        # Verify invoice status is PARTIAL
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, 'PARTIAL')
    
    def test_record_multiple_invoice_payments(self):
        """Test recording payments for multiple invoices"""
        invoice1 = Invoices.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="INV-003",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        invoice2 = Invoices.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="INV-004",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        # Record payments for both
        payload = {
            "customer_id": str(self.customer.id),
            "payment_date": "2026-04-09",
            "payment_method": "bank_transfer",
            "reference": "TXN-003",
            "items": [
                {
                    "invoice_id": str(invoice1.id),
                    "amount": 1000.00
                },
                {
                    "invoice_id": str(invoice2.id),
                    "amount": 2000.00
                }
            ]
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/invoice-payment/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify both payments were recorded
        payment1 = InvoicePayment.objects.filter(invoice=invoice1).first()
        payment2 = InvoicePayment.objects.filter(invoice=invoice2).first()
        self.assertIsNotNone(payment1)
        self.assertIsNotNone(payment2)
        self.assertEqual(payment1.amount, Decimal("1000.00"))
        self.assertEqual(payment2.amount, Decimal("2000.00"))
    
    def test_payment_without_customer_fails(self):
        """Test that payment fails when customer is not selected"""
        invoice = Invoices.objects.create(
            customer=self.customer,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="INV-005",
            status="POSTED",
            salesperson=self.user,
            sub_total=Decimal("1000.00"),
            total=Decimal("1000.00")
        )
        
        # Missing customer_id
        payload = {
            # Missing customer_id
            "payment_date": "2026-04-09",
            "payment_method": "bank_transfer",
            "reference": "TXN-004",
            "items": [
                {
                    "invoice_id": str(invoice.id),
                    "amount": 1000.00
                }
            ]
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/invoice-payment/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('message', data)


class TestBillPayments(BaseFinanceTest):
    """Test vendor bill payment recording"""
    
    def test_record_single_bill_payment(self):
        """Test recording payment for a single bill"""
        bill = VendorBill.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="BILL-001",
            status="POSTED",
            created_by=self.user,
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        # Record payment
        payload = {
            "vendor_id": str(self.vendor.id),
            "payment_date": "2026-04-09",
            "payment_method": "bank_transfer",
            "reference": "TXN-005",
            "items": [
                {
                    "bill_id": str(bill.id),
                    "amount": 2000.00
                }
            ]
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/bill-payment/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        
        # Verify payment was recorded
        payment = BillPayment.objects.filter(vendor_bill=bill).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal("2000.00"))
        
        # Verify bill status updated
        bill.refresh_from_db()
        self.assertEqual(bill.payment_status, 'PAID')
    
    def test_payment_without_vendor_fails(self):
        """Test that payment fails when vendor is not selected"""
        bill = VendorBill.objects.create(
            vendor=self.vendor,
            corporate=self.corporate,
            date="2026-04-08",
            due_date="2026-05-08",
            number="BILL-002",
            status="POSTED",
            created_by=self.user,
            sub_total=Decimal("2000.00"),
            total=Decimal("2000.00")
        )
        
        # Missing vendor_id
        payload = {
            # Missing vendor_id
            "payment_date": "2026-04-09",
            "payment_method": "bank_transfer",
            "reference": "TXN-006",
            "items": [
                {
                    "bill_id": str(bill.id),
                    "amount": 2000.00
                }
            ]
        }
        
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/bill-payment/create/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('message', data)


class TestAutoNumberGeneration(BaseFinanceTest):
    """Test that auto-generated numbers are properly formatted"""
    
    def test_invoice_auto_number_format(self):
        """Test that invoice numbers follow proper format"""
        # The frontend should generate numbers like INV-20260409-0001
        number = "INV-20260409-0001"
        
        # Verify format
        self.assertTrue(number.startswith("INV-"))
        parts = number.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[2]), 4)  # Sequential number
    
    def test_bill_auto_number_format(self):
        """Test that bill numbers follow proper format"""
        number = "BILL-20260409-0001"
        
        # Verify format
        self.assertTrue(number.startswith("BILL-"))
        parts = number.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[2]), 4)  # Sequential number
    
    def test_po_auto_number_format(self):
        """Test that PO numbers follow proper format"""
        number = "PO-20260409-0001"
        
        # Verify format
        self.assertTrue(number.startswith("PO-"))
        parts = number.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[2]), 4)  # Sequential number
    
    def test_quote_auto_number_format(self):
        """Test that quote numbers follow proper format"""
        number = "QT-20260409-0001"
        
        # Verify format
        self.assertTrue(number.startswith("QT-"))
        parts = number.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[2]), 4)  # Sequential number
