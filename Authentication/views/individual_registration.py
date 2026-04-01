import logging

from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from Authentication.models.role import Role
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data

logger = logging.getLogger(__name__)


@csrf_exempt
def register_individual_user(request):
    """
    Register an individual user:
    1. Creates Corporate + CorporateUser (both inactive until payment verified)
    2. Returns corporate_id for payment page
    3. After payment confirmation, user can login
    """
    from quidpath_backend.core.utils.request_parser import get_data
    data, metadata = get_data(request)
    
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    plan_tier = data.get("plan_tier", "starter")
    plan_id = data.get("plan_id")
    frontend_url = data.get("frontend_url", "https://stage.quidpath.com")

    if not username or not email or not password:
        return JsonResponse(
            {"error": "username, email, password are required"}, status=400
        )

    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=400)

    if CustomUser.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=400)

    try:
        corporate = Corporate.objects.create(
            name=f"{username} Organization",
            email=email,
            phone=data.get("phone", ""),
            industry="Individual",
            company_size="1-10",
            website="",
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            country=data.get("country", ""),
            zip_code=data.get("zip_code", ""),
            description=f"Individual account for {username}",
            is_approved=True,
            is_active=False,
            is_verified=False,
        )

        superadmin_role = Role.objects.get(name="SUPERADMIN")

        user = CorporateUser.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            corporate=corporate,
            role=superadmin_role,
            is_active=False,
        )

        user.metadata = {
            "plan_tier": plan_tier,
            "plan_id": plan_id,
            "payment_required": True,
        }
        user.save(update_fields=["metadata"])

        TransactionLogBase.log(
            "INDIVIDUAL_USER_REGISTERED",
            user=user,
            message=f"Individual user {username} registered with organization {corporate.name}",
        )

        return JsonResponse(
            {
                "message": "Registration successful! Please complete payment to activate your account.",
                "corporate_id": str(corporate.id),
                "email": email,
                "username": username,
            },
            status=201,
        )

    except Role.DoesNotExist:
        return JsonResponse({"error": "SUPERADMIN role not found"}, status=500)
    except Exception as e:
        TransactionLogBase.log(
            "INDIVIDUAL_USER_REGISTRATION_FAILED",
            user=None,
            message=f"Registration failed: {str(e)}",
        )
        return JsonResponse({"error": str(e)}, status=400)
