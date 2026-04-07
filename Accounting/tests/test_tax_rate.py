"""
Tests for Tax Rate Management
"""
from decimal import Decimal
from django.test import TestCase
from OrgAuth.models import Corporate
from Accounting.models import TaxRate, Account, AccountType


class TaxRateTestCase(TestCase):
    """Test cases for Tax Rate functionality"""

    def setUp(self):
        """Set up test data"""
        # Create corporate
        self.corporate = Corporate.objects.create(
            name="Test Corp",
            email="test@corp.com",
            phone="1234567890",
            address="123 Test St",
            is_approved=True,
            is_active=True
        )
        
        # Create account types
        self.revenue_type = AccountType.objects.create(
            name="REVENUE"
        )
        
        self.liability_type = AccountType.objects.create(
            name="LIABILITY"
        )
        
        # Create accounts
        self.sales_account = Account.objects.create(
            corporate=self.corporate,
            code="4000",
            name="Sales Tax Payable",
            account_type=self.liability_type,
            is_active=True
        )
        
        self.purchase_account = Account.objects.create(
            corporate=self.corporate,
            code="1500",
            name="Purchase Tax Receivable",
            account_type=self.liability_type,
            is_active=True
        )

    def test_create_tax_rate(self):
        """Test creating a tax rate"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated",
            rate=Decimal("16.00"),
            sales_account=self.sales_account,
            purchase_account=self.purchase_account
        )
        
        self.assertEqual(tax_rate.name, "general_rated")
        self.assertEqual(tax_rate.rate, Decimal("16.00"))
        self.assertEqual(tax_rate.sales_account, self.sales_account)
        self.assertEqual(tax_rate.purchase_account, self.purchase_account)

    def test_exempt_tax_rate_auto_zero(self):
        """Test that exempt tax rate automatically sets rate to 0"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="exempt",
            rate=Decimal("10.00")  # Will be overridden
        )
        
        self.assertEqual(tax_rate.rate, Decimal("0.00"))

    def test_zero_rated_tax_rate_auto_zero(self):
        """Test that zero_rated tax rate automatically sets rate to 0"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="zero_rated",
            rate=Decimal("5.00")  # Will be overridden
        )
        
        self.assertEqual(tax_rate.rate, Decimal("0.00"))

    def test_general_rated_auto_sixteen(self):
        """Test that general_rated automatically sets rate to 16%"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated",
            rate=Decimal("10.00")  # Will be overridden
        )
        
        self.assertEqual(tax_rate.rate, Decimal("16.00"))

    def test_unique_tax_rate_per_corporate(self):
        """Test that tax rate names must be unique per corporate"""
        TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated"
        )
        
        # Try to create another with same name
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            TaxRate.objects.create(
                corporate=self.corporate,
                name="general_rated"
            )

    def test_tax_rate_string_representation(self):
        """Test tax rate string representation"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated"
        )
        
        # Should return the display name from choices
        self.assertEqual(str(tax_rate), "VAT (16%)")

    def test_update_tax_rate(self):
        """Test updating a tax rate"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated"
        )
        
        # Update accounts
        tax_rate.sales_account = self.sales_account
        tax_rate.purchase_account = self.purchase_account
        tax_rate.save()
        
        tax_rate.refresh_from_db()
        
        self.assertEqual(tax_rate.sales_account, self.sales_account)
        self.assertEqual(tax_rate.purchase_account, self.purchase_account)

    def test_delete_tax_rate(self):
        """Test deleting a tax rate"""
        tax_rate = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated"
        )
        
        tax_rate_id = tax_rate.id
        tax_rate.delete()
        
        with self.assertRaises(TaxRate.DoesNotExist):
            TaxRate.objects.get(id=tax_rate_id)

    def test_multiple_corporates_same_tax_name(self):
        """Test that different corporates can have same tax rate name"""
        # Create another corporate
        corporate2 = Corporate.objects.create(
            name="Test Corp 2",
            email="test2@corp.com",
            phone="0987654321",
            address="456 Test Ave",
            is_approved=True,
            is_active=True
        )
        
        # Create tax rate for first corporate
        tax_rate1 = TaxRate.objects.create(
            corporate=self.corporate,
            name="general_rated"
        )
        
        # Create tax rate with same name for second corporate (should work)
        tax_rate2 = TaxRate.objects.create(
            corporate=corporate2,
            name="general_rated"
        )
        
        self.assertNotEqual(tax_rate1.id, tax_rate2.id)
        self.assertEqual(tax_rate1.name, tax_rate2.name)
        self.assertNotEqual(tax_rate1.corporate, tax_rate2.corporate)
