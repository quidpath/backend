from Authentication.models.logbase import (Notification, NotificationType,
                                           Transaction)

from .state_service import StateService


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
        return Notification.objects.create(
            title=title,
            message=message,
            destination=destination,
            notification_type=notification_type,
            state=state,
        )

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
