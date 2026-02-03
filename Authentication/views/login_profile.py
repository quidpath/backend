import base64
import os
import re

import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication

from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase


@csrf_exempt
def get_profile(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return ResponseProvider(
            {"error": "Missing or invalid Authorization header"}, "Unauthorized", 401
        ).unauthorized()

    token = auth_header.split(" ")[1].strip()
    jwt_auth = JWTAuthentication()

    try:
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
    except Exception:
        return ResponseProvider(
            {"error": "Invalid or expired token"}, "Unauthorized", 401
        ).unauthorized()

    corporate_user = CorporateUser.objects.filter(id=user.id).first()
    role = None
    corporate = None

    def is_valid_base64(data: str) -> bool:
        """Validate base64 string"""
        try:
            clean_data = re.sub(r"^data:image\/[^;]+;base64,", "", data)
            base64.b64decode(clean_data, validate=True)
            return True
        except Exception as e:
            TransactionLogBase.log(
                transaction_type="BASE_64_RETREIVAL_FAILED",
                user=user,
                message=str(e),
                state_name="Failed",
                request=request,
            )
            return False

    def convert_file_to_base64(file_path: str) -> str:
        """Convert file to base64 data URL"""
        try:
            if not os.path.exists(file_path):
                return ""

            with open(file_path, "rb") as file:
                file_content = file.read()
                encoded = base64.b64encode(file_content).decode("utf-8")

                # Detect content type from extension
                if file_path.lower().endswith(".svg"):
                    content_type = "image/svg+xml"
                elif file_path.lower().endswith(".png"):
                    content_type = "image/png"
                elif file_path.lower().endswith((".jpg", ".jpeg")):
                    content_type = "image/jpeg"
                else:
                    content_type = "image/png"

                return f"data:{content_type};base64,{encoded}"
        except Exception as e:
            TransactionLogBase.log(
                transaction_type="BASE_64_FILE_CONVERSION_FAILED",
                user=user,
                message=str(e),
                state_name="Failed",
                request=request,
            )
            return ""

    def process_logo_data(logo_value: str) -> str:
        """Process logo data and return base64 data URL"""
        if not logo_value:
            return ""

        logo_str = str(logo_value)

        # Case 1: Already a valid data URL
        if logo_str.startswith("data:image/"):
            if is_valid_base64(logo_str):
                return logo_str
            return ""

        # Case 2: Raw base64 string
        if is_valid_base64(logo_str) and not logo_str.startswith("http"):
            return f"data:image/png;base64,{logo_str}"

        # Case 3: SVG content
        if "<svg" in logo_str.lower():
            try:
                encoded = base64.b64encode(logo_str.encode("utf-8")).decode("utf-8")
                return f"data:image/svg+xml;base64,{encoded}"
            except Exception as e:
                TransactionLogBase.log(
                    transaction_type="SVG_ENCODE_FAILED",
                    user=user,
                    message=str(e),
                    state_name="Failed",
                    request=request,
                )
                return ""

        # Case 4: URL
        if logo_str.startswith("http"):
            try:
                response = requests.get(logo_str, timeout=10)
                if response.status_code == 200:
                    encoded = base64.b64encode(response.content).decode("utf-8")
                    content_type = response.headers.get("content-type", "image/png")
                    return f"data:{content_type};base64,{encoded}"
            except requests.RequestException as e:
                TransactionLogBase.log(
                    transaction_type="URL_FETCH_FAILED",
                    user=user,
                    message=str(e),
                    state_name="Failed",
                    request=request,
                )
            return ""

        # Case 5: Local absolute path
        if os.path.isabs(logo_str):
            return convert_file_to_base64(logo_str)

        # Case 6: Relative MEDIA path
        if hasattr(settings, "MEDIA_ROOT"):
            full_path = os.path.join(settings.MEDIA_ROOT, logo_str.lstrip("/"))
            return convert_file_to_base64(full_path)

        return ""

    if corporate_user:
        role = (
            {
                "id": corporate_user.role.id,
                "name": corporate_user.role.name,
            }
            if corporate_user.role
            else None
        )

        corp = corporate_user.corporate
        logo_data = ""

        if corp and corp.logo:
            try:
                if hasattr(corp.logo, "path") and os.path.exists(corp.logo.path):
                    # ✅ Use filesystem path directly
                    logo_data = process_logo_data(corp.logo.path)
                else:
                    # ✅ Build absolute path using MEDIA_ROOT
                    logo_data = process_logo_data(
                        os.path.join(settings.MEDIA_ROOT, str(corp.logo))
                    )
            except Exception as e:
                TransactionLogBase.log(
                    transaction_type="PROCESSING_LOGO_DATA_FAILED",
                    user=user,
                    message=str(e),
                    state_name="Failed",
                    request=request,
                )
                logo_data = ""

        corporate = {
            "id": corp.id if corp else None,
            "name": corp.name if corp else "",
            "description": corp.description if corp else "",
            "website": corp.website if corp else "",
            "logo": logo_data,
            "address": corp.address if corp else "",
            "city": corp.city if corp else "",
            "state": corp.state if corp else "",
            "country": corp.country if corp else "",
            "zip_code": corp.zip_code if corp else "",
            "phone": corp.phone if corp else "",
            "email": corp.email if corp else "",
            "is_approved": corp.is_approved if corp else False,
            "is_rejected": corp.is_rejected if corp else False,
            "rejection_reason": corp.rejection_reason if corp else "",
            "is_active": corp.is_active if corp else False,
            "is_seen": corp.is_seen if corp else False,
            "is_verified": corp.is_verified if corp else False,
            "created_at": corp.created_at if corp else None,
            "updated_at": corp.updated_at if corp else None,
        }
    else:
        corporate = {
            "id": None,
            "name": "",
            "logo": "",
        }

    user_profile = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "profilePhoto": user.profilePhoto,
        "phone_number": user.phone_number,
        "address": user.address,
        "city": user.city,
        "country": user.country,
        "zip_code": user.zip_code,
        "date_of_birth": user.date_of_birth,
        "gender": user.gender,
        "last_login": user.last_login,
        "otp_code": user.otp_code,
        "last_otp_sent_at": user.last_otp_sent_at,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "date_joined": user.date_joined,
        "groups": list(user.groups.values_list("name", flat=True)),
        "user_permissions": list(
            user.user_permissions.values_list("codename", flat=True)
        ),
        "corporate": corporate,
        "role": role,
    }

    TransactionLogBase.log(
        "USER_PROFILE_FETCHED", user=user, message="User profile retrieved successfully"
    )

    return ResponseProvider(
        {"user": user_profile}, "User profile fetched", 200
    ).success()
