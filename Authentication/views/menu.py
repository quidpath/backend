# Authentication/views/menu.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework_simplejwt.authentication import JWTAuthentication

from Authentication.models import CustomUser, ModulePermission
from OrgAuth.models import CorporateUser
from quidpath_backend.core.utils.json_response import ResponseProvider


def build_menu_for_user(user):
    """
    Build sidebar menu sections for the user based on their role's module_permissions.
    Superuser gets all modules from ModulePermission.
    Regular users get modules based on their role's module_permissions.
    
    Returns list of { id, label, path, icon, children?: [ { id, label, path } ] }.
    """
    # Check if user is superuser (handles both dict and model objects)
    if isinstance(user, dict):
        is_superuser = user.get("is_superuser", False)
    else:
        is_superuser = getattr(user, "is_superuser", False)
    
    if is_superuser:
        # Superuser gets ALL modules from ModulePermission
        qs = ModulePermission.objects.filter(parent__isnull=True).order_by("sort_order", "name")
        allowed_ids = set(ModulePermission.objects.values_list("id", flat=True))
    else:
        # Regular users - check corporate association
        corporate_user = CorporateUser.objects.filter(id=user.id).select_related("role").first()
        if not corporate_user or not corporate_user.role_id:
            return []
        role = corporate_user.role
        allowed_ids = set(role.module_permissions.values_list("id", flat=True))
        qs = ModulePermission.objects.filter(
            id__in=allowed_ids, parent__isnull=True
        ).order_by("sort_order", "name")

    sections = []
    for perm in qs:
        children = []
        for child in perm.children.filter(id__in=allowed_ids).order_by("sort_order", "name"):
            children.append({
                "id": child.codename,
                "label": child.name,
                "path": child.path,
            })
        sections.append({
            "id": perm.codename,
            "label": perm.name,
            "path": perm.path,
            "icon": perm.icon_slug or None,
            "children": children,
        })
    return sections


@csrf_exempt
@require_GET
def get_menu(request):
    """GET /menu/ - Returns nav sections for the authenticated user (Bearer token required)."""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return ResponseProvider(
            {"error": "Missing or invalid Authorization header"}, "Unauthorized", 401
        ).unauthorized()

    token = auth_header.split(" ")[1].strip()
    jwt_auth = JWTAuthentication()
    try:
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
    except Exception:
        return ResponseProvider(
            {"error": "Invalid or expired token"}, "Unauthorized", 401
        ).unauthorized()

    if not user:
        return ResponseProvider({"error": "User not found"}, "Unauthorized", 401).unauthorized()

    corporate_user = CorporateUser.objects.filter(id=user.id).first()
    sections = build_menu_for_user(user)
    return ResponseProvider(
        {"sections": sections},
        "OK",
        200,
    ).success()
