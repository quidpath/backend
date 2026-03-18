# decorators.py
from functools import wraps

from django.http import JsonResponse
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
