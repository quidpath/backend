from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider


@csrf_exempt
def get_profile(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header or not auth_header.startswith("Bearer "):
        return ResponseProvider({"error": "Missing or invalid Authorization header"}, "Unauthorized", 401).unauthorized()

    token = auth_header.split(" ")[1].strip()
    jwt_auth = JWTAuthentication()

    try:
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
    except Exception:
        return ResponseProvider({"error": "Invalid or expired token"}, "Unauthorized", 401).unauthorized()

    corporate_user = CorporateUser.objects.filter(id=user.id).first()
    role = None
    corporate = None

    if corporate_user:
        role = {
            "id": corporate_user.role.id,
            "name": corporate_user.role.name,
        } if corporate_user.role else None

        corp = corporate_user.corporate
        corporate = {
            "id": corp.id,
            "name": corp.name,
            "description": corp.description,
            "website": corp.website,
            "logo": corp.logo,  # will be serialized using comprehensive_serializer
            "address": corp.address,
            "city": corp.city,
            "state": corp.state,
            "country": corp.country,
            "zip_code": corp.zip_code,
            "phone": corp.phone,
            "email": corp.email,
            "is_approved": corp.is_approved,
            "is_rejected": corp.is_rejected,
            "rejection_reason": corp.rejection_reason,
            "is_active": corp.is_active,
            "is_seen": corp.is_seen,
            "is_verified": corp.is_verified,
            "created_at": corp.created_at,
            "updated_at": corp.updated_at,
        }

    user_profile = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "profilePhoto": user.profilePhoto,  # will be serialized using comprehensive_serializer
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
        "groups": list(user.groups.values_list('name', flat=True)),
        "user_permissions": list(user.user_permissions.values_list('codename', flat=True)),
        "corporate": corporate,
        "role": role,
    }

    TransactionLogBase.log("USER_PROFILE_FETCHED", user=user, message="User profile retrieved successfully")

    return ResponseProvider({"user": user_profile}, "User profile fetched", 200).success()
