"""
Role-based access control permissions for QuidPath ERP.
"""
from functools import wraps
from quidpath_backend.core.utils.json_response import ResponseProvider


def require_superuser_or_admin(view_func):
    """
    Decorator to restrict access to superusers and corporate admins only.
    Used for settings and sensitive operations.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, 'user', None)
        
        if not user:
            return ResponseProvider(
                message="Authentication required",
                code=401
            ).unauthorized()
        
        # Check if user is superuser
        is_superuser = getattr(user, 'is_superuser', False)
        
        # Check if user is corporate admin
        role = getattr(user, 'role', None)
        is_admin = role in ['superadmin', 'admin', 'corporate_admin']
        
        if not (is_superuser or is_admin):
            return ResponseProvider(
                message="Access denied. Only superusers and administrators can access this resource.",
                code=403
            ).forbidden()
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def check_user_permissions(user, required_role=None):
    """
    Check if user has required permissions.
    
    Args:
        user: User object
        required_role: Required role (superadmin, admin, manager, user)
    
    Returns:
        dict with 'allowed' boolean and 'message' string
    """
    if not user:
        return {'allowed': False, 'message': 'User not authenticated'}
    
    is_superuser = getattr(user, 'is_superuser', False)
    if is_superuser:
        return {'allowed': True, 'message': 'Superuser access'}
    
    user_role = getattr(user, 'role', 'user')
    
    # Role hierarchy
    role_hierarchy = {
        'superadmin': 4,
        'admin': 3,
        'corporate_admin': 3,
        'manager': 2,
        'user': 1,
    }
    
    user_level = role_hierarchy.get(user_role, 0)
    required_level = role_hierarchy.get(required_role, 0) if required_role else 0
    
    if user_level >= required_level:
        return {'allowed': True, 'message': 'Access granted'}
    
    return {
        'allowed': False,
        'message': f'Insufficient permissions. Required: {required_role}, Current: {user_role}'
    }
