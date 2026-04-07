# authentication/models/role.py
from django.db import models


class Role(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True, help_text="Role description")
    corporate = models.ForeignKey(
        "OrgAuth.Corporate",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
        help_text="If set, this role belongs to a specific corporate. If null, it is a system-wide role.",
    )
    module_permissions = models.ManyToManyField(
        "Authentication.ModulePermission",
        related_name="roles",
        blank=True,
        help_text="Modules/menu items this role can access",
    )

    class Meta:
        # Allow same name across different corporates, but unique globally for system roles
        unique_together = [("name", "corporate")]

    def __str__(self):
        return self.name
