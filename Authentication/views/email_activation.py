import hashlib
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from Authentication.models.role import Role
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.rate_limit import rate_limit
from quidpath_backend.core.utils.request_parser import get_clean_data


def generate_activation_token(user_id: str, email: str) -> str:
    data = f"{user_id}:{email}:{timezone.now().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="register_individual")
def register_individual_with_email_activation(request):
    """
    Register an individual user:
    1. Creates a Corporate + CorporateUser (inactive)
    2. Sends activation email with link
    3. User must click link to activate, then pay before accessing the system
    """
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
            is_active=False,  # Inactive until payment confirmed
            is_verified=False,
        )

        superadmin_role = Role.objects.get(name="SUPERADMIN")

        user = CorporateUser.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            corporate=corporate,
            role=superadmin_role,
            is_active=False,  # Inactive until email activation
        )

        activation_token = generate_activation_token(str(user.id), email)
        user.metadata = {
            "activation_token": activation_token,
            "activation_token_created": timezone.now().isoformat(),
            "plan_tier": plan_tier,
            "payment_required": True,
        }
        user.save(update_fields=["metadata"])

        frontend_url = data.get("frontend_url", "https://app.quidpath.com")
        activation_link = f"{frontend_url}/activate-account?token={activation_token}&email={email}"

        NotificationServiceHandler().send_notification([
            {
                "message_type": "2",
                "organisation_id": str(corporate.id),
                "destination": email,
                "message": f"""
                <h3>Welcome to Quidpath!</h3>
                <p>Hello {username},</p>
                <p>Thank you for registering with Quidpath ERP.</p>
                <p>Please click the link below to activate your account:</p>
                <p><a href="{activation_link}" style="background-color: #000000; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">Activate Account</a></p>
                <p>Or copy and paste this link in your browser:</p>
                <p>{activation_link}</p>
                <p>This link will expire in 24 hours.</p>
                <p>After activation, you will be prompted to complete your subscription payment before accessing the system.</p>
                <p>If you didn't create this account, please ignore this email.</p>
            """,
            }
        ])

        TransactionLogBase.log(
            "INDIVIDUAL_USER_REGISTERED_EMAIL_ACTIVATION",
            user=user,
            message=f"Individual user {username} registered with email activation",
            extra={"corporate_id": str(corporate.id), "plan_tier": plan_tier},
        )

        return JsonResponse(
            {
                "message": "Registration successful. Please check your email to activate your account.",
                "email": email,
                "activation_required": True,
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


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="activate_account")
def activate_account(request):
    """
    Activate account via email link.
    After activation, user must pay before they can log in and use the system.
    Returns payment_required=True so the frontend redirects to the payment page.
    """
    data, metadata = get_clean_data(request)
    token = data.get("token")
    email = data.get("email")

    if not token or not email:
        return JsonResponse({"error": "Token and email are required"}, status=400)

    try:
        user = CustomUser.objects.get(email=email, is_active=False)

        if not hasattr(user, "metadata") or user.metadata is None:
            user.metadata = {}

        stored_token = user.metadata.get("activation_token")
        token_created = user.metadata.get("activation_token_created")

        if not stored_token or stored_token != token:
            return JsonResponse({"error": "Invalid activation token"}, status=400)

        if token_created:
            from datetime import datetime
            token_time = datetime.fromisoformat(token_created)
            if timezone.now() - token_time > timedelta(hours=24):
                return JsonResponse({"error": "Activation link has expired. Please request a new one."}, status=400)

        # Activate the user account — but mark payment as still required
        user.is_active = True
        if not isinstance(user.metadata, dict):
            user.metadata = {}
        user.metadata["activated_at"] = timezone.now().isoformat()
        user.metadata["payment_required"] = True
        user.save()

        # Get corporate info for payment redirect
        corporate_id = None
        plan_tier = user.metadata.get("plan_tier", "starter")
        try:
            corp_user = CorporateUser.objects.select_related("corporate").get(id=user.id)
            corporate_id = str(corp_user.corporate.id)
        except CorporateUser.DoesNotExist:
            pass

        TransactionLogBase.log(
            "ACCOUNT_ACTIVATED",
            user=user,
            message=f"Account activated for {user.username}",
        )

        NotificationServiceHandler().send_notification([
            {
                "message_type": "2",
                "organisation_id": corporate_id,
                "destination": email,
                "message": f"""
                <h3>Account Activated!</h3>
                <p>Hello {user.username},</p>
                <p>Your account has been successfully activated.</p>
                <p>Please complete your subscription payment to start using Quidpath.</p>
                <p>Thank you for choosing Quidpath!</p>
            """,
            }
        ])

        return JsonResponse({
            "message": "Account activated successfully. Please complete payment to access the system.",
            "username": user.username,
            "payment_required": True,
            "corporate_id": corporate_id,
            "plan_tier": plan_tier,
        })

    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "Invalid activation link or account already activated"}, status=400)
    except Exception as e:
        TransactionLogBase.log(
            "ACCOUNT_ACTIVATION_FAILED",
            user=None,
            message=f"Activation failed: {str(e)}",
        )
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@rate_limit(max_requests=5, window_seconds=60, key_prefix="resend_activation")
def resend_activation_email(request):
    data, metadata = get_clean_data(request)
    email = data.get("email")

    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)

    try:
        user = CustomUser.objects.get(email=email, is_active=False)

        activation_token = generate_activation_token(str(user.id), email)

        if not hasattr(user, "metadata") or user.metadata is None:
            user.metadata = {}

        user.metadata["activation_token"] = activation_token
        user.metadata["activation_token_created"] = timezone.now().isoformat()
        user.save()

        corporate_id = None
        try:
            corp_user = CorporateUser.objects.select_related("corporate").get(id=user.id)
            corporate_id = str(corp_user.corporate.id)
        except CorporateUser.DoesNotExist:
            pass

        frontend_url = data.get("frontend_url", "https://app.quidpath.com")
        activation_link = f"{frontend_url}/activate-account?token={activation_token}&email={email}"

        NotificationServiceHandler().send_notification([
            {
                "message_type": "2",
                "organisation_id": corporate_id,
                "destination": email,
                "message": f"""
                <h3>Activation Link Resent</h3>
                <p>Hello {user.username},</p>
                <p>Here is your new activation link:</p>
                <p><a href="{activation_link}" style="background-color: #000000; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">Activate Account</a></p>
                <p>Or copy and paste this link in your browser:</p>
                <p>{activation_link}</p>
                <p>This link will expire in 24 hours.</p>
            """,
            }
        ])

        TransactionLogBase.log(
            "ACTIVATION_EMAIL_RESENT",
            user=user,
            message=f"Activation email resent to {email}",
        )

        return JsonResponse({
            "message": "Activation email resent successfully. Please check your inbox.",
        })

    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "No inactive account found with this email"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
