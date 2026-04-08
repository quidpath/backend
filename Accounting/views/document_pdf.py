"""
Document PDF Generation Views
Generates PDF documents for invoices, quotes, POs, and bills
"""
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from io import BytesIO
from decimal import Decimal

from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from OrgAuth.models.document_template import DocumentTemplate


def generate_document_pdf(document_data, document_type, company_info, template=None):
    """
    Generate PDF for a document (invoice, quote, PO, or bill)
    
    Args:
        document_data: Dict containing document information
        document_type: str - 'invoice', 'quote', 'po', or 'bill'
        company_info: Dict containing company information and logo
        template: DocumentTemplate instance or None (uses defaults)
    
    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Use template settings or defaults
    accent_color = colors.HexColor(template.accent_color if template else '#1565C0')
    font_name = template.font if template else 'Helvetica'
    show_logo = template.show_logo if template else True
    show_bank_details = template.show_bank_details if template else True
    show_signature = template.show_signature_line if template else True
    footer_text = template.footer_text if template else 'Thank you for your business.'
    header_bg = template.header_bg if template else True
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=accent_color,
        spaceAfter=30,
        alignment=TA_CENTER,
    )
    
    # Document title
    doc_titles = {
        'invoice': 'INVOICE',
        'quote': 'QUOTATION',
        'po': 'PURCHASE ORDER',
        'bill': 'VENDOR BILL',
    }
    title = Paragraph(doc_titles.get(document_type, 'DOCUMENT'), title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Company info and logo header
    header_data = []
    if company_info.get('logo_url'):
        try:
            # Note: In production, you'd fetch the logo from S3 or local storage
            # For now, we'll skip the logo if it's not accessible
            pass
        except Exception:
            pass
    
    # Company details
    company_details = [
        [Paragraph(f"<b>{company_info.get('name', 'Company Name')}</b>", styles['Normal'])],
        [Paragraph(company_info.get('address', ''), styles['Normal'])],
        [Paragraph(f"{company_info.get('city', '')}, {company_info.get('country', '')}", styles['Normal'])],
        [Paragraph(f"Phone: {company_info.get('phone', '')}", styles['Normal'])],
        [Paragraph(f"Email: {company_info.get('email', '')}", styles['Normal'])],
    ]
    
    # Document info
    doc_info = [
        [Paragraph(f"<b>Document #:</b> {document_data.get('number', 'N/A')}", styles['Normal'])],
        [Paragraph(f"<b>Date:</b> {document_data.get('date', 'N/A')}", styles['Normal'])],
    ]
    
    if document_data.get('due_date'):
        doc_info.append([Paragraph(f"<b>Due Date:</b> {document_data['due_date']}", styles['Normal'])])
    if document_data.get('valid_until'):
        doc_info.append([Paragraph(f"<b>Valid Until:</b> {document_data['valid_until']}", styles['Normal'])])
    
    # Create header table
    header_table = Table([[company_details, doc_info]], colWidths=[4*inch, 2.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Bill To / Vendor section
    if document_type in ['invoice', 'quote']:
        bill_to_label = 'BILL TO:'
        party_name = document_data.get('customer', 'N/A')
    else:
        bill_to_label = 'VENDOR:'
        party_name = document_data.get('vendor', 'N/A')
    
    bill_to = Paragraph(f"<b>{bill_to_label}</b><br/>{party_name}", styles['Normal'])
    elements.append(bill_to)
    elements.append(Spacer(1, 0.3*inch))
    
    # Line items table
    line_items_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]
    
    for line in document_data.get('lines', []):
        amount = line.get('amount') or (line.get('quantity', 0) * line.get('unit_price', 0))
        line_items_data.append([
            line.get('description', ''),
            str(line.get('quantity', 0)),
            f"${float(line.get('unit_price', 0)):.2f}",
            f"${float(amount):.2f}",
        ])
    
    line_items_table = Table(line_items_data, colWidths=[3.5*inch, 1*inch, 1.25*inch, 1.25*inch])
    line_items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(line_items_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Totals section
    totals_data = [
        ['Subtotal:', f"${float(document_data.get('sub_total', 0)):.2f}"],
        ['Tax:', f"${float(document_data.get('tax_total', 0)):.2f}"],
        ['<b>Total:</b>', f"<b>${float(document_data.get('total', 0)):.2f}</b>"],
    ]
    
    totals_table = Table(totals_data, colWidths=[1.5*inch, 1.5*inch], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
    ]))
    elements.append(totals_table)
    
    # Notes and terms
    if document_data.get('terms') or document_data.get('comments'):
        elements.append(Spacer(1, 0.4*inch))
        if document_data.get('terms'):
            elements.append(Paragraph(f"<b>Terms & Conditions:</b><br/>{document_data['terms']}", styles['Normal']))
            elements.append(Spacer(1, 0.2*inch))
        if document_data.get('comments'):
            elements.append(Paragraph(f"<b>Notes:</b><br/>{document_data['comments']}", styles['Normal']))
    
    # Bank details and signature (from template)
    if show_bank_details or show_signature:
        elements.append(Spacer(1, 0.3*inch))
        if show_bank_details:
            bank_info = Paragraph(
                f"<b>Bank Details:</b> {company_info.get('bank_name', 'N/A')} | "
                f"Account: {company_info.get('bank_account', 'N/A')} | "
                f"Branch: {company_info.get('bank_branch', 'N/A')}",
                styles['Normal']
            )
            elements.append(bank_info)
        if show_signature:
            elements.append(Spacer(1, 0.3*inch))
            sig_line = Paragraph("_________________________<br/>Authorised Signature", styles['Normal'])
            elements.append(sig_line)
    
    # Footer text
    elements.append(Spacer(1, 0.2*inch))
    footer = Paragraph(f"<i>{footer_text}</i>", ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.grey,
    ))
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


@csrf_exempt
@require_http_methods(["GET"])
def download_invoice_pdf(request):
    """Download invoice as PDF"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        invoice_id = data.get("id")
        if not invoice_id:
            return ResponseProvider(message="Invoice ID required", code=400).bad_request()
        
        registry = ServiceRegistry()
        
        # Get invoice
        invoice = registry.database(
            model_name="Invoices",
            operation="get",
            data={"id": invoice_id},
        )
        
        if not invoice:
            return ResponseProvider(message="Invoice not found", code=404).bad_request()
        
        # Get invoice lines
        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice_id},
        )
        
        # Get company info
        corporate = registry.database(
            model_name="Corporate",
            operation="get",
            data={"id": invoice["corporate_id"]},
        )
        
        company_info = {
            'name': corporate.get('name', 'Company Name'),
            'address': corporate.get('address', ''),
            'city': corporate.get('city', ''),
            'country': corporate.get('country', ''),
            'phone': corporate.get('phone', ''),
            'email': corporate.get('email', ''),
            'logo_url': corporate.get('logo_url', ''),
            'bank_name': corporate.get('bank_name', ''),
            'bank_account': corporate.get('bank_account', ''),
            'bank_branch': corporate.get('bank_branch', ''),
        }
        
        # Fetch template for this document type
        try:
            template = DocumentTemplate.objects.get(
                corporate_id=invoice["corporate_id"],
                document_type='invoice'
            )
        except DocumentTemplate.DoesNotExist:
            template = None
        
        # Prepare document data
        document_data = {
            'number': invoice.get('number'),
            'date': str(invoice.get('date')),
            'due_date': str(invoice.get('due_date')) if invoice.get('due_date') else None,
            'customer': invoice.get('customer', {}).get('name') if isinstance(invoice.get('customer'), dict) else str(invoice.get('customer', 'N/A')),
            'lines': [
                {
                    'description': line.get('description'),
                    'quantity': line.get('quantity'),
                    'unit_price': float(line.get('unit_price', 0)),
                    'amount': float(line.get('amount', 0)),
                }
                for line in lines
            ],
            'sub_total': float(invoice.get('sub_total', 0)),
            'tax_total': float(invoice.get('tax_total', 0)),
            'total': float(invoice.get('total', 0)),
            'terms': invoice.get('terms', ''),
            'comments': invoice.get('comments', ''),
        }
        
        # Generate PDF with template
        pdf_buffer = generate_document_pdf(document_data, 'invoice', company_info, template)
        
        # Return PDF response
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.get("number")}.pdf"'
        return response
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while generating PDF: {str(e)}", 
            code=500
        ).exception()


