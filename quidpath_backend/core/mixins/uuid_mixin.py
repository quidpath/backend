# core/mixins/uuid_mixin.py
import uuid
class UUIDMixin:
    def save(self, *args, **kwargs):
        if not self.pk:  # If the object is being created
            self.id = uuid.uuid4()
        super().save(*args, **kwargs)