from django.db import migrations, models


def migrate_data_forward(apps, schema_editor):
    """
    Migrate existing NotificationType records to use integer IDs.
    Ensures USSD=1, EMAIL=2 in the correct order.
    """
    NotificationType = apps.get_model("Authentication", "NotificationType")
    db_alias = schema_editor.connection.alias
    
    # Get all existing records
    existing = list(NotificationType.objects.using(db_alias).all().values('name', 'description'))
    
    # Clear the table (we'll recreate with proper IDs)
    NotificationType.objects.using(db_alias).all().delete()
    
    # Create in specific order to ensure correct IDs
    # USSD will get id=1, EMAIL will get id=2
    NotificationType.objects.using(db_alias).create(
        name="USSD",
        description="USSD notification"
    )
    
    NotificationType.objects.using(db_alias).create(
        name="EMAIL",
        description="EMAIL notification"
    )
    
    # Recreate any other existing types
    priority_names = ["USSD", "EMAIL"]
    for item in existing:
        if item['name'] not in priority_names:
            NotificationType.objects.using(db_alias).create(
                name=item['name'],
                description=item['description']
            )


def migrate_data_backward(apps, schema_editor):
    """
    Reverse migration - convert integer IDs back to CharField.
    """
    NotificationType = apps.get_model("Authentication", "NotificationType")
    db_alias = schema_editor.connection.alias
    
    # Get all records
    records = list(NotificationType.objects.using(db_alias).all().values('name', 'description'))
    
    # Clear and recreate with name as ID
    NotificationType.objects.using(db_alias).all().delete()
    
    for record in records:
        NotificationType.objects.using(db_alias).create(
            id=record['name'],
            name=record['name'],
            description=record['description']
        )


class Migration(migrations.Migration):
    dependencies = [
        ("Authentication", "0007_notification_is_read_corporate"),
    ]

    operations = [
        # Step 1: Remove the old CharField primary key
        migrations.RemoveField(
            model_name='notificationtype',
            name='id',
        ),
        
        # Step 2: Add new AutoField primary key
        migrations.AddField(
            model_name='notificationtype',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        
        # Step 3: Migrate data to ensure USSD=1, EMAIL=2
        migrations.RunPython(migrate_data_forward, migrate_data_backward),
    ]
