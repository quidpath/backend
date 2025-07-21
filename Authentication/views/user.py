# authentication/views/user.py
# authentication/views/user.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data


@login_required
def user_profile(request):
    """
    Get logged-in user profile
    """
    user = request.user
    return JsonResponse({
        "username": user.username,
        "email": user.email,
        "last_login": user.last_login,
    })


def refresh_token(request):
    """
    Refresh JWT token using refresh token
    """
    data, metadata = get_clean_data(request)
    refresh_token = data.get("refresh")
    if not refresh_token:
        return JsonResponse({"error": "refresh token required"}, status=400)

    try:
        token = RefreshToken(refresh_token)
        new_access = str(token.access_token)

        # If authenticated, log it
        if request.user.is_authenticated:
            TransactionLogBase.log("TOKEN_REFRESH", user=request.user, message="Token refreshed")

        return JsonResponse({"access": new_access})
    except Exception:
        return JsonResponse({"error": "invalid refresh token"}, status=401)
