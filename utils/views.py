"""
Utility views for common functionality across the application.
"""
import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

FRANKFURTER_BASE = 'https://api.frankfurter.app'
CACHE_TTL = 3600  # 1 hour in seconds


@api_view(['GET'])
@permission_classes([AllowAny])  # Public endpoint, no auth required
def get_currency_rates(request):
    """
    Proxy endpoint for fetching currency exchange rates from Frankfurter API.
    This avoids CORS issues by fetching rates server-side.
    
    Query Parameters:
        from: Base currency code (default: KES)
        to: Comma-separated list of target currencies (optional)
    
    Returns:
        JSON response with exchange rates relative to the base currency
        
    Example:
        GET /api/utils/currency/rates?from=KES
        Response: {
            "base": "KES",
            "date": "2026-04-23",
            "rates": {
                "KES": 1.0,
                "USD": 0.0077,
                "EUR": 0.0071,
                ...
            }
        }
    """
    base_currency = request.GET.get('from', 'KES').upper()
    target_currencies = request.GET.get('to', '').upper()
    
    # Create cache key
    cache_key = f'currency_rates_{base_currency}_{target_currencies}'
    
    # Try to get from cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f'Currency rates cache hit for {base_currency}')
        return Response(cached_data)
    
    try:
        # Build URL
        url = f'{FRANKFURTER_BASE}/latest?from={base_currency}'
        if target_currencies:
            url += f'&to={target_currencies}'
        
        # Fetch from Frankfurter API
        logger.info(f'Fetching currency rates from Frankfurter: {url}')
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Ensure the base currency itself is included as 1.0
        if 'rates' in data:
            data['rates'][base_currency] = 1.0
        
        # Add metadata for debugging
        data['cached'] = False
        data['fetched_at'] = cache.get(f'{cache_key}_timestamp') or 'just now'
        
        # Cache the response
        cache.set(cache_key, data, CACHE_TTL)
        cache.set(f'{cache_key}_timestamp', data.get('date', 'unknown'), CACHE_TTL)
        
        logger.info(f'Successfully fetched {len(data.get("rates", {}))} currency rates for {base_currency}')
        return Response(data)
        
    except requests.exceptions.Timeout:
        logger.error(f'Timeout fetching currency rates for {base_currency}')
        return Response(
            {
                'error': 'Currency service timeout',
                'message': 'The currency exchange service is taking too long to respond',
                'base': base_currency,
                'rates': {base_currency: 1.0}  # Fallback to base currency
            },
            status=status.HTTP_504_GATEWAY_TIMEOUT
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Error fetching currency rates: {str(e)}')
        return Response(
            {
                'error': 'Currency service unavailable',
                'message': 'Unable to fetch exchange rates at this time',
                'base': base_currency,
                'rates': {base_currency: 1.0}  # Fallback to base currency
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
        
    except Exception as e:
        logger.exception(f'Unexpected error fetching currency rates: {str(e)}')
        return Response(
            {
                'error': 'Internal server error',
                'message': 'An unexpected error occurred',
                'base': base_currency,
                'rates': {base_currency: 1.0}  # Fallback to base currency
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_supported_currencies(request):
    """
    Get list of supported currencies from Frankfurter API.
    
    Returns:
        JSON response with supported currency codes and names
    """
    cache_key = 'supported_currencies'
    
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return Response(cached_data)
    
    try:
        url = f'{FRANKFURTER_BASE}/currencies'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Cache for 24 hours (currencies don't change often)
        cache.set(cache_key, data, 86400)
        
        return Response(data)
        
    except Exception as e:
        logger.exception(f'Error fetching supported currencies: {str(e)}')
        # Return a minimal set of common currencies as fallback
        fallback = {
            'KES': 'Kenyan Shilling',
            'USD': 'United States Dollar',
            'EUR': 'Euro',
            'GBP': 'British Pound Sterling',
            'UGX': 'Ugandan Shilling',
            'TZS': 'Tanzanian Shilling',
        }
        return Response(fallback)
