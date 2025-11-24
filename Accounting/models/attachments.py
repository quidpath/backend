# Document attachments model
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import hashlib

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel


class DocumentAttachment(BaseModel):
    """
    Generic attachment model for invoices, quotes, LPOs, bills, etc.
    """
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(CorporateUser, on_delete=models.PROTECT, related_name="uploaded_attachments")
    
    # Generic foreign key to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()  # S3 URL
    file_size = models.BigIntegerField(default=0)  # Size in bytes
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    checksum = models.CharField(max_length=64, blank=True, null=True)  # SHA256 hash for integrity
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=False)  # Public attachments can be accessed without auth
    
    class Meta:
        verbose_name = "Document Attachment"
        verbose_name_plural = "Document Attachments"
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['corporate', 'created_at']),
        ]

    def __str__(self):
        return f"{self.file_name} - {self.content_object}"

    def save(self, *args, **kwargs):
        # Calculate checksum if not provided
        if not self.checksum and self.file_url:
            # In production, download file and calculate hash
            # For now, we'll set it during upload
            pass
        super().save(*args, **kwargs)




