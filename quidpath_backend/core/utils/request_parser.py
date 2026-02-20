# core/utils/request_parser.py
import json

import jwt
from django.contrib.auth import get_user_model
from django.http import QueryDict
from rest_framework_simplejwt.tokens import AccessToken

import quidpath_backend
from Authentication.models import CustomUser
from OrgAuth.models import CorporateUser
from quidpath_backend.settings import base as settings


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
