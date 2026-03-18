# quidpath_backend/core/decorators.py
"""Decorators for view-level permission checks (e.g. module access, superuser)."""
from functools import wraps

from Authentication.models import ModulePermission
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import resolve_user_from_token


def require_superuser(view_func):
    """
    Decorator that requires the authenticated user to be a superuser (system owner).
    Returns 401 if no/invalid token, 403 if not superuser.
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        user, _ = resolve_user_from_token(request)
        if not user:
            return ResponseProvider(
                {"error": "Authentication required"}, "Unauthorized", 401
            )._response(401)
        # Handle both dict (from JWT) and model objects
        if isinstance(user, dict):
            is_superuser = user.get("is_superuser", False)
        else:
            is_superuser = getattr(user, "is_superuser", False)
        if not is_superuser:
            return ResponseProvider(
                {"error": "Superuser access required"}, "Forbidden", 403
            )._response(403)
        return view_func(request, *args, **kwargs)
    return wrapped_view


def require_module_permission(module_slug):
    """
    Decorator that requires the authenticated user's role to have access to the given module_slug.
    Superusers bypass all permission checks.
    Use after get_clean_data so metadata is available, or resolve user from token inside.
    Returns 403 if user has no role or role lacks permission for the module.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            from quidpath_backend.core.utils.request_parser import resolve_user_from_token
            user, corporate_user = resolve_user_from_token(request)
            if not user:
                return ResponseProvider(
                    {"error": "Authentication required"}, "Forbidden", 403
                )._response(403)
            # Superuser bypass - check FIRST before corporate_user check
            # Handle both dict (from JWT) and model objects
            if isinstance(user, dict):
                is_superuser = user.get("is_superuser", False)
            else:
                is_superuser = getattr(user, "is_superuser", False)
            
            if is_superuser:
                return view_func(request, *args, **kwargs)
            if not corporate_user or not corporate_user.role_id:
                return ResponseProvider(
                    {"error": "You do not have access to this module"}, "Forbidden", 403
                )._response(403)
            has_access = corporate_user.role.module_permissions.filter(
                module_slug=module_slug
            ).exists()
            if not has_access:
                return ResponseProvider(
                    {"error": "You do not have access to this module"}, "Forbidden", 403
                )._response(403)
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator
