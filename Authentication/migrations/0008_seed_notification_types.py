from django.db import migrations


def seed_notification_types(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")
    db_alias = schema_editor.connection.alias

    types = [
        {"id": 1, "name": "USSD", "description": "USSD notification"},
        {"id": 2, "name": "EMAIL", "description": "Email notification"},
    ]

    for t in types:
        updated = NotificationType.objects.using(db_alias).filter(name=t["name"]).update(
            id=t["id"],
            description=t["description"]
        )
        if not updated:
            NotificationType.objects.using(db_alias).create(
                id=t["id"],
                name=t["name"],
                description=t["description"]
            )


def reverse_seed(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")
    db_alias = schema_editor.connection.alias
    NotificationType.objects.using(db_alias).filter(id__in=[1, 2]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("Authentication", "0007_notification_is_read_corporate"),
    ]

    operations = [
        migrations.RunPython(seed_notification_types, reverse_seed),
    ]