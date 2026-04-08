"""
Comprehensive tests for document PDF generation with templates.
Tests cover: Invoice, Quotation, Purchase Order, Vendor Bill
"""
import pytest
import base64
from io import BytesIO
from decimal import Decimal
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from PIL import Image as PILImage

from Accounting.views.document_pdf import (
    generate_document_pdf,
    hex_to_reportlab_color,
    get_logo_image,
)
from OrgAuth.models import Corporate, CorporateUser
from OrgAuth.models.document_template import DocumentTemplate
from Accounting.models import Invoices, InvoiceLine, Customer

User = get_user_model()


@pytest.fixture
def sample_logo_base64():
    """Create a simple test logo as base64"""
    # Create a simple 100x50 red rectangle
    img = PILImage.new('RGB', (100, 50), color='red')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_data = base64.b64encode(buffer.read()).decode('utf-8')
    return f"data:image/png;base64,{img_data}"


@pytest.fixture
def corporate_with_logo(db, sample_logo_base64):
    """Create a corporate with logo"""
    corporate = Corporate.objects.create(
        name="Test Company Ltd",
        email="test@company.com",
        phone="+254700000000",
        address="123 Test Street",
        city="Nairobi",
        country="Kenya",
        tax_id="TAX123456",
    )
    # Store logo as base64 (simulating what would be stored)
    corporate.logo = sample_logo_base64
    corporate.save()
    return corporate


@pytest.fixture
def document_template(corporate_with_logo):
    """Create a document template with custom settings"""
    return DocumentTemplate.objects.create(
        corporate=corporate_with_logo,
        document_type='invoice',
        accent_color='#2E7D32',
        font='Helvetica',
        logo_align='left',
        show_logo=True,
        show_tagline=True,
        tagline='Your Trusted Partner',
        border_style='thin',
        header_bg=True,
        footer_text='Thank you for your business!',
        show_bank_details=True,
        show_signature_line=True,
        show_stamp=False,
    )


@pytest.fixture
def sample_document_data():
    """Sample document data for PDF generation"""
    return {
        'number': 'INV-2026-001',
        'date': '2026-04-08',
        'due_date': '2026-05-08',
        'customer': 'Acme Corporation',
        'lines': [
            {
                'description': 'Professional Services',
                'quantity': 5,
                'unit_price': 200.00,
                'amount': 1000.00,
            },
            {
                'description': 'Consulting Fee',
                'quantity': 2,
                'unit_price': 150.00,
                'amount': 300.00,
            },
        ],
        'sub_total': 1300.00,
        'tax_total': 208.00,
        'total': 1508.00,
        'terms': 'Net 30',
        'comments': 'Please pay within 30 days.',
    }


@pytest.fixture
def sample_company_info(sample_logo_base64):
    """Sample company info for PDF generation"""
    return {
        'name': 'Test Company Ltd',
        'logo': sample_logo_base64,
        'address': '123 Test Street',
        'city': 'Nairobi',
        'country': 'Kenya',
        'phone': '+254700000000',
        'email': 'test@company.com',
        'tax_id': 'TAX123456',
        'bank_name': 'Test Bank',
        'bank_account': '1234567890',
        'bank_branch': 'Main Branch',
    }


class TestPDFGenerationUtilities:
    """Test utility functions for PDF generation"""
    
    def test_hex_to_reportlab_color_valid(self):
        """Test hex color conversion with valid input"""
        color = hex_to_reportlab_color('#2E7D32')
        assert color is not None
        # ReportLab colors have rgb attributes
        assert hasattr(color, 'rgb')
    
    def test_hex_to_reportlab_color_invalid(self):
        """Test hex color conversion with invalid input returns default"""
        color = hex_to_reportlab_color('invalid')
        assert color is not None
        # Should return default blue color
    
    def test_get_logo_image_with_base64(self, sample_logo_base64):
        """Test logo extraction from base64 data"""
        company_info = {'logo': sample_logo_base64}
        logo_img = get_logo_image(company_info)
        assert logo_img is not None
    
    def test_get_logo_image_without_logo(self):
        """Test logo extraction when no logo exists"""
        company_info = {}
        logo_img = get_logo_image(company_info)
        assert logo_img is None
    
    def test_get_logo_image_with_invalid_data(self):
        """Test logo extraction with invalid data doesn't crash"""
        company_info = {'logo': 'invalid_data'}
        logo_img = get_logo_image(company_info)
        # Should return None without crashing
        assert logo_img is None


