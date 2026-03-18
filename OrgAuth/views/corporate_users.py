import base64
import json
import uuid

from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt

from Authentication.models.role import Role
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.decorators import require_authenticated
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


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
def get_corporate_user(request):
    try:
        # Explicitly parse the JSON body
        try:
            body = json.loads(request.body.decode("utf-8"))
            user_id = body.get("id")
            print(f"Parsed request body: {body}, user_id: {user_id}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse({"error": "Invalid JSON in request body."}, status=400)

        # Fallback to get_clean_data
        data, meta = get_clean_data(request)
        email = meta.get("user")
        if not user_id:
            user_id = data.get("id")
            print(f"Fallback to get_clean_data, user_id: {user_id}")

        if not user_id:
            print("User ID not found in request")
            return JsonResponse({"error": "User ID is required."}, status=400)

        print(f"Fetching user with ID: {user_id}, acting user email: {email}")

        acting_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": email}
        )
        if not acting_user:
            print(f"Acting user not found for email: {email}")
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            print(f"Target user not found for ID: {user_id}")
            return JsonResponse({"error": "Target user not found."}, status=404)

        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        if not acting_corp_id:
            print(f"Acting user has no valid corporate association: {acting_user}")
            return JsonResponse(
                {"error": "Acting user has no valid corporate association."}, status=400
            )

        if not target_corp_id:
            print(f"Target user has no valid corporate association: {target_user}")
            return JsonResponse(
                {"error": "Target user has no valid corporate association."}, status=400
            )

        acting_user_id = get_attr(acting_user, "id")
        if str(acting_corp_id) != str(target_corp_id) and acting_user_id != user_id:
            print(
                f"Unauthorized access: acting_corp_id={acting_corp_id}, target_corp_id={target_corp_id}, acting_user_id={acting_user_id}, user_id={user_id}"
            )
            return JsonResponse(
                {"error": "Unauthorized: Cannot access user from different corporate."},
                status=403,
            )

        if isinstance(target_user, dict):
            role = target_user.get("role", {})
            role_data = (
                {"id": role.get("id"), "name": role.get("name")}
                if isinstance(role, dict)
                else {"id": role.id, "name": role.name} if role else None
            )
            corporate = target_user.get("corporate", {})
            corporate_data = (
                {"id": corporate.get("id"), "name": corporate.get("name")}
                if isinstance(corporate, dict)
                else {"id": corporate.id, "name": corporate.name} if corporate else None
            )
        else:
            role_data = (
                {"id": target_user.role.id, "name": target_user.role.name}
                if target_user.role
                else None
            )
            corporate_data = (
                {"id": target_user.corporate.id, "name": target_user.corporate.name}
                if target_user.corporate
                else None
            )

        user_data = {
            "id": get_attr(target_user, "id"),
            "username": get_attr(target_user, "username"),
            "email": get_attr(target_user, "email"),
            "phone_number": get_attr(target_user, "phone_number"),
            "country": get_attr(target_user, "country"),
            "state": get_attr(target_user, "state"),
            "city": get_attr(target_user, "city"),
            "address": get_attr(target_user, "address"),
            "zip_code": get_attr(target_user, "zip_code"),
            "profilePhoto": (
                get_attr(target_user, "profilePhoto.url")
                if get_attr(target_user, "profilePhoto")
                else None
            ),
            "email_verified": get_attr(target_user, "email_verified", True),
            "role": role_data,
            "corporate": corporate_data,
            "is_active": get_attr(target_user, "is_active", True),
        }

        print(f"Successfully fetched user data: {user_data}")

        TransactionLogBase.log(
            "CORPORATE_USER_FETCHED",
            user=email,
            message=f"Fetched user {user_data['username']}",
            request=request,
        )

        return JsonResponse({"user": user_data}, status=200)

    except Exception as e:
        print(f"Error in get_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


# Existing views (unchanged, included for completeness)
@csrf_exempt
def create_corporate_user(request):
    data, metadata = get_clean_data(request)
    admin_user = metadata.get("user")

    required_fields = {"username", "email", "role"}
    missing_fields = required_fields - data.keys()
    if missing_fields:
        return JsonResponse(
            {"error": f"Missing required fields: {missing_fields}"}, status=400
        )

    try:
        try:
            admin_corp_user = CorporateUser.objects.select_related(
                "corporate", "role"
            ).get(email=admin_user.email)
        except CorporateUser.DoesNotExist:
            return JsonResponse(
                {"error": "Authenticated user is not a corporate user."}, status=403
            )

        if not admin_corp_user.role or admin_corp_user.role.name != "SUPERADMIN":
            return JsonResponse(
                {"error": "You must be a SUPERADMIN to create new users."}, status=403
            )

        corporate = admin_corp_user.corporate
        data["corporate"] = corporate

        role_id = data.get("role")
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse(
                {"error": f"Role with ID {role_id} does not exist"}, status=404
            )
        data["role"] = role

        profile_photo_base64 = data.pop("profilePhoto", None)
        if profile_photo_base64:
            image_file = process_base64_image(
                profile_photo_base64, f"user_{data['username']}"
            )
            if image_file:
                data["profilePhoto"] = image_file
            else:
                return JsonResponse({"error": "Invalid image format"}, status=400)

        raw_password = get_random_string(length=12)
        data["password"] = make_password(raw_password)

        user_data = ServiceRegistry().database("corporateuser", "create", data=data)

        full_user = CorporateUser.objects.select_related("corporate").get(
            email=user_data["email"]
        )
        corporate = full_user.corporate

        TransactionLogBase.log(
            "CORPORATE_USER_CREATED",
            user=admin_user,
            message=f"User {full_user.username} created",
            request=request,
        )

        email_body = f"""
            <p>Hello <strong>{full_user.username}</strong>,</p>
            <p>You have been added to the corporate account: <strong>{corporate.name}</strong>.</p>
            <p>Your login credentials are:</p>
            <ul>
                <li>Username: <strong>{full_user.username}</strong></li>
                <li>Password: <strong>{raw_password}</strong></li>
            </ul>
            <p>Please login at <a href="https://quidpath.com/SignIn">https://quidpath.com/SignIn</a> and change your password after your first login.</p>
            <p>Regards,<br/>Quidpath Team</p>
        """

        NotificationServiceHandler().send_notification(
            notifications=[
                {
                    "message_type": "2",
                    "organisation_id": corporate.id,
                    "destination": full_user.email,
                    "message": email_body,
                }
            ]
        )

        return JsonResponse(
            {
                "message": "User created successfully",
                "id": str(full_user.id),
                "corporate": {"id": str(corporate.id), "name": corporate.name},
            }
        )

    except Exception as e:
        print(f"Error creating corporate user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def delete_corporate_user(request):
    data, meta = get_clean_data(request)
    admin_user = meta.get("user")

    user_id = data.get("id")
    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        acting_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": admin_user}
        )
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)
        target_user = CorporateUser.objects.select_related("role", "corporate").get(
            id=user_id
        )

        if target_user.corporate.id != admin_user.corporateuser.corporate.id:
            return JsonResponse({"error": "User not found or unauthorized"}, status=404)

        if target_user.role.name.upper() == "SUPERADMIN":
            return JsonResponse(
                {"error": "Cannot delete a SUPERADMIN user."}, status=403
            )

        username = target_user.username
        email = target_user.email
        corporate_id = str(target_user.corporate.id)

        target_user.delete()

        TransactionLogBase.log(
            "CORPORATE_USER_DELETED",
            user=admin_user,
            message=f"User {username} deleted",
            request=request,
        )

        if email:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account has been permanently deleted from our corporate platform.</p>
                <p>We’re sorry to see you go. If this was a mistake or you’d like to rejoin, please reach out to your administrator.</p>
                <p>Best regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": corporate_id,
                            "destination": email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "User deleted successfully"})

    except CorporateUser.DoesNotExist:
        return JsonResponse({"error": "User not found."}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def list_corporate_users(request):
    try:
        data, meta = get_clean_data(request)
        admin_user_obj = meta.get("user")
        admin_email = (
            getattr(admin_user_obj, "email", None)
            if admin_user_obj and not isinstance(admin_user_obj, dict)
            else (admin_user_obj.get("email") if isinstance(admin_user_obj, dict) else None)
        )

        if not admin_email:
            return JsonResponse(
                {"error": "Unauthorized: Email not found in token."}, status=403
            )

        admin_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": admin_email}
        )
        if not admin_user:
            return JsonResponse({"error": "Admin user not found."}, status=404)

        corporate_id = (
            admin_user["corporate"].id
            if isinstance(admin_user, dict)
            and hasattr(admin_user.get("corporate"), "id")
            else admin_user.corporate.id
        )

        users = ServiceRegistry().database(
            "corporateuser", "filter", data={"corporate": corporate_id}
        )
        user_list = []
        for cu in users:
            user_list.append(
                {
                    "id": cu.get("id") if isinstance(cu, dict) else cu.id,
                    "username": (
                        cu.get("username") if isinstance(cu, dict) else cu.username
                    ),
                    "email": cu.get("email") if isinstance(cu, dict) else cu.email,
                    "role": (
                        cu["role"]["name"]
                        if isinstance(cu, dict) and isinstance(cu.get("role"), dict)
                        else (
                            cu["role"].name
                            if isinstance(cu, dict) and hasattr(cu.get("role"), "name")
                            else (
                                cu.role.name
                                if hasattr(cu, "role") and cu.role
                                else None
                            )
                        )
                    ),
                    "is_active": (
                        cu.get("is_active") if isinstance(cu, dict) else cu.is_active
                    ),
                }
            )

        return JsonResponse({"users": user_list}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def get_corporate_id_by_name_or_id(user_obj):
    if not user_obj:
        return None
    corporate_identifier = None
    if isinstance(user_obj, dict):
        corporate_identifier = user_obj.get("corporate_id")
        if not corporate_identifier:
            corporate = user_obj.get("corporate")
            if isinstance(corporate, dict):
                corporate_identifier = corporate.get("id")
            elif corporate:
                corporate_identifier = corporate
    else:
        if hasattr(user_obj, "corporate_id"):
            corporate_identifier = user_obj.corporate_id
        elif hasattr(user_obj, "corporate") and user_obj.corporate:
            if hasattr(user_obj.corporate, "id"):
                corporate_identifier = user_obj.corporate.id
            else:
                corporate_identifier = user_obj.corporate
    if not corporate_identifier:
        return None
    try:
        import uuid

        uuid.UUID(str(corporate_identifier))
        return corporate_identifier
    except (ValueError, TypeError):
        try:
            corporate = ServiceRegistry().database(
                "corporate", "get", data={"name": corporate_identifier}
            )
            if corporate:
                return get_attr(corporate, "id")
            return None
        except Exception as e:
            print(f"Error looking up corporate by name '{corporate_identifier}': {e}")
            return None


def get_attr(obj, attr_path, default=None):
    if obj is None:
        return default
    attrs = attr_path.split(".")
    current = obj
    for attr in attrs:
        if isinstance(current, dict):
            current = current.get(attr)
        elif hasattr(current, attr):
            current = getattr(current, attr)
        else:
            return default
        if current is None:
            return default
    return current


@csrf_exempt
def update_corporate_user(request):
    data, meta = get_clean_data(request)
    email = meta.get("user")

    user_id = data.get("id")
    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        acting_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": email}
        )
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = (
                role_obj.get("name")
                if isinstance(role_obj, dict)
                else getattr(role_obj, "name", None)
            )
        else:
            role_name = acting_user.role.name if acting_user.role else None

        acting_user_id = get_attr(acting_user, "id")
        if (role_name or "").upper() != "SUPERADMIN" and acting_user_id != user_id:
            return JsonResponse(
                {
                    "error": "Only SUPERADMIN or the user themselves can update user data."
                },
                status=403,
            )

        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        if not acting_corp_id:
            return JsonResponse(
                {"error": "Acting user has no valid corporate association."}, status=400
            )

        if not target_corp_id:
            return JsonResponse(
                {"error": "Target user has no valid corporate association."}, status=400
            )

        if str(acting_corp_id) != str(target_corp_id):
            return JsonResponse(
                {"error": "Users belong to different organizations. Cannot update."},
                status=403,
            )

        profile_photo_base64 = data.pop("profilePhoto", None)
        if profile_photo_base64:
            image_file = process_base64_image(
                profile_photo_base64, f"user_{data.get('username', 'user')}"
            )
            if image_file:
                data["profilePhoto"] = image_file
            else:
                return JsonResponse({"error": "Invalid image format"}, status=400)

        if role_name and role_name.upper() != "SUPERADMIN":
            data.pop("username", None)
            data.pop("email", None)
            data.pop("role", None)
            data.pop("email_verified", None)

        role_id = data.get("role")
        if role_id:
            try:
                data["role"] = Role.objects.get(id=role_id)
            except Role.DoesNotExist:
                return JsonResponse({"error": "Invalid role ID provided."}, status=400)

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        ServiceRegistry().database(
            "corporateuser", "update", str(target_user_id), data=data
        )

        username = get_attr(target_user, "username") or "Unknown"
        TransactionLogBase.log(
            "CORPORATE_USER_UPDATED",
            user=email,
            message=f"User {username} updated",
            request=request,
        )

        target_email = get_attr(target_user, "email")
        if target_email and target_corp_id:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account details have been updated successfully.</p>
                <p>If you did not request this change, please contact your administrator.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(target_corp_id),
                            "destination": target_email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "User updated successfully."})

    except Exception as e:
        print(f"Error in update_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def suspend_corporate_user(request):
    data, meta = get_clean_data(request)
    email = meta.get("user")

    user_id = data.get("id")
    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        acting_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": email}
        )
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = (
                role_obj.get("name")
                if isinstance(role_obj, dict)
                else getattr(role_obj, "name", None)
            )
            is_admin = acting_user.get("is_admin", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_admin = getattr(acting_user, "is_admin", False)

        if not is_admin and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse(
                {"error": "Only admins or superadmins can suspend users."}, status=403
            )

        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        if not acting_corp_id:
            return JsonResponse(
                {"error": "Acting user has no valid corporate association."}, status=400
            )

        if not target_corp_id:
            return JsonResponse(
                {"error": "Target user has no valid corporate association."}, status=400
            )

        if str(acting_corp_id) != str(target_corp_id):
            return JsonResponse(
                {"error": "User does not belong to your corporate."}, status=403
            )

        if isinstance(target_user, dict):
            target_role_obj = target_user.get("role", {})
            target_role_name = (
                target_role_obj.get("name")
                if isinstance(target_role_obj, dict)
                else getattr(target_role_obj, "name", None)
            )
        else:
            target_role_name = target_user.role.name if target_user.role else None

        if (target_role_name or "").upper() == "SUPERADMIN":
            return JsonResponse({"error": "Cannot suspend a SUPERADMIN."}, status=403)

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        update_data = {"is_active": False}
        ServiceRegistry().database(
            "corporateuser", "update", str(target_user_id), data=update_data
        )

        username = get_attr(target_user, "username") or "Unknown"
        TransactionLogBase.log(
            "CORPORATE_USER_SUSPENDED",
            user=email,
            message=f"User {username} suspended",
            request=request,
        )

        target_email = get_attr(target_user, "email")
        if target_email and target_corp_id:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account has been suspended by your administrator.</p>
                <p>If you believe this is an error, please contact your system administrator.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(target_corp_id),
                            "destination": target_email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": f"User {username} suspended successfully."})

    except Exception as e:
        print(f"Error in suspend_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def unsuspend_corporate_user(request):
    data, meta = get_clean_data(request)
    email = meta.get("user")

    user_id = data.get("id")
    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        acting_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": email}
        )
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = (
                role_obj.get("name")
                if isinstance(role_obj, dict)
                else getattr(role_obj, "name", None)
            )
            is_admin = acting_user.get("is_admin", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_admin = getattr(acting_user, "is_admin", False)

        if not is_admin and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse(
                {"error": "Only admins or superadmins can unsuspend users."}, status=403
            )

        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        if not acting_corp_id:
            return JsonResponse(
                {"error": "Acting user has no valid corporate association."}, status=400
            )

        if not target_corp_id:
            return JsonResponse(
                {"error": "Target user has no valid corporate association."}, status=400
            )

        if str(acting_corp_id) != str(target_corp_id):
            return JsonResponse(
                {"error": "User does not belong to your corporate."}, status=403
            )

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        update_data = {"is_active": True}
        ServiceRegistry().database(
            "corporateuser", "update", str(target_user_id), data=update_data
        )

        username = get_attr(target_user, "username") or "Unknown"
        TransactionLogBase.log(
            "CORPORATE_USER_UNSUSPENDED",
            user=email,
            message=f"User {username} unsuspended",
            request=request,
        )

        target_email = get_attr(target_user, "email")
        if target_email and target_corp_id:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account has been reactivated. You can now log in and continue using the platform.</p>
                <p>If you experience any issues, please contact your administrator.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(target_corp_id),
                            "destination": target_email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": f"User {username} unsuspended successfully."})

    except Exception as e:
        print(f"Error in unsuspend_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def list_roles(request):
    try:
        _, meta = get_clean_data(request)
        acting_user = meta.get("user")

        roles = (
            Role.objects.exclude(name__iexact="SUPERUSER")
            .exclude(name__iexact="SUPERADMIN")
            .values("id", "name")
        )
        role_list = list(roles)

        if acting_user:
            TransactionLogBase.log(
                "ROLES_FETCHED",
                user=acting_user,
                message=f"Fetched {len(role_list)} roles (excluding SUPERUSER & SUPERADMIN)",
                request=request,
            )

        return JsonResponse({"roles": role_list}, status=200)

    except Exception as e:
        print(f"Error in list_roles: {e}")
        return JsonResponse({"error": str(e)}, status=400)
