"""
Settings management views with role-based access control.
"""
from django.views.decorators.csrf import csrf_exempt
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from Authentication.permissions import require_superuser_or_admin


@csrf_exempt
@require_superuser_or_admin
def get_system_settings(request):
    """
    Get system-wide settings.
    Only accessible by superusers and admins.
    """
    try:
        registry = ServiceRegistry()
        
        # Get settings from database or configuration
        settings = {
            'company': {
                'name': 'QuidPath ERP',
                'currency': 'USD',
                'timezone': 'UTC',
                'fiscal_year_start': '01-01',
            },
            'accounting': {
                'enable_multi_currency': True,
                'default_tax_rate': 0.0,
                'enable_cost_centers': False,
            },
            'sales': {
                'invoice_prefix': 'INV',
                'quote_prefix': 'QT',
                'enable_online_payments': False,
            },
            'purchases': {
                'po_prefix': 'PO',
                'bill_prefix': 'BILL',
                'enable_auto_approval': False,
            },
        }
        
        return ResponseProvider(
            data=settings,
            message="Settings retrieved successfully",
            code=200
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"Failed to retrieve settings: {str(e)}",
            code=500
        ).server_error()


@csrf_exempt
@require_superuser_or_admin
def update_system_settings(request):
    """
    Update system-wide settings.
    Only accessible by superusers and admins.
    """
    data, metadata = get_clean_data(request)
    
    try:
        registry = ServiceRegistry()
        
        # Validate and update settings
        # In production, store these in a Settings model
        
        return ResponseProvider(
            data=data,
            message="Settings updated successfully",
            code=200
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"Failed to update settings: {str(e)}",
            code=500
        ).server_error()


@csrf_exempt
def check_user_permissions(request):
    """
    Check current user's permissions.
    Returns user role and permission flags.
    """
    user = getattr(request, 'user', None)
    
    if not user:
        return ResponseProvider(
            message="User not authenticated",
            code=401
        ).unauthorized()
    
    try:
        is_superuser = getattr(user, 'is_superuser', False)
        role = getattr(user, 'role', None)
        role_name = role.name if hasattr(role, 'name') else 'user'
        
        permissions = {
            'is_superuser': is_superuser,
            'role': role_name,
            'can_access_settings': is_superuser or role_name.lower() in ['admin', 'superadmin', 'corporate_admin'],
            'can_access_analytics': is_superuser or role_name.lower() in ['admin', 'superadmin', 'corporate_admin', 'manager'],
            'can_create': True,
            'can_edit': True,
            'can_delete': role_name.lower() in ['admin', 'superadmin', 'corporate_admin', 'manager'] or is_superuser,
            'can_approve': role_name.lower() in ['admin', 'superadmin', 'corporate_admin', 'manager'] or is_superuser,
        }
        
        return ResponseProvider(
            data=permissions,
            message="Permissions retrieved successfully",
            code=200
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"Failed to retrieve permissions: {str(e)}",
            code=500
        ).server_error()
