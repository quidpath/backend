# decorators.py
from functools import wraps

from django.http import JsonResponse
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import resolve_user_from_token


def require_authenticated(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if the user is authenticated via JWT
        user, _ = resolve_user_from_token(request)
        if not user:
            return JsonResponse({"error": "Authentication required."}, status=401)

        # If authenticated, call the original view function
        return view_func(request, *args, **kwargs)

    return _wrapped_view


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
