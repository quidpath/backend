"""
Invoice Posting Views
Handles invoice posting with automatic journal entry creation
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from Accounting.models.sales import Invoices
from Accounting.services.journal_entry_service import JournalEntryService

logger = logging.getLogger(__name__)


@api_view(['POST'])
def post_invoice(request, invoice_id):
    """
    Post an invoice and create journal entry
    
    POST /api/accounting/invoices/{invoice_id}/post/
    
    Creates:
    - Journal Entry with balanced debits/credits
    - Updates invoice status to POSTED
    - Links journal entry to invoice
    """
    try:
        # Get invoice
        invoice = get_object_or_404(Invoices, id=invoice_id)
        
        # Validate corporate
        corporate_id = request.headers.get('X-Corporate-ID')
        if str(invoice.corporate_id) != corporate_id:
            return Response(
                {'error': 'Invoice does not belong to this corporate'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user ID
        user_id = request.headers.get('X-User-ID')
        
        # Create journal entry
        journal_entry = JournalEntryService.create_invoice_journal_entry(
            invoice,
            user_id=user_id
        )
        
        if journal_entry:
            return Response({
                'success': True,
                'message': f'Invoice {invoice.number} posted successfully',
                'invoice': {
                    'id': str(invoice.id),
                    'number': invoice.number,
                    'status': invoice.status,
                    'total': str(invoice.total),
                },
                'journal_entry': {
                    'id': str(journal_entry.id),
                    'reference': journal_entry.reference,
                    'date': journal_entry.date.isoformat(),
                    'total_debits': str(journal_entry.get_total_debits()),
                    'total_credits': str(journal_entry.get_total_credits()),
                    'is_balanced': journal_entry.is_balanced(),
                    'is_posted': journal_entry.is_posted,
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Failed to create journal entry'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Error posting invoice: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
def unpost_invoice(request, invoice_id):
    """
    Unpost an invoice and reverse journal entry
    
    POST /api/accounting/invoices/{invoice_id}/unpost/
    """
    try:
        invoice = get_object_or_404(Invoices, id=invoice_id)
        
        # Validate corporate
        corporate_id = request.headers.get('X-Corporate-ID')
        if str(invoice.corporate_id) != corporate_id:
            return Response(
                {'error': 'Invoice does not belong to this corporate'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if invoice is posted
        if invoice.status != 'POSTED':
            return Response(
                {'error': f'Invoice is not posted (status: {invoice.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Unpost journal entry
        if invoice.journal_entry:
            invoice.journal_entry.unpost()
        
        # Update invoice
        invoice.status = 'DRAFT'
        invoice.posted_at = None
        invoice.posted_by = None
        invoice.save()
        
        return Response({
            'success': True,
            'message': f'Invoice {invoice.number} unposted successfully',
            'invoice': {
                'id': str(invoice.id),
                'number': invoice.number,
                'status': invoice.status,
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error unposting invoice: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
def record_payment(request, invoice_id):
    """
    Record payment for an invoice
    
    POST /api/accounting/invoices/{invoice_id}/record-payment/
    
    Body:
    {
        "amount": "1160.00",
        "payment_method": "cash",
        "payment_reference": "PMT-001",
        "payment_date": "2026-04-15"
    }
    """
    try:
        invoice = get_object_or_404(Invoices, id=invoice_id)
        
        # Validate corporate
        corporate_id = request.headers.get('X-Corporate-ID')
        if str(invoice.corporate_id) != corporate_id:
            return Response(
                {'error': 'Invoice does not belong to this corporate'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get payment data
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'cash')
        payment_reference = request.data.get('payment_reference', '')
        
        if not amount:
            return Response(
                {'error': 'Payment amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user ID
        user_id = request.headers.get('X-User-ID')
        
        # Create payment journal entry
        journal_entry = JournalEntryService.create_payment_journal_entry(
            invoice,
            amount,
            payment_method,
            payment_reference,
            user_id=user_id
        )
        
        # Update invoice payment status
        # (This would be more sophisticated in production with payment tracking)
        if float(amount) >= float(invoice.total):
            invoice.payment_status = 'paid'
            invoice.status = 'PAID'
        else:
            invoice.payment_status = 'partial'
            invoice.status = 'PARTIALLY_PAID'
        
        invoice.payment_reference = payment_reference
        invoice.save()
        
        return Response({
            'success': True,
            'message': 'Payment recorded successfully',
            'invoice': {
                'id': str(invoice.id),
                'number': invoice.number,
                'status': invoice.status,
                'payment_status': invoice.payment_status,
            },
            'journal_entry': {
                'id': str(journal_entry.id),
                'reference': journal_entry.reference,
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error recording payment: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
