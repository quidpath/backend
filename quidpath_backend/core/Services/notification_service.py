from Authentication.models.logbase import (Notification, NotificationType,
                                           Transaction)
from .state_service import StateService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class NotificationTypeService:
    """Manage NotificationType model."""

    def get_or_create_type(self, name: str) -> NotificationType:
        """
        Get or create a NotificationType by name.
        Works with existing database structure where:
        - id=1, name=USSD
        - id=2, name=EMAIL
        """
        try:
            # Try to get by name (name is unique)
            obj = NotificationType.objects.get(name=name)
            return obj
        except NotificationType.DoesNotExist:
            # If not found, create with auto-incrementing ID
            obj = NotificationType.objects.create(
                name=name,
                description=f"{name} notification"
            )
            return obj

    def get_email_type(self) -> NotificationType:
        """Get EMAIL notification type (id=2 in your database)"""
        return self.get_or_create_type("EMAIL")

    def get_ussd_type(self) -> NotificationType:
        """Get USSD notification type (id=1 in your database)"""
        return self.get_or_create_type("USSD")


class NotificationService:
    """Manage Notification model."""

    def __init__(self):
        self.notification_type_service = NotificationTypeService()

    def create_notification(
        self, corporate, title, destination, message, notification_type, state
    ):
        notification = Notification.objects.create(
            title=title,
            message=message,
            destination=destination,
            notification_type=notification_type,
            state=state,
            corporate=corporate,
        )

        # Send real-time notification via WebSocket
        self.send_realtime_notification(notification)

        return notification

    def create_email_notification(
        self, corporate, title, destination, message, state
    ):
        """Convenience method to create an Email notification."""
        notification_type = self.notification_type_service.get_email_type()
        return self.create_notification(
            corporate=corporate,
            title=title,
            destination=destination,
            message=message,
            notification_type=notification_type,
            state=state,
        )

    def create_ussd_notification(
        self, corporate, title, destination, message, state
    ):
        """Convenience method to create a USSD notification."""
        notification_type = self.notification_type_service.get_ussd_type()
        return self.create_notification(
            corporate=corporate,
            title=title,
            destination=destination,
            message=message,
            notification_type=notification_type,
            state=state,
        )

    def send_realtime_notification(self, notification):
        """Send notification to user via WebSocket."""
        try:
            channel_layer = get_channel_layer()

            # Prepare notification data
            notification_data = {
                "id": str(notification.id),
                "title": notification.title,
                "message": notification.message,
                "destination": notification.destination,
                "notification_type": notification.notification_type.name,
                "state": notification.state.name,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            }

            # Send to user-specific group based on email/destination
            from Authentication.models.user import CustomUser
            try:
                user = CustomUser.objects.get(email=notification.destination)
                user_group = f"user_{user.id}_notifications"

                async_to_sync(channel_layer.group_send)(
                    user_group,
                    {
                        "type": "notification_message",
                        "notification": notification_data,
                    }
                )
            except CustomUser.DoesNotExist:
                pass

            # Also send to corporate group if applicable
            if notification.corporate:
                corporate_group = f"corporate_{notification.corporate.id}_notifications"
                async_to_sync(channel_layer.group_send)(
                    corporate_group,
                    {
                        "type": "notification_message",
                        "notification": notification_data,
                    }
                )

        except Exception as e:
            print(f"Error sending real-time notification: {e}")

    def mark_failed(self, notification_id):
        failed_state = StateService().get_failed()
        Notification.objects.filter(id=notification_id).update(state=failed_state)

    def mark_read(self, notification_id):
        """Mark a notification as read."""
        Notification.objects.filter(id=notification_id).update(is_read=True)

    def get_unread_notifications(self, corporate):
        """Get all unread notifications for a corporate."""
        return Notification.objects.filter(
            corporate=corporate,
            is_read=False
        ).order_by("-created_at")

    def update_transaction_notification_log(
        self, transaction: Transaction, response: dict
    ):
        """Append notification response to a transaction log."""
        notification_responses = transaction.notification_response or ""
        new_response = f"{notification_responses}|{response}"
        transaction.notification_response = new_response
        transaction.save()