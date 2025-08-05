import json
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from django.http import JsonResponse, HttpResponse
from django.db import models
from django.core.files.base import File

from .registry import ServiceRegistry
from .superserializer import json_super_serializer


def comprehensive_serializer(obj):
    """
    Comprehensive serializer that handles all common Django/Python objects
    """
    # Handle UUID
    if isinstance(obj, UUID):
        return str(obj)

    # Handle datetime objects
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # Handle Decimal
    if isinstance(obj, Decimal):
        return float(obj)

    # Handle Django model instances
    if isinstance(obj, models.Model):
        # Convert model instance to dictionary
        result = {}
        for field in obj._meta.fields:
            field_name = field.name
            field_value = getattr(obj, field_name)

            # Handle different field types
            if isinstance(field_value, models.Model):
                # Foreign key - just return the ID
                result[f"{field_name}_id"] = str(field_value.pk) if field_value.pk else None
            elif isinstance(field_value, (datetime, date)):
                result[field_name] = field_value.isoformat() if field_value else None
            elif isinstance(field_value, UUID):
                result[field_name] = str(field_value)
            elif isinstance(field_value, Decimal):
                result[field_name] = float(field_value)
            elif isinstance(field_value, File):
                result[field_name] = field_value.url if field_value else None
            else:
                result[field_name] = field_value

        return result

    # Handle File fields
    if isinstance(obj, File):
        return obj.url if obj else None

    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        return [comprehensive_serializer(item) for item in obj]

    # Handle dictionaries
    if isinstance(obj, dict):
        return {key: comprehensive_serializer(value) for key, value in obj.items()}

    # Handle sets
    if isinstance(obj, set):
        return list(obj)

    # If none of the above, try the original superserializer
    try:
        return json_super_serializer(obj)
    except:
        # Last resort - convert to string
        return str(obj)


class ResponseProvider:
    """Provides standardized JSON responses.

    Status Codes:
    400 - Bad Request
    200 - Success
    401 - Unauthorized Access
    500 - Internal Server Error
    """

    def __init__(self, data=None, message=None, code=None):
        self.data = data or {}
        if message:
            self.data["code"] = code
            self.data["message"] = message
        self.registry = ServiceRegistry()

    def _response(self, status):
        """Internal method to create JsonResponse with proper serialization"""
        return JsonResponse(
            self.data,
            status=status,
            json_dumps_params={'default': comprehensive_serializer},
            safe=False  # Allow non-dict objects to be serialized
        )

    def success(self):
        """Return a success response (200) with comprehensive serialization"""
        try:
            # Serialize the data first to catch any serialization errors
            serialized_data = json.loads(json.dumps(self.data, default=comprehensive_serializer))

            return JsonResponse(
                serialized_data,
                status=200,
                json_dumps_params={'default': comprehensive_serializer},
                safe=False
            )
        except Exception as e:
            # Log the error and return a safe error response
            error_response = {
                "code": 500,
                "message": "Serialization error occurred",
                "error": str(e)
            }
            return JsonResponse(error_response, status=500)

    def bad_request(self):
        """Return a bad request response (400)."""
        return self._response(status=400)

    def unauthorized(self):
        """Return an unauthorized response (401)."""
        return self._response(status=401)

    def exception(self):
        """Return an internal server error response (500)."""
        return self._response(status=500)