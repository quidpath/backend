"""
Tests for Petty Cash Management
"""
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from OrgAuth.models import Corporate, CorporateUser
from Accounting.models import PettyCashFund, PettyCashTransaction

User = get_user_model()


class PettyCashTestCase(TestCase):
    """Test cases for Petty Cash functionality"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create corporate
        self.corporate = Corporate.objects.create(
            name="Test Corp",
            email="test@corp.com",
            phone="1234567890",
            address="123 Test St",
            is_approved=True,
            is_active=True
        )
        
        # Create users
        self.admin_user = CorporateUser.objects.create(
            username="admin",
            email="admin@test.com",
            corporate=self.corporate,
            is_active=True
        )
        
        self.custodian_user = CorporateUser.objects.create(
            username="custodian",
            email="custodian@test.com",
            corporate=self.corporate,
            is_active=True
        )

    def test_create_petty_cash_fund(self):
        """Test creating a petty cash fund"""
        fund = PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            description="For small office expenses",
            custodian=self.custodian_user,
            initial_amount=Decimal("5000.00"),
            created_by=self.admin_user
        )
        
        self.assertEqual(fund.name, "Office Petty Cash")
        self.assertEqual(fund.current_balance, Decimal("5000.00"))
        self.assertEqual(fund.initial_amount, Decimal("5000.00"))
        self.assertTrue(fund.is_active)
        self.assertEqual(fund.custodian, self.custodian_user)

    def test_create_petty_cash_transaction(self):
        """Test creating a petty cash transaction"""
        fund = PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            custodian=self.custodian_user,
            initial_amount=Decimal("5000.00"),
            created_by=self.admin_user
        )
        
        transaction = PettyCashTransaction.objects.create(
            fund=fund,
            transaction_type="DISBURSEMENT",
            date="2026-04-07",
            reference="PC-001",
            description="Office supplies",
            category="Supplies",
            amount=Decimal("150.00"),
            recipient="John Doe",
            receipt_number="RCP-123",
            requested_by=self.admin_user,
            status="PENDING"
        )
        
        self.assertEqual(transaction.reference, "PC-001")
        self.assertEqual(transaction.amount, Decimal("150.00"))
        self.assertEqual(transaction.status, "PENDING")
        self.assertEqual(transaction.transaction_type, "DISBURSEMENT")

    def test_approve_disbursement_transaction(self):
        """Test approving a disbursement transaction"""
        fund = PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            custodian=self.custodian_user,
            initial_amount=Decimal("5000.00"),
            created_by=self.admin_user
        )
        
        transaction = PettyCashTransaction.objects.create(
            fund=fund,
            transaction_type="DISBURSEMENT",
            date="2026-04-07",
            reference="PC-001",
            description="Office supplies",
            amount=Decimal("150.00"),
            requested_by=self.admin_user,
            status="PENDING"
        )
        
        # Approve transaction
        transaction.approve(self.admin_user)
        
        # Refresh from database
        fund.refresh_from_db()
        transaction.refresh_from_db()
        
        self.assertEqual(transaction.status, "APPROVED")
        self.assertEqual(fund.current_balance, Decimal("4850.00"))
        self.assertIsNotNone(transaction.approved_at)
        self.assertEqual(transaction.approved_by, self.admin_user)

    def test_approve_replenishment_transaction(self):
        """Test approving a replenishment transaction"""
        fund = PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            custodian=self.custodian_user,
            initial_amount=Decimal("5000.00"),
            created_by=self.admin_user
        )
        
        # Set current balance lower
        fund.current_balance = Decimal("1000.00")
        fund.save()
        
        transaction = PettyCashTransaction.objects.create(
            fund=fund,
            transaction_type="REPLENISHMENT",
            date="2026-04-07",
            reference="PC-002",
            description="Replenish petty cash",
            amount=Decimal("4000.00"),
            requested_by=self.admin_user,
            status="PENDING"
        )
        
        # Approve transaction
        transaction.approve(self.admin_user)
        
        # Refresh from database
        fund.refresh_from_db()
        
        self.assertEqual(fund.current_balance, Decimal("5000.00"))

    def test_insufficient_balance_error(self):
        """Test that disbursement fails with insufficient balance"""
        fund = PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            custodian=self.custodian_user,
            initial_amount=Decimal("100.00"),
            created_by=self.admin_user
        )
        
        transaction = PettyCashTransaction.objects.create(
            fund=fund,
            transaction_type="DISBURSEMENT",
            date="2026-04-07",
            reference="PC-003",
            description="Large expense",
            amount=Decimal("500.00"),
            requested_by=self.admin_user,
            status="PENDING"
        )
        
        # Should raise ValidationError
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            transaction.approve(self.admin_user)

    def test_unique_fund_name_per_corporate(self):
        """Test that fund names must be unique per corporate"""
        PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            custodian=self.custodian_user,
            initial_amount=Decimal("5000.00"),
            created_by=self.admin_user
        )
        
        # Try to create another fund with same name
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PettyCashFund.objects.create(
                corporate=self.corporate,
                name="Office Petty Cash",
                custodian=self.custodian_user,
                initial_amount=Decimal("3000.00"),
                created_by=self.admin_user
            )

    def test_unique_transaction_reference_per_fund(self):
        """Test that transaction references must be unique per fund"""
        fund = PettyCashFund.objects.create(
            corporate=self.corporate,
            name="Office Petty Cash",
            custodian=self.custodian_user,
            initial_amount=Decimal("5000.00"),
            created_by=self.admin_user
        )
        
        PettyCashTransaction.objects.create(
            fund=fund,
            transaction_type="DISBURSEMENT",
            date="2026-04-07",
            reference="PC-001",
            description="First transaction",
            amount=Decimal("100.00"),
            requested_by=self.admin_user
        )
        
        # Try to create another transaction with same reference
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PettyCashTransaction.objects.create(
                fund=fund,
                transaction_type="DISBURSEMENT",
                date="2026-04-07",
                reference="PC-001",
                description="Duplicate reference",
                amount=Decimal("200.00"),
                requested_by=self.admin_user
            )
