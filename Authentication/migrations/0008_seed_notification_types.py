from django.db import migrations


def seed_notification_types(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")
    db_alias = schema_editor.connection.alias

    for type_id in ["USSD", "EMAIL"]:
        # Use queryset update to avoid Django PK-change insert behavior
        updated = NotificationType.objects.using(db_alias).filter(name=type_id).update(
            id=type_id,
            description=f"{type_id} notification"
        )
        if not updated:
            NotificationType.objects.using(db_alias).create(
                id=type_id,
                name=type_id,
                description=f"{type_id} notification"
            )


def reverse_seed(apps, schema_editor):
    NotificationType = apps.get_model("Authentication", "NotificationType")
    db_alias = schema_editor.connection.alias
    NotificationType.objects.using(db_alias).filter(id__in=["USSD", "EMAIL"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("Authentication", "0007_notification_is_read_corporate"),
    ]

    operations = [
        migrations.RunPython(seed_notification_types, reverse_seed),
    ]