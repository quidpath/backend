"""
Tests for Bank Reconciliation
"""
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from OrgAuth.models import Corporate, CorporateUser
from Banking.models import BankAccount
from Accounting.models import BankReconciliation, ReconciliationItem


class BankReconciliationTestCase(TestCase):
    """Test cases for Bank Reconciliation functionality"""

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
        
        # Create user
        self.user = CorporateUser.objects.create(
            username="testuser",
            email="user@test.com",
            corporate=self.corporate,
            is_active=True
        )
        
        # Create bank account
        self.bank_account = BankAccount.objects.create(
            corporate=self.corporate,
            bank_name="Test Bank",
            account_name="Main Account",
            account_number="1234567890",
            currency="USD"
        )

    def test_create_bank_reconciliation(self):
        """Test creating a bank reconciliation"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12500.00"),
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user
        )
        
        self.assertEqual(reconciliation.status, "IN_PROGRESS")
        self.assertEqual(reconciliation.opening_balance, Decimal("10000.00"))
        self.assertEqual(reconciliation.closing_balance, Decimal("12000.00"))

    def test_add_reconciliation_items(self):
        """Test adding items to reconciliation"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12500.00"),
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user
        )
        
        # Add deposit in transit
        item1 = ReconciliationItem.objects.create(
            reconciliation=reconciliation,
            item_type="DEPOSIT_IN_TRANSIT",
            date="2026-04-30",
            reference="DEP-001",
            description="Deposit not yet cleared",
            amount=Decimal("500.00")
        )
        
        # Add outstanding check
        item2 = ReconciliationItem.objects.create(
            reconciliation=reconciliation,
            item_type="OUTSTANDING_CHECK",
            date="2026-04-28",
            reference="CHK-001",
            description="Check not yet cashed",
            amount=Decimal("300.00")
        )
        
        self.assertEqual(reconciliation.items.count(), 2)
        self.assertEqual(item1.item_type, "DEPOSIT_IN_TRANSIT")
        self.assertEqual(item2.item_type, "OUTSTANDING_CHECK")

    def test_calculate_difference(self):
        """Test difference calculation"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12500.00"),
            book_balance=Decimal("12000.00"),
            total_deposits_in_transit=Decimal("500.00"),
            total_outstanding_checks=Decimal("300.00"),
            total_bank_charges=Decimal("50.00"),
            reconciled_by=self.user
        )
        
        # Calculate: statement_balance - (book_balance + deposits - checks - charges)
        # 12500 - (12000 + 500 - 300 - 50) = 12500 - 12150 = 350
        difference = reconciliation.calculate_difference()
        self.assertEqual(difference, Decimal("350.00"))

    def test_is_balanced(self):
        """Test balance check"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12150.00"),
            book_balance=Decimal("12000.00"),
            total_deposits_in_transit=Decimal("500.00"),
            total_outstanding_checks=Decimal("300.00"),
            total_bank_charges=Decimal("50.00"),
            reconciled_by=self.user
        )
        
        # Should be balanced: 12150 = 12000 + 500 - 300 - 50
        self.assertTrue(reconciliation.is_balanced())

    def test_complete_balanced_reconciliation(self):
        """Test completing a balanced reconciliation"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12150.00"),
            book_balance=Decimal("12000.00"),
            total_deposits_in_transit=Decimal("500.00"),
            total_outstanding_checks=Decimal("300.00"),
            total_bank_charges=Decimal("50.00"),
            reconciled_by=self.user
        )
        
        reconciliation.complete()
        self.assertEqual(reconciliation.status, "COMPLETED")

    def test_complete_unbalanced_reconciliation_fails(self):
        """Test that completing unbalanced reconciliation raises error"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("15000.00"),  # Unbalanced
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            reconciliation.complete()

    def test_review_reconciliation(self):
        """Test reviewing a completed reconciliation"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12000.00"),
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user,
            status="COMPLETED"
        )
        
        reviewer = CorporateUser.objects.create(
            username="reviewer",
            email="reviewer@test.com",
            corporate=self.corporate,
            is_active=True
        )
        
        reconciliation.review(reviewer)
        
        self.assertEqual(reconciliation.status, "REVIEWED")
        self.assertEqual(reconciliation.reviewed_by, reviewer)
        self.assertIsNotNone(reconciliation.reviewed_at)

    def test_review_non_completed_fails(self):
        """Test that reviewing non-completed reconciliation fails"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12000.00"),
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user,
            status="IN_PROGRESS"
        )
        
        with self.assertRaises(ValidationError):
            reconciliation.review(self.user)

    def test_unique_reconciliation_per_period(self):
        """Test that reconciliation is unique per bank account and period"""
        BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12000.00"),
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user
        )
        
        # Try to create another for same period
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            BankReconciliation.objects.create(
                corporate=self.corporate,
                bank_account=self.bank_account,
                period_start="2026-04-01",
                period_end="2026-04-30",
                opening_balance=Decimal("10000.00"),
                closing_balance=Decimal("12000.00"),
                statement_balance=Decimal("12000.00"),
                book_balance=Decimal("12000.00"),
                reconciled_by=self.user
            )

    def test_clear_reconciliation_item(self):
        """Test clearing a reconciliation item"""
        reconciliation = BankReconciliation.objects.create(
            corporate=self.corporate,
            bank_account=self.bank_account,
            period_start="2026-04-01",
            period_end="2026-04-30",
            opening_balance=Decimal("10000.00"),
            closing_balance=Decimal("12000.00"),
            statement_balance=Decimal("12000.00"),
            book_balance=Decimal("12000.00"),
            reconciled_by=self.user
        )
        
        item = ReconciliationItem.objects.create(
            reconciliation=reconciliation,
            item_type="OUTSTANDING_CHECK",
            date="2026-04-28",
            reference="CHK-001",
            description="Check",
            amount=Decimal("300.00")
        )
        
        item.clear("2026-05-01")
        
        self.assertTrue(item.is_cleared)
        self.assertIsNotNone(item.cleared_date)
