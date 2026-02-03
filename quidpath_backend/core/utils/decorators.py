# decorators.py
from functools import wraps

from django.http import JsonResponse


def require_authenticated(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)

        # If authenticated, call the original view function
        return view_func(request, *args, **kwargs)

    return _wrapped_view
