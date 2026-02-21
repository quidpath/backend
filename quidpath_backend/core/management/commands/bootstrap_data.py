"""
Bootstrap essential data for the application.
Run this after migrations to ensure required records exist.
"""
from django.core.management.base import BaseCommand
from Authentication.models.logbase import State, NotificationType


class Command(BaseCommand):
    help = 'Bootstrap essential data (States, NotificationTypes)'

    def handle(self, *args, **options):
        self.stdout.write('Bootstrapping essential data...')
        
        # Bootstrap States
        self.stdout.write('Creating States...')
        State.bootstrap_defaults()
        self.stdout.write(self.style.SUCCESS(f' States created/verified'))
        
        # Bootstrap NotificationTypes
        self.stdout.write('Creating NotificationTypes...')
        NotificationType.bootstrap_defaults()
        self.stdout.write(self.style.SUCCESS(f'NotificationTypes created/verified'))
        
        self.stdout.write(self.style.SUCCESS('\n Bootstrap complete!'))
