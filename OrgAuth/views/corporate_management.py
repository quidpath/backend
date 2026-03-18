"""
Additional corporate management functions (unsuspend, ban, unban, edit).
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.decorators import require_superuser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
@require_superuser
def unsuspend_corporate(request):
    """Unsuspend (activate) a corporate organization."""
    data, metadata = get_clean_data(request)
    corporate_id = data.get("id")

    if not corporate_id:
        return JsonResponse({"error": "Corporate ID is required"}, status=400)

    try:
        corporate = ServiceRegistry().database(
            "corporate", "get", data={"id": corporate_id}
        )
        if not corporate:
            return JsonResponse({"error": "Corporate not found"}, status=404)

        # Update to active
        ServiceRegistry().database(
            "corporate", "update", str(corporate_id), data={"is_active": True}
        )

        corporate_name = (
            corporate.get("name") if isinstance(corporate, dict) else corporate.name
        )

        TransactionLogBase.log(
            "CORPORATE_UNSUSPENDED",
            user=metadata.get("user"),
            message=f"Corporate {corporate_name} unsuspended",
            request=request,
        )

        # Send notification email
        email = corporate.get("email") if isinstance(corporate, dict) else corporate.email
        if email:
            email_body = f"""
                <p>Hello <strong>{corporate_name}</strong>,</p>
                <p>Your organization has been reactivated. You can now access all platform features.</p>
                <p>If you have any questions, please contact support.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(corporate_id),
                            "destination": email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "Corporate unsuspended successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_superuser
def ban_corporate(request):
    """Ban a corporate organization."""
    data, metadata = get_clean_data(request)
    corporate_id = data.get("id")

    if not corporate_id:
        return JsonResponse({"error": "Corporate ID is required"}, status=400)

    try:
        corporate = ServiceRegistry().database(
            "corporate", "get", data={"id": corporate_id}
        )
        if not corporate:
            return JsonResponse({"error": "Corporate not found"}, status=404)

        # Ban corporate (set is_banned=True and is_active=False)
        ServiceRegistry().database(
            "corporate",
            "update",
            str(corporate_id),
            data={"is_banned": True, "is_active": False},
        )

        corporate_name = (
            corporate.get("name") if isinstance(corporate, dict) else corporate.name
        )

        TransactionLogBase.log(
            "CORPORATE_BANNED",
            user=metadata.get("user"),
            message=f"Corporate {corporate_name} banned",
            request=request,
        )

        # Send notification email
        email = corporate.get("email") if isinstance(corporate, dict) else corporate.email
        if email:
            email_body = f"""
                <p>Hello <strong>{corporate_name}</strong>,</p>
                <p>Your organization has been banned from the platform.</p>
                <p>If you believe this is an error, please contact support immediately.</p>
                <p>Regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(corporate_id),
                            "destination": email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "Corporate banned successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_superuser
def unban_corporate(request):
    """Unban a corporate organization."""
    data, metadata = get_clean_data(request)
    corporate_id = data.get("id")

    if not corporate_id:
        return JsonResponse({"error": "Corporate ID is required"}, status=400)

    try:
        corporate = ServiceRegistry().database(
            "corporate", "get", data={"id": corporate_id}
        )
        if not corporate:
            return JsonResponse({"error": "Corporate not found"}, status=404)

        # Unban corporate (set is_banned=False and is_active=True)
        ServiceRegistry().database(
            "corporate",
            "update",
            str(corporate_id),
            data={"is_banned": False, "is_active": True},
        )

        corporate_name = (
            corporate.get("name") if isinstance(corporate, dict) else corporate.name
        )

        TransactionLogBase.log(
            "CORPORATE_UNBANNED",
            user=metadata.get("user"),
            message=f"Corporate {corporate_name} unbanned",
            request=request,
        )

        # Send notification email
        email = corporate.get("email") if isinstance(corporate, dict) else corporate.email
        if email:
            email_body = f"""
                <p>Hello <strong>{corporate_name}</strong>,</p>
                <p>Your organization has been unbanned. You can now access the platform again.</p>
                <p>Please log in at <a href="https://quidpath.com/SignIn">https://quidpath.com/SignIn</a></p>
                <p>Regards,<br/>Quidpath Team</p>
            """
            try:
                NotificationServiceHandler().send_notification(
                    notifications=[
                        {
                            "message_type": "2",
                            "organisation_id": str(corporate_id),
                            "destination": email,
                            "message": email_body,
                        }
                    ]
                )
            except Exception as email_error:
                print(f"Email notification failed: {email_error}")

        return JsonResponse({"message": "Corporate unbanned successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
