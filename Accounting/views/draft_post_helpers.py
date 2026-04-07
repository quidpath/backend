"""
Draft/Post state machine helpers for Accounting documents.
Provides validation and transition logic for DRAFT → POSTED workflow.
"""
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from quidpath_backend.core.utils.json_response import ResponseProvider


def validate_quotation_for_posting(quotation_data, lines_data, registry):
    """Validate that a quotation has all required fields before posting."""
    errors = []
    
    if not quotation_data.get('customer'):
        errors.append("A customer is required before posting.")
    
    if not lines_data or len(lines_data) == 0:
        errors.append("Cannot post a quotation with no line items.")
    
    if not quotation_data.get('date'):
        errors.append("Date is required before posting.")
    
    if not quotation_data.get('valid_until'):
        errors.append("Valid until date is required before posting.")
    
    if not quotation_data.get('salesperson'):
        errors.append("Salesperson is required before posting.")
    
    # Validate line items have required fields
    for idx, line in enumerate(lines_data):
        if not line.get('description'):
            errors.append(f"Line {idx + 1}: Description is required.")
        if not line.get('quantity') or Decimal(str(line.get('quantity', 0))) <= 0:
            errors.append(f"Line {idx + 1}: Quantity must be greater than zero.")
        if not line.get('unit_price'):
            errors.append(f"Line {idx + 1}: Unit price is required.")
    
    return errors


def validate_invoice_for_posting(invoice_data, lines_data, registry):
    """Validate that an invoice has all required fields before posting."""
    errors = []
    
    if not invoice_data.get('customer'):
        errors.append("A customer is required before posting.")
    
    if not lines_data or len(lines_data) == 0:
        errors.append("Cannot post an invoice with no line items.")
    
    if not invoice_data.get('date'):
        errors.append("Date is required before posting.")
    
    if not invoice_data.get('due_date'):
        errors.append("Due date is required before posting.")
    
    if not invoice_data.get('salesperson'):
        errors.append("Salesperson is required before posting.")
    
    # Validate line items
    for idx, line in enumerate(lines_data):
        if not line.get('description'):
            errors.append(f"Line {idx + 1}: Description is required.")
        if not line.get('quantity') or Decimal(str(line.get('quantity', 0))) <= 0:
            errors.append(f"Line {idx + 1}: Quantity must be greater than zero.")
        if not line.get('unit_price'):
            errors.append(f"Line {idx + 1}: Unit price is required.")
        if not line.get('account'):
            errors.append(f"Line {idx + 1}: Revenue account is required.")
    
    return errors


def validate_purchase_order_for_posting(po_data, lines_data, registry):
    """Validate that a purchase order has all required fields before posting."""
    errors = []
    
    if not po_data.get('vendor'):
        errors.append("A vendor is required before posting.")
    
    if not lines_data or len(lines_data) == 0:
        errors.append("Cannot post a purchase order with no line items.")
    
    if not po_data.get('date'):
        errors.append("Date is required before posting.")
    
    if not po_data.get('expected_delivery'):
        errors.append("Expected delivery date is required before posting.")
    
    # Validate line items
    for idx, line in enumerate(lines_data):
        if not line.get('description'):
            errors.append(f"Line {idx + 1}: Description is required.")
        if not line.get('quantity') or Decimal(str(line.get('quantity', 0))) <= 0:
            errors.append(f"Line {idx + 1}: Quantity must be greater than zero.")
        if not line.get('unit_price'):
            errors.append(f"Line {idx + 1}: Unit price is required.")
        if not line.get('account'):
            errors.append(f"Line {idx + 1}: Expense account is required.")
    
    return errors


def validate_vendor_bill_for_posting(bill_data, lines_data, registry):
    """Validate that a vendor bill has all required fields before posting."""
    errors = []
    
    if not bill_data.get('vendor'):
        errors.append("A vendor is required before posting.")
    
    if not lines_data or len(lines_data) == 0:
        errors.append("Cannot post a vendor bill with no line items.")
    
    if not bill_data.get('date'):
        errors.append("Date is required before posting.")
    
    if not bill_data.get('due_date'):
        errors.append("Due date is required before posting.")
    
    # Validate line items
    for idx, line in enumerate(lines_data):
        if not line.get('description'):
            errors.append(f"Line {idx + 1}: Description is required.")
        if not line.get('quantity') or Decimal(str(line.get('quantity', 0))) <= 0:
            errors.append(f"Line {idx + 1}: Quantity must be greater than zero.")
        if not line.get('unit_price'):
            errors.append(f"Line {idx + 1}: Unit price is required.")
        if not line.get('account'):
            errors.append(f"Line {idx + 1}: Expense account is required.")
    
    return errors


def check_document_is_editable(document, document_type="document"):
    """Check if a document can be edited (must be in DRAFT status)."""
    status_field = 'status' if hasattr(document, 'status') else 'state'
    current_status = getattr(document, status_field, None)
    
    if current_status and current_status.upper() != 'DRAFT':
        return False, f"Posted {document_type}s cannot be edited. Current status: {current_status}"
    
    return True, None


def mark_document_as_posted(document, user_id, registry):
    """Mark a document as posted with timestamp and user."""
    document['status'] = 'POSTED'
    document['posted_at'] = timezone.now().isoformat()
    document['posted_by'] = user_id
    return document


def mark_document_as_drafted(document):
    """Mark a document as drafted with timestamp."""
    if not document.get('drafted_at'):
        document['drafted_at'] = timezone.now().isoformat()
    return document