class TestPDFGenerationWithTemplate:
    """Test PDF generation with document templates"""
    
    def test_generate_invoice_pdf_with_template(
        self, sample_document_data, sample_company_info, document_template
    ):
        """Test invoice PDF generation with custom template"""
        pdf_buffer = generate_document_pdf(
            sample_document_data,
            'invoice',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        assert isinstance(pdf_buffer, BytesIO)
        
        # Check that PDF has content
        pdf_content = pdf_buffer.getvalue()
        assert len(pdf_content) > 0
        
        # Check PDF header
        assert pdf_content.startswith(b'%PDF')
    
    def test_generate_quotation_pdf_with_template(
        self, sample_company_info, document_template
    ):
        """Test quotation PDF generation"""
        quote_data = {
            'number': 'QT-2026-001',
            'date': '2026-04-08',
            'valid_until': '2026-05-08',
            'customer': 'Acme Corporation',
            'lines': [
                {
                    'description': 'Product A',
                    'quantity': 10,
                    'unit_price': 50.00,
                    'amount': 500.00,
                },
            ],
            'sub_total': 500.00,
            'tax_total': 80.00,
            'total': 580.00,
        }
        
        pdf_buffer = generate_document_pdf(
            quote_data,
            'quote',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        pdf_content = pdf_buffer.getvalue()
        assert len(pdf_content) > 0
        assert pdf_content.startswith(b'%PDF')
    
    def test_generate_po_pdf_with_template(
        self, sample_company_info, document_template
    ):
        """Test purchase order PDF generation"""
        po_data = {
            'number': 'PO-2026-001',
            'date': '2026-04-08',
            'expected_delivery': '2026-04-20',
            'vendor': 'Supplier Inc',
            'lines': [
                {
                    'description': 'Raw Materials',
                    'quantity': 100,
                    'unit_price': 10.00,
                    'amount': 1000.00,
                },
            ],
            'sub_total': 1000.00,
            'tax_total': 160.00,
            'total': 1160.00,
        }
        
        pdf_buffer = generate_document_pdf(
            po_data,
            'po',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        pdf_content = pdf_buffer.getvalue()
        assert len(pdf_content) > 0
        assert pdf_content.startswith(b'%PDF')
    
    def test_generate_bill_pdf_with_template(
        self, sample_company_info, document_template
    ):
        """Test vendor bill PDF generation"""
        bill_data = {
            'number': 'BILL-2026-001',
            'date': '2026-04-08',
            'due_date': '2026-05-08',
            'vendor': 'Supplier Inc',
            'lines': [
                {
                    'description': 'Services Rendered',
                    'quantity': 1,
                    'unit_price': 5000.00,
                    'amount': 5000.00,
                },
            ],
            'sub_total': 5000.00,
            'tax_total': 800.00,
            'total': 5800.00,
        }
        
        pdf_buffer = generate_document_pdf(
            bill_data,
            'bill',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        pdf_content = pdf_buffer.getvalue()
        assert len(pdf_content) > 0
        assert pdf_content.startswith(b'%PDF')


class TestPDFGenerationWithoutTemplate:
    """Test PDF generation without templates (using defaults)"""
    
    def test_generate_pdf_without_template(
        self, sample_document_data, sample_company_info
    ):
        """Test PDF generation with default settings when no template exists"""
        pdf_buffer = generate_document_pdf(
            sample_document_data,
            'invoice',
            sample_company_info,
            None  # No template
        )
        
        assert pdf_buffer is not None
        pdf_content = pdf_buffer.getvalue()
        assert len(pdf_content) > 0
        assert pdf_content.startswith(b'%PDF')


class TestPDFGenerationEdgeCases:
    """Test edge cases and error handling"""
    
    def test_generate_pdf_with_empty_lines(
        self, sample_company_info, document_template
    ):
        """Test PDF generation with no line items"""
        doc_data = {
            'number': 'INV-2026-001',
            'date': '2026-04-08',
            'customer': 'Test Customer',
            'lines': [],
            'sub_total': 0.00,
            'tax_total': 0.00,
            'total': 0.00,
        }
        
        pdf_buffer = generate_document_pdf(
            doc_data,
            'invoice',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
    
    def test_generate_pdf_with_missing_optional_fields(
        self, sample_company_info, document_template
    ):
        """Test PDF generation with minimal data"""
        doc_data = {
            'number': 'INV-2026-001',
            'date': '2026-04-08',
            'customer': 'Test Customer',
            'lines': [
                {
                    'description': 'Item',
                    'quantity': 1,
                    'unit_price': 100.00,
                },
            ],
            'sub_total': 100.00,
            'tax_total': 0.00,
            'total': 100.00,
        }
        
        pdf_buffer = generate_document_pdf(
            doc_data,
            'invoice',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
    
    def test_generate_pdf_with_long_descriptions(
        self, sample_company_info, document_template
    ):
        """Test PDF generation with very long line descriptions"""
        doc_data = {
            'number': 'INV-2026-001',
            'date': '2026-04-08',
            'customer': 'Test Customer',
            'lines': [
                {
                    'description': 'This is a very long description that should wrap properly in the PDF document without causing any layout issues or crashes. ' * 5,
                    'quantity': 1,
                    'unit_price': 100.00,
                    'amount': 100.00,
                },
            ],
            'sub_total': 100.00,
            'tax_total': 16.00,
            'total': 116.00,
        }
        
        pdf_buffer = generate_document_pdf(
            doc_data,
            'invoice',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
    
    def test_generate_pdf_with_special_characters(
        self, sample_company_info, document_template
    ):
        """Test PDF generation with special characters"""
        doc_data = {
            'number': 'INV-2026-001',
            'date': '2026-04-08',
            'customer': 'Test & Company <Ltd>',
            'lines': [
                {
                    'description': 'Item with special chars: & < > " \'',
                    'quantity': 1,
                    'unit_price': 100.00,
                    'amount': 100.00,
                },
            ],
            'sub_total': 100.00,
            'tax_total': 16.00,
            'total': 116.00,
            'comments': 'Notes with special chars: & < > " \'',
        }
        
        pdf_buffer = generate_document_pdf(
            doc_data,
            'invoice',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0


class TestTemplateAlignmentOptions:
    """Test different logo alignment options"""
    
    def test_generate_pdf_with_left_alignment(
        self, sample_document_data, sample_company_info, corporate_with_logo
    ):
        """Test PDF with left-aligned logo"""
        template = DocumentTemplate.objects.create(
            corporate=corporate_with_logo,
            document_type='invoice',
            logo_align='left',
            show_logo=True,
        )
        
        pdf_buffer = generate_document_pdf(
            sample_document_data,
            'invoice',
            sample_company_info,
            template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
    
    def test_generate_pdf_with_center_alignment(
        self, sample_document_data, sample_company_info, corporate_with_logo
    ):
        """Test PDF with center-aligned logo"""
        template = DocumentTemplate.objects.create(
            corporate=corporate_with_logo,
            document_type='invoice',
            logo_align='center',
            show_logo=True,
        )
        
        pdf_buffer = generate_document_pdf(
            sample_document_data,
            'invoice',
            sample_company_info,
            template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
    
    def test_generate_pdf_with_right_alignment(
        self, sample_document_data, sample_company_info, corporate_with_logo
    ):
        """Test PDF with right-aligned logo"""
        template = DocumentTemplate.objects.create(
            corporate=corporate_with_logo,
            document_type='invoice',
            logo_align='right',
            show_logo=True,
        )
        
        pdf_buffer = generate_document_pdf(
            sample_document_data,
            'invoice',
            sample_company_info,
            template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
    
    def test_generate_pdf_without_logo(
        self, sample_document_data, sample_company_info, corporate_with_logo
    ):
        """Test PDF with logo disabled"""
        template = DocumentTemplate.objects.create(
            corporate=corporate_with_logo,
            document_type='invoice',
            show_logo=False,
        )
        
        pdf_buffer = generate_document_pdf(
            sample_document_data,
            'invoice',
            sample_company_info,
            template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0


class TestPDFGenerationPerformance:
    """Test PDF generation performance and resource usage"""
    
    def test_generate_pdf_with_many_lines(
        self, sample_company_info, document_template
    ):
        """Test PDF generation with many line items (100+)"""
        lines = [
            {
                'description': f'Item {i}',
                'quantity': i,
                'unit_price': 10.00,
                'amount': i * 10.00,
            }
            for i in range(1, 101)
        ]
        
        doc_data = {
            'number': 'INV-2026-001',
            'date': '2026-04-08',
            'customer': 'Test Customer',
            'lines': lines,
            'sub_total': sum(line['amount'] for line in lines),
            'tax_total': sum(line['amount'] for line in lines) * 0.16,
            'total': sum(line['amount'] for line in lines) * 1.16,
        }
        
        pdf_buffer = generate_document_pdf(
            doc_data,
            'invoice',
            sample_company_info,
            document_template
        )
        
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 0
        # PDF should be generated even with many lines
