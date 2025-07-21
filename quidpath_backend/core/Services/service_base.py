from django.db.models import Model, QuerySet
from typing import Any, Optional

class ServiceBase:
    def __init__(self, manager: QuerySet):
        """
        Initialize the ServiceBase class with a model manager.

        :param manager: The manager of a Django model (e.g., Model.objects).
        """
        self.manager = manager

    def create(self, **kwargs) -> Model:
        """
        Create and save a new instance of the model.

        :param kwargs: Dictionary of field values.
        :return: Created model instance.
        """
        instance = self.manager.create(**kwargs)
        return instance

    def get(self, **kwargs) -> Optional[Model]:
        """
        Retrieve a single model instance based on filter criteria.

        :param kwargs: Dictionary of field values.
        :return: Retrieved model instance or None if not found.
        """
        return self.manager.filter(**kwargs).first()

    def update(self, instance_id: Any, **kwargs) -> Optional[Model]:
        """
        Update an existing instance of the model.

        :param instance_id: The primary key of the instance.
        :param kwargs: Dictionary of field values to update.
        :return: Updated model instance.
        """
        instance = self.manager.filter(pk=instance_id).first()
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            instance.save()
            return instance
        return None

    def delete(self, instance_id: Any, soft: bool = True) -> bool:
        """
        Delete an instance of the model.

        :param instance_id: The primary key of the instance.
        :param soft: Whether to perform a soft delete (if the model supports it).
        :return: True if deleted, False if instance not found.
        """
        instance = self.manager.filter(pk=instance_id).first()
        if instance:
            if soft and hasattr(instance, 'is_active'):
                instance.is_active = False
                instance.save()
            else:
                instance.delete()
            return True
        return False

    def get_all_records(self) -> QuerySet:
        """
        Retrieve all records for the model.

        :return: QuerySet containing all records.
        """
        return self.manager.all()
