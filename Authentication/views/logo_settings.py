import base64
import uuid

from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.decorators import require_authenticated
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.request_parser import get_clean_data


def process_base64_logo(base64_string, filename_prefix="logo"):
    try:
        if base64_string.startswith("data:"):
            header, data = base64_string.split(",", 1)
            if "jpeg" in header or "jpg" in header:
                ext = "jpg"
            elif "png" in header:
                ext = "png"
            elif "gif" in header:
                ext = "gif"
            elif "webp" in header:
                ext = "webp"
            elif "svg" in header:
                ext = "svg"
            else:
                ext = "jpg"
        else:
            data = base64_string
            ext = "jpg"
        
        image_data = base64.b64decode(data)
        
        if len(image_data) > 5 * 1024 * 1024:
            return None, "Image size exceeds 5MB limit"
        
        filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        return ContentFile(image_data, name=filename), None
    except Exception as e:
        return None, f"Error processing image: {str(e)}"


@csrf_exempt
@require_authenticated
def upload_corporate_logo(request):
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return JsonResponse({"error": "User ID not found"}, status=400)

    try:
        corporate_user = CorporateUser.objects.filter(
            customuser_ptr_id=user_id
        ).first()

        if not corporate_user:
            return JsonResponse(
                {"error": "User has no corporate association"}, status=400
            )

        if corporate_user.role.name not in ["SUPERADMIN"]:
            return JsonResponse(
                {"error": "Only SUPERADMIN can upload corporate logo"}, status=403
            )

        corporate = corporate_user.corporate
        logo_data = data.get("logo")

        if not logo_data:
            return JsonResponse({"error": "Logo data is required"}, status=400)

        if logo_data.startswith("data:image/"):
            processed_logo, error = process_base64_logo(logo_data, f"logo_{corporate.id}")
            if error:
                return JsonResponse({"error": error}, status=400)
            
            if corporate.logo:
                try:
                    corporate.logo.delete(save=False)
                except Exception:
                    pass
            
            corporate.logo = processed_logo
            corporate.save()

            with open(corporate.logo.path, "rb") as img:
                encoded = base64.b64encode(img.read()).decode("utf-8")
                ext = corporate.logo.name.split(".")[-1].lower()
                logo_url = f"data:image/{ext};base64,{encoded}"

            TransactionLogBase.log(
                "CORPORATE_LOGO_UPLOADED",
                user=user,
                message=f"Corporate logo uploaded for {corporate.name}",
                request=request,
            )

            return JsonResponse(
                {
                    "message": "Logo uploaded successfully",
                    "logo": logo_url,
                    "corporate_id": str(corporate.id),
                }
            )
        else:
            return JsonResponse(
                {"error": "Logo must be a valid base64-encoded image"}, status=400
            )

    except Exception as e:
        TransactionLogBase.log(
            "CORPORATE_LOGO_UPLOAD_FAILED",
            user=user,
            message=f"Logo upload failed: {str(e)}",
            request=request,
        )
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_authenticated
def get_corporate_logo(request):
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    # Check if user is superuser
    if isinstance(user, dict):
        is_superuser = user.get("is_superuser", False)
    else:
        is_superuser = getattr(user, "is_superuser", False)

    # Superusers don't have a corporate, return empty/default response
    if is_superuser:
        return JsonResponse({
            "logo": None,
            "corporate_id": None,
            "corporate_name": "System Admin",
            "message": "Superuser - no corporate associated"
        })

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return JsonResponse({"error": "User ID not found"}, status=400)

    try:
        corporate_user = CorporateUser.objects.filter(
            customuser_ptr_id=user_id
        ).first()

        if not corporate_user:
            return JsonResponse(
                {"error": "User has no corporate association"}, status=400
            )

        corporate = corporate_user.corporate

        if corporate.logo:
            try:
                with open(corporate.logo.path, "rb") as img:
                    encoded = base64.b64encode(img.read()).decode("utf-8")
                    ext = corporate.logo.name.split(".")[-1].lower()
                    logo_url = f"data:image/{ext};base64,{encoded}"
                
                return JsonResponse(
                    {
                        "logo": logo_url,
                        "corporate_id": str(corporate.id),
                        "corporate_name": corporate.name,
                    }
                )
            except Exception as e:
                return JsonResponse(
                    {"error": f"Failed to read logo: {str(e)}"}, status=500
                )
        else:
            return JsonResponse(
                {
                    "logo": None,
                    "corporate_id": str(corporate.id),
                    "corporate_name": corporate.name,
                }
            )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_authenticated
def delete_corporate_logo(request):
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return JsonResponse({"error": "User ID not found"}, status=400)

    try:
        corporate_user = CorporateUser.objects.filter(
            customuser_ptr_id=user_id
        ).first()

        if not corporate_user:
            return JsonResponse(
                {"error": "User has no corporate association"}, status=400
            )

        if corporate_user.role.name not in ["SUPERADMIN"]:
            return JsonResponse(
                {"error": "Only SUPERADMIN can delete corporate logo"}, status=403
            )

        corporate = corporate_user.corporate

        if corporate.logo:
            try:
                corporate.logo.delete(save=False)
            except Exception:
                pass
            
            corporate.logo = None
            corporate.save()

            TransactionLogBase.log(
                "CORPORATE_LOGO_DELETED",
                user=user,
                message=f"Corporate logo deleted for {corporate.name}",
                request=request,
            )

            return JsonResponse(
                {
                    "message": "Logo deleted successfully",
                    "corporate_id": str(corporate.id),
                }
            )
        else:
            return JsonResponse({"message": "No logo to delete"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
