"""
Role and Permission Management API
Only accessible by Django superusers
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from Authentication.models.role import Role
from Authentication.models.module_permission import ModulePermission
from quidpath_backend.core.utils.decorators import require_superuser
from quidpath_backend.core.utils.Logbase import TransactionLogBase


@csrf_exempt
@require_superuser
def list_all_roles(request):
    """List all roles with their permissions"""
    try:
        roles = Role.objects.prefetch_related('module_permissions').all()
        result = []
        for role in roles:
            result.append({
                'id': role.id,
                'name': role.name,
                'description': role.description or '',
                'permissions': list(role.module_permissions.values('id', 'codename', 'name', 'module_slug'))
            })
        return JsonResponse({'roles': result}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_superuser
def list_all_permissions(request):
    """List all available module permissions"""
    try:
        permissions = ModulePermission.objects.all().order_by('sort_order', 'name')
        result = list(permissions.values('id', 'codename', 'name', 'module_slug', 'path', 'icon_slug', 'sort_order'))
        return JsonResponse({'permissions': result}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_superuser
def create_role(request):
    """Create a new role"""
    try:
        body = json.loads(request.body)
        name = body.get('name', '').strip()
        description = body.get('description', '').strip()
        permission_ids = body.get('permission_ids', [])
        
        if not name:
            return JsonResponse({'error': 'Role name is required'}, status=400)
        
        if Role.objects.filter(name__iexact=name).exists():
            return JsonResponse({'error': 'Role with this name already exists'}, status=400)
        
        role = Role.objects.create(name=name, description=description)
        
        if permission_ids:
            permissions = ModulePermission.objects.filter(id__in=permission_ids)
            role.module_permissions.set(permissions)
        
        TransactionLogBase.log(
            "ROLE_CREATED",
            user=request.user,
            message=f"Created role: {name} with {len(permission_ids)} permissions"
        )
        
        return JsonResponse({
            'message': 'Role created successfully',
            'role': {
                'id': role.id,
                'name': role.name,
                'description': role.description
            }
        }, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_superuser
def update_role(request):
    """Update role details and permissions"""
    try:
        body = json.loads(request.body)
        role_id = body.get('role_id')
        name = body.get('name', '').strip()
        description = body.get('description', '').strip()
        permission_ids = body.get('permission_ids')
        
        if not role_id:
            return JsonResponse({'error': 'Role ID is required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({'error': 'Role not found'}, status=404)
        
        # Prevent modifying system roles
        if role.name in ['SUPERUSER']:
            return JsonResponse({'error': 'Cannot modify system role'}, status=403)
        
        if name:
            # Check for duplicate name (excluding current role)
            if Role.objects.filter(name__iexact=name).exclude(id=role_id).exists():
                return JsonResponse({'error': 'Role with this name already exists'}, status=400)
            role.name = name
        
        if description is not None:
            role.description = description
        
        role.save()
        
        if permission_ids is not None:
            permissions = ModulePermission.objects.filter(id__in=permission_ids)
            role.module_permissions.set(permissions)
        
        TransactionLogBase.log(
            "ROLE_UPDATED",
            user=request.user,
            message=f"Updated role: {role.name}"
        )
        
        return JsonResponse({'message': 'Role updated successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_superuser
def delete_role(request):
    """Delete a role (only if not assigned to any users)"""
    try:
        body = json.loads(request.body)
        role_id = body.get('role_id')
        
        if not role_id:
            return JsonResponse({'error': 'Role ID is required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({'error': 'Role not found'}, status=404)
        
        # Prevent deleting system roles
        if role.name in ['SUPERADMIN', 'SUPERUSER', 'ADMIN']:
            return JsonResponse({'error': 'Cannot delete system role'}, status=403)
        
        # Check if role is assigned to any users
        from OrgAuth.models import CorporateUser
        user_count = CorporateUser.objects.filter(role=role).count()
        if user_count > 0:
            return JsonResponse({
                'error': f'Cannot delete role. It is assigned to {user_count} user(s)'
            }, status=400)
        
        role_name = role.name
        role.delete()
        
        TransactionLogBase.log(
            "ROLE_DELETED",
            user=request.user,
            message=f"Deleted role: {role_name}"
        )
        
        return JsonResponse({'message': 'Role deleted successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_superuser
def add_permission_to_role(request):
    """Add a single permission to a role"""
    try:
        body = json.loads(request.body)
        role_id = body.get('role_id')
        permission_id = body.get('permission_id')
        
        if not role_id or not permission_id:
            return JsonResponse({'error': 'Role ID and Permission ID are required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
            permission = ModulePermission.objects.get(id=permission_id)
        except (Role.DoesNotExist, ModulePermission.DoesNotExist):
            return JsonResponse({'error': 'Role or Permission not found'}, status=404)
        
        role.module_permissions.add(permission)
        
        TransactionLogBase.log(
            "PERMISSION_ADDED",
            user=request.user,
            message=f"Added {permission.name} to {role.name}"
        )
        
        return JsonResponse({'message': 'Permission added successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_superuser
def remove_permission_from_role(request):
    """Remove a single permission from a role"""
    try:
        body = json.loads(request.body)
        role_id = body.get('role_id')
        permission_id = body.get('permission_id')
        
        if not role_id or not permission_id:
            return JsonResponse({'error': 'Role ID and Permission ID are required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
            permission = ModulePermission.objects.get(id=permission_id)
        except (Role.DoesNotExist, ModulePermission.DoesNotExist):
            return JsonResponse({'error': 'Role or Permission not found'}, status=404)
        
        role.module_permissions.remove(permission)
        
        TransactionLogBase.log(
            "PERMISSION_REMOVED",
            user=request.user,
            message=f"Removed {permission.name} from {role.name}"
        )
        
        return JsonResponse({'message': 'Permission removed successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
