from django.db import models

from Authentication.models import CustomUser
from Authentication.models.role import Role
from quidpath_backend.core.base_models.base import BaseModel


# Create your models here.
class Corporate(BaseModel):
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=255, blank=True, null=True)
    company_size = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    registration_number = models.CharField(max_length=255, blank=True, null=True)
    tax_id = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    website = models.URLField()
    logo = models.ImageField(upload_to="corporates/logos/")
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    email = models.EmailField()
    is_approved = models.BooleanField(default=False, blank=True, null=True)
    is_rejected = models.BooleanField(default=False, blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_seen = models.BooleanField(default=False, blank=True, null=True)
    is_verified = models.BooleanField(default=False, blank=True, null=True)

    def __str__(self):
        return self.name


class CorporateUser(CustomUser):
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return self.username


# Import subscription model
from OrgAuth.models.subscription import CorporateSubscription
