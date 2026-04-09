"""
Document PDF Generation Views
Generates PDF documents for invoices, quotes, POs, and bills
"""
import base64
import os
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from io import BytesIO
from decimal import Decimal

from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from OrgAuth.models.document_template import DocumentTemplate


def build_company_info(corporate):
    """Build company_info dict from a Corporate registry dict, resolving the logo file path."""
    import os
    from django.conf import settings as django_settings

    logo = ''
    raw_logo = corporate.get('logo') or corporate.get('logo_url') or ''
    if raw_logo:
        raw_logo = str(raw_logo)
        if os.path.isabs(raw_logo) and os.path.exists(raw_logo):
            logo = raw_logo
        elif raw_logo.startswith('data:image'):
            logo = raw_logo
        elif hasattr(django_settings, 'MEDIA_ROOT'):
            full_path = os.path.join(django_settings.MEDIA_ROOT, raw_logo.lstrip('/'))
            if os.path.exists(full_path):
                logo = full_path

    return {
        'name': corporate.get('name', 'Company Name'),
        'address': corporate.get('address', ''),
        'city': corporate.get('city', ''),
        'country': corporate.get('country', ''),
        'phone': corporate.get('phone', ''),
        'email': corporate.get('email', ''),
        'tax_id': corporate.get('tax_id', ''),
        'website': corporate.get('website', ''),
        'logo': logo,
    }


def hex_to_reportlab_color(hex_color):
    """Convert hex color to reportlab Color object"""
    try:
        return colors.HexColor(hex_color)
    except:
        return colors.HexColor('#1565C0')


