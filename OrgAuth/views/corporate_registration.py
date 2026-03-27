import base64
import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db.models.fields.files import ImageFieldFile
from django.forms import model_to_dict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate
from quidpath_backend.core.utils.decorators import require_authenticated
from quidpath_backend.core.decorators import require_superuser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase, logger
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_corporate(request):
    data, metadata = get_clean_data(request)
    try:
        corporate_name = data.get("name")
        email = data.get("email")

        if not corporate_name:
            return JsonResponse({"error": "Corporate name is required"}, status=400)

        existing = ServiceRegistry().database(
            "corporate", "filter", data={"name": corporate_name}
        )
        if existing:
            return JsonResponse(
                {
                    "error": f"A corporate with the name '{corporate_name}' already exists."
                },
                status=400,
            )

        if email:
            existing_email = ServiceRegistry().database(
                "corporate", "filter", data={"email": email}
            )
            if existing_email:
                return JsonResponse(
                    {"error": f"A corporate with the email '{email}' already exists."},
                    status=400,
                )

        # Filter data to only include valid Corporate model fields
        valid_fields = {
            'name', 'industry', 'company_size', 'message', 'registration_number',
            'tax_id', 'description', 'website', 'logo', 'address', 'city', 'state',
            'country', 'zip_code', 'phone', 'email', 'is_approved', 'is_rejected',
            'rejection_reason', 'is_active', 'is_seen', 'is_verified'
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        # Create the corporate
        corporate = ServiceRegistry().database("corporate", "create", data=filtered_data)

        if isinstance(corporate, dict):
            corporate_name = corporate.get("name")
            corporate_id = corporate.get("id")
        else:
            corporate_name = corporate.name
            corporate_id = corporate.id

        # Notify billing service that a new corporate was created (non-fatal)
        try:
            from quidpath_backend.core.Services.billing_service import billing_service as bs
            bs.create_trial(
                corporate_id=str(corporate_id),
                corporate_name=corporate_name,
                plan_tier="starter",
            )
            logger.info(f"Trial record created in billing service for corporate {corporate_name}")
        except Exception as e:
            logger.warning(f"Billing service trial creation skipped for {corporate_name}: {e}")

        # Log the creation
        TransactionLogBase.log(
            "CORPORATE_CREATED",
            user=None,
            message=f"Corporate {corporate_name} created",
            request=request,
        )

        # Send email notification
        notification_service = NotificationServiceHandler()
        email_recipient = email
        replace_items = {"corporate_name": corporate_name}
        message = notification_service.createCorporateEmail(**replace_items)

        notification_service.send_notification(
            [
                {
                    "message_type": "2",
                    "organisation_id": corporate_id,
                    "destination": email_recipient,
                    "message": message,
                }
            ]
        )

        return JsonResponse(
            {"message": "Corporate created successfully", "id": corporate_id}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_superuser
def list_corporates(request):
    try:
        corporates = ServiceRegistry().database("corporate", "filter", data={})
        corp_list = []

        for corp in corporates:
            corp_dict = {}

            if hasattr(corp, "_meta"):  
                for field in corp.meta.fields:
                    field_name = field.name
                    value = getattr(corp, field_name)

                    if isinstance(
                        value, ImageFieldFile
                    ):  # Catch raw ImageFieldFile directly
                        if value and value.path:
                            try:
                                with open(value.path, "rb") as img:
                                    encoded = base64.b64encode(img.read()).decode(
                                        "utf-8"
                                    )
                                    ext = value.name.split(".")[-1].lower()
                                    corp_dict[field_name] = (
                                        f"data:image/{ext};base64,{encoded}"
                                    )
                            except Exception:
                                corp_dict[field_name] = None
                        else:
                            corp_dict[field_name] = None
                    else:
                        corp_dict[field_name] = value

            elif isinstance(corp, dict):  # It's a dictionary
                for key, value in corp.items():
                    if isinstance(value, ImageFieldFile):  # Handle raw ImageFieldFile
                        if value and value.path:
                            try:
                                with open(value.path, "rb") as img:
                                    encoded = base64.b64encode(img.read()).decode(
                                        "utf-8"
                                    )
                                    ext = value.name.split(".")[-1].lower()
                                    corp_dict[key] = (
                                        f"data:image/{ext};base64,{encoded}"
                                    )
                            except Exception:
                                corp_dict[key] = None
                        else:
                            corp_dict[key] = None
                    elif isinstance(value, str) and value.lower().endswith(
                        (".jpg", ".jpeg", ".png", ".gif")
                    ):
                        try:
                            with open(value, "rb") as img:
                                encoded = base64.b64encode(img.read()).decode("utf-8")
                                ext = value.split(".")[-1].lower()
                                corp_dict[key] = f"data:image/{ext};base64,{encoded}"
                        except Exception:
                            corp_dict[key] = None
                    else:
                        corp_dict[key] = value
            else:
                continue  # Unknown object type

            corp_list.append(corp_dict)

        return JsonResponse({"corporates": corp_list}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def process_base64_image(base64_string, filename_prefix="profile"):
    """
    Process base64 image string and return ContentFile
    """
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
            else:
                ext = "jpg"
        else:
            data = base64_string
            ext = "jpg"
        image_data = base64.b64decode(data)
        filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        return ContentFile(image_data, name=filename)
    except Exception as e:
        print(f"Error processing base64 image: {e}")
        return None


@csrf_exempt
def update_corporate(request):
    try:
        # Parse request data and metadata
        logger.debug("Parsing request data")
        data, metadata = get_clean_data(request)
        logger.debug(f"Received data: {data}, metadata: {metadata}")

        user = metadata.get("user")
        if not user:
            logger.warning("User not authenticated")
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        if not user_id:
            logger.warning("User ID not found")
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        # Initialize service registry
        logger.debug("Initializing ServiceRegistry")
        registry = ServiceRegistry()

        # Validate user corporate association
        logger.debug(f"Filtering CorporateUser for user_id: {user_id}")
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        logger.debug(f"Corporate users: {corporate_users}")
        if not corporate_users:
            logger.warning("No corporate association found for user")
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            logger.warning("Corporate ID not found in corporate_users")
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        # Handle base64 logo
        logger.debug("Processing logo data")
        logo_data = data.get("logo")
        if (
            logo_data
            and isinstance(logo_data, str)
            and logo_data.startswith("data:image/")
        ):
            try:
                logger.debug("Decoding base64 logo")
                base64_string = logo_data.split(";base64,")[-1]
                image_data = base64.b64decode(base64_string)
                if len(image_data) > 5 * 1024 * 1024:
                    logger.warning("Image size exceeds 5MB limit")
                    return JsonResponse(
                        {"error": "Image size exceeds 5MB limit"}, status=400
                    )

                ext = logo_data.split(";")[0].split("/")[-1]
                processed_logo = ContentFile(
                    image_data, name=f"logo_{corporate_id}.{ext}"
                )
                data["logo"] = processed_logo
                logger.debug("Logo processed successfully")
            except Exception as e:
                logger.error(f"Failed to process base64 logo: {str(e)}", exc_info=True)
                return JsonResponse(
                    {"error": f"Invalid base64 image data: {str(e)}"}, status=400
                )
        elif logo_data == "":
            logger.debug("Logo removal requested")
            data["logo"] = None
        elif logo_data:
            logger.warning("Invalid logo format")
            return JsonResponse(
                {"error": "Logo must be a valid base64-encoded image"}, status=400
            )

        # Update corporate
        logger.debug(f"Updating Corporate with ID: {corporate_id}, data: {data}")
        updated = registry.database("Corporate", "update", corporate_id, data=data)
        logger.debug(f"Update result: {updated}")

        # Ensure updated is a model instance
        if isinstance(updated, dict):
            logger.debug(f"Fetching Corporate instance for ID: {corporate_id}")
            updated = registry.database(
                model_name="Corporate", operation="filter", data={"id": corporate_id}
            )
            logger.debug(f"Filter result: {updated}")
            if not updated:
                logger.error("Failed to retrieve updated corporate")
                return JsonResponse(
                    {"error": "Failed to retrieve updated corporate"}, status=400
                )
            updated = updated[0] if isinstance(updated, list) else updated

        # Convert to dict with base64 logo
        logger.debug("Converting updated to dict")
        updated_dict = (
            model_to_dict(updated) if not isinstance(updated, dict) else updated
        )
        if updated_dict.get("logo"):
            try:
                if hasattr(updated, "logo") and hasattr(updated.logo, "path"):
                    logger.debug("Encoding logo to base64")
                    with open(updated.logo.path, "rb") as img:
                        encoded = base64.b64encode(img.read()).decode("utf-8")
                        ext = updated.logo.name.split(".")[-1].lower()
                        updated_dict["logo"] = f"data:image/{ext};base64,{encoded}"
                else:
                    # If logo is an ImageFieldFile or string, convert to URL or null
                    updated_dict["logo"] = (
                        str(updated_dict["logo"]) if updated_dict["logo"] else None
                    )
            except Exception as e:
                logger.error(f"Failed to encode logo: {str(e)}", exc_info=True)
                updated_dict["logo"] = None

        # Log the update
        changed_fields = [k for k in data.keys() if k != "id"]
        logger.debug(f"Logging update for fields: {changed_fields}")
        TransactionLogBase.log(
            "CORPORATE_UPDATED",
            user=user,
            message=f"Corporate {updated_dict.get('name', 'Unknown')} updated (fields: {', '.join(changed_fields)})",
            request=request,
        )

        # Send notification
        if updated_dict.get("email"):
            logger.debug(f"Sending notification to {updated_dict.get('email')}")
            try:
                notification_service = NotificationServiceHandler()
                replace_items = {
                    "corporate_name": updated_dict.get('name', 'Customer'),
                    "fields": ', '.join(changed_fields),
                }
                message = notification_service.createCorporateProfileUpdatedEmail(**replace_items)
                
                notification_service.send_notification(
                    [
                        {
                            "message_type": "2",
                            "organisation_id": updated_dict.get("id"),
                            "destination": updated_dict.get("email"),
                            "message": message,
                        }
                    ]
                )
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}", exc_info=True)

        logger.info("Corporate updated successfully")
        return JsonResponse(
            {"message": "Corporate updated successfully", "corporate": updated_dict}
        )

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}", exc_info=True)
        return JsonResponse({"error": f"Invalid data: {str(ve)}"}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in update_corporate: {str(e)}", exc_info=True)
        return JsonResponse({"error": "An unexpected error occurred"}, status=500)


@csrf_exempt
def delete_corporate(request):
    data, _ = get_clean_data(request)
    corp_id = data.get("id")

    if not corp_id:
        return JsonResponse({"error": "Corporate ID is required"}, status=400)

    try:
        # Retrieve the corporate record as a dict
        corporates = ServiceRegistry().database(
            "corporate", "filter", data={"id": corp_id}
        )

        corporate = corporates[0] if corporates else None

        if not corporate:
            return JsonResponse({"error": "Corporate not found"}, status=404)

        name = corporate.get("name", "Unknown")
        email = corporate.get("email")

        # Delete using a filter instead of instance_id
        ServiceRegistry().database("corporate", "delete", corp_id)

        TransactionLogBase.log(
            "CORPORATE_DELETED",
            user=None,
            message=f"Corporate '{name}' (ID {corp_id}) deleted",
            request=request,
        )

        if email:
            notification_service = NotificationServiceHandler()
            replace_items = {"corporate_name": name}
            message = notification_service.createCorporateDeletedEmail(**replace_items)
            
            notification_service.send_notification(
                [
                    {
                        "organisation_id": corp_id,
                        "destination": email,
                        "message_type": "2",
                        "message": message,
                    }
                ]
            )

        return JsonResponse({"message": f"Corporate '{name}' deleted successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_superuser
def approve_corporate(request):
    data, _ = get_clean_data(request)
    corporate_id = data.get("id")
    decision_raw = data.get("approved")

    if corporate_id is None or decision_raw is None:
        return JsonResponse(
            {"error": "Corporate ID and approval decision are required."}, status=400
        )

    try:
        decision = str(decision_raw).lower() == "true"  # Ensures boolean

        corporate = Corporate.objects.filter(id=corporate_id).first()
        if not corporate:
            return JsonResponse({"error": "Corporate not found."}, status=404)

        corporate.is_seen = True

        if decision:
            corporate.is_approved = True
            corporate.is_disapproved = False
            corporate.save()

            # Manually trigger signal (if you use post_save signal normally)
            from OrgAuth.core.signals import create_superadmin_on_approval

            create_superadmin_on_approval(
                sender=Corporate, instance=corporate, created=False
            )

            message = "Corporate approved successfully."
        else:
            corporate.is_approved = False
            corporate.is_disapproved = True
            corporate.save()

            notification_service = NotificationServiceHandler()
            replace_items = {"corporate_name": corporate.name}
            message = notification_service.createCorporateDisapprovalEmail(**replace_items)
            
            notification_service.send_notification(
                [
                    {
                        "message_type": "2",
                        "organisation_id": corporate.id,
                        "destination": corporate.email,
                        "message": message,
                    }
                ]
            )
            message = "Corporate disapproved and notified."

        TransactionLogBase.log(
            "CORPORATE_APPROVAL_DECISION",
            user=request.user,
            message=f"Corporate {corporate.name} approval decision: {decision}",
            request=request,
        )

        return JsonResponse({"message": message})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def suspend_corporate(request):
    data, metadata = get_clean_data(request)
    corporate_id = data.get("id")
    if not corporate_id:
        return JsonResponse({"error": "Corporate ID is required."}, status=400)

    try:
        corporate = Corporate.objects.filter(id=corporate_id).first()
        if not corporate:
            return JsonResponse({"error": "Corporate not found."}, status=404)

        # Mark corporate as inactive
        corporate.is_active = False
        corporate.save()

        # Log the action
        TransactionLogBase.log(
            "CORPORATE_SUSPENDED",
            user=getattr(request, "user", None),  # Optional fallback
            message=f"Corporate {corporate.name} suspended",
            request=request,
        )

        # Send suspension notification
        notification_service = NotificationServiceHandler()
        replace_items = {"corporate_name": corporate.name}
        message = notification_service.createCorporateSuspendedEmail(**replace_items)
        
        notification_service.send_notification(
            [
                {
                    "message_type": "2",
                    "organisation_id": str(corporate.id),
                    "destination": corporate.email,
                    "message": message,
                }
            ]
        )

        return JsonResponse(
            {"message": "Corporate suspended and notified successfully."}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
