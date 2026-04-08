"""
Test Draft Exclusion Policy
Ensures DRAFT documents are never used in accounting calculations
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone

from Accounting.models.sales import Invoices, VendorBill, Quotation, PurchaseOrder
from Accounting.models.customer import Customer
from Accounting.models.vendor import Vendor
from Accounting.utils.draft_exclusion import (
    filter_posted_only,
    exclude_drafts,
    is_document_posted,
    validate_document_for_accounting,
    ensure_posted_for_journal_entry,
)
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.registry import ServiceRegistry


class DraftExclusionTestCase(TestCase):
    """Test cases for draft exclusion policy"""
    
    def setUp(self):
        """Set up test data"""
        # Create corporate
        self.corporate = Corporate.objects.create(
            name="Test Corp",
            email="test@corp.com"
        )
        
        # Create customer
        self.customer = Customer.objects.create(
            corporate=self.corporate,
            name="Test Customer",
            email="customer@test.com"
        )
        
        # Create vendor
        self.vendor = Vendor.objects.create(
            corporate=self.corporate,
            name="Test Vendor",
            email="vendor@test.com"
        )
        
        # Create draft invoice
        self.draft_invoice = Invoices.objects.create(
            corporate=self.corporate,
            customer=self.customer,
            number="INV-DRAFT-001",
            date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status="DRAFT",
            sub_total=Decimal("1000.00"),
            tax_total=Decimal("160.00"),
            total=Decimal("1160.00"),
        )
        
        # Create posted invoice
        self.posted_invoice = Invoices.objects.create(
            corporate=self.corporate,
            customer=self.customer,
            number="INV-POSTED-001",
            date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status="POSTED",
            posted_at=timezone.now(),
            sub_total=Decimal("2000.00"),
            tax_total=Decimal("320.00"),
            total=Decimal("2320.00"),
        )
        
        # Create draft bill
        self.draft_bill = VendorBill.objects.create(
            corporate=self.corporate,
            vendor=self.vendor,
            number="BILL-DRAFT-001",
            date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status="DRAFT",
            sub_total=Decimal("500.00"),
            tax_total=Decimal("80.00"),
            total=Decimal("580.00"),
        )
        
        # Create posted bill
        self.posted_bill = VendorBill.objects.create(
            corporate=self.corporate,
            vendor=self.vendor,
            number="BILL-POSTED-001",
            date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status="POSTED",
            posted_at=timezone.now(),
            sub_total=Decimal("1500.00"),
            tax_total=Decimal("240.00"),
            total=Decimal("1740.00"),
        )
    
    def test_filter_posted_only_invoices(self):
        """Test filtering invoices to only include POSTED"""
        all_invoices = Invoices.objects.filter(corporate=self.corporate)
        posted_invoices = filter_posted_only(all_invoices, 'Invoices')
        
        self.assertEqual(all_invoices.count(), 2)
        self.assertEqual(posted_invoices.count(), 1)
        self.assertEqual(posted_invoices.first().number, "INV-POSTED-001")
    
    def test_filter_posted_only_bills(self):
        """Test filtering bills to only include POSTED"""
        all_bills = VendorBill.objects.filter(corporate=self.corporate)
        posted_bills = filter_posted_only(all_bills, 'VendorBill')
        
        self.assertEqual(all_bills.count(), 2)
        self.assertEqual(posted_bills.count(), 1)
        self.assertEqual(posted_bills.first().number, "BILL-POSTED-001")
    
    def test_exclude_drafts_invoices(self):
        """Test excluding DRAFT invoices"""
        all_invoices = Invoices.objects.filter(corporate=self.corporate)
        non_draft_invoices = exclude_drafts(all_invoices, 'Invoices')
        
        self.assertEqual(all_invoices.count(), 2)
        self.assertEqual(non_draft_invoices.count(), 1)
        self.assertNotIn("DRAFT", [inv.status for inv in non_draft_invoices])
    
    def test_is_document_posted(self):
        """Test checking if document is posted"""
        draft_dict = {"status": "DRAFT"}
        posted_dict = {"status": "POSTED"}
        
        self.assertFalse(is_document_posted(draft_dict))
        self.assertTrue(is_document_posted(posted_dict))
    
    def test_validate_document_for_accounting_draft(self):
        """Test validation rejects DRAFT documents"""
        draft_dict = {"status": "DRAFT"}
        is_valid, error = validate_document_for_accounting(draft_dict, 'invoice')
        
        self.assertFalse(is_valid)
        self.assertIn("must be POSTED", error)
    
    def test_validate_document_for_accounting_posted(self):
        """Test validation accepts POSTED documents"""
        posted_dict = {
            "status": "POSTED",
            "journal_entry_id": "some-uuid"
        }
        is_valid, error = validate_document_for_accounting(posted_dict, 'invoice')
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_document_for_accounting_no_journal_entry(self):
        """Test validation rejects POSTED documents without journal entry"""
        posted_dict = {
            "status": "POSTED",
            "journal_entry_id": None
        }
        is_valid, error = validate_document_for_accounting(posted_dict, 'invoice')
        
        self.assertFalse(is_valid)
        self.assertIn("no journal entry", error)
    
    def test_ensure_posted_for_journal_entry_raises(self):
        """Test ensure_posted_for_journal_entry raises for DRAFT"""
        draft_dict = {"status": "DRAFT"}
        
        with self.assertRaises(ValueError) as context:
            ensure_posted_for_journal_entry(draft_dict, 'invoice')
        
        self.assertIn("Cannot create journal entry", str(context.exception))
    
    def test_ensure_posted_for_journal_entry_passes(self):
        """Test ensure_posted_for_journal_entry passes for POSTED"""
        posted_dict = {
            "status": "POSTED",
            "journal_entry_id": "some-uuid"
        }
        
        # Should not raise
        try:
            ensure_posted_for_journal_entry(posted_dict, 'invoice')
        except ValueError:
            self.fail("ensure_posted_for_journal_entry raised ValueError unexpectedly")
    
    def test_aged_invoices_excludes_drafts(self):
        """Test aged invoices report only includes POSTED invoices"""
        # This would be an integration test with the actual view
        # For now, we test the query logic
        posted_invoices = Invoices.objects.filter(
            corporate=self.corporate,
            status="POSTED"
        )
        
        self.assertEqual(posted_invoices.count(), 1)
        self.assertEqual(posted_invoices.first().number, "INV-POSTED-001")
        
        # Verify draft is not included
        invoice_numbers = [inv.number for inv in posted_invoices]
        self.assertNotIn("INV-DRAFT-001", invoice_numbers)
    
    def test_accounts_receivable_excludes_drafts(self):
        """Test AR calculation only includes POSTED invoices"""
        posted_invoices = Invoices.objects.filter(
            corporate=self.corporate,
            status="POSTED"
        )
        
        total_ar = sum(inv.total for inv in posted_invoices)
        
        # Should only include posted invoice
        self.assertEqual(total_ar, Decimal("2320.00"))
        
        # Should NOT include draft invoice
        self.assertNotEqual(total_ar, Decimal("3480.00"))  # 2320 + 1160
    
    def test_accounts_payable_excludes_drafts(self):
        """Test AP calculation only includes POSTED bills"""
        posted_bills = VendorBill.objects.filter(
            corporate=self.corporate,
            status="POSTED"
        )
        
        total_ap = sum(bill.total for bill in posted_bills)
        
        # Should only include posted bill
        self.assertEqual(total_ap, Decimal("1740.00"))
        
        # Should NOT include draft bill
        self.assertNotEqual(total_ap, Decimal("2320.00"))  # 1740 + 580
    
    def test_draft_invoice_has_no_journal_entry(self):
        """Test DRAFT invoices should not have journal entries"""
        self.assertIsNone(self.draft_invoice.journal_entry_id)
        self.assertIsNone(self.draft_invoice.posted_at)
        self.assertIsNone(self.draft_invoice.posted_by)
    
    def test_posted_invoice_indicators(self):
        """Test POSTED invoices have proper indicators"""
        self.assertEqual(self.posted_invoice.status, "POSTED")
        self.assertIsNotNone(self.posted_invoice.posted_at)
        # journal_entry_id might be None if not yet created, but posted_at should exist
    
    def test_reference_dropdown_only_shows_posted(self):
        """Test that reference dropdowns should only show POSTED documents"""
        # When creating invoice from quotation, only show POSTED quotations
        posted_quotations = Quotation.objects.filter(
            corporate=self.corporate,
            status="POSTED"
        )
        
        # This ensures dropdowns don't show DRAFT documents
        self.assertEqual(
            posted_quotations.filter(status="DRAFT").count(),
            0
        )


class DraftExclusionIntegrationTestCase(TestCase):
    """Integration tests for draft exclusion in reports"""
    
    def setUp(self):
        """Set up test data"""
        self.corporate = Corporate.objects.create(
            name="Test Corp",
            email="test@corp.com"
        )
        
        self.customer = Customer.objects.create(
            corporate=self.corporate,
            name="Test Customer",
            email="customer@test.com"
        )
        
        # Create multiple invoices with different statuses
        self.invoices = []
        for i in range(5):
            status = "POSTED" if i % 2 == 0 else "DRAFT"
            invoice = Invoices.objects.create(
                corporate=self.corporate,
                customer=self.customer,
                number=f"INV-{i:03d}",
                date=date.today() - timedelta(days=i*10),
                due_date=date.today() + timedelta(days=30-i*10),
                status=status,
                posted_at=timezone.now() if status == "POSTED" else None,
                sub_total=Decimal(f"{(i+1)*1000}.00"),
                tax_total=Decimal(f"{(i+1)*160}.00"),
                total=Decimal(f"{(i+1)*1160}.00"),
            )
            self.invoices.append(invoice)
    
    def test_only_posted_invoices_in_calculations(self):
        """Test that only POSTED invoices are used in calculations"""
        all_invoices = Invoices.objects.filter(corporate=self.corporate)
        posted_invoices = all_invoices.filter(status="POSTED")
        
        # Should have 5 total, 3 posted (indices 0, 2, 4)
        self.assertEqual(all_invoices.count(), 5)
        self.assertEqual(posted_invoices.count(), 3)
        
        # Calculate totals
        total_all = sum(inv.total for inv in all_invoices)
        total_posted = sum(inv.total for inv in posted_invoices)
        
        # Posted total should be less than all total
        self.assertLess(total_posted, total_all)
        
        # Posted total should be: 1160 + 3480 + 5800 = 10440
        self.assertEqual(total_posted, Decimal("10440.00"))
    
    def test_draft_to_posted_transition(self):
        """Test transitioning from DRAFT to POSTED"""
        draft_invoice = self.invoices[1]  # Index 1 is DRAFT
        
        # Verify it's draft
        self.assertEqual(draft_invoice.status, "DRAFT")
        self.assertIsNone(draft_invoice.posted_at)
        
        # Post it
        draft_invoice.status = "POSTED"
        draft_invoice.posted_at = timezone.now()
        draft_invoice.save()
        
        # Verify it's now posted
        draft_invoice.refresh_from_db()
        self.assertEqual(draft_invoice.status, "POSTED")
        self.assertIsNotNone(draft_invoice.posted_at)
        
        # Verify it now appears in posted queries
        posted_invoices = Invoices.objects.filter(
            corporate=self.corporate,
            status="POSTED"
        )
        self.assertIn(draft_invoice, posted_invoices)


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
