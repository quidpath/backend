# views/forgot_password.py
import random
import string

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from Authentication.models.forgotPassword import ForgotPassword
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data, get_data


def generate_otp(length=6):
    """
    Generate a numeric OTP of specified length.
    """
    return "".join(random.choices(string.digits, k=length))


@csrf_exempt
def forgot_password(request):
    try:
        data, metadata = get_data(request)
        username = data.get("username")

        # Check if username is provided
        if not username:
            return ResponseProvider(
                message="Username is required", code=400
            ).bad_request()
        # Use Django ORM directly to avoid ServiceRegistry tuple issues
        try:
            from OrgAuth.models import CorporateUser

            user_instance = CorporateUser.objects.get(username=username)
            user_id = user_instance.id
            email = user_instance.email
            organisation = user_instance.corporate
            organisation_id = (
                str(organisation.id if hasattr(organisation, "id") else organisation)
                if organisation
                else None
            )
        except CorporateUser.DoesNotExist:
            return ResponseProvider(message="User not found", code=404).bad_request()
        except Exception as e:
            return ResponseProvider(
                message=f"Error finding user: {str(e)}", code=500
            ).exception()

        # Invalidate any existing valid OTP entries for this user using ServiceRegistry
        try:
            existing_otps = ServiceRegistry().database(
                "forgotpassword", "filter", data={"user": user_id, "is_valid": True}
            )

            for otp_item in existing_otps:
                # Handle nested tuples safely
                otp_entry = otp_item
                while isinstance(otp_entry, tuple):
                    otp_entry = otp_entry[0]

                otp_id = (
                    otp_entry.id
                    if hasattr(otp_entry, "id")
                    else (
                        otp_entry.get("id")
                        if hasattr(otp_entry, "get")
                        else str(otp_entry)
                    )
                )
                ServiceRegistry().database(
                    "forgotpassword",
                    "update",
                    instance_id=otp_id,
                    data={"is_valid": False},
                )
        except Exception as e:
            print(f"Warning: Could not invalidate existing OTPs: {str(e)}")
            # Continue anyway - this is not critical

        otp = generate_otp()

        # Create new OTP entry using ServiceRegistry
        try:
            forgot_password_entry = ServiceRegistry().database(
                "forgotpassword",
                "create",
                data={"user": user_instance, "otp": otp, "is_valid": True},
            )
        except Exception as e:
            return ResponseProvider(
                message=f"Error creating OTP entry: {str(e)}", code=500
            ).exception()

        # Send OTP Email
        try:
            notification_handler = NotificationServiceHandler()
            message = notification_handler.createOtpEmail(
                username=username,
                otp_code=otp,
            )

            notification_handler.send_notification(
                notifications=[
                    {
                        "message_type": "2",
                        "message": message,
                        "destination": email,
                        "organisation_id": organisation_id,
                    }
                ]
            )
        except Exception as e:
            return ResponseProvider(
                message=f"Error sending notification: {str(e)}", code=500
            ).exception()

        TransactionLogBase.log(
            "OTP_SENT", user=user_instance, message="OTP sent successfully"
        )

        return ResponseProvider(message="OTP sent to email", code=200).success()

    except Exception as e:
        return ResponseProvider(
            message=f"Error sending OTP: {str(e)}", code=500
        ).exception()


@csrf_exempt
def verify_pass_otp(request):
    try:
        data, metadata = get_clean_data(request)
        otp = data.get("otp")

        # Check if OTP is provided
        if not otp:
            return ResponseProvider(message="OTP is required", code=400).bad_request()

        # Get OTP entry using ServiceRegistry
        otp_entries = ServiceRegistry().database(
            "forgotpassword",
            "filter",
            data={"otp": otp, "is_valid": True, "is_verified": False},
        )

        if not otp_entries:
            return ResponseProvider(
                message="Invalid or expired OTP", code=400
            ).bad_request()

        otp_entry = otp_entries[0]

        # Get user model and instance using email
        User = get_user_model()
        user_instance = User.objects.get(email=otp_entry["user"])  # Get user from email
        user_id = user_instance.id

        # Get the ForgotPassword instance
        forgot_password_instance = ForgotPassword.objects.get(id=otp_entry["id"])

        if forgot_password_instance.has_expired():
            ServiceRegistry().database(
                "forgotpassword",
                "update",
                instance_id=otp_entry["id"],
                data={"is_valid": False},
            )
            return ResponseProvider(message="OTP has expired", code=400).bad_request()

        # Mark OTP as verified
        ServiceRegistry().database(
            "forgotpassword",
            "update",
            instance_id=otp_entry["id"],
            data={"is_valid": True, "is_verified": True},
        )

        # Log the OTP verification
        TransactionLogBase.log(
            "OTP_VERIFIED", user=user_instance, message="OTP verified successfully"
        )

        return ResponseProvider(
            message={
                "message": "OTP verified successfully",
                "forgot_password_id": str(otp_entry["id"]),
            },
            code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(
            message=f"Error verifying OTP: {str(e)}", code=500
        ).exception()


@csrf_exempt
def reset_password(request):
    user_instance = None
    try:
        data, metadata = get_clean_data(request)
        new_password = data.get("new_password")

        # Check if new password is provided
        if not new_password:
            return ResponseProvider(
                message="New password is required", code=400
            ).bad_request()

        # Get latest valid and verified OTP entry
        otp_entries = ServiceRegistry().database(
            "forgotpassword", "filter", data={"is_valid": True, "is_verified": True}
        )

        if not otp_entries:
            return ResponseProvider(
                message="No valid OTP session found", code=400
            ).bad_request()

        otp_entry = otp_entries[0]

        # Check expiration
        forgot_password_instance = ForgotPassword.objects.get(id=otp_entry["id"])
        if forgot_password_instance.has_expired():
            ServiceRegistry().database(
                "forgotpassword",
                "update",
                instance_id=otp_entry["id"],
                data={"is_valid": False},
            )
            return ResponseProvider(
                message="OTP session has expired", code=400
            ).bad_request()

        # Get user using email (if otp_entry["user"] is email)
        User = get_user_model()
        user_instance = User.objects.get(
            email=otp_entry["user"]
        )  # Adjust if user ID is returned

        # Set and hash new password
        user_instance.set_password(new_password)
        user_instance.save()  # Save to hash and update

        # Update user password in DB using ServiceRegistry
        ServiceRegistry().database(
            "customuser",
            "update",
            instance_id=str(user_instance.id),
            data={"password": user_instance.password},
        )

        # Invalidate and delete OTP entry
        ServiceRegistry().database(
            "forgotpassword",
            "update",
            instance_id=otp_entry["id"],
            data={"is_valid": False, "used_at": timezone.now()},
        )
        ServiceRegistry().database(
            "forgotpassword", "delete", instance_id=otp_entry["id"]
        )

        # Log success
        TransactionLogBase.log(
            "PASSWORD_RESET_SUCCESS",
            user=user_instance,
            message="Password reset successfully",
            request=request,
        )

        return ResponseProvider(
            message="Password reset successfully", code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            "PASSWORD_RESET_FAILED",
            user=user_instance,
            message=f"Password reset failed: {str(e)}",
        )
        return ResponseProvider(
            message=f"Error resetting password: {str(e)}", code=500
        ).exception()
