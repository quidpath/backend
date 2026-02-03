# Change password view
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def change_password(request):
    """
    Change password for authenticated user.

    POST /change-password/

    Request:
    {
        "current_password": "old_password",
        "new_password": "new_password"
    }

    Response:
    {
        "code": 200,
        "message": "Password changed successfully"
    }
    """
    user_instance = None
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")

        if not user:
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        current_password = data.get("current_password")
        new_password = data.get("new_password")

        if not current_password:
            return ResponseProvider(
                message="Current password is required", code=400
            ).bad_request()

        if not new_password:
            return ResponseProvider(
                message="New password is required", code=400
            ).bad_request()

        if len(new_password) < 8:
            return ResponseProvider(
                message="New password must be at least 8 characters long", code=400
            ).bad_request()

        # Get user instance
        User = get_user_model()
        user_instance = User.objects.get(id=user_id)

        # Verify current password
        if not user_instance.check_password(current_password):
            return ResponseProvider(
                message="Current password is incorrect", code=400
            ).bad_request()

        # Check if new password is same as current
        if user_instance.check_password(new_password):
            return ResponseProvider(
                message="New password must be different from current password", code=400
            ).bad_request()

        # Set new password
        user_instance.set_password(new_password)
        user_instance.save()

        # Log success
        TransactionLogBase.log(
            "PASSWORD_CHANGED",
            user=user_instance,
            message="Password changed successfully",
            request=request,
        )

        return ResponseProvider(
            message="Password changed successfully", code=200
        ).success()

    except User.DoesNotExist:
        return ResponseProvider(message="User not found", code=404).bad_request()
    except Exception as e:
        TransactionLogBase.log(
            "PASSWORD_CHANGE_FAILED",
            user=user_instance,
            message=f"Password change failed: {str(e)}",
        )
        return ResponseProvider(
            message=f"Error changing password: {str(e)}", code=500
        ).exception()
