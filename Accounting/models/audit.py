# Audit log model
import json

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class AuditLog(BaseModel):
    """
    Audit trail for all important actions in the system.
    """

    ACTION_TYPES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("view", "View"),
        ("export", "Export"),
        ("send", "Send"),
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("post", "Post"),
        ("payment", "Payment"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("password_change", "Password Change"),
        ("permission_change", "Permission Change"),
    ]

    user = models.ForeignKey(
        CorporateUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    corporate = models.ForeignKey(
        Corporate, on_delete=models.CASCADE, related_name="audit_logs"
    )
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)

    # Generic foreign key to any model
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    model_name = models.CharField(max_length=100)  # e.g., "Invoice", "Payment"
    object_id_str = models.CharField(
        max_length=255, blank=True, null=True
    )  # String representation of object ID
    changes = models.JSONField(default=dict, blank=True)  # Store before/after changes
    description = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)  # Additional context

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["corporate", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_type_display()} {self.model_name} by {self.user} at {self.created_at}"
