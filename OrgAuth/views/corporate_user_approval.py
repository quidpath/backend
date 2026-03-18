"""
Corporate user approval and ban functionality.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def get_attr(obj, attr_path, default=None):
    """Helper to get nested attributes from dict or object."""
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
def approve_corporate_user(request):
    """Approve or reject a corporate user (superuser only)."""
    data, meta = get_clean_data(request)
    email = meta.get("user")

    user_id = data.get("id")
    approved = data.get("approved", True)

    if not user_id:
        return JsonResponse({"error": "User ID is required."}, status=400)

    try:
        acting_user = ServiceRegistry().database(
            "corporateuser", "get", data={"email": email}
        )
        if not acting_user:
            return JsonResponse({"error": "Authenticated user not found."}, status=404)

        # Check if acting user is superuser or superadmin
        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = (
                role_obj.get("name")
                if isinstance(role_obj, dict)
                else getattr(role_obj, "name", None)
            )
            is_superuser = acting_user.get("is_superuser", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_superuser = getattr(acting_user, "is_superuser", False)

        if not is_superuser and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse(
                {"error": "Only superusers or superadmins can approve users."},
                status=403,
            )

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        # Update approval status
        update_data = {"is_approved": approved}
        ServiceRegistry().database(
            "corporateuser", "update", str(target_user_id), data=update_data
        )

        username = get_attr(target_user, "username") or "Unknown"
        action = "approved" if approved else "rejected"

        TransactionLogBase.log(
            f"CORPORATE_USER_{action.upper()}",
            user=email,
            message=f"User {username} {action}",
            request=request,
        )

        # Send notification email
        target_email = get_attr(target_user, "email")
        corporate_id = get_attr(target_user, "corporate.id")

        if target_email and corporate_id:
            if approved:
                email_body = f"""
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>Your account has been approved! You can now access all features of the platform.</p>
                    <p>Please log in at <a href="https://quidpath.com/SignIn">https://quidpath.com/SignIn</a></p>
                    <p>Regards,<br/>Quidpath Team</p>
                """
            else:
                email_body = f"""
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>Unfortunately, your account registration has been rejected.</p>
                    <p>If you believe this is an error, please contact your administrator.</p>
                    <p>Regards,<br/>Quidpath Team</p>
                """

            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(corporate_id),
                            "destination": target_email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": f"User {action} successfully."})

    except Exception as e:
        print(f"Error in approve_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def ban_corporate_user(request):
    """Ban a corporate user (superuser only)."""
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

        # Check if acting user is superuser or superadmin
        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = (
                role_obj.get("name")
                if isinstance(role_obj, dict)
                else getattr(role_obj, "name", None)
            )
            is_superuser = acting_user.get("is_superuser", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_superuser = getattr(acting_user, "is_superuser", False)

        if not is_superuser and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse(
                {"error": "Only superusers or superadmins can ban users."}, status=403
            )

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        # Ban user (set is_banned=True and is_active=False)
        update_data = {"is_banned": True, "is_active": False}
        ServiceRegistry().database(
            "corporateuser", "update", str(target_user_id), data=update_data
        )

        username = get_attr(target_user, "username") or "Unknown"

        TransactionLogBase.log(
            "CORPORATE_USER_BANNED",
            user=email,
            message=f"User {username} banned",
            request=request,
        )

        # Send notification email
        target_email = get_attr(target_user, "email")
        corporate_id = get_attr(target_user, "corporate.id")

        if target_email and corporate_id:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account has been banned from the platform.</p>
                <p>If you believe this is an error, please contact your administrator.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """

            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(corporate_id),
                            "destination": target_email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "User banned successfully."})

    except Exception as e:
        print(f"Error in ban_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def unban_corporate_user(request):
    """Unban a corporate user (superuser only)."""
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

        # Check if acting user is superuser or superadmin
        if isinstance(acting_user, dict):
            role_obj = acting_user.get("role", {})
            role_name = (
                role_obj.get("name")
                if isinstance(role_obj, dict)
                else getattr(role_obj, "name", None)
            )
            is_superuser = acting_user.get("is_superuser", False)
        else:
            role_name = acting_user.role.name if acting_user.role else None
            is_superuser = getattr(acting_user, "is_superuser", False)

        if not is_superuser and (role_name or "").upper() != "SUPERADMIN":
            return JsonResponse(
                {"error": "Only superusers or superadmins can unban users."}, status=403
            )

        target_user = ServiceRegistry().database(
            "corporateuser", "get", data={"id": user_id}
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found."}, status=404)

        target_user_id = get_attr(target_user, "id")
        if not target_user_id:
            return JsonResponse({"error": "Target user ID not found."}, status=400)

        # Unban user (set is_banned=False and is_active=True)
        update_data = {"is_banned": False, "is_active": True}
        ServiceRegistry().database(
            "corporateuser", "update", str(target_user_id), data=update_data
        )

        username = get_attr(target_user, "username") or "Unknown"

        TransactionLogBase.log(
            "CORPORATE_USER_UNBANNED",
            user=email,
            message=f"User {username} unbanned",
            request=request,
        )

        # Send notification email
        target_email = get_attr(target_user, "email")
        corporate_id = get_attr(target_user, "corporate.id")

        if target_email and corporate_id:
            email_body = f"""
                <p>Hello <strong>{username}</strong>,</p>
                <p>Your account has been unbanned. You can now access the platform again.</p>
                <p>Please log in at <a href="https://quidpath.com/SignIn">https://quidpath.com/SignIn</a></p>
                <p>Regards,<br/>Quidpath Team</p>
            """

            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(corporate_id),
                            "destination": target_email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "User unbanned successfully."})

    except Exception as e:
        print(f"Error in unban_corporate_user: {e}")
        return JsonResponse({"error": str(e)}, status=400)
