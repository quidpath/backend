# authentication/models/permission.py
from django.db import models

from quidpath_backend.core.base_models.base import BaseModel


class Permission(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name
