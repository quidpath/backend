# authentication/views/auth.py
import json
from datetime import timedelta
from importlib.metadata import metadata

from django.http import JsonResponse
from django.utils.timezone import now
from django.contrib.auth.hashers import check_password
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import get_authorization_header

from Authentication.models import CustomUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler


from rest_framework_simplejwt.tokens import RefreshToken

from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

def issue_tokens_for_user(user):
    """Helper to issue access + refresh tokens"""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    return access_token, str(refresh)


@csrf_exempt
def login_user(request):
    """
    Login flow:
    - If last_otp_sent_at < 24h -> issue tokens immediately
    - If > 24h -> send OTP, require verification before tokens
    """
    data, metadata = get_clean_data(request)
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return JsonResponse({"error": "username & password required"}, status=400)

    # Get user
    user_data = ServiceRegistry().database("customuser", "get", data={"username": username})
    if not user_data:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    if isinstance(user_data, dict):
        user = CustomUser.objects.get(id=user_data["id"])
    else:
        user = user_data

    # Verify password
    if not check_password(password, user.password):
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # ✅ Check OTP expiry logic
    otp_expired = (
        not user.last_otp_sent_at or (now() - user.last_otp_sent_at > timedelta(hours=24))
    )

    if not otp_expired:
        # ✅ Within 24h → normal login, issue tokens immediately
        access_token, refresh_token = issue_tokens_for_user(user)

        user.is_active = True
        user.save()
        TransactionLogBase.log("USER_LOGIN", user=user, message="User logged in (OTP not required)")

        response = JsonResponse({
            "access": access_token,
            "refresh": refresh_token,
            "otp_required": False
        })
        response["Authorization"] = f"Bearer {access_token}"
        return response

    else:
        otp_code = user.generate_otp()
        user.last_otp_sent_at = now()
        user.save()

        NotificationServiceHandler().send_notification([{
            "message_type": "EMAIL",
            "organisation_id": None,
            "destination": user.email,
            "message": f"<p>Hello {user.username},</p><p>Your OTP is <b>{otp_code}</b>.</p>",
            "confirmation_code": otp_code
        }])
        TransactionLogBase.log("OTP_SENT", user=user, message="OTP required for login")

        return JsonResponse({
            "message": "OTP required. Please verify to continue.",
            "otp_required": True
        })

from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.decorators import method_decorator

@csrf_exempt
def logout_user(request):
    """
    Logs out the user:
    - Invalidates OTP fields
    - Marks user inactive
    """
    # ✅ Always use DRF's built-in extractor
    raw_header = get_authorization_header(request).decode('utf-8')
    print("AUTH RAW HEADER >>>", raw_header)

    if not raw_header or not raw_header.startswith("Bearer "):
        return JsonResponse({"error": "Missing or invalid Authorization header"}, status=401)

    token = raw_header.split(" ")[1].strip()

    jwt_auth = JWTAuthentication()
    try:
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
    except Exception as e:
        print("JWT ERROR >>>", e)
        return JsonResponse({"error": "Invalid or expired token"}, status=401)

    user.last_otp_sent_at = None
    if hasattr(user, "otp_code"):
        user.otp_code = None
    user.is_active = False
    user.save()

    TransactionLogBase.log("USER_LOGOUT", user=user, message="User logged out")

    return JsonResponse({"message": "User logged out successfully"})

@csrf_exempt
def delete_user(request):
    """
    Deletes a user directly using user_id from request.
    """
    data, metadata = get_clean_data(request)
    user_id = data.get("id")

    if not user_id:
        return JsonResponse({"error": "user_id is required"}, status=400)

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    username = user.username
    user.delete()

    TransactionLogBase.log("USER_DELETED", user=None, message=f"User {username} deleted by admin/request")
    return JsonResponse({"message": f"User {username} deleted successfully"})

@csrf_exempt
def verify_otp(request):
    """
    Verifies OTP:
    - If valid -> issue access + refresh tokens
    - Clear OTP after success
    """
    data, metadata = get_clean_data(request)
    otp_code = data.get("otp")

    if not otp_code:
        return JsonResponse({"error": "OTP required"}, status=400)

    try:
        user = CustomUser.objects.get(otp_code=otp_code)
    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "Invalid OTP"}, status=400)

    # Check OTP expiry
    if not user.last_otp_sent_at or (now() - user.last_otp_sent_at > timedelta(hours=24)):
        return JsonResponse({"error": "OTP expired"}, status=400)

    # ✅ OTP valid → issue new tokens
    access_token, refresh_token = issue_tokens_for_user(user)

    # Clear OTP
    user.otp_code = None
    user.last_otp_sent_at = now()  # reset login time
    user.is_active = True
    user.save()

    TransactionLogBase.log("OTP_VERIFIED", user=user, message="OTP verified, login completed")

    response = JsonResponse({
        "message": "OTP verified successfully",
        "access": access_token,
        "refresh": refresh_token,
        "otp_required": False
    })
    response["Authorization"] = f"Bearer {access_token}"
    return response