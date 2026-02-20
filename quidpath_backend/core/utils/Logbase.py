# core/utils/logbase.py
import logging
import uuid

from django.db import transaction
from django.http import HttpRequest
from django.utils.timezone import now

from Authentication.models.logbase import State, Transaction, TransactionType
from Authentication.models.user import CustomUser
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class TransactionLogBase:
    """
    Logs *all* steps in authentication/notifications.
    Works with ServiceRegistry to abstract DB calls.
    """

    def __init__(self):
        self.registry = ServiceRegistry()

    @classmethod
    def log(
        cls,
        transaction_type: str,
        user=None,
        message="",
        state_name="Active",
        extra=None,
        notification_resp=None,
        request=None,
    ):
        """
        Static shortcut for logging a transaction.
        - transaction_type: str (e.g. 'USER_LOGIN', 'OTP_SENT')
        - user: User instance or dict
        - message: log message
        - state_name: Active | Completed | Failed
        - extra: dict with additional info
        - notification_resp: response from NotificationServiceHandler
        - request: optional HttpRequest for IP & headers
        """
        instance = cls()
        return instance._log_transaction(
            transaction_type=transaction_type,
            user=user,
            message=message,
            state_name=state_name,
            extra=extra,
            notification_resp=notification_resp,
            request=request,
        )

    def _log_transaction(
        self,
        transaction_type,
        user=None,
        message="",
        state_name="Active",
        extra=None,
        notification_resp=None,
        request=None,
    ):
        """
        Internal method that creates the transaction entry.
        """
        try:
            with transaction.atomic():
                #  1. Get or create State
                state = self._get_state(state_name)

                #  2. Get or create TransactionType
                txn_type = self._get_transaction_type(transaction_type)

                #  3. Normalize user (can be dict or model)
                user_instance = self._normalize_user(user)

                #  4. Extract request IP if present
                source_ip = self._get_request_ip(request)

                #  5. Compose extra payload
                details_payload = extra or {}
                if request:
                    details_payload.update(
                        {
                            "user_agent": request.META.get("HTTP_USER_AGENT"),
                            "headers": {
                                k: v
                                for k, v in request.META.items()
                                if k.startswith("HTTP_")
                            },
                        }
                    )

                #  6. Create Transaction
                txn_data = {
                    "reference": str(uuid.uuid4()),
                    "transaction_type": txn_type,
                    "user": user_instance,
                    "amount": 0,
                    "message": message,
                    "response": (
                        "200.000.000" if state_name == "Completed" else "400.000.000"
                    ),
                    "source_ip": source_ip or "0.0.0.0",
                    "state": state,
                    "notification_response": (
                        str(notification_resp) if notification_resp else None
                    ),
                }

                transaction_obj = Transaction.objects.create(**txn_data)

                logger.info(
                    f"[TransactionLog] {transaction_type} | user={user_instance} | state={state_name}"
                )

                return transaction_obj

        except Exception as e:
            logger.exception(
                f"[TransactionLog] Failed logging {transaction_type}: {e}"
            )
            return None

    def _get_state(self, state_name: str) -> State:
        """Fetch or create State (Active/Completed/Failed)"""
        return State.objects.get_or_create(
            name=state_name, defaults={"description": f"{state_name} state"}
        )[0]

    def _get_transaction_type(self, txn_name: str) -> TransactionType:
        """Fetch or create TransactionType"""
        return TransactionType.objects.get_or_create(
            name=txn_name, defaults={"simple_name": txn_name, "class_name": txn_name}
        )[0]

    def _normalize_user(self, user):
        """Ensure we always return a proper User instance"""
        if not user:
            return None
        if isinstance(user, CustomUser):
            return user
        elif isinstance(user, dict) and user.get("id"):
            try:
                return CustomUser.objects.get(id=user["id"])
            except CustomUser.DoesNotExist:
                logger.warning("[TransactionLog] User not found in DB")
                return None
        return None

    def _get_request_ip(self, request: HttpRequest):
        """Extract client IP from request"""
        if not request:
            return None
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")
