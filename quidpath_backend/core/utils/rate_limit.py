"""
Simple IP-based rate limiting using Django's cache framework.
Limits to 5 requests per minute per IP by default.
"""
import functools
import hashlib
import logging

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def rate_limit(max_requests: int = 5, window_seconds: int = 60, key_prefix: str = "rl"):
    """
    Decorator that limits a view to max_requests per window_seconds per IP.
    Returns 429 when limit is exceeded.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = get_client_ip(request)
            # Hash the IP to avoid storing raw IPs in cache
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
            cache_key = f"{key_prefix}:{view_func.__name__}:{ip_hash}"

            count = cache.get(cache_key, 0)
            if count >= max_requests:
                logger.warning(f"Rate limit exceeded for {view_func.__name__} from {ip_hash}")
                return JsonResponse(
                    {
                        "error": "Too many requests",
                        "message": f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds.",
                        "retry_after": window_seconds,
                    },
                    status=429,
                )

            # Increment counter; set expiry only on first request
            if count == 0:
                cache.set(cache_key, 1, timeout=window_seconds)
            else:
                cache.incr(cache_key)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
