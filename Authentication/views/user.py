# authentication/views/user.py
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.rate_limit import rate_limit
from quidpath_backend.core.utils.request_parser import get_clean_data


@login_required
def user_profile(request):
    user = request.user
    return JsonResponse(
        {
            "username": user.username,
            "email": user.email,
            "last_login": user.last_login,
        }
    )


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="refresh")
def refresh_token(request):
    """
    Refresh JWT access token using a valid refresh token.
    Returns a new access token (and rotated refresh token) with all custom claims preserved.
    """
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    refresh_token_str = body.get("refresh")
    if not refresh_token_str:
        return JsonResponse({"error": "Refresh token required"}, status=400)

    try:
        old_token = RefreshToken(refresh_token_str)

        # Extract user from token payload
        user_id = old_token.get("user_id")
        if not user_id:
            return JsonResponse({"error": "Invalid token payload"}, status=401)

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=401)

        if not user.is_active and not user.is_superuser:
            return JsonResponse({"error": "User account is inactive"}, status=401)

        # Resolve role and corporate_id
        corporate_user = CorporateUser.objects.filter(id=user.id).first()
        role = corporate_id = None
        if corporate_user:
            role = corporate_user.role.name if corporate_user.role else None
            corporate_id = corporate_user.corporate_id

        # Blacklist old token and issue fresh tokens with custom claims
        old_token.blacklist()

        from Authentication.views.auth import issue_tokens_for_user
        access_token, new_refresh_token = issue_tokens_for_user(user, role, corporate_id)

        TransactionLogBase.log(
            "TOKEN_REFRESHED", user=user, message="JWT token refreshed successfully"
        )

        return JsonResponse({
            "access": access_token,
            "refresh": new_refresh_token,
        })

    except TokenError as e:
        return JsonResponse({"error": "Invalid or expired refresh token", "detail": str(e)}, status=401)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=401)
