"""
Role and Permission Management API

Access rules:
- SUPERUSER (is_superuser=True): full access to all roles across all corporates;
  can filter by corporate via ?corporate_id=
- SUPERADMIN role: can manage roles scoped to their own corporate only
- All other users: 403
"""
import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from Authentication.models.role import Role
from Authentication.models.module_permission import ModulePermission
from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.utils.request_parser import resolve_user_from_token
from quidpath_backend.core.utils.Logbase import TransactionLogBase

SYSTEM_ROLES = {"SUPERADMIN", "SUPERUSER"}


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _resolve_caller(request):
    """Returns (user, corporate_user, is_superuser, corporate_id)."""
    user, corporate_user = resolve_user_from_token(request)
    if not user:
        return None, None, False, None
    is_su = getattr(user, "is_superuser", False) or (
        isinstance(user, dict) and user.get("is_superuser", False)
    )
    corp_id = None
    if not is_su and corporate_user:
        corp_id = getattr(corporate_user, "corporate_id", None)
    return user, corporate_user, is_su, corp_id


def require_role_admin(view_func):
    """Allow Django superusers OR SUPERADMIN role users."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user, corporate_user, is_su, corp_id = _resolve_caller(request)
        if not user:
            return JsonResponse({"error": "Authentication required"}, status=401)
        if is_su:
            return view_func(request, *args, **kwargs)
        if corporate_user and corporate_user.role and corporate_user.role.name == "SUPERADMIN":
            return view_func(request, *args, **kwargs)
        return JsonResponse({"error": "Admin access required"}, status=403)
    return wrapped


def require_superuser_only(view_func):
    """Allow only Django superusers (is_superuser=True)."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user, _, is_su, _ = _resolve_caller(request)
        if not user:
            return JsonResponse({"error": "Authentication required"}, status=401)
        if not is_su:
            return JsonResponse({"error": "Superuser access required"}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapped


# ── Helpers ───────────────────────────────────────────────────────────────────

def _role_to_dict(role):
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description or "",
        "corporate_id": str(role.corporate_id) if role.corporate_id else None,
        "corporate_name": role.corporate.name if role.corporate else "System",
        "permissions": list(role.module_permissions.values(
            "id", "codename", "name", "module_slug"
        )),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@csrf_exempt
@require_role_admin
def list_all_roles(request):
    """
    SUPERUSER: returns all roles; accepts ?corporate_id= to filter.
    SUPERADMIN: returns only their corporate's roles.
    """
    user, corporate_user, is_su, corp_id = _resolve_caller(request)
    try:
        qs = Role.objects.prefetch_related("module_permissions", "corporate").all()
        if is_su:
            # Optional filter by corporate
            filter_corp = request.GET.get("corporate_id")
            if filter_corp:
                qs = qs.filter(corporate_id=filter_corp)
        else:
            # SUPERADMIN: only their corporate's roles
            qs = qs.filter(corporate_id=corp_id)

        return JsonResponse({"roles": [_role_to_dict(r) for r in qs]}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_role_admin
def list_all_permissions(request):
    """List all available module permissions (both SUPERUSER and SUPERADMIN)."""
    try:
        perms = ModulePermission.objects.all().order_by("sort_order", "name")
        return JsonResponse({
            "permissions": list(perms.values(
                "id", "codename", "name", "module_slug", "path", "icon_slug", "sort_order"
            ))
        }, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_superuser_only
def list_corporates_for_roles(request):
    """SUPERUSER only: list all corporates for the dropdown."""
    try:
        corps = Corporate.objects.filter(is_active=True).values("id", "name")
        return JsonResponse({"corporates": list(corps)}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_role_admin
def create_role(request):
    """
    SUPERADMIN: creates a role scoped to their corporate.
    SUPERUSER: must supply corporate_id in body.
    Cannot create SUPERADMIN or SUPERUSER roles.
    """
    user, corporate_user, is_su, corp_id = _resolve_caller(request)
    try:
        body = json.loads(request.body)
        name = body.get("name", "").strip()
        description = body.get("description", "").strip()
        permission_ids = body.get("permission_ids", [])

        if not name:
            return JsonResponse({"error": "Role name is required"}, status=400)

        if name.upper() in SYSTEM_ROLES:
            return JsonResponse({"error": "Cannot create system roles"}, status=403)

        # Determine corporate
        if is_su:
            target_corp_id = body.get("corporate_id")
            if not target_corp_id:
                return JsonResponse({"error": "corporate_id is required for superuser"}, status=400)
            try:
                corporate = Corporate.objects.get(id=target_corp_id)
            except Corporate.DoesNotExist:
                return JsonResponse({"error": "Corporate not found"}, status=404)
        else:
            corporate = corporate_user.corporate

        if Role.objects.filter(name__iexact=name, corporate=corporate).exists():
            return JsonResponse({"error": "Role with this name already exists for this corporate"}, status=400)

        role = Role.objects.create(name=name, description=description, corporate=corporate)
        if permission_ids:
            role.module_permissions.set(ModulePermission.objects.filter(id__in=permission_ids))

        TransactionLogBase.log("ROLE_CREATED", user=user,
            message=f"Created role '{name}' for corporate '{corporate.name}'")

        return JsonResponse({"message": "Role created successfully", "role": _role_to_dict(role)}, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_role_admin
def update_role(request):
    """
    SUPERADMIN: can only update roles belonging to their corporate.
    SUPERUSER: can update any role.
    Cannot modify SUPERUSER system role.
    """
    user, corporate_user, is_su, corp_id = _resolve_caller(request)
    try:
        body = json.loads(request.body)
        role_id = body.get("role_id")
        if not role_id:
            return JsonResponse({"error": "role_id is required"}, status=400)

        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({"error": "Role not found"}, status=404)

        if role.name == "SUPERUSER":
            return JsonResponse({"error": "Cannot modify SUPERUSER system role"}, status=403)

        # SUPERADMIN can only touch their own corporate's roles
        if not is_su and str(role.corporate_id) != str(corp_id):
            return JsonResponse({"error": "Cannot modify roles from another corporate"}, status=403)

        name = body.get("name", "").strip()
        if name:
            if name.upper() in SYSTEM_ROLES and role.name.upper() not in SYSTEM_ROLES:
                return JsonResponse({"error": "Cannot rename to a system role name"}, status=403)
            if Role.objects.filter(name__iexact=name, corporate=role.corporate).exclude(id=role_id).exists():
                return JsonResponse({"error": "Role name already exists for this corporate"}, status=400)
            role.name = name

        if "description" in body:
            role.description = body["description"]
        role.save()

        if "permission_ids" in body:
            role.module_permissions.set(ModulePermission.objects.filter(id__in=body["permission_ids"]))

        TransactionLogBase.log("ROLE_UPDATED", user=user, message=f"Updated role '{role.name}'")
        return JsonResponse({"message": "Role updated successfully", "role": _role_to_dict(role)}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_role_admin
def delete_role(request):
    """
    SUPERADMIN: can only delete roles belonging to their corporate.
    SUPERUSER: can delete any non-system role.
    Cannot delete SUPERADMIN, SUPERUSER, or ADMIN.
    """
    user, corporate_user, is_su, corp_id = _resolve_caller(request)
    try:
        body = json.loads(request.body)
        role_id = body.get("role_id")
        if not role_id:
            return JsonResponse({"error": "role_id is required"}, status=400)

        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({"error": "Role not found"}, status=404)

        if role.name.upper() in {"SUPERADMIN", "SUPERUSER", "ADMIN"}:
            return JsonResponse({"error": "Cannot delete system role"}, status=403)

        if not is_su and str(role.corporate_id) != str(corp_id):
            return JsonResponse({"error": "Cannot delete roles from another corporate"}, status=403)

        user_count = CorporateUser.objects.filter(role=role).count()
        if user_count > 0:
            return JsonResponse({"error": f"Cannot delete: role assigned to {user_count} user(s)"}, status=400)

        role_name = role.name
        role.delete()
        TransactionLogBase.log("ROLE_DELETED", user=user, message=f"Deleted role '{role_name}'")
        return JsonResponse({"message": "Role deleted successfully"}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_role_admin
def add_permission_to_role(request):
    """Add a permission to a role. SUPERADMIN scoped to their corporate."""
    user, corporate_user, is_su, corp_id = _resolve_caller(request)
    try:
        body = json.loads(request.body)
        role_id = body.get("role_id")
        permission_id = body.get("permission_id")
        if not role_id or not permission_id:
            return JsonResponse({"error": "role_id and permission_id are required"}, status=400)

        role = Role.objects.get(id=role_id)
        permission = ModulePermission.objects.get(id=permission_id)

        if not is_su and str(role.corporate_id) != str(corp_id):
            return JsonResponse({"error": "Cannot modify roles from another corporate"}, status=403)

        role.module_permissions.add(permission)
        TransactionLogBase.log("PERMISSION_ADDED", user=user,
            message=f"Added '{permission.name}' to role '{role.name}'")
        return JsonResponse({"message": "Permission added successfully"}, status=200)
    except (Role.DoesNotExist, ModulePermission.DoesNotExist):
        return JsonResponse({"error": "Role or Permission not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_role_admin
def remove_permission_from_role(request):
    """Remove a permission from a role. SUPERADMIN scoped to their corporate."""
    user, corporate_user, is_su, corp_id = _resolve_caller(request)
    try:
        body = json.loads(request.body)
        role_id = body.get("role_id")
        permission_id = body.get("permission_id")
        if not role_id or not permission_id:
            return JsonResponse({"error": "role_id and permission_id are required"}, status=400)

        role = Role.objects.get(id=role_id)
        permission = ModulePermission.objects.get(id=permission_id)

        if not is_su and str(role.corporate_id) != str(corp_id):
            return JsonResponse({"error": "Cannot modify roles from another corporate"}, status=403)

        role.module_permissions.remove(permission)
        TransactionLogBase.log("PERMISSION_REMOVED", user=user,
            message=f"Removed '{permission.name}' from role '{role.name}'")
        return JsonResponse({"message": "Permission removed successfully"}, status=200)
    except (Role.DoesNotExist, ModulePermission.DoesNotExist):
        return JsonResponse({"error": "Role or Permission not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
