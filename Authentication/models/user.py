import random
from datetime import timedelta

from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        Group, Permission, PermissionsMixin)
from django.db import models
from django.utils.timezone import now

from quidpath_backend.core.base_models.base import BaseModel


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)


class CustomUser(BaseModel, AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    profilePhoto = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    last_login = models.DateTimeField(blank=True, null=True)

    # ✅ OTP-related fields
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    last_otp_sent_at = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    groups = models.ManyToManyField(Group, related_name="customuser_set", blank=True)
    user_permissions = models.ManyToManyField(
        Permission, related_name="customuser_set", blank=True
    )

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    # ✅ OTP Generation
    def generate_otp(self):
        """Generate a new 6-digit OTP and update timestamp"""
        code = f"{random.randint(100000, 999999)}"
        self.otp_code = code
        self.last_otp_sent_at = now()
        self.save(update_fields=["otp_code", "last_otp_sent_at"])
        return code

    # ✅ OTP Validation
    def otp_is_valid(self, otp):
        """Check if OTP matches and is <24h old"""
        if not self.otp_code or not self.last_otp_sent_at:
            return False
        if now() - self.last_otp_sent_at > timedelta(hours=24):
            return False
        return otp == self.otp_code
