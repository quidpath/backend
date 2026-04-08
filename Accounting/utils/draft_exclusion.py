"""
Draft Exclusion Utility
Provides helper functions to ensure DRAFT documents are never used in accounting calculations
"""
from typing import Dict, List, Any, Optional
from django.db.models import Q, QuerySet


class DraftExclusionMixin:
    """
    Mixin to add draft exclusion methods to views
    """
    
    @staticmethod
    def get_posted_invoices_filter(corporate_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get filter dict for posted invoices only
        
        Args:
            corporate_id: Corporate ID
            **kwargs: Additional filter parameters
            
        Returns:
            Filter dictionary with status=POSTED
        """
        filter_dict = {
            "corporate_id": corporate_id,
            "status": "POSTED",
            **kwargs
        }
        return filter_dict
    
    @staticmethod
    def get_posted_bills_filter(corporate_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get filter dict for posted vendor bills only
        
        Args:
            corporate_id: Corporate ID
            **kwargs: Additional filter parameters
            
        Returns:
            Filter dictionary with status=POSTED
        """
        filter_dict = {
            "corporate_id": corporate_id,
            "status": "POSTED",
            **kwargs
        }
        return filter_dict
    
    @staticmethod
    def get_posted_quotations_filter(corporate_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get filter dict for posted quotations only
        
        Args:
            corporate_id: Corporate ID
            **kwargs: Additional filter parameters
            
        Returns:
            Filter dictionary with status=POSTED
        """
        filter_dict = {
            "corporate_id": corporate_id,
            "status": "POSTED",
            **kwargs
        }
        return filter_dict
    
    @staticmethod
    def get_posted_pos_filter(corporate_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get filter dict for posted purchase orders only
        
        Args:
            corporate_id: Corporate ID
            **kwargs: Additional filter parameters
            
        Returns:
            Filter dictionary with status=POSTED
        """
        filter_dict = {
            "corporate_id": corporate_id,
            "status": "POSTED",
            **kwargs
        }
        return filter_dict


def filter_posted_only(queryset: QuerySet, model_name: str) -> QuerySet:
    """
    Filter queryset to only include POSTED documents
    
    Args:
        queryset: Django QuerySet
        model_name: Name of the model (Invoices, VendorBill, Quotation, PurchaseOrder)
        
    Returns:
        Filtered QuerySet with only POSTED documents
        
    Example:
        invoices = Invoices.objects.filter(corporate_id=corp_id)
        posted_invoices = filter_posted_only(invoices, 'Invoices')
    """
    if model_name in ['Invoices', 'VendorBill', 'Quotation', 'PurchaseOrder', 'ProformaInvoice']:
        return queryset.filter(status='POSTED')
    return queryset


def exclude_drafts(queryset: QuerySet, model_name: str) -> QuerySet:
    """
    Exclude DRAFT documents from queryset
    
    Args:
        queryset: Django QuerySet
        model_name: Name of the model
        
    Returns:
        QuerySet excluding DRAFT documents
        
    Example:
        invoices = Invoices.objects.filter(corporate_id=corp_id)
        non_draft_invoices = exclude_drafts(invoices, 'Invoices')
    """
    if model_name in ['Invoices', 'VendorBill', 'Quotation', 'PurchaseOrder', 'ProformaInvoice']:
        return queryset.exclude(status='DRAFT')
    return queryset


def is_document_posted(document: Dict[str, Any]) -> bool:
    """
    Check if a document is posted
    
    Args:
        document: Document dictionary with 'status' field
        
    Returns:
        True if document is POSTED, False otherwise
    """
    return document.get('status') == 'POSTED'


def validate_document_for_accounting(document: Dict[str, Any], document_type: str) -> tuple[bool, Optional[str]]:
    """
    Validate if a document can be used in accounting calculations
    
    Args:
        document: Document dictionary
        document_type: Type of document (invoice, bill, quotation, po)
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Example:
        is_valid, error = validate_document_for_accounting(invoice, 'invoice')
        if not is_valid:
            raise ValueError(error)
    """
    if not document:
        return False, f"{document_type} not found"
    
    status = document.get('status')
    if status != 'POSTED':
        return False, f"{document_type} must be POSTED to be used in accounting. Current status: {status}"
    
    # Check if journal entry exists for documents that should have one
    if document_type in ['invoice', 'bill']:
        if not document.get('journal_entry_id'):
            return False, f"{document_type} is POSTED but has no journal entry"
    
    return True, None


def get_posted_documents_for_reference(
    registry,
    model_name: str,
    corporate_id: str,
    partner_id: Optional[str] = None,
    partner_field: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get posted documents that can be used as references in other documents
    
    Args:
        registry: ServiceRegistry instance
        model_name: Model name (Quotation, PurchaseOrder, etc.)
        corporate_id: Corporate ID
        partner_id: Optional partner ID (customer_id or vendor_id)
        partner_field: Optional partner field name ('customer_id' or 'vendor_id')
        
    Returns:
        List of posted documents suitable for reference
        
    Example:
        # Get posted quotations for a customer
        quotations = get_posted_documents_for_reference(
            registry,
            'Quotation',
            corporate_id,
            partner_id=customer_id,
            partner_field='customer_id'
        )
    """
    filter_data = {
        "corporate_id": corporate_id,
        "status": "POSTED"
    }
    
    if partner_id and partner_field:
        filter_data[partner_field] = partner_id
    
    documents = registry.database(
        model_name=model_name,
        operation="filter",
        data=filter_data
    )
    
    return documents


def ensure_posted_for_journal_entry(document: Dict[str, Any], document_type: str) -> None:
    """
    Ensure document is POSTED before creating journal entry
    Raises ValueError if document is not POSTED
    
    Args:
        document: Document dictionary
        document_type: Type of document
        
    Raises:
        ValueError: If document is not POSTED
        
    Example:
        ensure_posted_for_journal_entry(invoice, 'invoice')
        # Proceeds only if invoice is POSTED, otherwise raises ValueError
    """
    is_valid, error = validate_document_for_accounting(document, document_type)
    if not is_valid:
        raise ValueError(f"Cannot create journal entry: {error}")


def get_accounting_documents_summary(registry, corporate_id: str) -> Dict[str, Any]:
    """
    Get summary of posted vs draft documents for a corporate
    
    Args:
        registry: ServiceRegistry instance
        corporate_id: Corporate ID
        
    Returns:
        Dictionary with counts of posted and draft documents
        
    Example:
        summary = get_accounting_documents_summary(registry, corporate_id)
        # {
        #     'invoices': {'posted': 10, 'draft': 3},
        #     'bills': {'posted': 5, 'draft': 2},
        #     ...
        # }
    """
    summary = {}
    
    models = [
        ('invoices', 'Invoices'),
        ('bills', 'VendorBill'),
        ('quotations', 'Quotation'),
        ('purchase_orders', 'PurchaseOrder'),
    ]
    
    for key, model_name in models:
        all_docs = registry.database(
            model_name=model_name,
            operation="filter",
            data={"corporate_id": corporate_id}
        )
        
        posted_count = sum(1 for doc in all_docs if doc.get('status') == 'POSTED')
        draft_count = sum(1 for doc in all_docs if doc.get('status') == 'DRAFT')
        
        summary[key] = {
            'posted': posted_count,
            'draft': draft_count,
            'total': len(all_docs)
        }
    
    return summary


# Decorator for views that should only work with posted documents
def require_posted_document(document_type: str):
    """
    Decorator to ensure a document is POSTED before processing
    
    Args:
        document_type: Type of document (invoice, bill, etc.)
        
    Example:
        @require_posted_document('invoice')
        def create_invoice_journal_entry(invoice_id, user):
            # This will only execute if invoice is POSTED
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract document from args/kwargs
            document = None
            if args and isinstance(args[0], dict):
                document = args[0]
            elif 'document' in kwargs:
                document = kwargs['document']
            
            if document:
                is_valid, error = validate_document_for_accounting(document, document_type)
                if not is_valid:
                    raise ValueError(error)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Constants
POSTED_STATUS = 'POSTED'
DRAFT_STATUS = 'DRAFT'

# Document types that require POSTED status for accounting
ACCOUNTING_DOCUMENT_TYPES = [
    'Invoices',
    'VendorBill',
    'Quotation',
    'PurchaseOrder',
    'ProformaInvoice',
]

# Fields that indicate a document is posted
POSTED_INDICATORS = [
    'posted_at',
    'posted_by',
    'journal_entry_id',
]
