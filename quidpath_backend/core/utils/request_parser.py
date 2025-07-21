# core/utils/request_parser.py
import json
from django.http import QueryDict

def get_request_data(request):
    """
    Parse incoming request data safely with support for JSON, form-data, and query params.
    """
    try:
        if request is None:
            return {}

        content_type = request.META.get('CONTENT_TYPE', '')
        method = request.method.upper()

        # JSON request
        if 'application/json' in content_type:
            return json.loads(request.body or '{}')

        # Multipart form-data
        elif 'multipart/form-data' in content_type:
            return request.POST.dict()

        # Standard GET/POST form requests
        elif method == 'GET':
            return request.GET.dict()
        elif method == 'POST':
            return request.POST.dict()

        # Fallback: attempt JSON
        elif request.body:
            return json.loads(request.body)

        return {}
    except json.JSONDecodeError:
        return {}
    except Exception as e:
        raise ValueError(f"Error parsing request data: {e}")


def get_clean_data(request):
    """
    Parse request data and clean headers for safe logging.
    """
    data = get_request_data(request)

    # Capture only important headers for metadata
    metadata = {
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT"),
        "origin": request.META.get("HTTP_ORIGIN"),
    }

    return data, metadata


def get_client_ip(request):
    """Extract client IP from request META."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
