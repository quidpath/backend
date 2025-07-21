from django.apps import AppConfig
from django.db.models.signals import post_migrate


def bootstrap_system_data(sender, **kwargs):
    from Authentication.models.logbase import State, NotificationType, TransactionType, Organisation
    State.bootstrap_defaults()
    NotificationType.bootstrap_defaults()
    TransactionType.bootstrap_defaults()
    Organisation.bootstrap_defaults()


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(bootstrap_system_data, sender=self)
