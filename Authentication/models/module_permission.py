# Authentication/models/module_permission.py
from django.db import models


class ModulePermission(models.Model):
    """Represents a navigable module or sub-route for the frontend sidebar/menu."""

    codename = models.CharField(max_length=100, unique=True, help_text="e.g. accounting.view, accounting.invoices")
    module_slug = models.CharField(max_length=50, db_index=True, help_text="e.g. accounting, banking")
    name = models.CharField(max_length=100)
    path = models.CharField(max_length=255, help_text="Frontend path e.g. /accounting")
    icon_slug = models.CharField(max_length=50, blank=True, help_text="MUI icon name for frontend")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.codename} ({self.name})"
