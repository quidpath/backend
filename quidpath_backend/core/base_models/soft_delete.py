# core/base_models/soft_delete.py
from django.db import models
from django.utils import timezone


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save()

    class Meta:
        abstract = True
