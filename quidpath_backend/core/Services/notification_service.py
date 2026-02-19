from Authentication.models.logbase import (Notification, NotificationType,
                                           Transaction)
from .state_service import StateService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class NotificationTypeService:
    """Manage NotificationType model."""

    def get_or_create_type(self, name: str) -> NotificationType:
        return NotificationType.objects.get_or_create(
            name=name, defaults={"description": f"{name} notification"}
        )[0]


class NotificationService:
    """Manage Notification model."""

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

    def send_realtime_notification(self, notification):
        """Send notification to user via WebSocket"""
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
            
            # Send to user-specific group (based on email/destination)
            # You may need to map email to user_id for better targeting
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
            # Log error but don't fail the notification creation
            print(f"Error sending real-time notification: {e}")

    def mark_failed(self, notification_id):
        failed_state = StateService().get_failed()
        Notification.objects.filter(id=notification_id).update(state=failed_state)

    def update_transaction_notification_log(
        self, transaction: Transaction, response: dict
    ):
        """Append notification response to a transaction log."""
        notification_responses = transaction.notification_response or ""
        new_response = f"{notification_responses}|{response}"
        transaction.notification_response = new_response
        transaction.save()
