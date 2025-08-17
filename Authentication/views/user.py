# authentication/views/user.py
# authentication/views/user.py
import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
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

@csrf_exempt
def refresh_token(request):
    """
    Refresh JWT token using refresh token only — without trying to extract user from expired access token.
    """
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    refresh_token_str = body.get("refresh")
    if not refresh_token_str:
        return JsonResponse({"error": "Refresh token required"}, status=400)

    try:
        token = RefreshToken(refresh_token_str)
        access_token = str(token.access_token)

        return JsonResponse({"access": access_token})
    except Exception as e:
        return JsonResponse({"error": "Invalid or expired refresh token"}, status=401)