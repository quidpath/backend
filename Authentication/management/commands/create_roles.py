"""
Create default roles for the application.
"""
from django.core.management.base import BaseCommand
from Authentication.models.role import Role


class Command(BaseCommand):
    help = 'Create default roles (SUPERADMIN, ADMIN, USER, etc.)'

    def handle(self, *args, **options):
        self.stdout.write('Creating default roles...')
        
        roles = [
            'SUPERADMIN',
            'ADMIN',
            'USER',
            'ACCOUNTANT',
            'MANAGER',
            'VIEWER',
        ]
        
        created_count = 0
        existing_count = 0
        
        for role_name in roles:
            role, created = Role.objects.get_or_create(name=role_name)
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created role: {role_name}'))
            else:
                existing_count += 1
                self.stdout.write(f'  Role already exists: {role_name}')
        
        self.stdout.write(self.style.SUCCESS(f'\nRoles created: {created_count}'))
        self.stdout.write(f'Roles already existed: {existing_count}')
        self.stdout.write(self.style.SUCCESS('Role creation complete!'))
