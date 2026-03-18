# authentication/models/role.py
from django.db import models


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    module_permissions = models.ManyToManyField(
        "Authentication.ModulePermission",
        related_name="roles",
        blank=True,
        help_text="Modules/menu items this role can access",
    )

    def __str__(self):
        return self.name
