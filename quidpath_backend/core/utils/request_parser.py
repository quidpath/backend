# core/utils/request_parser.py
import json
import logging

import jwt
from django.contrib.auth import get_user_model
from django.http import QueryDict
from rest_framework_simplejwt.tokens import AccessToken

import quidpath_backend
from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser
from quidpath_backend.settings import base as settings

logger = logging.getLogger(__name__)


def get_clean_data_safe(request, allowed_methods=None, require_json_body=True, max_body_length=1024 * 1024):
    """
    Parse and validate request: method check and optional JSON body.
    Returns (data, error_response). If error_response is not None, return it from the view.
    For GET, data is request.GET as dict; for POST/PUT/PATCH, data is parsed JSON body.
    """
    if allowed_methods is None:
        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    from quidpath_backend.core.utils.json_response import ResponseProvider

    if request.method not in allowed_methods:
        return None, ResponseProvider.method_not_allowed(allowed_methods)

    data = None
    if require_json_body and request.method in ("POST", "PUT", "PATCH") and request.body:
        if len(request.body) > max_body_length:
            return None, ResponseProvider.error_response("Request body too large", status=413)
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Invalid JSON body: %s", e)
            return None, ResponseProvider.error_response("Invalid JSON body", status=400)
        if not isinstance(data, dict):
            return None, ResponseProvider.error_response("JSON body must be an object", status=400)
    elif request.method == "GET":
        data = dict(request.GET.items())

    return data, None


def get_request_data(request):
    try:
        if request is None:
            return {}

        content_type = request.META.get("CONTENT_TYPE", "")
        method = request.method.upper()

        if "application/json" in content_type:
            return json.loads(request.body or "{}")
        elif "multipart/form-data" in content_type:
            return request.POST.dict()
        elif method == "GET":
            return request.GET.dict()
        elif method == "POST":
            return request.POST.dict()
        elif request.body:
            return json.loads(request.body)

        return {}
    except json.JSONDecodeError:
        return {}
    except Exception as e:
        raise ValueError(f"Error parsing request data: {e}")


def get_data(request):
    data = get_request_data(request)

    metadata = {
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT"),
        "origin": request.META.get("HTTP_ORIGIN"),
    }
    return data, metadata


def get_clean_data(request):
    data = get_request_data(request)
    user, corporate_user = resolve_user_from_token(request)

    metadata = {
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT"),
        "origin": request.META.get("HTTP_ORIGIN"),
        "user": user,
        "corporate_user": corporate_user,
        "role": getattr(corporate_user, "role", None),
        "organisation_id": getattr(corporate_user, "corporate_id", None),
    }

    return data, metadata


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def resolve_user_from_token(request):
    try:
        token = request.headers.get("Authorization", "").split("Bearer ")[-1].strip()

        if not token:
            return None, None

        access_token = AccessToken(token)
        user_id = access_token.get("user_id")

        if not user_id:
            return None, None

        user = CustomUser.objects.filter(id=user_id).first()

        # Fix: Correct way to get CorporateUser if it inherits from CustomUser
        corporate_user = (
            CorporateUser.objects.filter(pk=user.pk).first() if user else None
        )

        return user, corporate_user

    except Exception as e:
        print("Token decode error:", e)
        return None, None
