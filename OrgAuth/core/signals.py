import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string

from Authentication.models.role import Role
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Corporate)
def create_superadmin_on_approval(sender, instance: Corporate, created: bool, **kwargs):
    """
    When a corporate is approved:
    1. Create a SUPERADMIN user with generated credentials
    2. Start a 14-day trial (corporate stays inactive until billing details entered)
    3. Send approval email with credentials + link to billing/payment page
    """
    if not created and instance.is_approved:
        try:
            superadmin_role = Role.objects.get(name="SUPERADMIN")
        except Role.DoesNotExist:
            logger.error("SUPERADMIN role not found — run bootstrap_data first")
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

        user = CorporateUser(
            username=username,
            email=email,
            corporate=instance,
            role=superadmin_role,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        # Notify billing microservice to create a trial (idempotent)
        try:
            from quidpath_backend.core.Services.billing_service import BillingServiceClient
            billing_client = BillingServiceClient()
            billing_client.create_trial(
                corporate_id=str(instance.id),
                corporate_name=instance.name,
                plan_tier="starter",
            )
            logger.info(f"Trial created in billing service for corporate {instance.name}")
        except Exception as e:
            logger.warning(f"Billing service trial creation failed for {instance.name}: {e}")

        # Send approval email with credentials and billing page link
        frontend_url = "https://app.quidpath.com"
        billing_url = f"{frontend_url}/billing/setup?corporate_id={instance.id}"

        NotificationServiceHandler().send_notification(
            [
                {
                    "message_type": "2",
                    "organisation_id": str(instance.id),
                    "destination": email,
                    "message": f"""
                <h3>Your Organisation Has Been Approved!</h3>
                <p>Congratulations! <b>{instance.name}</b> has been approved on Quidpath ERP.</p>
                <p>Your login credentials are:</p>
                <p>Username: <b>{username}</b></p>
                <p>Password: <b>{password}</b></p>
                <p>Please change your password after first login.</p>
                <hr/>
                <h4>Your 14-Day Free Trial Has Started</h4>
                <p>You have a <b>14-day free trial</b> to explore all features.</p>
                <p>To activate your account and start your trial, please enter your billing details:</p>
                <p><a href="{billing_url}" style="background-color: #000000; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">Set Up Billing</a></p>
                <p>After your trial ends, you will receive an M-Pesa STK push to continue your subscription.</p>
                <p>Without payment, access to the system will be restricted.</p>
            """,
                }
            ]
        )

        if not instance.is_verified:
            instance.is_verified = True
            instance.save(update_fields=["is_verified"])
