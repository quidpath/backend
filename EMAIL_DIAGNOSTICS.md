# Email Sending Diagnostics & Setup Guide

## Issues Found

### 1. **Variable Name Mismatch in Settings**
- **Problem**: `settings.base.py` defines `SMTP_PASS` but `email.py` uses `settings.SMTP_PASSWORD`
- **Location**: Line 159 in `quidpath_backend/settings/base.py`
- **Impact**: Email sending fails because password is `None`

### 2. **NotificationType ID Mismatch**
- **Problem**: `NotificationTypeService` expects integer IDs (1, 2) but model uses CharField primary key
- **Location**: `quidpath_backend/core/Services/notification_service.py` lines 11-14
- **Impact**: Creates duplicate notification types with wrong IDs

### 3. **Missing Database Records**
- **Problem**: Fresh database needs State and NotificationType records
- **Impact**: Foreign key constraints fail when creating notifications

## Required Fixes

### Fix 1: Update Settings Variable Name
```python
# In quidpath_backend/settings/base.py line 159
# Change from:
SMTP_PASS = os.environ.get("SMTP_PASSWORD")

# To:
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
```

### Fix 2: Update NotificationTypeService
```python
# In quidpath_backend/core/Services/notification_service.py
# Remove the NOTIFICATION_TYPES dictionary and update methods
```

### Fix 3: Run Migration
The migration `0008_seed_notification_types.py` will seed NotificationType records.

## Fresh Database Setup Checklist

For a new database to work with email notifications, you need:

### 1. **State Records** (Required)
```sql
INSERT INTO "Authentication_state" (id, name, description, created_at, updated_at) VALUES
('Active', 'Active', 'Active state', NOW(), NOW()),
('Completed', 'Completed', 'Completed state', NOW(), NOW()),
('Failed', 'Failed', 'Failed state', NOW(), NOW()),
('Pending', 'Pending', 'Pending state', NOW(), NOW()),
('Sent', 'Sent', 'Sent state', NOW(), NOW());
```

### 2. **NotificationType Records** (Required)
```sql
INSERT INTO "Authentication_notificationtype" (id, name, description) VALUES
('EMAIL', 'EMAIL', 'EMAIL notification'),
('USSD', 'USSD', 'USSD notification'),
('SMS', 'SMS', 'SMS notification');
```

### 3. **Environment Variables** (Already Set)
✅ SMTP_USER=quidpath@gmail.com
✅ SMTP_PASSWORD=krpmwhuyjfavlstb

### 4. **SMTP Settings** (Already Configured)
✅ SMTP_HOST=smtp.gmail.com
✅ SMTP_PORT=587
✅ DEFAULT_FROM_EMAIL=noreply@quidpath.com

## Email Flow

1. **User Registration** → `Authentication/views/register.py`
2. **Calls** → `NotificationServiceHandler().send_notification()`
3. **Creates** → `Notification` record in database
4. **Sends** → Email via `_send_email()` method
5. **Uses** → SMTP credentials from settings

## Testing Email

After fixes, test with:
```bash
# In Django shell
python manage.py shell

from quidpath_backend.core.utils.email import NotificationServiceHandler

handler = NotificationServiceHandler()
result = handler.send_notification([{
    "message_type": "EMAIL",
    "organisation_id": None,
    "destination": "test@example.com",
    "message": "<p>Test email</p>",
    "confirmation_code": "123456"
}])

print(result)
```

## Common Issues

### Issue: "SMTP credentials not configured"
- **Cause**: SMTP_PASSWORD is None
- **Fix**: Apply Fix 1 above

### Issue: "NotificationType matching query does not exist"
- **Cause**: Missing NotificationType records
- **Fix**: Run migration 0008 or manually insert records

### Issue: "State matching query does not exist"
- **Cause**: Missing State records
- **Fix**: Run `State.bootstrap_defaults()` or insert manually

### Issue: "SMTPAuthenticationError"
- **Cause**: Invalid Gmail credentials or App Password
- **Fix**: Generate new App Password at https://myaccount.google.com/apppasswords

## Priority Actions

1. ✅ Fix SMTP_PASS → SMTP_PASSWORD in settings
2. ✅ Update NotificationTypeService to remove integer IDs
3. ✅ Ensure State.bootstrap_defaults() runs on startup
4. ✅ Run migration 0008 to seed NotificationType
5. ✅ Test email sending
