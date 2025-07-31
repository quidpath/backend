from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def corporateuser_update_profile(request):
    user_instance = None
    try:
        data, metadata = get_clean_data(request)
        user_id = metadata.get("user_id")  # Set by auth middleware/session

        if not user_id:
            return ResponseProvider(message="User ID is missing", code=400).bad_request()

        User = get_user_model()
        user_instance = User.objects.get(id=user_id)

        allowed_fields = [
            "username", "email", "phone_number", "address",
            "city", "country", "zip_code", "date_of_birth",
            "gender", "profilePhoto"
        ]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            return ResponseProvider(message="No valid fields provided for update", code=400).bad_request()

        ServiceRegistry().database("customuser", "update",
            instance_id=user_id,
            data=update_data
        )

        TransactionLogBase.log(
            "CORPORATE_USER_PROFILE_UPDATED",
            user=user_instance,
            message="Corporate user profile updated successfully",
            request=request
        )

        return ResponseProvider(message="Profile updated successfully", code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            "CORPORATE_USER_PROFILE_UPDATE_FAILED",
            user=user_instance,
            message=f"Profile update failed: {str(e)}"
        )
        return ResponseProvider(message=f"Error updating profile: {str(e)}", code=500).exception()
