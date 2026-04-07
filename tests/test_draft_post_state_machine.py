"""
Comprehensive tests for draft → posted state machine across all document types.
Tests cover: Quotation, Invoice, PurchaseOrder, VendorBill
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestQuotationDraftPost:
    """Tests for Quotation draft/post workflow."""
    
    def test_create_quotation_defaults_to_draft(self, client, corporate, user, customer):
        """Test that new quotations default to DRAFT status."""
        data = {
            "corporate": str(corporate.id),
            "customer": str(customer.id),
            "date": "2026-04-05",
            "number": "QT-001",
            "valid_until": "2026-05-05",
            "comments": "Test quotation",
            "T_and_C": "Standard terms",
            "salesperson": str(user.id),
            "ship_date": "2026-04-10",
            "ship_via": "DHL",
            "terms": "Net 30",
            "fob": "Origin",
        }
        
        response = client.post('/api/quotations/save-draft/', data, content_type='application/json')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['status'] == 'DRAFT'
        assert result['data']['drafted_at'] is not None
        assert result['data']['posted_at'] is None
    
    def test_draft_quotation_is_editable(self, client, draft_quotation):
        """Test that draft quotations can be edited."""
        update_data = {
            "id": str(draft_quotation.id),
            "comments": "Updated comments"
        }
        
        response = client.post('/api/quotations/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['comments'] == 'Updated comments'
        assert result['data']['status'] == 'DRAFT'
    
    def test_posted_quotation_is_not_editable(self, client, posted_quotation):
        """Test that posted quotations cannot be edited."""
        update_data = {
            "id": str(posted_quotation.id),
            "comments": "Should not update"
        }
        
        response = client.post('/api/quotations/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 403
        assert 'Posted' in response.json()['message']
    
    def test_save_draft_partial_data_accepted(self, client, draft_quotation):
        """Test that partial data is accepted for draft saves."""
        partial_data = {
            "id": str(draft_quotation.id),
            "comments": "Partial update"
        }
        
        response = client.post('/api/quotations/save-draft/', partial_data, content_type='application/json')
        assert response.status_code == 200
    
    def test_post_fails_without_required_fields(self, client, incomplete_quotation):
        """Test that posting fails when required fields are missing."""
        response = client.post(f'/api/quotations/{incomplete_quotation.id}/post/')
        assert response.status_code == 400
        errors = response.json()['errors']
        assert any('line items' in str(e).lower() for e in errors)
    
    def test_post_succeeds_with_valid_quotation(self, client, complete_quotation, user):
        """Test that posting succeeds with all required fields."""
        response = client.post(f'/api/quotations/{complete_quotation.id}/post/')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['status'] == 'POSTED'
        assert result['data']['posted_at'] is not None
        assert result['data']['posted_by'] == str(user.id)
    
    def test_auto_save_accepts_any_partial_payload(self, client, draft_quotation):
        """Test that auto-save accepts minimal partial data."""
        partial_data = {"comments": "Auto-saved"}
        
        response = client.patch(
            f'/api/quotations/{draft_quotation.id}/auto-save/',
            partial_data,
            content_type='application/json'
        )
        assert response.status_code == 200
    
    def test_posted_at_and_posted_by_set_on_post(self, client, complete_quotation, user):
        """Test that posted_at and posted_by are set correctly."""
        response = client.post(f'/api/quotations/{complete_quotation.id}/post/')
        result = response.json()
        
        assert result['data']['posted_at'] is not None
        assert result['data']['posted_by'] == str(user.id)
    
    def test_draft_not_visible_to_other_tenant(self, client, draft_quotation, other_corporate_user):
        """Test that drafts are isolated by corporate."""
        client.force_authenticate(user=other_corporate_user)
        response = client.get(f'/api/quotations/{draft_quotation.id}/')
        assert response.status_code == 404
    
    def test_only_authorised_role_can_post(self, client, complete_quotation, viewer_user):
        """Test that only users with post permission can post documents."""
        client.force_authenticate(user=viewer_user)
        response = client.post(f'/api/quotations/{complete_quotation.id}/post/')
        assert response.status_code == 403


@pytest.mark.django_db
class TestInvoiceDraftPost:
    """Tests for Invoice draft/post workflow."""
    
    def test_create_invoice_defaults_to_draft(self, client, corporate, user, customer):
        """Test that new invoices default to DRAFT status."""
        data = {
            "corporate": str(corporate.id),
            "customer": str(customer.id),
            "date": "2026-04-05",
            "number": "INV-001",
            "due_date": "2026-05-05",
            "salesperson": str(user.id),
        }
        
        response = client.post('/api/invoices/save-draft/', data, content_type='application/json')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['status'] == 'DRAFT'
    
    def test_draft_invoice_is_editable(self, client, draft_invoice):
        """Test that draft invoices can be edited."""
        update_data = {
            "id": str(draft_invoice.id),
            "comments": "Updated"
        }
        
        response = client.post('/api/invoices/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 200
    
    def test_posted_invoice_is_not_editable(self, client, posted_invoice):
        """Test that posted invoices cannot be edited."""
        update_data = {
            "id": str(posted_invoice.id),
            "comments": "Should fail"
        }
        
        response = client.post('/api/invoices/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 403
    
    def test_post_invoice_creates_journal_entry(self, client, complete_invoice):
        """Test that posting an invoice creates a journal entry."""
        response = client.post(f'/api/invoices/{complete_invoice.id}/post/')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['journal_entry'] is not None


@pytest.mark.django_db
class TestPurchaseOrderDraftPost:
    """Tests for PurchaseOrder draft/post workflow."""
    
    def test_create_purchase_order_defaults_to_draft(self, client, corporate, user, vendor):
        """Test that new purchase orders default to DRAFT status."""
        data = {
            "corporate": str(corporate.id),
            "vendor": str(vendor.id),
            "date": "2026-04-05",
            "number": "PO-001",
            "expected_delivery": "2026-05-05",
            "created_by": str(user.id),
        }
        
        response = client.post('/api/purchase-orders/save-draft/', data, content_type='application/json')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['status'] == 'DRAFT'
    
    def test_draft_purchase_order_is_editable(self, client, draft_po):
        """Test that draft purchase orders can be edited."""
        update_data = {
            "id": str(draft_po.id),
            "comments": "Updated"
        }
        
        response = client.post('/api/purchase-orders/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 200
    
    def test_posted_purchase_order_is_not_editable(self, client, posted_po):
        """Test that posted purchase orders cannot be edited."""
        update_data = {
            "id": str(posted_po.id),
            "comments": "Should fail"
        }
        
        response = client.post('/api/purchase-orders/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.django_db
class TestVendorBillDraftPost:
    """Tests for VendorBill draft/post workflow."""
    
    def test_create_vendor_bill_defaults_to_draft(self, client, corporate, user, vendor):
        """Test that new vendor bills default to DRAFT status."""
        data = {
            "corporate": str(corporate.id),
            "vendor": str(vendor.id),
            "date": "2026-04-05",
            "number": "BILL-001",
            "due_date": "2026-05-05",
            "created_by": str(user.id),
        }
        
        response = client.post('/api/vendor-bills/save-draft/', data, content_type='application/json')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['status'] == 'DRAFT'
    
    def test_draft_vendor_bill_is_editable(self, client, draft_bill):
        """Test that draft vendor bills can be edited."""
        update_data = {
            "id": str(draft_bill.id),
            "comments": "Updated"
        }
        
        response = client.post('/api/vendor-bills/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 200
    
    def test_posted_vendor_bill_is_not_editable(self, client, posted_bill):
        """Test that posted vendor bills cannot be edited."""
        update_data = {
            "id": str(posted_bill.id),
            "comments": "Should fail"
        }
        
        response = client.post('/api/vendor-bills/save-draft/', update_data, content_type='application/json')
        assert response.status_code == 403
    
    def test_post_vendor_bill_creates_journal_entry(self, client, complete_bill):
        """Test that posting a vendor bill creates a journal entry."""
        response = client.post(f'/api/vendor-bills/{complete_bill.id}/post/')
        assert response.status_code == 200
        result = response.json()
        assert result['data']['journal_entry'] is not None


# Fixtures
@pytest.fixture
def corporate(db):
    """Create a test corporate."""
    from OrgAuth.models import Corporate
    return Corporate.objects.create(name="Test Corp", email="test@corp.com")


@pytest.fixture
def user(db, corporate):
    """Create a test user."""
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        corporate=corporate
    )


@pytest.fixture
def customer(db, corporate):
    """Create a test customer."""
    from Accounting.models import Customer
    return Customer.objects.create(
        corporate=corporate,
        name="Test Customer",
        email="customer@test.com"
    )


@pytest.fixture
def vendor(db, corporate):
    """Create a test vendor."""
    from Accounting.models import Vendor
    return Vendor.objects.create(
        corporate=corporate,
        name="Test Vendor",
        email="vendor@test.com"
    )


@pytest.fixture
def draft_quotation(db, corporate, customer, user):
    """Create a draft quotation."""
    from Accounting.models import Quotation
    return Quotation.objects.create(
        corporate=corporate,
        customer=customer,
        date="2026-04-05",
        number="QT-DRAFT-001",
        status="DRAFT",
        valid_until="2026-05-05",
        comments="Draft",
        T_and_C="Terms",
        salesperson=user,
        ship_date="2026-04-10",
        ship_via="DHL",
        terms="Net 30",
        fob="Origin",
        drafted_at=timezone.now()
    )


@pytest.fixture
def posted_quotation(db, corporate, customer, user):
    """Create a posted quotation."""
    from Accounting.models import Quotation
    return Quotation.objects.create(
        corporate=corporate,
        customer=customer,
        date="2026-04-05",
        number="QT-POSTED-001",
        status="POSTED",
        valid_until="2026-05-05",
        comments="Posted",
        T_and_C="Terms",
        salesperson=user,
        ship_date="2026-04-10",
        ship_via="DHL",
        terms="Net 30",
        fob="Origin",
        posted_at=timezone.now(),
        posted_by=user
    )


@pytest.fixture
def complete_quotation(db, corporate, customer, user):
    """Create a complete quotation ready for posting."""
    from Accounting.models import Quotation, QuotationLine, TaxRate
    
    tax_rate = TaxRate.objects.create(
        corporate=corporate,
        name="general_rated",
        rate=Decimal("16.00")
    )
    
    quotation = Quotation.objects.create(
        corporate=corporate,
        customer=customer,
        date="2026-04-05",
        number="QT-COMPLETE-001",
        status="DRAFT",
        valid_until="2026-05-05",
        comments="Complete",
        T_and_C="Terms",
        salesperson=user,
        ship_date="2026-04-10",
        ship_via="DHL",
        terms="Net 30",
        fob="Origin"
    )
    
    QuotationLine.objects.create(
        quotation=quotation,
        description="Test Item",
        quantity=10,
        unit_price=Decimal("100.00"),
        amount=Decimal("1000.00"),
        discount=Decimal("0.00"),
        taxable=tax_rate,
        tax_amount=Decimal("160.00"),
        sub_total=Decimal("1000.00"),
        total=Decimal("1160.00")
    )
    
    return quotation


@pytest.fixture
def incomplete_quotation(db, corporate, customer, user):
    """Create an incomplete quotation (no lines)."""
    from Accounting.models import Quotation
    return Quotation.objects.create(
        corporate=corporate,
        customer=customer,
        date="2026-04-05",
        number="QT-INCOMPLETE-001",
        status="DRAFT",
        valid_until="2026-05-05",
        comments="Incomplete",
        T_and_C="Terms",
        salesperson=user,
        ship_date="2026-04-10",
        ship_via="DHL",
        terms="Net 30",
        fob="Origin"
    )
