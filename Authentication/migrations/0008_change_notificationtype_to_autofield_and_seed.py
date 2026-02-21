from django.db import migrations, models


def migrate_data_forward(apps, schema_editor):
    """
    Migrate existing NotificationType records to use integer IDs.
    Ensures USSD=1, EMAIL=2 in the correct order.
    
    Strategy:
    1. Temporarily disable foreign key constraints
    2. Save existing notification type data
    3. Drop and recreate the table with new ID type
    4. Recreate notification types with correct integer IDs
    5. Update foreign key references in Notification table
    """
    db_alias = schema_editor.connection.alias
    
    with schema_editor.connection.cursor() as cursor:
        # Step 1: Save existing notification type data
        cursor.execute("""
            SELECT id, name, description 
            FROM "Authentication_notificationtype"
        """)
        existing_types = cursor.fetchall()
        
        # Step 2: Save notification mappings (old_id -> notification_ids)
        cursor.execute("""
            SELECT notification_type_id, array_agg(id) as notification_ids
            FROM "Authentication_notification"
            GROUP BY notification_type_id
        """)
        notification_mappings = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Step 3: Drop foreign key constraint temporarily
        cursor.execute("""
            ALTER TABLE "Authentication_notification" 
            DROP CONSTRAINT IF EXISTS "Authentication_notif_notification_type_i_c61c1d8e_fk_Authentic";
        """)
        
        # Step 4: Truncate notification type table
        cursor.execute('TRUNCATE TABLE "Authentication_notificationtype" CASCADE')
        
        # Step 5: Recreate notification types with integer IDs in correct order
        # Map old IDs to new IDs
        id_mapping = {}
        
        # Priority order: USSD=1, EMAIL=2
        priority_types = [
            ("USSD", "USSD notification"),
            ("EMAIL", "EMAIL notification")
        ]
        
        new_id = 1
        for name, desc in priority_types:
            # Find matching existing type
            old_id = None
            old_desc = desc
            for old_type in existing_types:
                if old_type[1] == name:
                    old_id = old_type[0]
                    old_desc = old_type[2] or desc
                    break
            
            cursor.execute("""
                INSERT INTO "Authentication_notificationtype" (id, name, description)
                VALUES (%s, %s, %s)
            """, [new_id, name, old_desc])
            
            if old_id:
                id_mapping[old_id] = new_id
            
            new_id += 1
        
        # Add any other existing types
        for old_type in existing_types:
            old_id, name, desc = old_type
            if name not in ["USSD", "EMAIL"]:
                cursor.execute("""
                    INSERT INTO "Authentication_notificationtype" (id, name, description)
                    VALUES (%s, %s, %s)
                """, [new_id, name, desc or f"{name} notification"])
                id_mapping[old_id] = new_id
                new_id += 1
        
        # Step 6: Update notification foreign keys (column is TEXT at this point)
        for old_id, new_id in id_mapping.items():
            cursor.execute("""
                UPDATE "Authentication_notification"
                SET notification_type_id = %s
                WHERE notification_type_id = %s
            """, [str(new_id), str(old_id)])  # Both must be strings since column is TEXT
        
        # Step 7: Reset sequence
        cursor.execute("""
            SELECT setval(
                pg_get_serial_sequence('"Authentication_notificationtype"', 'id'),
                (SELECT MAX(id) FROM "Authentication_notificationtype")
            )
        """)


def migrate_data_backward(apps, schema_editor):
    """
    Reverse migration - convert integer IDs back to CharField.
    """
    db_alias = schema_editor.connection.alias
    
    with schema_editor.connection.cursor() as cursor:
        # Get all records
        cursor.execute("""
            SELECT id, name, description 
            FROM "Authentication_notificationtype"
        """)
        records = cursor.fetchall()
        
        # Drop foreign key constraint
        cursor.execute("""
            ALTER TABLE "Authentication_notification" 
            DROP CONSTRAINT IF EXISTS "Authentication_notif_notification_type_i_c61c1d8e_fk_Authentic";
        """)
        
        # Clear table
        cursor.execute('TRUNCATE TABLE "Authentication_notificationtype" CASCADE')
        
        # Recreate with name as ID
        for record in records:
            old_id, name, desc = record
            cursor.execute("""
                INSERT INTO "Authentication_notificationtype" (id, name, description)
                VALUES (%s, %s, %s)
            """, [name, name, desc])
            
            # Update notifications
            cursor.execute("""
                UPDATE "Authentication_notification"
                SET notification_type_id = %s
                WHERE notification_type_id = %s
            """, [name, str(old_id)])


class Migration(migrations.Migration):
    dependencies = [
        ("Authentication", "0007_notification_is_read_corporate"),
    ]

    operations = [
        # Step 1: Remove the old CharField primary key from NotificationType
        migrations.RemoveField(
            model_name='notificationtype',
            name='id',
        ),
        
        # Step 2: Change Notification.notification_type_id to text temporarily
        migrations.RunSQL(
            sql='ALTER TABLE "Authentication_notification" ALTER COLUMN "notification_type_id" TYPE TEXT',
            reverse_sql='ALTER TABLE "Authentication_notification" ALTER COLUMN "notification_type_id" TYPE VARCHAR(50)'
        ),
        
        # Step 3: Add new AutoField primary key to NotificationType
        migrations.AddField(
            model_name='notificationtype',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        
        # Step 4: Migrate data to ensure USSD=1, EMAIL=2
        migrations.RunPython(migrate_data_forward, migrate_data_backward),
        
        # Step 5: Change Notification.notification_type_id to integer
        migrations.RunSQL(
            sql='ALTER TABLE "Authentication_notification" ALTER COLUMN "notification_type_id" TYPE INTEGER USING "notification_type_id"::integer',
            reverse_sql='ALTER TABLE "Authentication_notification" ALTER COLUMN "notification_type_id" TYPE VARCHAR(50)'
        ),
        
        # Step 6: Recreate foreign key constraint
        migrations.RunSQL(
            sql='''
                ALTER TABLE "Authentication_notification" 
                ADD CONSTRAINT "Authentication_notif_notification_type_i_c61c1d8e_fk_Authentic"
                FOREIGN KEY ("notification_type_id") 
                REFERENCES "Authentication_notificationtype" ("id") 
                DEFERRABLE INITIALLY DEFERRED
            ''',
            reverse_sql='ALTER TABLE "Authentication_notification" DROP CONSTRAINT IF EXISTS "Authentication_notif_notification_type_i_c61c1d8e_fk_Authentic"'
        ),
    ]