def get_logo_image(corporate):
    """Extract logo from corporate and return Image object"""
    try:
        # Support both 'logo' and 'logo_url' keys
        logo_path = corporate.get('logo') or corporate.get('logo_url')
        if not logo_path:
            return None
        
        # If logo is a file path
        if isinstance(logo_path, str) and os.path.exists(logo_path):
            return Image(logo_path, width=2*inch, height=0.8*inch, kind='proportional')
        
        # If logo is base64 data URL
        if isinstance(logo_path, str) and logo_path.startswith('data:image'):
            # Extract base64 data
            parts = logo_path.split(',', 1)
            if len(parts) == 2:
                image_data = base64.b64decode(parts[1])
                img_buffer = BytesIO(image_data)
                return Image(img_buffer, width=2*inch, height=0.8*inch, kind='proportional')
        
        return None
    except Exception as e:
        print(f"Error loading logo: {str(e)}")
        return None


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
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=0.5*inch, 
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Use template settings or defaults
    accent_color = hex_to_reportlab_color(template.accent_color if template else '#1565C0')
    font_name = template.font if template and template.font in ['Helvetica', 'Times-Roman', 'Courier'] else 'Helvetica'
    logo_align = template.logo_align if template else 'left'
    show_logo = template.show_logo if template else True
    show_tagline = template.show_tagline if template else False
    tagline = template.tagline if template else ''
    show_bank_details = template.show_bank_details if template else True
    show_signature = template.show_signature_line if template else True
    footer_text = template.footer_text if template else 'Thank you for your business.'
    header_bg = template.header_bg if template else True
    border_style = template.border_style if template else 'thin'
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Document title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=accent_color,
        spaceAfter=12,
        alignment=TA_RIGHT,
        fontName=f'{font_name}-Bold' if font_name != 'Courier' else font_name,
    )
    
    company_name_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Normal'],
        fontSize=14,
        textColor=accent_color,
        fontName=f'{font_name}-Bold' if font_name != 'Courier' else font_name,
        alignment=TA_LEFT if logo_align == 'left' else TA_CENTER if logo_align == 'center' else TA_RIGHT,
    )
    
    # Document title
    doc_titles = {
        'invoice': 'INVOICE',
        'quote': 'QUOTATION',
        'po': 'PURCHASE ORDER',
        'bill': 'VENDOR BILL',
    }
    
    # Header section with logo and company info
    header_elements = []
    
    # Get logo if available
    logo_img = None
    if show_logo:
        logo_img = get_logo_image(company_info)
    
    # Build header table based on logo alignment
    if logo_align == 'center':
        # Centered layout: logo and company name centered, document title on right
        if logo_img:
            header_elements.append([logo_img])
        header_elements.append([Paragraph(f"<b>{company_info.get('name', 'Company Name')}</b>", company_name_style)])
        if show_tagline and tagline:
            header_elements.append([Paragraph(tagline, ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))])
        
        # Add company details
        company_details = []
        if company_info.get('address'):
            company_details.append(company_info['address'])
        if company_info.get('city') or company_info.get('country'):
            company_details.append(f"{company_info.get('city', '')}, {company_info.get('country', '')}".strip(', '))
        if company_info.get('phone'):
            company_details.append(f"Phone: {company_info['phone']}")
        if company_info.get('email'):
            company_details.append(f"Email: {company_info['email']}")
        
        for detail in company_details:
            header_elements.append([Paragraph(detail, ParagraphStyle('Detail', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))])
        
        header_table = Table(header_elements, colWidths=[6.5*inch])
        header_style = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        if header_bg:
            header_style.append(('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.92, 0.95, 0.98)))
        header_table.setStyle(TableStyle(header_style))
        elements.append(header_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Document title and info on the right
        doc_title = Paragraph(doc_titles.get(document_type, 'DOCUMENT'), title_style)
        doc_info_lines = [
            Paragraph(f"<b>{document_data.get('number', 'N/A')}</b>", ParagraphStyle('DocNum', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)),
            Paragraph(f"Date: {document_data.get('date', 'N/A')}", ParagraphStyle('DocDate', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)),
        ]
        
        if document_data.get('due_date'):
            doc_info_lines.append(Paragraph(f"Due: {document_data['due_date']}", ParagraphStyle('DueDate', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
        if document_data.get('valid_until'):
            doc_info_lines.append(Paragraph(f"Valid Until: {document_data['valid_until']}", ParagraphStyle('ValidUntil', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
        
        doc_info_table = Table([[doc_title]] + [[line] for line in doc_info_lines], colWidths=[6.5*inch])
        doc_info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ]))
        elements.append(doc_info_table)
        
    else:
        # Left or Right alignment
        left_content = []
        right_content = []
        
        if logo_align == 'left':
            # Logo and company on left, document title on right
            if logo_img:
                left_content.append(logo_img)
            left_content.append(Paragraph(f"<b>{company_info.get('name', 'Company Name')}</b>", company_name_style))
            if show_tagline and tagline:
                left_content.append(Paragraph(tagline, ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=9)))
            
            # Company details
            if company_info.get('address'):
                left_content.append(Paragraph(company_info['address'], ParagraphStyle('Addr', parent=styles['Normal'], fontSize=9)))
            if company_info.get('city') or company_info.get('country'):
                left_content.append(Paragraph(f"{company_info.get('city', '')}, {company_info.get('country', '')}".strip(', '), ParagraphStyle('City', parent=styles['Normal'], fontSize=9)))
            if company_info.get('phone'):
                left_content.append(Paragraph(f"Phone: {company_info['phone']}", ParagraphStyle('Phone', parent=styles['Normal'], fontSize=9)))
            if company_info.get('email'):
                left_content.append(Paragraph(f"Email: {company_info['email']}", ParagraphStyle('Email', parent=styles['Normal'], fontSize=9)))
            
            # Document info on right
            right_content.append(Paragraph(doc_titles.get(document_type, 'DOCUMENT'), title_style))
            right_content.append(Paragraph(f"<b>{document_data.get('number', 'N/A')}</b>", ParagraphStyle('DocNum', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)))
            right_content.append(Paragraph(f"Date: {document_data.get('date', 'N/A')}", ParagraphStyle('DocDate', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
            
            if document_data.get('due_date'):
                right_content.append(Paragraph(f"Due: {document_data['due_date']}", ParagraphStyle('DueDate', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
            if document_data.get('valid_until'):
                right_content.append(Paragraph(f"Valid Until: {document_data['valid_until']}", ParagraphStyle('ValidUntil', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
        
        else:  # right alignment
            # Document title on left, logo and company on right
            left_content.append(Paragraph(doc_titles.get(document_type, 'DOCUMENT'), ParagraphStyle('TitleLeft', parent=title_style, alignment=TA_LEFT)))
            left_content.append(Paragraph(f"<b>{document_data.get('number', 'N/A')}</b>", ParagraphStyle('DocNum', parent=styles['Normal'], fontSize=10)))
            left_content.append(Paragraph(f"Date: {document_data.get('date', 'N/A')}", ParagraphStyle('DocDate', parent=styles['Normal'], fontSize=9)))
            
            if document_data.get('due_date'):
                left_content.append(Paragraph(f"Due: {document_data['due_date']}", ParagraphStyle('DueDate', parent=styles['Normal'], fontSize=9)))
            if document_data.get('valid_until'):
                left_content.append(Paragraph(f"Valid Until: {document_data['valid_until']}", ParagraphStyle('ValidUntil', parent=styles['Normal'], fontSize=9)))
            
            # Company on right
            if logo_img:
                right_content.append(logo_img)
            right_content.append(Paragraph(f"<b>{company_info.get('name', 'Company Name')}</b>", ParagraphStyle('CompanyRight', parent=company_name_style, alignment=TA_RIGHT)))
            if show_tagline and tagline:
                right_content.append(Paragraph(tagline, ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
            
            if company_info.get('address'):
                right_content.append(Paragraph(company_info['address'], ParagraphStyle('Addr', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
            if company_info.get('city') or company_info.get('country'):
                right_content.append(Paragraph(f"{company_info.get('city', '')}, {company_info.get('country', '')}".strip(', '), ParagraphStyle('City', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
            if company_info.get('phone'):
                right_content.append(Paragraph(f"Phone: {company_info['phone']}", ParagraphStyle('Phone', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
            if company_info.get('email'):
                right_content.append(Paragraph(f"Email: {company_info['email']}", ParagraphStyle('Email', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)))
        
        # Create two-column header
        max_rows = max(len(left_content), len(right_content))
        header_data = []
        for i in range(max_rows):
            left_item = left_content[i] if i < len(left_content) else ''
            right_item = right_content[i] if i < len(right_content) else ''
            header_data.append([left_item, right_item])
        
        header_table = Table(header_data, colWidths=[3.5*inch, 3*inch])
        header_style = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]
        if header_bg:
            header_style.append(('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.92, 0.95, 0.98)))
        header_table.setStyle(TableStyle(header_style))
        elements.append(header_table)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Bill To / Vendor section
    if document_type in ['invoice', 'quote']:
        bill_to_label = 'BILL TO:'
        party_name = document_data.get('customer', 'N/A')
    else:
        bill_to_label = 'VENDOR:'
        party_name = document_data.get('vendor', 'N/A')
    
    bill_to = Paragraph(
        f"<b><font color='{template.accent_color if template else '#1565C0'}'>{bill_to_label}</font></b><br/>{party_name}", 
        ParagraphStyle('BillTo', parent=styles['Normal'], fontSize=10, fontName=font_name)
    )
    elements.append(bill_to)
    elements.append(Spacer(1, 0.25*inch))
    
    # Line items table
    line_items_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]
    
    for line in document_data.get('lines', []):
        amount = line.get('amount') or (line.get('quantity', 0) * line.get('unit_price', 0))
        line_items_data.append([
            Paragraph(line.get('description', ''), ParagraphStyle('LineDesc', parent=styles['Normal'], fontSize=9, fontName=font_name)),
            str(line.get('quantity', 0)),
            f"${float(line.get('unit_price', 0)):.2f}",
            f"${float(amount):.2f}",
        ])
    
    line_items_table = Table(line_items_data, colWidths=[3.5*inch, 1*inch, 1.25*inch, 1.25*inch])
    line_items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), f'{font_name}-Bold' if font_name != 'Courier' else font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    elements.append(line_items_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Totals section
    totals_data = [
        ['Subtotal:', f"${float(document_data.get('sub_total', 0)):.2f}"],
        ['Tax:', f"${float(document_data.get('tax_total', 0)):.2f}"],
    ]
    
    # Add total with proper formatting
    total_para = Paragraph(
        f"<b>${float(document_data.get('total', 0)):.2f}</b>",
        ParagraphStyle('TotalAmount', parent=styles['Normal'], fontSize=12, fontName=f'{font_name}-Bold' if font_name != 'Courier' else font_name, textColor=accent_color)
    )
    totals_data.append([Paragraph('<b>Total:</b>', ParagraphStyle('TotalLabel', parent=styles['Normal'], fontSize=12, fontName=f'{font_name}-Bold' if font_name != 'Courier' else font_name)), total_para])
    
    totals_table = Table(totals_data, colWidths=[1.5*inch, 1.5*inch], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), font_name),
        ('FONTSIZE', (0, 0), (-1, -2), 10),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, accent_color),
        ('TOPPADDING', (0, -1), (-1, -1), 10),
    ]))
    elements.append(totals_table)
    
    # Notes and terms
    if document_data.get('terms') or document_data.get('comments'):
        elements.append(Spacer(1, 0.3*inch))
        if document_data.get('terms'):
            terms_para = Paragraph(
                f"<b>Terms & Conditions:</b><br/>{document_data['terms']}", 
                ParagraphStyle('Terms', parent=styles['Normal'], fontSize=9, fontName=font_name)
            )
            elements.append(terms_para)
            elements.append(Spacer(1, 0.15*inch))
        if document_data.get('comments'):
            comments_para = Paragraph(
                f"<b>Notes:</b><br/>{document_data['comments']}", 
                ParagraphStyle('Comments', parent=styles['Normal'], fontSize=9, fontName=font_name)
            )
            elements.append(comments_para)
    
    # Bank details and signature (from template)
    if show_bank_details or show_signature:
        elements.append(Spacer(1, 0.3*inch))
        if show_bank_details:
            contact_parts = []
            if company_info.get('phone'):
                contact_parts.append(f"Phone: {company_info['phone']}")
            if company_info.get('email'):
                contact_parts.append(f"Email: {company_info['email']}")
            if company_info.get('tax_id'):
                contact_parts.append(f"Tax ID: {company_info['tax_id']}")
            if company_info.get('website'):
                contact_parts.append(f"Web: {company_info['website']}")
            if contact_parts:
                bank_info = Paragraph(
                    ' | '.join(contact_parts),
                    ParagraphStyle('BankInfo', parent=styles['Normal'], fontSize=8, fontName=font_name, textColor=colors.grey)
                )
                elements.append(bank_info)
        if show_signature:
            elements.append(Spacer(1, 0.3*inch))
            sig_table = Table([['_' * 40], ['Authorised Signature']], colWidths=[2*inch], hAlign='RIGHT')
            sig_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 1), (0, 1), 8),
                ('TEXTCOLOR', (0, 1), (0, 1), colors.grey),
            ]))
            elements.append(sig_table)
    
    # Footer text
    elements.append(Spacer(1, 0.2*inch))
    footer = Paragraph(
        f"<i>{footer_text}</i>", 
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=9,
            textColor=colors.grey,
            fontName=font_name,
        )
    )
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
        
        company_info = build_company_info(corporate)
        
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
        
        company_info = build_company_info(corporate)
        
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
        
        company_info = build_company_info(corporate)
        
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
        
        company_info = build_company_info(corporate)
        
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
