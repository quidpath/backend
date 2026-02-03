"""
Microservice API Views
Provides endpoints for microservices to validate users and fetch data
"""

from functools import wraps

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from Authentication.models import CustomUser
from OrgAuth.models import Corporate, CorporateUser


def require_service_key(view_func):
    """Decorator to validate service API key"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        service_key = request.headers.get("X-Service-Key")

        # Get valid service keys from settings
        valid_keys = getattr(settings, "SERVICE_API_KEYS", {}).values()

        if not service_key or service_key not in valid_keys:
            return Response(
                {"error": "Invalid or missing service API key"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


@api_view(["GET"])
@require_service_key
def get_user_details(request, user_id):
    """
    Get user details for microservices

    Args:
        user_id: UUID of the user

    Returns:
        User details including corporate information
    """
    user = get_object_or_404(CustomUser, id=user_id)

    # Check if user is a CorporateUser
    corporate_user = None
    corporate_data = None
    try:
        corporate_user = CorporateUser.objects.select_related("corporate", "role").get(
            customuser_ptr_id=user_id
        )
        corporate_data = {
            "id": str(corporate_user.corporate.id),
            "name": corporate_user.corporate.name,
            "industry": corporate_user.corporate.industry,
            "company_size": corporate_user.corporate.company_size,
            "email": corporate_user.corporate.email,
            "phone": corporate_user.corporate.phone,
            "is_active": corporate_user.corporate.is_active,
            "is_approved": corporate_user.corporate.is_approved,
            "is_verified": corporate_user.corporate.is_verified,
        }
    except CorporateUser.DoesNotExist:
        pass

    return Response(
        {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "address": user.address,
            "city": user.city,
            "country": user.country,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "corporate": corporate_data,
            "role": (
                corporate_user.role.name
                if corporate_user and corporate_user.role
                else None
            ),
        }
    )


@api_view(["GET"])
@require_service_key
def get_corporate_details(request, corporate_id):
    """
    Get corporate details for microservices

    Args:
        corporate_id: UUID of the corporate

    Returns:
        Corporate details
    """
    corporate = get_object_or_404(Corporate, id=corporate_id)

    return Response(
        {
            "id": str(corporate.id),
            "name": corporate.name,
            "industry": corporate.industry,
            "company_size": corporate.company_size,
            "registration_number": corporate.registration_number,
            "tax_id": corporate.tax_id,
            "description": corporate.description,
            "website": corporate.website,
            "email": corporate.email,
            "phone": corporate.phone,
            "address": corporate.address,
            "city": corporate.city,
            "state": corporate.state,
            "country": corporate.country,
            "zip_code": corporate.zip_code,
            "is_active": corporate.is_active,
            "is_approved": corporate.is_approved,
            "is_verified": corporate.is_verified,
            "created_at": (
                corporate.created_at.isoformat()
                if hasattr(corporate, "created_at")
                else None
            ),
        }
    )


@api_view(["POST"])
@require_service_key
def batch_get_users(request):
    """
    Get multiple user details in a single request

    Request body:
        {
            "user_ids": ["uuid1", "uuid2", ...]
        }

    Returns:
        List of user details
    """
    user_ids = request.data.get("user_ids", [])

    if not user_ids or not isinstance(user_ids, list):
        return Response(
            {"error": "user_ids must be a non-empty list"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    users = CustomUser.objects.filter(id__in=user_ids)
    corporate_users = CorporateUser.objects.filter(
        customuser_ptr_id__in=user_ids
    ).select_related("corporate", "role")

    # Create a mapping of user_id to corporate_user
    corporate_user_map = {str(cu.customuser_ptr_id): cu for cu in corporate_users}

    result = []
    for user in users:
        corporate_user = corporate_user_map.get(str(user.id))
        corporate_data = None

        if corporate_user:
            corporate_data = {
                "id": str(corporate_user.corporate.id),
                "name": corporate_user.corporate.name,
                "industry": corporate_user.corporate.industry,
                "is_active": corporate_user.corporate.is_active,
            }

        result.append(
            {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "corporate": corporate_data,
                "role": (
                    corporate_user.role.name
                    if corporate_user and corporate_user.role
                    else None
                ),
            }
        )

    return Response({"users": result})


@api_view(["POST"])
@require_service_key
def batch_get_corporates(request):
    """
    Get multiple corporate details in a single request

    Request body:
        {
            "corporate_ids": ["uuid1", "uuid2", ...]
        }

    Returns:
        List of corporate details
    """
    corporate_ids = request.data.get("corporate_ids", [])

    if not corporate_ids or not isinstance(corporate_ids, list):
        return Response(
            {"error": "corporate_ids must be a non-empty list"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    corporates = Corporate.objects.filter(id__in=corporate_ids)

    result = [
        {
            "id": str(corp.id),
            "name": corp.name,
            "industry": corp.industry,
            "company_size": corp.company_size,
            "email": corp.email,
            "phone": corp.phone,
            "is_active": corp.is_active,
            "is_approved": corp.is_approved,
        }
        for corp in corporates
    ]

    return Response({"corporates": result})
