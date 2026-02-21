# Changes Summary - Email Notification Fix

## Model Changes

### NotificationType Model (Authentication/models/logbase.py)
- **Changed**: ID field from `CharField(max_length=50, primary_key=True)` to auto-incrementing integer
- **Result**: IDs now auto-generate as 1, 2, 3... instead of using string IDs
- **Order**: USSD=1, EMAIL=2

## Migration Created

### 0008_change_notificationtype_to_autofield_and_seed.py
This migration:
1. Removes the old CharField ID field
2. Adds a new AutoField (auto-incrementing integer) ID
3. Migrates existing data preserving records
4. Ensures USSD gets id=1 and EMAIL gets id=2

## Service Updates

### NotificationTypeService (quidpath_backend/core/Services/notification_service.py)
- Simplified to use name-based lookups
- Removed hardcoded ID mappings
- IDs now auto-generate from database

## Settings Fix

### quidpath_backend/settings/base.py
- **Fixed**: Changed `SMTP_PASS` to `SMTP_PASSWORD` (line 159)
- **Impact**: Email sending now works correctly

### quidpath_backend/core/utils/DocsEmail.py
- **Fixed**: Changed `settings.SMTP_PASS` to `settings.SMTP_PASSWORD`

## Bootstrap Command

### New Management Command: bootstrap_data
- Location: `quidpath_backend/core/management/commands/bootstrap_data.py`
- Purpose: Automatically creates required State and NotificationType records
- Usage: `python manage.py bootstrap_data`

## Entrypoint Update

### entrypoint.sh
- Added automatic bootstrap after migrations
- Ensures fresh databases have all required records

## Database Structure

### NotificationType Table
```
id (AutoField) | name (CharField) | description (TextField)
1              | USSD             | USSD notification
2              | EMAIL            | EMAIL notification
```

### State Table
```
name      | description
Active    | Active state
Completed | Completed state
Failed    | Failed state
Pending   | Pending state
Sent      | Sent state
```

## Testing

After deployment:
1. Migrations will run automatically
2. Bootstrap will create required records
3. USSD will have id=1
4. EMAIL will have id=2
5. Email sending should work with correct SMTP credentials

## Rollback Plan

If issues occur, the migration has a reverse function that:
1. Converts IDs back to CharField
2. Uses name as the ID value
3. Preserves all data
