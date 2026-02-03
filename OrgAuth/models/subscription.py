"""
Corporate Subscription Model
Stores subscription information synced from Billing Service
"""

from django.db import models

from quidpath_backend.core.base_models.base import BaseModel


class CorporateSubscription(BaseModel):
    """
    Stores subscription information for corporates
    Synced from Billing Service via webhooks
    """

    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("suspended", "Suspended"),
    ]

    corporate_id = models.UUIDField(db_index=True)
    plan_id = models.UUIDField()  # Reference to Plan in Billing Service
    plan_name = models.CharField(max_length=100)
    plan_slug = models.CharField(
        max_length=100
    )  # e.g., 'basic', 'premium', 'enterprise'

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    trial_end_date = models.DateTimeField(null=True, blank=True)

    # Features enabled by this subscription
    features = models.JSONField(default=dict)  # {"feature_name": True/False}

    # Reference to Billing Service subscription
    billing_subscription_id = models.UUIDField(unique=True)

    # Sync metadata
    last_synced_at = models.DateTimeField(auto_now=True)
    sync_source = models.CharField(
        max_length=20, default="webhook"
    )  # webhook, api, manual

    # Renewal settings
    auto_renew = models.BooleanField(default=True)
    grace_period_days = models.IntegerField(default=7)

    class Meta:
        db_table = "corporate_subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["corporate_id", "status"]),
            models.Index(fields=["billing_subscription_id"]),
            models.Index(fields=["end_date"]),
        ]

    def __str__(self):
        return f"{self.plan_name} - {self.corporate_id} ({self.status})"

    @property
    def is_active(self):
        """Check if subscription is currently active"""
        from django.utils import timezone

        if self.status == "active":
            return timezone.now() <= self.end_date
        elif self.status == "trial":
            return timezone.now() <= (self.trial_end_date or self.end_date)
        return False

    @property
    def is_in_grace_period(self):
        """Check if subscription is in grace period after expiry"""
        from datetime import timedelta

        from django.utils import timezone

        if self.status == "expired":
            grace_end = self.end_date + timedelta(days=self.grace_period_days)
            return timezone.now() <= grace_end
        return False

    @property
    def days_until_expiry(self):
        """Calculate days until subscription expires"""
        from django.utils import timezone

        if self.is_active:
            delta = self.end_date - timezone.now()
            return delta.days
        return 0

    def has_feature(self, feature_name: str) -> bool:
        """Check if subscription includes a specific feature"""
        return self.features.get(feature_name, False)

    def get_enabled_features(self):
        """Get list of enabled feature names"""
        return [feature for feature, enabled in self.features.items() if enabled]
