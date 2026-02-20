# authentication/views/register.py
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def register_user(request):
    """
    Register a new user:
    - Creates user
    - Sends OTP (must be verified before login)
    - Does NOT issue tokens until OTP is verified
    """
    data, metadata = get_clean_data(request)
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    # Required fields
    if not username or not email or not password:
        return JsonResponse(
            {"error": "username, email, password are required"}, status=400
        )

    # Check duplicates
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=400)

    if CustomUser.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=400)

    # Create user via registry (inactive by default)
    user_data = {
        "username": username,
        "email": email,
        "password": make_password(password),
        "is_active": False,  # Only activate after OTP verification
    }
    created_user = ServiceRegistry().database("customuser", "create", data=user_data)

    # Get actual model instance
    if isinstance(created_user, dict):
        user = CustomUser.objects.get(id=created_user["id"])
    else:
        user = created_user

    # Generate OTP & timestamp
    otp_code = user.generate_otp()
    user.last_otp_sent_at = now()
    user.save()

    # Send OTP email
    NotificationServiceHandler().send_notification(
        [
            {
                "message_type": "EMAIL",
                "organisation_id": None,
                "destination": user.email,
                "message": f"<p>Welcome {user.username},</p><p>Your OTP is <b>{otp_code}</b>.</p>",
                "confirmation_code": otp_code,
            }
        ]
    )

    # Log actions
    TransactionLogBase.log(
        "USER_REGISTERED",
        user=user,
        message="New user registered (awaiting OTP verification)",
    )
    TransactionLogBase.log(
        "OTP_SENT", user=user, message="Initial OTP sent for registration"
    )

    # Respond without issuing tokens (must verify OTP)
    return JsonResponse(
        {
            "message": "User registered successfully. OTP sent to email.",
            "otp_required": True,
        },
        status=201,
    )
