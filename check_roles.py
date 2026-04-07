import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()
from Authentication.models.role import Role
from Authentication.models.module_permission import ModulePermission
from OrgAuth.models import Corporate

print("Role fields:", [f.name for f in Role._meta.get_fields()])
print("ModulePermission fields:", [f.name for f in ModulePermission._meta.get_fields()])
print("Corporates:", Corporate.objects.count())
roles = list(Role.objects.values("id", "name"))
print("Roles:", roles)
perms = list(ModulePermission.objects.values("id", "name", "module_slug"))
print("Permissions:", perms[:5])
