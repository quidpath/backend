from django.db import migrations


def seed_notification_types(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")

    for type_id in ["USSD", "EMAIL"]:
        obj = NotificationType.objects.filter(name=type_id).first()
        if obj:
            obj.id = type_id
            obj.description = f"{type_id} notification"
            obj.save()
        else:
            NotificationType.objects.create(
                id=type_id,
                name=type_id,
                description=f"{type_id} notification"
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