@csrf_exempt
@require_http_methods(["GET"])
def download_quotation_pdf(request):
    """Download quotation as PDF"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        quote_id = data.get("id")
        if not quote_id:
            return ResponseProvider(message="Quotation ID required", code=400).bad_request()
        
        registry = ServiceRegistry()
        
        # Get quotation
        quote = registry.database(
            model_name="Quotation",
            operation="get",
            data={"id": quote_id},
        )
        
        if not quote:
            return ResponseProvider(message="Quotation not found", code=404).bad_request()
        
        # Get quotation lines
        lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quote_id},
        )
        
        # Get company info
        corporate = registry.database(
            model_name="Corporate",
            operation="get",
            data={"id": quote["corporate_id"]},
        )
        
        company_info = {
            'name': corporate.get('name', 'Company Name'),
            'address': corporate.get('address', ''),
            'city': corporate.get('city', ''),
            'country': corporate.get('country', ''),
            'phone': corporate.get('phone', ''),
            'email': corporate.get('email', ''),
            'logo_url': corporate.get('logo_url', ''),
            'bank_name': corporate.get('bank_name', ''),
            'bank_account': corporate.get('bank_account', ''),
            'bank_branch': corporate.get('bank_branch', ''),
        }
        
        # Fetch template for this document type
        try:
            template = DocumentTemplate.objects.get(
                corporate_id=quote["corporate_id"],
                document_type='quotation'
            )
        except DocumentTemplate.DoesNotExist:
            template = None
        
        # Prepare document data
        document_data = {
            'number': quote.get('number'),
            'date': str(quote.get('date')),
            'valid_until': str(quote.get('valid_until')) if quote.get('valid_until') else None,
            'customer': quote.get('customer', {}).get('name') if isinstance(quote.get('customer'), dict) else str(quote.get('customer', 'N/A')),
            'lines': [
                {
                    'description': line.get('description'),
                    'quantity': line.get('quantity'),
                    'unit_price': float(line.get('unit_price', 0)),
                    'amount': float(line.get('amount', 0)),
                }
                for line in lines
            ],
            'sub_total': float(quote.get('sub_total', 0)) if quote.get('sub_total') else sum(float(l.get('amount', 0)) for l in lines),
            'tax_total': float(quote.get('tax_total', 0)) if quote.get('tax_total') else 0,
            'total': float(quote.get('total', 0)) if quote.get('total') else sum(float(l.get('total', 0)) for l in lines),
            'terms': quote.get('terms', ''),
            'comments': quote.get('comments', ''),
        }
        
        # Generate PDF with template
        pdf_buffer = generate_document_pdf(document_data, 'quote', company_info, template)
        
        # Return PDF response
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="quote_{quote.get("number")}.pdf"'
        return response
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while generating PDF: {str(e)}", 
            code=500
        ).exception()



@csrf_exempt
@require_http_methods(["GET"])
def download_po_pdf(request):
    """Download purchase order as PDF"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        po_id = data.get("id")
        if not po_id:
            return ResponseProvider(message="Purchase Order ID required", code=400).bad_request()
        
        registry = ServiceRegistry()
        
        # Get purchase order
        po = registry.database(
            model_name="PurchaseOrder",
            operation="get",
            data={"id": po_id},
        )
        
        if not po:
            return ResponseProvider(message="Purchase Order not found", code=404).bad_request()
        
        # Get PO lines
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": po_id},
        )
        
        # Get company info
        corporate = registry.database(
            model_name="Corporate",
            operation="get",
            data={"id": po["corporate_id"]},
        )
        
        company_info = {
            'name': corporate.get('name', 'Company Name'),
            'address': corporate.get('address', ''),
            'city': corporate.get('city', ''),
            'country': corporate.get('country', ''),
            'phone': corporate.get('phone', ''),
            'email': corporate.get('email', ''),
            'logo_url': corporate.get('logo_url', ''),
            'bank_name': corporate.get('bank_name', ''),
            'bank_account': corporate.get('bank_account', ''),
            'bank_branch': corporate.get('bank_branch', ''),
        }
        
        # Fetch template for this document type
        try:
            template = DocumentTemplate.objects.get(
                corporate_id=po["corporate_id"],
                document_type='purchase_order'
            )
        except DocumentTemplate.DoesNotExist:
            template = None
        
        # Prepare document data
        document_data = {
            'number': po.get('number'),
            'date': str(po.get('date')),
            'expected_delivery': str(po.get('expected_delivery')) if po.get('expected_delivery') else None,
            'vendor': po.get('vendor', {}).get('name') if isinstance(po.get('vendor'), dict) else str(po.get('vendor', 'N/A')),
            'lines': [
                {
                    'description': line.get('description'),
                    'quantity': line.get('quantity'),
                    'unit_price': float(line.get('unit_price', 0)),
                    'amount': float(line.get('amount', 0)),
                }
                for line in lines
            ],
            'sub_total': float(po.get('sub_total', 0)) if po.get('sub_total') else sum(float(l.get('sub_total', 0)) for l in lines),
            'tax_total': float(po.get('tax_total', 0)) if po.get('tax_total') else 0,
            'total': float(po.get('total', 0)) if po.get('total') else sum(float(l.get('total', 0)) for l in lines),
            'terms': po.get('terms', ''),
            'comments': po.get('comments', ''),
        }
        
        # Generate PDF with template
        pdf_buffer = generate_document_pdf(document_data, 'po', company_info, template)
        
        # Return PDF response
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="po_{po.get("number")}.pdf"'
        return response
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while generating PDF: {str(e)}", 
            code=500
        ).exception()


