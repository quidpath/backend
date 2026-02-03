from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string

from Authentication.models.role import Role
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.registry import ServiceRegistry


@receiver(post_save, sender=Corporate)
def create_superadmin_on_approval(sender, instance: Corporate, created: bool, **kwargs):
    if not created and instance.is_approved:
        try:
            superadmin_role = Role.objects.get(name="SUPERADMIN")
        except Role.DoesNotExist:
            return

        existing_superadmin = CorporateUser.objects.filter(
            corporate=instance, role=superadmin_role
        )
        if existing_superadmin.exists():
            return

        # Generate credentials
        username = f"{instance.name.lower().replace(' ', '_')}_admin"
        password = get_random_string(10)
        email = instance.email

        # Create superadmin user properly
        user = CorporateUser(
            username=username,
            email=email,
            corporate=instance,
            role=superadmin_role,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        # Send email
        NotificationServiceHandler().send_notification(
            [
                {
                    "message_type": "2",
                    "organisation_id": str(instance.id),
                    "destination": email,
                    "message": f"""
                <h3>Your Company has been approved</h3>
                <p>Login using the following credentials:</p>
                <p>Username: <b>{username}</b></p>
                <p>Password: <b>{password}</b></p>
                <p>Please change your password after first login.</p>
            """,
                }
            ]
        )

        if not instance.is_verified:
            instance.is_verified = True
            instance.save(update_fields=["is_verified"])
