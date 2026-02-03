from django.core.exceptions import ValidationError
from django.db import models

from OrgAuth.models import Corporate
from quidpath_backend.core.base_models.base import BaseModel


class Customer(BaseModel):
    CATEGORY_CHOICES = [
        ("individual", "Individual"),
        ("company", "Company"),
    ]
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    corporate = models.ForeignKey(
        Corporate, on_delete=models.SET_NULL, blank=True, null=True
    )
    company_name = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.category == "company" and self.company_name:
            return self.company_name
        return f"{self.first_name} {self.last_name}"

    def clean(self):
        if self.category == "company" and not self.company_name:
            raise ValidationError("Company name is required for company customers.")
        if self.category == "individual" and self.company_name:
            raise ValidationError(
                "Company name should be blank for individual customers."
            )
