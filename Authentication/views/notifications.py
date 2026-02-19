from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q

from Authentication.models.logbase import Notification, NotificationType, State
from quidpath_backend.core.Services.organisation_service import CorporateService


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Get notifications for the authenticated user.
    Query params:
    - is_read: filter by read status (true/false)
    - notification_type: filter by type (EMAIL, SMS)
    - page: page number
    - page_size: items per page
    """
    try:
        user = request.user
        
        # Get user's corporate/organization
        corporate = CorporateService().get_or_default(user.corporate_id)
        
        # Base queryset - notifications for user's organization
        queryset = Notification.objects.filter(
            Q(destination=user.email) | Q(corporate=corporate)
        ).select_related("notification_type", "state").order_by("-created_at")
        
        # Apply filters
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            is_read_bool = is_read.lower() == "true"
            queryset = queryset.filter(is_read=is_read_bool)
        
        notification_type = request.query_params.get("notification_type")
        if notification_type:
            queryset = queryset.filter(notification_type__name=notification_type)
        
        # Paginate
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        # Serialize
        notifications_data = [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "destination": n.destination,
                "notification_type": n.notification_type.name,
                "state": n.state.name,
                "is_read": getattr(n, "is_read", False),
                "created_at": n.created_at.isoformat(),
                "updated_at": n.updated_at.isoformat(),
            }
            for n in page
        ]
        
        return paginator.get_paginated_response(notifications_data)
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read."""
    try:
        user = request.user
        
        notification = Notification.objects.filter(
            id=notification_id,
            destination=user.email,
        ).first()
        
        if not notification:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Add is_read field if it doesn't exist (for backward compatibility)
        if not hasattr(notification, "is_read"):
            # You may need to add this field to the model
            pass
        
        notification.is_read = True
        notification.save()
        
        return Response(
            {"message": "Notification marked as read"},
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the authenticated user."""
    try:
        user = request.user
        
        updated_count = Notification.objects.filter(
            destination=user.email,
            is_read=False,
        ).update(is_read=True)
        
        return Response(
            {
                "message": f"{updated_count} notifications marked as read",
                "count": updated_count,
            },
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get count of unread notifications for the authenticated user."""
    try:
        user = request.user
        
        count = Notification.objects.filter(
            destination=user.email,
            is_read=False,
        ).count()
        
        return Response(
            {"unread_count": count},
            status=status.HTTP_200_OK,
        )
    
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
