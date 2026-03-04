from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from Authentication.models.role import Role
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.billing_client import BillingServiceClient
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def register_individual_user(request):
    data, metadata = get_clean_data(request)
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    plan_tier = data.get("plan_tier", "starter")

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

        otp_code = user.generate_otp()
        user.last_otp_sent_at = now()
        user.save()

        billing_client = BillingServiceClient()
        subscription_result = billing_client.create_subscription(
            corporate_id=str(corporate.id),
            corporate_name=corporate.name,
            plan_tier=plan_tier,
            billing_cycle="monthly",
        )

        if not subscription_result.get("success"):
            TransactionLogBase.log(
                "BILLING_SUBSCRIPTION_FAILED",
                user=user,
                message=f"Failed to create subscription: {subscription_result.get('message')}",
            )

        NotificationServiceHandler().send_notification(
            [
                {
                    "message_type": "2",
                    "organisation_id": str(corporate.id),
                    "destination": user.email,
                    "message": f"""
                    <h3>Welcome to Quidpath!</h3>
                    <p>Hello {user.username},</p>
                    <p>Your account has been created successfully.</p>
                    <p>Your OTP is <b>{otp_code}</b>.</p>
                    <p>Please verify your email and complete payment to activate your account.</p>
                """,
                    "confirmation_code": otp_code,
                }
            ]
        )

        TransactionLogBase.log(
            "INDIVIDUAL_USER_REGISTERED",
            user=user,
            message=f"Individual user {username} registered with organization {corporate.name}",
        )

        return JsonResponse(
            {
                "message": "User registered successfully. Please verify OTP and complete payment.",
                "otp_required": True,
                "corporate_id": str(corporate.id),
                "subscription_required": True,
                "subscription_details": subscription_result.get("data", {}),
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
