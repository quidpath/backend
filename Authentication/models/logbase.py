from django.db import models
from pip._internal.utils._jaraco_text import _

from quidpath_backend.core.base_models.base import BaseModel


class State(BaseModel):
    """Represents a global state e.g. Active, Completed, Failed."""

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def bootstrap_defaults(cls):
        """Ensure default states always exist."""
        defaults = ["Active", "Completed", "Failed", "Pending", "Sent"]
        for name in defaults:
            cls.objects.get_or_create(
                name=name, defaults={"description": f"{name} state"}
            )


class NotificationType(models.Model):
    """Type of notification (Email, SMS, Push)."""

    # Using AutoField for auto-incrementing integer IDs (1, 2, 3...)
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def bootstrap_defaults(cls):
        """Ensure default notification types exist."""
        defaults = [
            {"name": "USSD", "description": "USSD notification"},
            {"name": "EMAIL", "description": "Email notification"},
        ]
        for item in defaults:
            cls.objects.get_or_create(
                name=item["name"],
                defaults={"description": item["description"]}
            )

class Notification(BaseModel):
    """Actual notification record."""

    title = models.CharField(max_length=255)
    message = models.TextField()
    destination = models.CharField(max_length=255)  # Email or phone
    notification_type = models.ForeignKey(NotificationType, on_delete=models.PROTECT)
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    response_payload = models.JSONField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    corporate = models.ForeignKey(
        "OrgAuth.Corporate",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="notifications",
    )

    def __str__(self):
        return f"{self.title} → {self.destination}"


class TransactionType(BaseModel):
    """High-level transaction type e.g. OTP_SENT, USER_LOGIN"""

    name = models.CharField(max_length=100, unique=True)
    simple_name = models.CharField(max_length=100, blank=True, null=True)
    class_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def bootstrap_defaults(cls):
        """Default system transaction types."""
        defaults = ["OTP_SENT", "USER_LOGIN", "USER_REGISTERED"]
        for name in defaults:
            cls.objects.get_or_create(
                name=name, defaults={"simple_name": name, "class_name": name}
            )


class Transaction(BaseModel):
    """Transaction log for user/system actions."""

    reference = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(
        "Authentication.CustomUser",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="transactions",
    )
    transaction_type = models.ForeignKey(TransactionType, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    message = models.TextField(blank=True, null=True)
    response = models.CharField(max_length=255, blank=True, null=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    notification_response = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.reference} - {self.transaction_type.name}"


class Organisation(BaseModel):
    """Optional: Corporate/Org context."""

    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name

    @classmethod
    def create_from_user_email(cls, user_email: str):
        """
        Create an organisation where:
        - name = email prefix (before @)
        - email = user email
        """
        email_prefix = user_email.split("@")[0]
        org, created = cls.objects.get_or_create(
            name=email_prefix, defaults={"email": user_email}
        )
        return org

    @classmethod
    def bootstrap_defaults(cls):
        """Fallback default organisation if none exists."""
        if not cls.objects.exists():
            cls.objects.create(name="Default Organisation", email="info@example.com")
