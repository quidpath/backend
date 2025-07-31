import base64

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.files import ImageFieldFile
from django.forms import model_to_dict
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from OrgAuth.models import Corporate
from quidpath_backend.core.utils.decorators import require_authenticated
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry


@csrf_exempt
def create_corporate(request):
    data, metadata = get_clean_data(request)
    try:
        corporate_name = data.get("name")
        email = data.get("email")

        if not corporate_name:
            return JsonResponse({"error": "Corporate name is required"}, status=400)

        existing = ServiceRegistry().database("corporate", "filter", data={"name": corporate_name})
        if existing:
            return JsonResponse({"error": f"A corporate with the name '{corporate_name}' already exists."}, status=400)

        if email:
            existing_email = ServiceRegistry().database("corporate", "filter", data={"email": email})
            if existing_email:
                return JsonResponse({"error": f"A corporate with the email '{email}' already exists."}, status=400)

        # ✅ Create the corporate
        corporate = ServiceRegistry().database("corporate", "create", data=data)

        if isinstance(corporate, dict):
            corporate_name = corporate.get("name")
            corporate_id = corporate.get("id")
        else:
            corporate_name = corporate.name
            corporate_id = corporate.id

        # ✅ Log the creation
        TransactionLogBase.log("CORPORATE_CREATED", user=None, message=f"Corporate {corporate_name} created",request=request)

        # ✅ Send email notification
        notification_service = NotificationServiceHandler()
        email_recipient = email
        replace_items = {"corporate_name": corporate_name}
        message = notification_service.createCorporateEmail(**replace_items)

        notification_service.send_notification([{
            "message_type": "2",
            "organisation_id": corporate_id,
            "destination": email_recipient,
            "message": message
        }])

        return JsonResponse({"message": "Corporate created successfully", "id": corporate_id})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def list_corporates(request):
    try:
        corporates = ServiceRegistry().database("corporate", "filter", data={})
        corp_list = []

        for corp in corporates:
            corp_dict = {}

            if hasattr(corp, "_meta"):  # It's a Django model
                for field in corp._meta.fields:
                    field_name = field.name
                    value = getattr(corp, field_name)

                    if isinstance(value, ImageFieldFile):  # Catch raw ImageFieldFile directly
                        if value and value.path:
                            try:
                                with open(value.path, "rb") as img:
                                    encoded = base64.b64encode(img.read()).decode("utf-8")
                                    ext = value.name.split(".")[-1].lower()
                                    corp_dict[field_name] = f"data:image/{ext};base64,{encoded}"
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
                                    encoded = base64.b64encode(img.read()).decode("utf-8")
                                    ext = value.name.split(".")[-1].lower()
                                    corp_dict[key] = f"data:image/{ext};base64,{encoded}"
                            except Exception:
                                corp_dict[key] = None
                        else:
                            corp_dict[key] = None
                    elif isinstance(value, str) and value.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
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

@csrf_exempt
def update_corporate(request):
    data, _ = get_clean_data(request)
    corp_id = data.get("id")
    if not corp_id:
        return JsonResponse({"error": "Corporate ID is required"}, status=400)

    try:
        corporate = ServiceRegistry().database("corporate", "get", data={"id": corp_id})
        if not corporate:
            return JsonResponse({"error": "Corporate not found"}, status=404)

        updated = ServiceRegistry().database("corporate", "update", data=data)
        TransactionLogBase.log("CORPORATE_UPDATED", user=None, message=f"Corporate {updated.name} updated",request=request)
        return JsonResponse({"message": "Corporate updated successfully"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def delete_corporate(request):
    data, _ = get_clean_data(request)
    corp_id = data.get("id")

    if not corp_id:
        return JsonResponse({"error": "Corporate ID is required"}, status=400)

    try:
        # Retrieve the corporate record as a dict
        corporates = ServiceRegistry().database("corporate", "filter", data={"id": corp_id})

        corporate = corporates[0] if corporates else None

        if not corporate:
            return JsonResponse({"error": "Corporate not found"}, status=404)

        name = corporate.get("name", "Unknown")
        email = corporate.get("email")

        # Delete using a filter instead of instance_id
        ServiceRegistry().database("corporate","delete",corp_id)

        TransactionLogBase.log("CORPORATE_DELETED", user=None, message=f"Corporate '{name}' (ID {corp_id}) deleted",request=request)

        if email:
            NotificationServiceHandler().send_notification([{
                "organisation_id": corp_id,
                "destination": email,
                "message_type": "2",
                "message": f"Dear {name}, your organisation account has been deleted from our system. "
                           f"If this was unexpected, kindly contact support."
            }])

        return JsonResponse({"message": f"Corporate '{name}' deleted successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def approve_corporate(request):
    data, _ = get_clean_data(request)
    corporate_id = data.get("id")
    decision_raw = data.get("approved")

    if corporate_id is None or decision_raw is None:
        return JsonResponse({"error": "Corporate ID and approval decision are required."}, status=400)

    try:
        decision = str(decision_raw).lower() == "true"  # ✅ Ensures boolean

        corporate = Corporate.objects.filter(id=corporate_id).first()
        if not corporate:
            return JsonResponse({"error": "Corporate not found."}, status=404)

        corporate.is_seen = True

        if decision:
            corporate.is_approved = True
            corporate.is_disapproved = False
            corporate.save()

            # ✅ Manually trigger signal (if you use post_save signal normally)
            from OrgAuth.core.signals import create_superadmin_on_approval
            create_superadmin_on_approval(sender=Corporate, instance=corporate, created=False)

            message = "Corporate approved successfully."
        else:
            corporate.is_approved = False
            corporate.is_disapproved = True
            corporate.save()

            NotificationServiceHandler().send_notification([{
                "message_type": "0",
                "organisation_id": corporate.id,
                "destination": corporate.email,
                "message": f"""
                    <h3>Application Update</h3>
                    <p>We regret to inform you that your organisation has not been approved at this time.</p>
                    <p>Thank you for your interest.</p>
                """
            }])
            message = "Corporate disapproved and notified."

        TransactionLogBase.log(
            "CORPORATE_APPROVAL_DECISION",
            user=request.user,
            message=f"Corporate {corporate.name} approval decision: {decision}",
            request=request
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
            request=request
        )

        # Send suspension notification
        NotificationServiceHandler().send_notification([{
            "message_type": "2",
            "organisation_id": str(corporate.id),
            "destination": corporate.email,
            "message": f"""
                <h3>Your account has been suspended</h3>
                <p>Dear {corporate.name},</p>
                <p>We regret to inform you that your corporate account has been suspended.</p>
                <p>If you believe this is a mistake, please contact support.</p>
            """
        }])

        return JsonResponse({"message": "Corporate suspended and notified successfully."})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

from django.urls import path


urlpatterns = [
    path("create/", create_corporate, name="create_corporate"),
    path("list/", list_corporates, name="list_corporates"),
    path("update/", update_corporate, name="update_corporate"),
    path("delete/", delete_corporate, name="delete_corporate"),
    path("approve/", approve_corporate, name="approve_corporate"),
    path("suspend/", suspend_corporate, name="suspend_corporate"),
]