# Flutterwave Payment Integration Setup

This document explains how to configure Flutterwave for all payments (M-Pesa, Card, Mobile Money).

## Credentials Provided

- **Client ID**: `aa1c28d0-175a-41b8-83ab-f0a82d25f3de`
- **Client Secret**: `YKtJzGlz84wTXZ0SD0MnoknZLh3L76Qg`
- **Encryption Key**: `XQELn0YLms2u8SsF5zTJqyqoNXer7SgR4tt/XKvLQ+E=`

## Configuration Steps

### 1. Create Payment Provider in Database

You need to create a `PaymentProvider` record for each corporate organization. Here's an example using Django shell:

```python
from Payments.models import PaymentProvider
from OrgAuth.models import Corporate

# Get your corporate
corporate = Corporate.objects.get(id='your-corporate-id')

# Create Flutterwave payment provider
provider = PaymentProvider.objects.create(
    corporate=corporate,
    provider_type='flutterwave',
    provider_name='Flutterwave',
    is_active=True,
    test_mode=False,  # Set to True for testing
    config_json={
        'client_id': 'aa1c28d0-175a-41b8-83ab-f0a82d25f3de',
        'client_secret': 'YKtJzGlz84wTXZ0SD0MnoknZLh3L76Qg',
        'encryption_key': 'XQELn0YLms2u8SsF5zTJqyqoNXer7SgR4tt/XKvLQ+E=',
        'callback_url': 'https://your-domain.com/api/v1/payments/flutterwave/webhook/'
    }
)
```

### 2. Environment Variables (Optional)

Alternatively, you can set these in your `.env` file:

```env
FLUTTERWAVE_CLIENT_ID=aa1c28d0-175a-41b8-83ab-f0a82d25f3de
FLUTTERWAVE_CLIENT_SECRET=YKtJzGlz84wTXZ0SD0MnoknZLh3L76Qg
FLUTTERWAVE_ENCRYPTION_KEY=XQELn0YLms2u8SsF5zTJqyqoNXer7SgR4tt/XKvLQ+E=
```

### 3. Webhook Configuration

1. Log in to your Flutterwave dashboard
2. Go to Settings > Webhooks
3. Add webhook URL: `https://your-domain.com/api/v1/payments/flutterwave/webhook/`
4. Select events:
   - `charge.completed`
   - `charge.failed`
5. Copy the webhook secret hash (if provided) and add it to your `config_json`

### 4. Testing

#### Test M-Pesa Payment:
```bash
POST /api/v1/payments/mpesa/stk-initiate/
{
  "msisdn": "254712345678",
  "amount": 100.00,
  "currency": "KES",
  "invoice_id": "optional-invoice-uuid"
}
```

#### Test Card Payment:
```bash
POST /api/v1/payments/card/initiate/
{
  "email": "customer@example.com",
  "amount": 100.00,
  "currency": "USD",
  "invoice_id": "optional-invoice-uuid"
}
```

## Payment Methods Supported

Flutterwave adapter supports:
- **M-Pesa STK Push** (via `/mpesa/stk-initiate/`)
- **Card Payments** (via `/card/initiate/`)
- **Mobile Money** (via Flutterwave API)
- **Bank Transfer** (via Flutterwave API)

## Important Notes

1. **M-Pesa payments** are now handled through Flutterwave, not M-Pesa Daraja directly
2. All payments go through Flutterwave's unified API
3. Webhook verification uses the encryption key for HMAC-SHA256
4. Transaction references are auto-generated in format: `QUIDPATH-{uuid}`

## Important Notes

1. **All payments now use Flutterwave** - M-Pesa, Card, Mobile Money, Bank Transfer
2. **M-Pesa payments** are processed through Flutterwave's mobile money API
3. **Webhook verification** uses the encryption key for HMAC-SHA256
4. **Transaction references** are auto-generated in format: `QUIDPATH-{uuid}`

