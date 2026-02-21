# Database Setup for Email Notifications

## Automatic Setup (Recommended)

After deploying with the fixes, the system will automatically create required records:

1. Run migrations: `python manage.py migrate`
2. Run bootstrap: `python manage.py bootstrap_data`

The entrypoint.sh now runs both automatically on container startup.

## What Gets Created

### 1. State Table (Authentication_state)
- Active
- Completed
- Failed
- Pending
- Sent

### 2. NotificationType Table (Authentication_notificationtype)
- id=1, name=USSD
- id=2, name=EMAIL

The IDs are auto-generated integers (1, 2, 3...) and the migration ensures USSD=1 and EMAIL=2.

## Manual Setup (If Needed)

If you need to manually set up a fresh database:

### State Records
```sql
INSERT INTO "Authentication_state" (name, description, created_at, updated_at) VALUES
('Active', 'Active state', NOW(), NOW()),
('Completed', 'Completed state', NOW(), NOW()),
('Failed', 'Failed state', NOW(), NOW()),
('Pending', 'Pending state', NOW(), NOW()),
('Sent', 'Sent state', NOW(), NOW());
```

### NotificationType Records
```sql
-- These will be created by migration 0008 with correct IDs
-- id=1 for USSD, id=2 for EMAIL
```

## Verification

Check if records exist:

```sql
-- Check States
SELECT * FROM "Authentication_state";

-- Check NotificationTypes (should show id=1 for USSD, id=2 for EMAIL)
SELECT id, name, description FROM "Authentication_notificationtype" ORDER BY id;
```

Expected output:
- 5 State records
- 2 NotificationType records with id=1 (USSD) and id=2 (EMAIL)

## Environment Variables Required

Ensure these are set in your .env file:

```bash
SMTP_USER=quidpath@gmail.com
SMTP_PASSWORD=krpmwhuyjfavlstb
```

## Testing Email After Setup

```python
# Django shell
python manage.py shell

from quidpath_backend.core.utils.email import NotificationServiceHandler

handler = NotificationServiceHandler()
result = handler.send_notification([{
    "message_type": "EMAIL",
    "organisation_id": None,
    "destination": "your-test-email@example.com",
    "message": "<p>Test email from Quidpath</p>",
    "confirmation_code": "123456"
}])

print(result)
# Expected: {'status': 'success', 'code': '200.001.001', 'message': 'Email sent successfully'}
```

## Troubleshooting

### "State matching query does not exist"
Run: `python manage.py bootstrap_data`

### "NotificationType matching query does not exist"
Run: `python manage.py migrate` then `python manage.py bootstrap_data`

### "SMTP credentials not configured"
Check that SMTP_USER and SMTP_PASSWORD are set in .env

### Email not sending but no errors
1. Check Gmail App Password is valid
2. Check SMTP_HOST and SMTP_PORT are correct
3. Check firewall allows outbound port 587
4. Check Django logs for SMTP errors
