"""
Journal Entry Service
Automated journal entry creation for invoices, bills, and other transactions
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime

from django.db import transaction
from django.core.exceptions import ValidationError

from Accounting.models.accounts import Account, JournalEntry, JournalEntryLine
from Accounting.models.sales import Invoices, VendorBill
from OrgAuth.models import Corporate

logger = logging.getLogger(__name__)


class JournalEntryService:
    """Service for creating automated journal entries"""
    
    @staticmethod
    def get_default_account(corporate: Corporate, account_code: str) -> Optional[Account]:
        """Get default account by code"""
        try:
            return Account.objects.get(corporate=corporate, code=account_code, is_active=True)
        except Account.DoesNotExist:
            logger.error(f"Account {account_code} not found for corporate {corporate.id}")
            return None
    
    @staticmethod
    def get_account_by_type(corporate: Corporate, account_type: str, 
                           sub_type: str = None) -> Optional[Account]:
        """Get account by type and optional sub-type"""
        try:
            query = Account.objects.filter(
                corporate=corporate,
                account_type__name=account_type,
                is_active=True
            )
            if sub_type:
                query = query.filter(account_sub_type__name=sub_type)
            return query.first()
        except Exception as e:
            logger.error(f"Error getting account by type: {str(e)}")
            return None
    
    @staticmethod
    @transaction.atomic
    def create_invoice_journal_entry(invoice: Invoices, user_id: str = None) -> Optional[JournalEntry]:
        """
        Create journal entry when invoice is posted
        
        Journal Entry for Sale:
        Dr: Accounts Receivable (or Cash if paid immediately)
        Cr: Sales Revenue
        Cr: VAT Payable (if applicable)
        """
        try:
            # Validate invoice
            if invoice.status != 'DRAFT':
                raise ValidationError(f"Invoice must be in DRAFT status to post (current: {invoice.status})")
            
            if invoice.journal_entry:
                raise ValidationError("Invoice already has a journal entry")
            
            # Get accounts
            receivable_account = invoice.receivable_account or JournalEntryService.get_account_by_type(
                invoice.corporate, 'ASSET', 'Accounts Receivable'
            )
            
            if not receivable_account:
                raise ValidationError("Accounts Receivable account not found")
            
            revenue_account = JournalEntryService.get_default_account(invoice.corporate, '4000')
            if not revenue_account:
                revenue_account = JournalEntryService.get_account_by_type(
                    invoice.corporate, 'REVENUE', 'Sales Revenue'
                )
            
            if not revenue_account:
                raise ValidationError("Sales Revenue account not found")
            
            vat_account = None
            if invoice.tax_total > 0:
                vat_account = JournalEntryService.get_default_account(invoice.corporate, '2100')
                if not vat_account:
                    vat_account = JournalEntryService.get_account_by_type(
                        invoice.corporate, 'LIABILITY', 'VAT Payable'
                    )
                
                if not vat_account:
                    raise ValidationError("VAT Payable account not found")
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                corporate=invoice.corporate,
                date=invoice.date,
                reference=f"INV-{invoice.number}",
                description=f"Sale to {invoice.customer}",
                source_type='invoice',
                source_id=invoice.id,
                created_by_id=user_id,
            )
            
            # Line 1: Debit Accounts Receivable
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=receivable_account,
                debit=invoice.total,
                credit=Decimal('0'),
                description=f"Invoice {invoice.number} - {invoice.customer}",
            )
            
            # Line 2: Credit Sales Revenue
            revenue_amount = invoice.sub_total - invoice.total_discount
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=revenue_account,
                debit=Decimal('0'),
                credit=revenue_amount,
                description=f"Sales revenue - Invoice {invoice.number}",
            )
            
            # Line 3: Credit VAT Payable (if applicable)
            if invoice.tax_total > 0 and vat_account:
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=vat_account,
                    debit=Decimal('0'),
                    credit=invoice.tax_total,
                    description=f"VAT 16% - Invoice {invoice.number}",
                )
            
            # Validate and post journal entry
            if not journal_entry.is_balanced():
                raise ValidationError(
                    f"Journal entry not balanced: "
                    f"Debits={journal_entry.get_total_debits()}, "
                    f"Credits={journal_entry.get_total_credits()}"
                )
            
            journal_entry.post()
            
            # Update invoice
            invoice.journal_entry = journal_entry
            invoice.status = 'POSTED'
            invoice.posted_at = datetime.now()
            invoice.posted_by_id = user_id
            invoice.save()
            
            logger.info(
                f"Journal entry {journal_entry.reference} created for invoice {invoice.number}"
            )
            
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating invoice journal entry: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def create_vendor_bill_journal_entry(bill: VendorBill, user_id: str = None) -> Optional[JournalEntry]:
        """
        Create journal entry when vendor bill is posted
        
        Journal Entry for Purchase:
        Dr: Expense/Inventory Account
        Dr: VAT Input (if applicable)
        Cr: Accounts Payable
        """
        try:
            # Validate bill
            if bill.status != 'DRAFT':
                raise ValidationError(f"Bill must be in DRAFT status to post (current: {bill.status})")
            
            if bill.journal_entry:
                raise ValidationError("Bill already has a journal entry")
            
            # Get accounts
            payable_account = bill.payable_account or JournalEntryService.get_account_by_type(
                bill.corporate, 'LIABILITY', 'Accounts Payable'
            )
            
            if not payable_account:
                raise ValidationError("Accounts Payable account not found")
            
            # Get expense account (default to COGS)
            expense_account = JournalEntryService.get_default_account(bill.corporate, '5000')
            if not expense_account:
                expense_account = JournalEntryService.get_account_by_type(
                    bill.corporate, 'EXPENSE', 'Cost of Goods Sold'
                )
            
            if not expense_account:
                raise ValidationError("Expense account not found")
            
            vat_input_account = None
            if bill.tax_total > 0:
                vat_input_account = JournalEntryService.get_default_account(bill.corporate, '1300')
                if not vat_input_account:
                    vat_input_account = JournalEntryService.get_account_by_type(
                        bill.corporate, 'ASSET', 'VAT Input'
                    )
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                corporate=bill.corporate,
                date=bill.date,
                reference=f"BILL-{bill.number}",
                description=f"Purchase from {bill.vendor}",
                source_type='vendor_bill',
                source_id=bill.id,
                created_by_id=user_id,
            )
            
            # Line 1: Debit Expense/COGS
            expense_amount = bill.sub_total - bill.total_discount
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=expense_account,
                debit=expense_amount,
                credit=Decimal('0'),
                description=f"Purchase - Bill {bill.number}",
            )
            
            # Line 2: Debit VAT Input (if applicable)
            if bill.tax_total > 0 and vat_input_account:
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=vat_input_account,
                    debit=bill.tax_total,
                    credit=Decimal('0'),
                    description=f"VAT Input - Bill {bill.number}",
                )
            
            # Line 3: Credit Accounts Payable
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=payable_account,
                debit=Decimal('0'),
                credit=bill.total,
                description=f"Bill {bill.number} - {bill.vendor}",
            )
            
            # Validate and post journal entry
            if not journal_entry.is_balanced():
                raise ValidationError(
                    f"Journal entry not balanced: "
                    f"Debits={journal_entry.get_total_debits()}, "
                    f"Credits={journal_entry.get_total_credits()}"
                )
            
            journal_entry.post()
            
            # Update bill
            bill.journal_entry = journal_entry
            bill.status = 'POSTED'
            bill.posted_at = datetime.now()
            bill.posted_by_id = user_id
            bill.save()
            
            logger.info(
                f"Journal entry {journal_entry.reference} created for bill {bill.number}"
            )
            
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating bill journal entry: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def create_payment_journal_entry(invoice: Invoices, payment_amount: Decimal,
                                    payment_method: str, payment_reference: str,
                                    user_id: str = None) -> Optional[JournalEntry]:
        """
        Create journal entry for invoice payment
        
        Journal Entry for Payment:
        Dr: Cash/Bank
        Cr: Accounts Receivable
        """
        try:
            # Get accounts
            receivable_account = invoice.receivable_account or JournalEntryService.get_account_by_type(
                invoice.corporate, 'ASSET', 'Accounts Receivable'
            )
            
            # Determine payment account based on method
            if payment_method in ['cash']:
                payment_account = JournalEntryService.get_default_account(invoice.corporate, '1000')
            else:  # card, mpesa, bank_transfer
                payment_account = JournalEntryService.get_default_account(invoice.corporate, '1010')
            
            if not payment_account:
                payment_account = JournalEntryService.get_account_by_type(
                    invoice.corporate, 'ASSET', 'Cash'
                )
            
            if not receivable_account or not payment_account:
                raise ValidationError("Required accounts not found")
            
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                corporate=invoice.corporate,
                date=datetime.now().date(),
                reference=f"PMT-{invoice.number}-{payment_reference}",
                description=f"Payment for Invoice {invoice.number}",
                source_type='payment',
                source_id=invoice.id,
                created_by_id=user_id,
            )
            
            # Line 1: Debit Cash/Bank
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=payment_account,
                debit=payment_amount,
                credit=Decimal('0'),
                description=f"Payment received - {payment_method.upper()}",
            )
            
            # Line 2: Credit Accounts Receivable
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=receivable_account,
                debit=Decimal('0'),
                credit=payment_amount,
                description=f"Payment for Invoice {invoice.number}",
            )
            
            # Validate and post
            if not journal_entry.is_balanced():
                raise ValidationError("Journal entry not balanced")
            
            journal_entry.post()
            
            logger.info(
                f"Payment journal entry {journal_entry.reference} created"
            )
            
            return journal_entry
            
        except Exception as e:
            logger.error(f"Error creating payment journal entry: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def get_account_balance_summary(corporate: Corporate, as_of_date=None) -> Dict:
        """Get summary of account balances by type"""
        from datetime import date
        
        if as_of_date is None:
            as_of_date = date.today()
        
        summary = {
            'ASSET': Decimal('0'),
            'LIABILITY': Decimal('0'),
            'EQUITY': Decimal('0'),
            'REVENUE': Decimal('0'),
            'EXPENSE': Decimal('0'),
        }
        
        accounts = Account.objects.filter(corporate=corporate, is_active=True)
        
        for account in accounts:
            balance = account.get_balance(as_of_date)
            account_type = account.account_type.name
            summary[account_type] += balance
        
        return summary
