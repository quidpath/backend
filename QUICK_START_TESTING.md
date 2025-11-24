# Quick Start Testing Guide - Flutterwave Payments

## Quick Setup

### 1. Create Payment Provider

```python
from Payments.models import PaymentProvider
from OrgAuth.models import Corporate

corporate = Corporate.objects.first()

PaymentProvider.objects.create(
    corporate=corporate,
    provider_type='flutterwave',
    provider_name='Flutterwave',
    is_active=True,
    test_mode=True,
    config_json={
        'client_id': 'aa1c28d0-175a-41b8-83ab-f0a82d25f3de',
        'client_secret': 'YKtJzGlz84wTXZ0SD0MnoknZLh3L76Qg',
        'encryption_key': 'XQELn0YLms2u8SsF5zTJqyqoNXer7SgR4tt/XKvLQ+E=',
        'callback_url': 'https://your-ngrok-url.ngrok.io/api/v1/payments/mpesa/webhook/'
    }
)
```

### 2. Setup ngrok

```bash
ngrok http 8000
```

Copy the HTTPS URL and update the `callback_url` in PaymentProvider.

### 3. Test M-Pesa STK Push

```bash
curl -X POST http://localhost:8000/api/v1/payments/mpesa/stk-initiate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "msisdn": "254712345678",
    "amount": 100.00,
    "currency": "KES"
  }'
```

### 4. Test Card Payment

```bash
curl -X POST http://localhost:8000/api/v1/payments/card/initiate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "email": "customer@example.com",
    "amount": 100.00,
    "currency": "USD"
  }'
```

## Using Test Script

```bash
# Test M-Pesa
python test_payments.py --type mpesa --phone 254712345678 --amount 100 --currency KES

# Test Card
python test_payments.py --type card --email customer@example.com --amount 100 --currency USD
```

## Important Notes

- All payments now use Flutterwave (M-Pesa, Card, Mobile Money, Bank Transfer)
- M-Pesa payments are processed through Flutterwave's mobile money API
- Webhook URLs must be configured in Flutterwave dashboard
- Encryption key is used for webhook signature verification
