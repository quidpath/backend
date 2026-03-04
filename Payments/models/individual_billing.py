from decimal import Decimal

from django.db import models

from Authentication.models import CustomUser
from quidpath_backend.core.base_models.base import BaseModel


class IndividualSubscriptionPlan(BaseModel):
    PLAN_TIERS = [
        ("starter", "Starter"),
        ("professional", "Professional"),
        ("business", "Business"),
        ("enterprise", "Enterprise"),
    ]
    
    tier = models.CharField(max_length=50, choices=PLAN_TIERS, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    monthly_price_kes = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=dict)
    max_transactions = models.IntegerField(default=100)
    max_invoices = models.IntegerField(default=50)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = "individual_subscription_plans"
        ordering = ["monthly_price_kes"]
    
    def __str__(self):
        return f"{self.name} - KES {self.monthly_price_kes}/month"


class IndividualSubscription(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending Payment"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("suspended", "Suspended"),
    ]
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="individual_subscriptions"
    )
    plan = models.ForeignKey(
        IndividualSubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    
    class Meta:
        db_table = "individual_subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "end_date"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        from django.utils import timezone
        return self.status == "active" and timezone.now() <= self.end_date
    
    @property
    def days_until_expiry(self):
        from django.utils import timezone
        if self.is_active:
            delta = self.end_date - timezone.now()
            return delta.days
        return 0


class IndividualPayment(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="individual_payments"
    )
    subscription = models.ForeignKey(
        IndividualSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    mpesa_checkout_request_id = models.CharField(max_length=255, blank=True, null=True)
    mpesa_merchant_request_id = models.CharField(max_length=255, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=255, blank=True, null=True)
    mpesa_transaction_date = models.DateTimeField(blank=True, null=True)
    
    idempotency_key = models.CharField(max_length=255, unique=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = "individual_payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["mpesa_checkout_request_id"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["status", "created_at"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} - KES {self.amount_kes} ({self.status})"
