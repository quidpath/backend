"""
Banking Transaction Service
Automatically creates bank transactions for payments and expenses
"""
import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional
from django.db import transaction
from django.utils import timezone

from Banking.models import BankAccount, BankTransaction
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class BankingTransactionService:
    """
    Service to automatically create bank transactions
    for payments, expenses, and other financial activities
    """
    
    def __init__(self):
        self.registry = ServiceRegistry()
    
    @transaction.atomic
    def create_pos_payment_transaction(
        self,
        corporate_id: str,
        payment_account_id: str,
        amount: Decimal,
        reference: str,
        narration: str,
        payment_method: str = 'cash',
        user_id: str = None,
        transaction_date: datetime = None
    ) -> Dict:
        """
        Create bank transaction for POS payment
        
        Args:
            corporate_id: Corporate UUID
            payment_account_id: Bank account UUID where payment was received
            amount: Payment amount
            reference: Transaction reference (e.g., order number)
            narration: Transaction description
            payment_method: Payment method (cash, card, mpesa, etc.)
            user_id: User who created the transaction
            transaction_date: Date of transaction (defaults to now)
        
        Returns:
            {
                'success': bool,
                'transaction_id': str,
                'balance': Decimal,
                'error': str
            }
        """
        result = {
            'success': False,
            'transaction_id': None,
            'balance': None,
            'error': None
        }
        
        try:
            # Validate bank account
            accounts = self.registry.database(
                model_name="BankAccount",
                operation="filter",
                data={
                    "id": payment_account_id,
                    "corporate_id": corporate_id,
                    "is_active": True
                }
            )
            
            if not accounts:
                result['error'] = f"Bank account {payment_account_id} not found or inactive"
                logger.error(result['error'])
                return result
            
            account = accounts[0]
            
            # Create transaction
            txn_date = transaction_date or timezone.now().date()
            
            transaction_data = {
                'bank_account_id': payment_account_id,
                'transaction_type': 'deposit',
                'amount': str(amount),
                'reference': reference,
                'narration': narration or f"POS Payment - {payment_method.upper()}",
                'transaction_date': txn_date,
                'status': 'confirmed',
                'created_by': user_id,
            }
            
            txn = self.registry.database(
                model_name="BankTransaction",
                operation="create",
                data=transaction_data
            )
            
            result['transaction_id'] = str(txn['id'])
            
            # Calculate new balance
            balance = self._calculate_account_balance(payment_account_id)
            result['balance'] = balance
            result['success'] = True
            
            logger.info(
                f"Created POS payment transaction {reference} for account {payment_account_id}. "
                f"Amount: {amount}, New balance: {balance}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating POS payment transaction: {str(e)}", exc_info=True)
            result['error'] = str(e)
            return result
    
    @transaction.atomic
    def create_expense_transaction(
        self,
        corporate_id: str,
        payment_account_id: str,
        amount: Decimal,
        reference: str,
        narration: str,
        user_id: str = None,
        transaction_date: datetime = None
    ) -> Dict:
        """
        Create bank transaction for expense payment
        
        Args:
            corporate_id: Corporate UUID
            payment_account_id: Bank account UUID from which payment was made
            amount: Payment amount
            reference: Transaction reference (e.g., expense number)
            narration: Transaction description
            user_id: User who created the transaction
            transaction_date: Date of transaction (defaults to now)
        
        Returns:
            {
                'success': bool,
                'transaction_id': str,
                'balance': Decimal,
                'error': str
            }
        """
        result = {
            'success': False,
            'transaction_id': None,
            'balance': None,
            'error': None
        }
        
        try:
            # Validate bank account
            accounts = self.registry.database(
                model_name="BankAccount",
                operation="filter",
                data={
                    "id": payment_account_id,
                    "corporate_id": corporate_id,
                    "is_active": True
                }
            )
            
            if not accounts:
                result['error'] = f"Bank account {payment_account_id} not found or inactive"
                logger.error(result['error'])
                return result
            
            account = accounts[0]
            
            # Check if sufficient balance
            current_balance = self._calculate_account_balance(payment_account_id)
            if current_balance < amount:
                result['error'] = f"Insufficient balance. Available: {current_balance}, Required: {amount}"
                logger.warning(result['error'])
                # Still create the transaction but log warning
            
            # Create transaction
            txn_date = transaction_date or timezone.now().date()
            
            transaction_data = {
                'bank_account_id': payment_account_id,
                'transaction_type': 'withdrawal',
                'amount': str(amount),
                'reference': reference,
                'narration': narration or "Expense Payment",
                'transaction_date': txn_date,
                'status': 'confirmed',
                'created_by': user_id,
            }
            
            txn = self.registry.database(
                model_name="BankTransaction",
                operation="create",
                data=transaction_data
            )
            
            result['transaction_id'] = str(txn['id'])
            
            # Calculate new balance
            balance = self._calculate_account_balance(payment_account_id)
            result['balance'] = balance
            result['success'] = True
            
            logger.info(
                f"Created expense transaction {reference} for account {payment_account_id}. "
                f"Amount: {amount}, New balance: {balance}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating expense transaction: {str(e)}", exc_info=True)
            result['error'] = str(e)
            return result
    
    def _calculate_account_balance(self, account_id: str) -> Decimal:
        """Calculate current balance for an account"""
        try:
            # Get account
            accounts = self.registry.database(
                model_name="BankAccount",
                operation="filter",
                data={"id": account_id}
            )
            
            if not accounts:
                return Decimal('0')
            
            account = accounts[0]
            opening_balance = Decimal(str(account.get('opening_balance', 0)))
            
            # Get all confirmed transactions
            transactions = self.registry.database(
                model_name="BankTransaction",
                operation="filter",
                data={
                    "bank_account_id": account_id,
                    "status": "confirmed"
                }
            )
            
            balance = opening_balance
            for txn in transactions:
                amount = Decimal(str(txn.get('amount', 0)))
                txn_type = txn.get('transaction_type', '')
                
                if txn_type in ('deposit', 'transfer_in'):
                    balance += amount
                elif txn_type in ('withdrawal', 'transfer_out', 'charge'):
                    balance -= amount
            
            return balance
            
        except Exception as e:
            logger.error(f"Error calculating balance: {str(e)}")
            return Decimal('0')
    
    @transaction.atomic
    def create_invoice_payment_transaction(
        self,
        corporate_id: str,
        payment_account_id: str,
        amount: Decimal,
        invoice_number: str,
        customer_name: str,
        user_id: str = None,
        transaction_date: datetime = None
    ) -> Dict:
        """
        Create bank transaction for invoice payment
        
        Args:
            corporate_id: Corporate UUID
            payment_account_id: Bank account UUID where payment was received
            amount: Payment amount
            invoice_number: Invoice number
            customer_name: Customer name
            user_id: User who created the transaction
            transaction_date: Date of transaction (defaults to now)
        
        Returns:
            {
                'success': bool,
                'transaction_id': str,
                'balance': Decimal,
                'error': str
            }
        """
        return self.create_pos_payment_transaction(
            corporate_id=corporate_id,
            payment_account_id=payment_account_id,
            amount=amount,
            reference=invoice_number,
            narration=f"Payment from {customer_name} for Invoice {invoice_number}",
            payment_method='invoice',
            user_id=user_id,
            transaction_date=transaction_date
        )
    
    @transaction.atomic
    def create_bill_payment_transaction(
        self,
        corporate_id: str,
        payment_account_id: str,
        amount: Decimal,
        bill_number: str,
        vendor_name: str,
        user_id: str = None,
        transaction_date: datetime = None
    ) -> Dict:
        """
        Create bank transaction for bill payment
        
        Args:
            corporate_id: Corporate UUID
            payment_account_id: Bank account UUID from which payment was made
            amount: Payment amount
            bill_number: Bill number
            vendor_name: Vendor name
            user_id: User who created the transaction
            transaction_date: Date of transaction (defaults to now)
        
        Returns:
            {
                'success': bool,
                'transaction_id': str,
                'balance': Decimal,
                'error': str
            }
        """
        return self.create_expense_transaction(
            corporate_id=corporate_id,
            payment_account_id=payment_account_id,
            amount=amount,
            reference=bill_number,
            narration=f"Payment to {vendor_name} for Bill {bill_number}",
            user_id=user_id,
            transaction_date=transaction_date
        )
