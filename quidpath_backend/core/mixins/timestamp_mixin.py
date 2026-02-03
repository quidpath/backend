# core/mixins/timestamp_mixin.py
from django.utils import timezone


class TimestampMixin:
    def save(self, *args, **kwargs):
        if not self.pk:  # If the object is being created
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
