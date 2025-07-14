# core/mixins/user_tracking_mixin.py
from django.conf import settings
class UserTrackingMixin:
    def save(self, *args, **kwargs):
        if not self.pk:  # If the object is being created
            self.created_by = settings.DEFAULT_USER  # Set this to your logic
        self.updated_by = settings.DEFAULT_USER  # Set this to your logic
        super().save(*args, **kwargs)