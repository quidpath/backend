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
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.email import NotificationServiceHandler


from rest_framework_simplejwt.tokens import RefreshToken

from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def issue_tokens_for_user(user, role=None, corporate_id=None):
    refresh = RefreshToken.for_user(user)
    if role:
        refresh["role"] = role
    if corporate_id:
        refresh["organisation_id"] = str(corporate_id)
    refresh["is_global_user"] = False if corporate_id else True
    return str(refresh.access_token), str(refresh)


@csrf_exempt
def login_user(request):
    data, _ = get_clean_data(request)
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return JsonResponse({"error": "Username and password required"}, status=400)


    try:
        user = CustomUser.objects.get(username=username)
    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    if not user.is_active:
        return JsonResponse({"error": "User is suspended"}, status=401)

    if not check_password(password, user.password):
        return JsonResponse({"error": "Invalid password"}, status=401)

    corporate_user = CorporateUser.objects.filter(id=user.id).first()
    role = corporate_id = None
    if corporate_user:
        role = corporate_user.role.name if corporate_user.role else None
        corporate_id = corporate_user.corporate_id

    otp_expired = not user.last_otp_sent_at or (now() - user.last_otp_sent_at > timedelta(hours=24))

    if otp_expired:
        user.is_active = False
        user.save(update_fields=["is_active"])
        otp_code = user.generate_otp()

        NotificationServiceHandler().send_notification([{
            "message_type": "EMAIL",
            "organisation_id": corporate_id,
            "destination": user.email,
            "message": f"<p>Hello {user.username},</p><p>Your OTP is <b>{otp_code}</b>.</p>",
            "confirmation_code": otp_code
        }])
        TransactionLogBase.log("OTP_SENT", user=user, message="OTP sent due to expiration")

        return JsonResponse({
            "message": "OTP expired. A new one has been sent to your email.",
            "otp_required": True
        })

    user.is_active = True
    user.save(update_fields=["is_active"])

    access_token, refresh_token = issue_tokens_for_user(user, role, corporate_id)
    TransactionLogBase.log("USER_LOGIN", user=user, message="User logged in successfully")

    response = JsonResponse({
        "access": access_token,
        "refresh": refresh_token,
        "otp_required": False,
        "is_global_user": not corporate_user,
        "organisation_id": corporate_id,
        "role": role,
    })
    response["Authorization"] = f"Bearer {access_token}"
    return response

@csrf_exempt
def verify_otp(request):
    data, _ = get_clean_data(request)
    otp_code = data.get("otp")

    if not otp_code:
        return JsonResponse({"error": "OTP required"}, status=400)

    try:
        user = CustomUser.objects.get(otp_code=otp_code)
    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "Invalid OTP"}, status=400)

    if not user.last_otp_sent_at or (now() - user.last_otp_sent_at > timedelta(hours=24)):
        return JsonResponse({"error": "OTP expired"}, status=400)

    user.otp_code = None
    user.last_otp_sent_at = now()
    user.is_active = True
    user.save()

    corporate_user = CorporateUser.objects.filter(id=user.id).first()
    role = corporate_id = None
    if corporate_user:
        role = corporate_user.role.name if corporate_user.role else None
        corporate_id = corporate_user.corporate_id

    access_token, refresh_token = issue_tokens_for_user(user, role, corporate_id)

    TransactionLogBase.log("OTP_VERIFIED", user=user, message="OTP verified, login completed")

    response = JsonResponse({
        "message": "OTP verified successfully",
        "access": access_token,
        "refresh": refresh_token,
        "otp_required": False
    })
    response["Authorization"] = f"Bearer {access_token}"
    return response

from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.decorators import method_decorator

@csrf_exempt
def logout_user(request):
    auth_header = get_authorization_header(request).decode('utf-8')

    if not auth_header or not auth_header.startswith("Bearer "):
        return JsonResponse({"error": "Missing or invalid Authorization header"}, status=401)

    token = auth_header.split(" ")[1].strip()
    jwt_auth = JWTAuthentication()

    try:
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
    except Exception:
        return JsonResponse({"error": "Invalid or expired token"}, status=401)

    user.last_otp_sent_at = None
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

