from django.db import migrations


def seed_notification_types(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")
    
    # Use name as lookup field since it's unique
    ussd, created = NotificationType.objects.update_or_create(
        name="USSD",
        defaults={"id": "USSD", "description": "USSD notification"}
    )
    
    email, created = NotificationType.objects.update_or_create(
        name="EMAIL",
        defaults={"id": "EMAIL", "description": "EMAIL notification"}
    )


def reverse_seed(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")
    NotificationType.objects.filter(id__in=["USSD", "EMAIL"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("Authentication", "0007_notification_is_read_corporate"),
    ]

    operations = [
        migrations.RunPython(seed_notification_types, reverse_seed),
    ]
