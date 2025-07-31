import json

from django.http import JsonResponse, HttpResponse
from .registry import ServiceRegistry

import json
from uuid import UUID

from .superserializer import json_super_serializer


def uuid_converter(o):
    if isinstance(o, UUID):
        return str(o)
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

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
		return JsonResponse(self.data, status=status, json_dumps_params={'default': json_super_serializer})

	def success(self):
		try:
			# Use the custom encoder
			json_data = json.dumps(self.data, default=uuid_converter)
			return HttpResponse(json_data, content_type="application/json")
		except Exception as e:
			# Handle or log the error appropriately
			return HttpResponse(json.dumps({"error": str(e)}), content_type="application/json")

	def bad_request(self):
		"""Return a bad request response (400)."""
		return self._response(status=400)

	def unauthorized(self):
		"""Return an unauthorized response (401)."""
		return self._response(status=401)

	def exception(self):
		"""Return an internal server error response (500)."""
		return self._response(status=500)