@csrf_exempt
@require_http_methods(["GET"])
def download_bill_pdf(request):
    """Download vendor bill as PDF"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        bill_id = data.get("id")
        if not bill_id:
            return ResponseProvider(message="Vendor Bill ID required", code=400).bad_request()
        
        registry = ServiceRegistry()
        
        # Get vendor bill
        bill = registry.database(
            model_name="VendorBill",
            operation="get",
            data={"id": bill_id},
        )
        
        if not bill:
            return ResponseProvider(message="Vendor Bill not found", code=404).bad_request()
        
        # Get bill lines
        lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": bill_id},
        )
        
        # Get company info
        corporate = registry.database(
            model_name="Corporate",
            operation="get",
            data={"id": bill["corporate_id"]},
        )
        
        company_info = {
            'name': corporate.get('name', 'Company Name'),
            'address': corporate.get('address', ''),
            'city': corporate.get('city', ''),
            'country': corporate.get('country', ''),
            'phone': corporate.get('phone', ''),
            'email': corporate.get('email', ''),
            'logo_url': corporate.get('logo_url', ''),
            'bank_name': corporate.get('bank_name', ''),
            'bank_account': corporate.get('bank_account', ''),
            'bank_branch': corporate.get('bank_branch', ''),
        }
        
        # Fetch template for this document type
        try:
            template = DocumentTemplate.objects.get(
                corporate_id=bill["corporate_id"],
                document_type='vendor_bill'
            )
        except DocumentTemplate.DoesNotExist:
            template = None
        
        # Prepare document data
        document_data = {
            'number': bill.get('number'),
            'date': str(bill.get('date')),
            'due_date': str(bill.get('due_date')) if bill.get('due_date') else None,
            'vendor': bill.get('vendor', {}).get('name') if isinstance(bill.get('vendor'), dict) else str(bill.get('vendor', 'N/A')),
            'lines': [
                {
                    'description': line.get('description'),
                    'quantity': line.get('quantity'),
                    'unit_price': float(line.get('unit_price', 0)),
                    'amount': float(line.get('amount', 0)),
                }
                for line in lines
            ],
            'sub_total': float(bill.get('sub_total', 0)),
            'tax_total': float(bill.get('tax_total', 0)),
            'total': float(bill.get('total', 0)),
            'terms': bill.get('terms', ''),
            'comments': bill.get('comments', ''),
        }
        
        # Generate PDF with template
        pdf_buffer = generate_document_pdf(document_data, 'bill', company_info, template)
        
        # Return PDF response
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="bill_{bill.get("number")}.pdf"'
        return response
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while generating PDF: {str(e)}", 
            code=500
        ).exception()
