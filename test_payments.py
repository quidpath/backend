#!/usr/bin/env python
"""
Test script for Flutterwave payments (M-Pesa and Card).

Usage:
    python test_payments.py --type mpesa
    python test_payments.py --type card
"""

import requests
import json
import argparse
import sys

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE_URL = f"{BASE_URL}/api/v1/payments/"

# Test credentials (replace with your actual credentials)
TEST_MPESA_PHONE = "254712345678"  # Replace with your test M-Pesa number
TEST_CARD_EMAIL = "test@example.com"  # Replace with test email
TEST_AMOUNT = 100.00
TEST_CURRENCY_MPESA = "KES"
TEST_CURRENCY_CARD = "USD"

# You'll need to get an access token from your login endpoint
ACCESS_TOKEN = None  # Set this after logging in


def get_headers():
    """Get request headers with authentication."""
    headers = {
        "Content-Type": "application/json",
    }
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    return headers


def test_mpesa_stk_push():
    """Test M-Pesa STK Push via Flutterwave."""
    print("\n=== Testing M-Pesa STK Push (Flutterwave) ===\n")
    
    # Check if PaymentProvider is configured
    print("Note: Ensure you have created a PaymentProvider with:")
    print("  - provider_type='flutterwave'")
    print("  - config_json with client_id, client_secret, encryption_key")
    print()
    
    url = f"{API_BASE_URL}mpesa/stk-initiate/"
    
    payload = {
        "msisdn": TEST_MPESA_PHONE,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY_MPESA,
        "callback_url": f"{BASE_URL}/api/v1/payments/mpesa/webhook/"
    }
    
    print(f"Request URL: {url}")
    print(f"Request Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=30)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200:
                print("\n✅ STK Push initiated successfully!")
                print(f"Payment ID: {data.get('data', {}).get('payment_id')}")
                print(f"Checkout Request ID: {data.get('data', {}).get('checkout_request_id')}")
                print("\n📱 Check your phone for the M-Pesa prompt!")
            else:
                print(f"\n❌ Failed: {data.get('message')}")
        else:
            print(f"\n❌ Request failed with status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")


def test_card_payment():
    """Test Card payment via Flutterwave."""
    print("\n=== Testing Card Payment (Flutterwave) ===\n")
    
    # Check if PaymentProvider is configured
    print("Note: Ensure you have created a PaymentProvider with:")
    print("  - provider_type='flutterwave'")
    print("  - config_json with client_id, client_secret, encryption_key")
    print()
    
    url = f"{API_BASE_URL}card/initiate/"
    
    payload = {
        "email": TEST_CARD_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY_CARD,
        "callback_url": f"{BASE_URL}/api/v1/payments/card/webhook/"
    }
    
    print(f"Request URL: {url}")
    print(f"Request Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=30)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200:
                print("\n✅ Card payment initiated successfully!")
                print(f"Payment ID: {data.get('data', {}).get('payment_id')}")
                checkout_url = data.get('data', {}).get('checkout_url')
                if checkout_url:
                    print(f"Checkout URL: {checkout_url}")
                    print("\n💳 Redirect to checkout URL to complete payment!")
            else:
                print(f"\n❌ Failed: {data.get('message')}")
        else:
            print(f"\n❌ Request failed with status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description='Test Flutterwave payments')
    parser.add_argument('--type', choices=['mpesa', 'card'], required=True,
                       help='Payment type to test')
    parser.add_argument('--token', type=str, help='Access token for authentication')
    parser.add_argument('--phone', type=str, help='M-Pesa phone number (for M-Pesa test)')
    parser.add_argument('--email', type=str, help='Email address (for card test)')
    parser.add_argument('--amount', type=float, help='Payment amount')
    parser.add_argument('--currency', type=str, help='Currency code')
    
    args = parser.parse_args()
    
    global ACCESS_TOKEN, TEST_MPESA_PHONE, TEST_CARD_EMAIL, TEST_AMOUNT, TEST_CURRENCY_MPESA, TEST_CURRENCY_CARD
    
    if args.token:
        ACCESS_TOKEN = args.token
    if args.phone:
        TEST_MPESA_PHONE = args.phone
    if args.email:
        TEST_CARD_EMAIL = args.email
    if args.amount:
        TEST_AMOUNT = args.amount
    if args.currency:
        if args.type == 'mpesa':
            TEST_CURRENCY_MPESA = args.currency
        else:
            TEST_CURRENCY_CARD = args.currency
    
    if args.type == 'mpesa':
        test_mpesa_stk_push()
    elif args.type == 'card':
        test_card_payment()
    else:
        print("Invalid payment type. Use --type mpesa or --type card")
        sys.exit(1)


if __name__ == "__main__":
    main()
