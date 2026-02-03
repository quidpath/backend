import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def default_expiry():
    return timezone.now() + timedelta(minutes=2)


class ForgotPassword(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forgot_password_entries",
    )
    otp = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)

    is_valid = models.BooleanField(default=True)  # Controls whether OTP is usable
    is_verified = models.BooleanField(
        default=False
    )  # Marks if OTP was successfully verified
    used_at = models.DateTimeField(null=True, blank=True)  # Timestamp of usage

    def has_expired(self):
        return timezone.now() > self.expires_at

    def mark_used(self):
        self.is_valid = False
        self.used_at = timezone.now()
        self.save()

    def __str__(self):
        return f"ForgotPassword(user={self.user.username}, otp={self.otp}, is_valid={self.is_valid})"
