# Flutterwave Credentials Configuration

## Credentials Provided

- **Client ID**: `aa1c28d0-175a-41b8-83ab-f0a82d25f3de`
- **Client Secret**: `YKtJzGlz84wTXZ0SD0MnoknZLh3L76Qg`
- **Encryption Key**: `XQELn0YLms2u8SsF5zTJqyqoNXer7SgR4tt/XKvLQ+E=`

## Database Configuration

To configure Flutterwave for your corporate, create a PaymentProvider record:

```python
from Payments.models import PaymentProvider
from OrgAuth.models import Corporate

corporate = Corporate.objects.get(id='your-corporate-id')

PaymentProvider.objects.create(
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

## Important Notes

1. **All payments now use Flutterwave** - M-Pesa, Card, Mobile Money, Bank Transfer
2. **M-Pesa payments** are processed through Flutterwave's mobile money API
3. **Webhook URL** must be configured in Flutterwave dashboard
4. **Encryption Key** is used for webhook signature verification

## API Endpoints

- **M-Pesa STK Push**: `POST /mpesa/stk-initiate/`
- **Card Payment**: `POST /card/initiate/`
- **M-Pesa Webhook**: `POST /mpesa/webhook/`
- **Card Webhook**: `POST /card/webhook/`








