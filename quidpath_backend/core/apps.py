"""
Core app configuration
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quidpath_backend.core'
    verbose_name = 'Core & Billing'
    
    def ready(self):
        """Import admin when app is ready"""
        try:
            from . import admin  # noqa
        except ImportError:
            pass
