"""
Data Validation Views for Banking Module
Provides endpoints to validate and fix data integrity issues
"""
import traceback
from django.views.decorators.csrf import csrf_exempt
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from Banking.services.data_validation_service import DataValidationService


@csrf_exempt
def validate_data_integrity(request):
    """
    Validate data integrity for banking and related modules
    
    Returns validation report with issues found and fixes applied
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        
        if not user:
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        # Get user's corporate ID
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        if not user_id:
            return ResponseProvider(
                message="User ID not found", code=400
            ).bad_request()

        from quidpath_backend.core.utils.registry import ServiceRegistry
        registry = ServiceRegistry()

        # Get corporate linked to this user
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        
        # Run validation
        validation_service = DataValidationService()
        validation_result = validation_service.validate_all_data_tables(corporate_id)
        
        # Log the validation
        TransactionLogBase.log(
            transaction_type="DATA_VALIDATION_COMPLETED",
            user=user,
            message=f"Data validation completed for corporate {corporate_id}",
            state_name="Success",
            extra={
                "corporate_id": corporate_id,
                "validation_summary": {
                    "bank_accounts_total": validation_result['bank_accounts']['total_accounts'],
                    "issues_found": len(validation_result['bank_accounts']['validation_errors']),
                    "fixes_applied": len(validation_result['bank_accounts']['fixed_issues'])
                }
            },
            request=request,
        )
        
        return ResponseProvider(
            message="Data validation completed successfully",
            data=validation_result,
            code=200,
        ).success()
        
    except Exception as e:
        error_trace = traceback.format_exc()
        TransactionLogBase.log(
            transaction_type="DATA_VALIDATION_FAILED",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=error_trace,
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred during data validation", code=500
        ).exception()


@csrf_exempt
def fix_data_integrity_issues(request):
    """
    Fix common data integrity issues
    
    Applies automatic fixes for known data problems
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        
        if not user:
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        # Get user's corporate ID
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        if not user_id:
            return ResponseProvider(
                message="User ID not found", code=400
            ).bad_request()

        from quidpath_backend.core.utils.registry import ServiceRegistry
        registry = ServiceRegistry()

        # Get corporate linked to this user
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        
        # Apply fixes
        validation_service = DataValidationService()
        fix_result = validation_service.fix_data_integrity_issues(corporate_id)
        
        # Log the fixes
        TransactionLogBase.log(
            transaction_type="DATA_INTEGRITY_FIXES_APPLIED",
            user=user,
            message=f"Data integrity fixes applied for corporate {corporate_id}",
            state_name="Success",
            extra={
                "corporate_id": corporate_id,
                "fixes_applied": len(fix_result['fixes_applied']),
                "errors": len(fix_result['errors'])
            },
            request=request,
        )
        
        return ResponseProvider(
            message=f"Applied {len(fix_result['fixes_applied'])} data integrity fixes",
            data=fix_result,
            code=200,
        ).success()
        
    except Exception as e:
        error_trace = traceback.format_exc()
        TransactionLogBase.log(
            transaction_type="DATA_INTEGRITY_FIXES_FAILED",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=error_trace,
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while applying data fixes", code=500
        ).exception()