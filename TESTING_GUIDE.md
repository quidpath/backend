# Testing Guide - Flutterwave Payments

## Overview

This guide explains how to test Flutterwave payments (M-Pesa STK Push and Card payments) locally before going live.

## Prerequisites

1. **Flutterwave Account**
   - Register at https://flutterwave.com/
   - Get Client ID, Client Secret, and Encryption Key
   - Configure webhook URL in Flutterwave dashboard

2. **Local Development Setup**
   - Django backend running
   - Frontend running
   - ngrok or similar for webhook callbacks (if testing locally)

## Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Flutterwave
FLUTTERWAVE_CLIENT_ID=your_client_id
FLUTTERWAVE_CLIENT_SECRET=your_client_secret
FLUTTERWAVE_ENCRYPTION_KEY=your_encryption_key
FLUTTERWAVE_TEST_MODE=True

# AWS SES (for email sending)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_SES_TEST_MODE=True

# SMS Provider (AfricasTalking example)
SMS_PROVIDER_TYPE=africas_talking
SMS_API_KEY=your_api_key
SMS_USERNAME=your_username
SMS_SENDER_ID=QUIDPATH
SMS_TEST_MODE=True
```

## Testing M-Pesa STK Push (via Flutterwave)

### 1. Setup Flutterwave

1. **Register at Flutterwave**
   - Go to https://flutterwave.com/
   - Create account and verify email
   - Get your API credentials from Settings > API Keys

2. **Get Credentials**
   - Client ID
   - Client Secret
   - Encryption Key (for webhook verification)

3. **Configure Webhook URL**
   - Use ngrok to expose local server: `ngrok http 8000`
   - Set webhook URL in Flutterwave dashboard: `https://your-ngrok-url.ngrok.io/api/v1/payments/mpesa/webhook/`
   - Select events: `charge.completed`, `charge.failed`

### 2. Create Payment Provider in Database

Run this in Django shell or create via admin:

```python
from Payments.models import PaymentProvider
from OrgAuth.models import Corporate

corporate = Corporate.objects.first()  # Your corporate

PaymentProvider.objects.create(
    corporate=corporate,
    provider_type='flutterwave',
    provider_name='Flutterwave',
    is_active=True,
    test_mode=True,
    config_json={
        'client_id': 'your_client_id',
        'client_secret': 'your_client_secret',
        'encryption_key': 'your_encryption_key',
        'callback_url': 'https://your-ngrok-url.ngrok.io/api/v1/payments/mpesa/webhook/'
    }
)
```

### 3. Test M-Pesa STK Push

Using curl:

```bash
curl -X POST http://localhost:8000/api/v1/payments/mpesa/stk-initiate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "msisdn": "254712345678",
    "amount": 100.00,
    "currency": "KES",
    "callback_url": "https://your-ngrok-url.ngrok.io/api/v1/payments/mpesa/webhook/"
  }'
```

Or using the test script:

```bash
python test_payments.py --type mpesa --phone 254712345678 --amount 100 --currency KES
```

## Testing Card Payments (via Flutterwave)

### 1. Setup Flutterwave

Same as M-Pesa setup above.

### 2. Test Card Payment

Using curl:

```bash
curl -X POST http://localhost:8000/api/v1/payments/card/initiate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "email": "customer@example.com",
    "amount": 100.00,
    "currency": "USD",
    "callback_url": "https://your-ngrok-url.ngrok.io/api/v1/payments/card/webhook/"
  }'
```

Or using the test script:

```bash
python test_payments.py --type card --email customer@example.com --amount 100 --currency USD
```

## Webhook Testing

### 1. Setup ngrok

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 2. Update Webhook URL

- In Flutterwave dashboard, set webhook URL to: `https://your-ngrok-url.ngrok.io/api/v1/payments/mpesa/webhook/`
- Also set card webhook URL: `https://your-ngrok-url.ngrok.io/api/v1/payments/card/webhook/`

### 3. Test Webhook

Flutterwave will automatically send webhooks when payments are completed. You can also use their webhook testing tool in the dashboard.

## Troubleshooting

### M-Pesa STK Push Issues

1. **No prompt received**
   - Check if phone number is correct (format: 254XXXXXXXXX)
   - Verify Flutterwave account is active
   - Check Flutterwave dashboard for transaction status

2. **Payment fails**
   - Check Flutterwave dashboard for error details
   - Verify account has sufficient balance (for test mode)
   - Check webhook logs

3. **Webhook not received**
   - Verify ngrok is running
   - Check webhook URL in Flutterwave dashboard
   - Verify webhook signature verification (check encryption key)

### Card Payment Issues

1. **Checkout URL not working**
   - Verify Flutterwave credentials are correct
   - Check if test mode is enabled
   - Verify redirect URL is configured

2. **Payment not completing**
   - Check Flutterwave dashboard for transaction status
   - Verify webhook is configured correctly
   - Check webhook logs

## Production Checklist

Before going live:

- [ ] Switch to live Flutterwave credentials
- [ ] Update webhook URLs to production URLs
- [ ] Test with real M-Pesa numbers
- [ ] Test with real card payments
- [ ] Verify webhook signature verification
- [ ] Set up monitoring and alerts
- [ ] Test error handling and edge cases
