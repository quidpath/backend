"""
Bootstrap essential data for the application.
Run this after migrations to ensure required records exist.
"""
from django.core.management.base import BaseCommand
from Authentication.models.logbase import State, NotificationType
from Authentication.models.role import Role


class Command(BaseCommand):
    help = 'Bootstrap essential data (States, NotificationTypes, Roles)'

    def handle(self, *args, **options):
        self.stdout.write('Bootstrapping essential data...')
        
        # Bootstrap States
        self.stdout.write('Creating States...')
        State.bootstrap_defaults()
        self.stdout.write(self.style.SUCCESS(' States created/verified'))
        
        # Bootstrap NotificationTypes
        self.stdout.write('Creating NotificationTypes...')
        NotificationType.bootstrap_defaults()
        self.stdout.write(self.style.SUCCESS(' NotificationTypes created/verified'))
        
        # Bootstrap Roles
        self.stdout.write('Creating Roles...')
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
            else:
                existing_count += 1
        
        self.stdout.write(self.style.SUCCESS(f' Roles created: {created_count}, existing: {existing_count}'))
        
        self.stdout.write(self.style.SUCCESS('\nBootstrap complete!'))
