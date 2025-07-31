from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password

from Authentication.models.role import Role
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.decorators import require_authenticated
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry


@csrf_exempt
def create_corporate_user(request):
    data, metadata = get_clean_data(request)
    admin_user = metadata.get("user")

    required_fields = {"username", "email", "role"}
    missing_fields = required_fields - data.keys()
    if missing_fields:
        return JsonResponse({"error": f"Missing required fields: {missing_fields}"}, status=400)

    try:
        # Get CorporateUser for admin from email
        try:
            admin_corp_user = CorporateUser.objects.select_related("corporate", "role").get(email=admin_user.email)
        except CorporateUser.DoesNotExist:
            return JsonResponse({"error": "Authenticated user is not a corporate user."}, status=403)

        # Check if user has role
        if not admin_corp_user.role or admin_corp_user.role.name != "SUPERADMIN":
            return JsonResponse({"error": "You must be a SUPERADMIN to create new users."}, status=403)

        corporate = admin_corp_user.corporate
        data["corporate"] = corporate

        # Get Role instance from ID
        role_id = data.get("role")
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({"error": f"Role with ID {role_id} does not exist"}, status=404)
        data["role"] = role

        # Generate and hash password
        raw_password = get_random_string(length=12)
        data["password"] = make_password(raw_password)

        # Create user through ServiceRegistry
        user_data = ServiceRegistry().database("corporateuser", "create", data=data)

        # Retrieve actual saved CorporateUser instance
        full_user = CorporateUser.objects.select_related("corporate").get(email=user_data["email"])
        corporate = full_user.corporate

        # Log action
        TransactionLogBase.log(
            "CORPORATE_USER_CREATED",
            user=admin_user,
            message=f"User {full_user.username} created",
            request=request
        )

        # Prepare email
        email_body = f"""
            <p>Hello <strong>{full_user.username}</strong>,</p>
            <p>You have been added to the corporate account: <strong>{corporate.name}</strong>.</p>
            <p>Your login credentials are:</p>
            <ul>
                <li>Username: <strong>{full_user.username}</strong></li>
                <li>Password: <strong>{raw_password}</strong></li>
            </ul>
            <p>Please login at <a href="https://yourplatform.com/login">https://yourplatform.com/login</a> and change your password after your first login.</p>
            <p>Regards,<br/>Quidpath Team</p>
        """

        # Send email notification
        NotificationServiceHandler().send_notification(
            notifications=[{
                "message_type": "2",
                "organisation_id": corporate.id,
                "destination": full_user.email,
                "message": email_body,
            }]
        )

        return JsonResponse({
            "message": "User created successfully",
            "id": str(full_user.id),
            "corporate": {
                "id": str(corporate.id),
                "name": corporate.name
            }
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def delete_corporate_user(request):
    data, meta = get_clean_data(request)
    admin_user = meta.get("user")

    user_id = data.get("id")
    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        # Get the acting CorporateUser by email
        acting_user = ServiceRegistry().database("corporateuser", "get", data={"email": admin_user})
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)
        target_user = CorporateUser.objects.select_related("role", "corporate").get(id=user_id)

        if target_user.corporate.id != admin_user.corporateuser.corporate.id:
            return JsonResponse({"error": "User not found or unauthorized"}, status=404)

        if target_user.role.name.upper() == "SUPERADMIN":
            return JsonResponse({"error": "Cannot delete a SUPERADMIN user."}, status=403)

        # Store details for email before deletion
        username = target_user.username
        email = target_user.email
        corporate_id = str(target_user.corporate.id)

        # Delete the user
        target_user.delete()

        # Log the deletion
        TransactionLogBase.log("CORPORATE_USER_DELETED", user=admin_user, message=f"User {username} deleted",request=request)

        # Send email
        if email:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account has been permanently deleted from our corporate platform.</p>
                <p>We’re sorry to see you go. If this was a mistake or you’d like to rejoin, please reach out to your administrator.</p>
                <p>Best regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[{
                        "message_type": "2",
                        "organisation_id": corporate_id,
                        "destination": email,
                        "message": email_body,
                    }]
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
        admin_email = meta.get("user")

        if not admin_email:
            return JsonResponse({"error": "Unauthorized: Email not found in token."}, status=403)

        # Get the admin CorporateUser using their email
        admin_user = ServiceRegistry().database("corporateuser", "get", data={"email": admin_email})
        if not admin_user:
            return JsonResponse({"error": "Admin user not found."}, status=404)

        # If corporate is a model, access id directly
        corporate_id = (
            admin_user["corporate"].id
            if isinstance(admin_user, dict) and hasattr(admin_user.get("corporate"), "id")
            else admin_user.corporate.id
        )

        users = ServiceRegistry().database("corporateuser", "filter", data={"corporate": corporate_id})
        user_list = []
        for cu in users:
            user_list.append({
                "id": cu.get("id") if isinstance(cu, dict) else cu.id,
                "username": cu.get("username") if isinstance(cu, dict) else cu.username,
                "email": cu.get("email") if isinstance(cu, dict) else cu.email,
                "role": (
                    cu["role"]["name"] if isinstance(cu, dict) and isinstance(cu.get("role"), dict)
                    else cu["role"].name if isinstance(cu, dict) and hasattr(cu.get("role"), "name")
                    else cu.role.name if hasattr(cu, "role") and cu.role else None
                ),
                "is_active": cu.get("is_active") if isinstance(cu, dict) else cu.is_active,
            })

        return JsonResponse({"users": user_list}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def get_corporate_id_by_name_or_id(user_obj):
    """Extract corporate ID from user object, handling both name and UUID formats."""
    if not user_obj:
        return None

    # Try different possible structures to get corporate identifier
    corporate_identifier = None

    if isinstance(user_obj, dict):
        # Try direct corporate_id first
        corporate_identifier = user_obj.get("corporate_id")
        if not corporate_identifier:
            # Try nested corporate.id
            corporate = user_obj.get("corporate")
            if isinstance(corporate, dict):
                corporate_identifier = corporate.get("id")
            elif corporate:  # Could be name or ID
                corporate_identifier = corporate
    else:
        # Django model instance
        if hasattr(user_obj, 'corporate_id'):
            corporate_identifier = user_obj.corporate_id
        elif hasattr(user_obj, 'corporate') and user_obj.corporate:
            if hasattr(user_obj.corporate, 'id'):
                corporate_identifier = user_obj.corporate.id
            else:
                corporate_identifier = user_obj.corporate

    if not corporate_identifier:
        return None

    # Check if it's already a valid UUID
    try:
        import uuid
        uuid.UUID(str(corporate_identifier))
        return corporate_identifier  # It's already a UUID
    except (ValueError, TypeError):
        # It's not a UUID, assume it's a name and look it up
        try:
            # Use ServiceRegistry to look up corporate by name
            corporate = ServiceRegistry().database("corporate", "get", data={"name": corporate_identifier})
            if corporate:
                return get_attr(corporate, "id")
            return None
        except Exception as e:
            print(f"Error looking up corporate by name '{corporate_identifier}': {e}")
            return None


def get_attr(obj, attr_path, default=None):
    """Safely get nested attributes from an object or dictionary."""
    if obj is None:
        return default

    attrs = attr_path.split('.')
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
        # Get the acting CorporateUser by email
        acting_user = ServiceRegistry().database("corporateuser", "get", data={"email": email})
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        # Get the target user to update
        target_user = ServiceRegistry().database("corporateuser", "get", data={"id": user_id})
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        # ✅ Get role name safely - handle both dict and model formats
        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = role_obj.get("name") if isinstance(role_obj, dict) else getattr(role_obj, 'name', None)
        else:
            role_name = acting_user.role.name if acting_user.role else None

        if (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse({"error": "Only SUPERADMIN can update users."}, status=403)

        # ✅ Get corporate IDs using the helper function (converts name to UUID if needed)
        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        # More specific error messages
        if not acting_corp_id:
            return JsonResponse({"error": "Acting user has no valid corporate association."}, status=400)

        if not target_corp_id:
            return JsonResponse({"error": "Target user has no valid corporate association."}, status=400)

        if str(acting_corp_id) != str(target_corp_id):
            return JsonResponse({
                "error": f"Users belong to different organizations. Cannot update."
            }, status=403)

        # Optional role update
        role_id = data.get("role")
        if role_id:
            try:
                data["role"] = Role.objects.get(id=role_id)
            except Role.DoesNotExist:
                return JsonResponse({"error": "Invalid role ID provided."}, status=400)

        # Get target user ID safely
        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        # Update the user
        ServiceRegistry().database("corporateuser", "update", str(target_user_id), data=data)

        # Log
        username = get_attr(target_user, 'username') or 'Unknown'
        TransactionLogBase.log(
            "CORPORATE_USER_UPDATED",
            user=email,
            message=f"User {username} updated",
            request=request
        )

        # ✅ Send email notification with proper validation
        target_email = get_attr(target_user, "email")

        if target_email and target_corp_id:
            username = get_attr(target_user, 'username') or 'User'
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account credentials have been updated successfully.</p>
                <p>Kindly contact your admin for the new credentials or Role change.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """

            try:
                NotificationServiceHandler().send_notification(
                    notifications=[{
                        "message_type": "2",
                        "organisation_id": str(target_corp_id),  # Now guaranteed to be a valid UUID
                        "destination": target_email,
                        "message": email_body,
                    }]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")
                # Don't fail the whole operation if email fails

        return JsonResponse({"message": "User updated successfully."})

    except Exception as e:
        print(f"Error in update_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def suspend_corporate_user(request):
    data, meta = get_clean_data(request)
    email = meta.get("user")  # Extract the acting user's email from token metadata

    user_id = data.get("id")
    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        # Get the acting CorporateUser by email
        acting_user = ServiceRegistry().database("corporateuser", "get", data={"email": email})
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        # Get the target user to suspend
        target_user = ServiceRegistry().database("corporateuser", "get", data={"id": user_id})
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        # ✅ Check if acting user is admin or superadmin
        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = role_obj.get("name") if isinstance(role_obj, dict) else getattr(role_obj, 'name', None)
            is_admin = acting_user.get("is_admin", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_admin = getattr(acting_user, 'is_admin', False)

        # Check authorization - must be admin or superadmin
        if not is_admin and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse({"error": "Only admins or superadmins can suspend users."}, status=403)

        # ✅ Get corporate IDs using the helper function (converts name to UUID if needed)
        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        # Validate corporate associations
        if not acting_corp_id:
            return JsonResponse({"error": "Acting user has no valid corporate association."}, status=400)

        if not target_corp_id:
            return JsonResponse({"error": "Target user has no valid corporate association."}, status=400)

        if str(acting_corp_id) != str(target_corp_id):
            return JsonResponse({"error": "User does not belong to your corporate."}, status=403)

        # ✅ Check if target user is SUPERADMIN
        if isinstance(target_user, dict):
            target_role_obj = target_user.get("role", {})
            target_role_name = target_role_obj.get("name") if isinstance(target_role_obj, dict) else getattr(
                target_role_obj, 'name', None)
        else:
            target_role_name = target_user.role.name if target_user.role else None

        if (target_role_name or "").upper() == "SUPERADMIN":
            return JsonResponse({"error": "Cannot suspend a SUPERADMIN."}, status=403)

        # Get target user ID safely
        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        # ✅ Suspend the user by setting is_active to False
        update_data = {"is_active": False}
        ServiceRegistry().database("corporateuser", "update", str(target_user_id), data=update_data)

        # Get username for logging and email
        username = get_attr(target_user, 'username') or 'Unknown'

        # Log the suspension
        TransactionLogBase.log(
            "CORPORATE_USER_SUSPENDED",
            user=email,
            message=f"User {username} suspended",
            request=request
        )

        # ✅ Send email notification about account suspension
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
                    notifications=[{
                        "message_type": "2",
                        "organisation_id": str(target_corp_id),  # Now guaranteed to be a valid UUID
                        "destination": target_email,
                        "message": email_body,
                    }]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")
                # Don't fail the whole operation if email fails

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
        # Get acting CorporateUser
        acting_user = ServiceRegistry().database("corporateuser", "get", data={"email": email})
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        # Get target user
        target_user = ServiceRegistry().database("corporateuser", "get", data={"id": user_id})
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        # Validate acting user
        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = role_obj.get("name") if isinstance(role_obj, dict) else getattr(role_obj, 'name', None)
            is_admin = acting_user.get("is_admin", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_admin = getattr(acting_user, 'is_admin', False)

        if not is_admin and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse({"error": "Only admins or superadmins can unsuspend users."}, status=403)

        acting_corp_id = get_corporate_id_by_name_or_id(acting_user)
        target_corp_id = get_corporate_id_by_name_or_id(target_user)

        if str(acting_corp_id) != str(target_corp_id):
            return JsonResponse({"error": "User does not belong to your corporate."}, status=403)

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        # Reactivate the user
        update_data = {"is_active": True}
        ServiceRegistry().database("corporateuser", "update", str(target_user_id), data=update_data)

        # Log
        username = get_attr(target_user, "username") or "Unknown"
        TransactionLogBase.log("CORPORATE_USER_UNSUSPENDED", user=email, message=f"User {username} unsuspended",request=request)

        # Send email
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
                    notifications=[{
                        "message_type": "2",
                        "organisation_id": str(target_corp_id),
                        "destination": target_email,
                        "message": email_body,
                    }]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": f"User {username} unsuspended successfully."})

    except Exception as e:
        print(f"Error in unsuspend_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)