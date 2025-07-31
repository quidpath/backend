from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def corporate_update_profile(request):
    user_instance = None
    try:
        data, metadata = get_clean_data(request)
        user_id = metadata.get("user_id")

        if not user_id:
            return ResponseProvider(message="User ID is required", code=400).bad_request()

        # Get the user and corporate instance
        User = get_user_model()
        user_instance = User.objects.get(id=user_id)
        corporate_instance = user_instance.corporate  # via CorporateUser FK

        allowed_fields = [
            "name", "description", "website", "logo", "address",
            "city", "state", "country", "zip_code", "phone", "email"
        ]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            return ResponseProvider(message="No valid fields provided for corporate update", code=400).bad_request()

        ServiceRegistry().database("corporate", "update",
            instance_id=str(corporate_instance.id),
            data=update_data
        )

        TransactionLogBase.log(
            "CORPORATE_PROFILE_UPDATED",
            user=user_instance,
            message="Corporate profile updated successfully",
            request=request
        )

        return ResponseProvider(message="Corporate profile updated successfully", code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            "CORPORATE_PROFILE_UPDATE_FAILED",
            user=user_instance,
            message=f"Corporate update failed: {str(e)}"
        )
        return ResponseProvider(message=f"Error updating corporate profile: {str(e)}", code=500).exception()
