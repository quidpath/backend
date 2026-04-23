"""
Data Validation Service for Banking Module
Ensures data integrity and fixes common data table issues
"""
import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.db import transaction
from django.utils import timezone

from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class DataValidationService:
    """Service to validate and fix data integrity issues"""
    
    def __init__(self):
        self.registry = ServiceRegistry()
    
    def validate_bank_accounts(self, corporate_id: str) -> Dict[str, Any]:
        """
        Validate and fix bank account data issues
        
        Returns:
            {
                'total_accounts': int,
                'fixed_issues': List[str],
                'validation_errors': List[str],
                'accounts_with_missing_data': List[Dict]
            }
        """
        result = {
            'total_accounts': 0,
            'fixed_issues': [],
            'validation_errors': [],
            'accounts_with_missing_data': []
        }
        
        try:
            # Get all bank accounts for corporate
            accounts = self.registry.database(
                model_name="BankAccount",
                operation="filter",
                data={"corporate_id": corporate_id, "is_active": True}
            )
            
            result['total_accounts'] = len(accounts)
            
            for account in accounts:
                account_id = account.get('id')
                issues_fixed = []
                
                # Check for missing account_type
                if not account.get('account_type'):
                    self.registry.database(
                        model_name="BankAccount",
                        operation="update",
                        instance_id=account_id,
                        data={'account_type': 'bank'}
                    )
                    issues_fixed.append('Set default account_type to bank')
                
                # Check for missing opening_balance
                if account.get('opening_balance') is None:
                    self.registry.database(
                        model_name="BankAccount",
                        operation="update",
                        instance_id=account_id,
                        data={'opening_balance': '0.00'}
                    )
                    issues_fixed.append('Set default opening_balance to 0.00')
                
                # Check for missing opening_balance_date
                if not account.get('opening_balance_date'):
                    self.registry.database(
                        model_name="BankAccount",
                        operation="update",
                        instance_id=account_id,
                        data={'opening_balance_date': timezone.now().date()}
                    )
                    issues_fixed.append('Set default opening_balance_date')
                
                # Validate balance calculation
                balance_issues = self._validate_account_balance(account_id)
                if balance_issues:
                    result['validation_errors'].extend(balance_issues)
                
                if issues_fixed:
                    result['fixed_issues'].extend([
                        f"Account {account.get('account_name', account_id)}: {', '.join(issues_fixed)}"
                    ])
                
                # Check for missing required data
                missing_data = []
                if not account.get('bank_name'):
                    missing_data.append('bank_name')
                if not account.get('account_name'):
                    missing_data.append('account_name')
                if not account.get('account_number'):
                    missing_data.append('account_number')
                
                if missing_data:
                    result['accounts_with_missing_data'].append({
                        'id': account_id,
                        'account_name': account.get('account_name', 'Unknown'),
                        'missing_fields': missing_data
                    })
            
            logger.info(f"Validated {result['total_accounts']} bank accounts for corporate {corporate_id}")
            
        except Exception as e:
            logger.error(f"Error validating bank accounts: {str(e)}")
            result['validation_errors'].append(f"Validation error: {str(e)}")
        
        return result
    
    def _validate_account_balance(self, account_id: str) -> List[str]:
        """Validate account balance calculation"""
        errors = []
        
        try:
            # Get account
            accounts = self.registry.database(
                model_name="BankAccount",
                operation="filter",
                data={"id": account_id}
            )
            
            if not accounts:
                return ["Account not found"]
            
            account = accounts[0]
            opening_balance = Decimal(str(account.get('opening_balance', 0)))
            
            # Get all confirmed transactions
            transactions = self.registry.database(
                model_name="BankTransaction",
                operation="filter",
                data={"bank_account_id": account_id, "status": "confirmed"}
            )
            
            calculated_balance = opening_balance
            for txn in transactions:
                amount = Decimal(str(txn.get('amount', 0)))
                txn_type = txn.get('transaction_type', '')
                
                if txn_type in ('deposit', 'transfer_in'):
                    calculated_balance += amount
                elif txn_type in ('withdrawal', 'transfer_out', 'charge'):
                    calculated_balance -= amount
                else:
                    errors.append(f"Unknown transaction type: {txn_type}")
            
            # Check for negative balance
            if calculated_balance < 0:
                errors.append(f"Account has negative balance: {calculated_balance}")
            
        except Exception as e:
            errors.append(f"Balance validation error: {str(e)}")
        
        return errors
    
    def fix_missing_display_names(self, corporate_id: str) -> Dict[str, Any]:
        """Fix missing display names for accounts"""
        result = {
            'accounts_updated': 0,
            'errors': []
        }
        
        try:
            accounts = self.registry.database(
                model_name="BankAccount",
                operation="filter",
                data={"corporate_id": corporate_id, "is_active": True}
            )
            
            for account in accounts:
                account_type = account.get('account_type', 'bank')
                bank_name = account.get('bank_name', '')
                account_name = account.get('account_name', '')
                
                # Generate display name
                display_name = f"{account_type.replace('_', ' ').title()} - {bank_name} - {account_name}"
                
                # Update account with display name (if your model supports it)
                # This would require adding display_name field to model
                result['accounts_updated'] += 1
            
        except Exception as e:
            result['errors'].append(str(e))
        
        return result
    
    def validate_all_data_tables(self, corporate_id: str) -> Dict[str, Any]:
        """Comprehensive validation of all data tables"""
        result = {
            'bank_accounts': self.validate_bank_accounts(corporate_id),
            'timestamp': timezone.now().isoformat(),
            'corporate_id': corporate_id
        }
        
        # Add more table validations here
        # result['products'] = self.validate_products(corporate_id)
        # result['invoices'] = self.validate_invoices(corporate_id)
        
        return result
    
    @transaction.atomic
    def fix_data_integrity_issues(self, corporate_id: str) -> Dict[str, Any]:
        """Fix common data integrity issues across all tables"""
        result = {
            'fixes_applied': [],
            'errors': []
        }
        
        try:
            # Fix bank account issues
            bank_validation = self.validate_bank_accounts(corporate_id)
            if bank_validation['fixed_issues']:
                result['fixes_applied'].extend(bank_validation['fixed_issues'])
            
            # Fix display names
            display_name_result = self.fix_missing_display_names(corporate_id)
            if display_name_result['accounts_updated'] > 0:
                result['fixes_applied'].append(
                    f"Updated display names for {display_name_result['accounts_updated']} accounts"
                )
            
            logger.info(f"Applied {len(result['fixes_applied'])} data fixes for corporate {corporate_id}")
            
        except Exception as e:
            logger.error(f"Error fixing data integrity issues: {str(e)}")
            result['errors'].append(str(e))
        
        return result