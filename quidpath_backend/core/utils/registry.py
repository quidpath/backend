# core/utils/registry.py
from datetime import datetime
from django.db.models import Q, QuerySet, Model
from django.contrib.contenttypes.models import ContentType
from typing import Any, Dict, Type, Optional, Union

from quidpath_backend.core.Services.service_base import ServiceBase


class ServiceRegistry:
    """
    Dynamic CRUD service registry that allows fetching model classes
    and performing CRUD operations easily.
    """

    def get_model_class(self, model_name: str) -> Type[Model]:
        """
        Retrieve the model class based on its name.
        """
        content_type = ContentType.objects.filter(model=model_name.lower()).first()
        if not content_type:
            raise ValueError(f"Model '{model_name}' is not recognized.")
        return content_type.model_class()

    def get_service(self, model: Type[Model]) -> ServiceBase:
        """
        Create and return a service instance for the given model.
        """
        return ServiceBase(manager=model.objects)

    def serialize_data(self, data: Any) -> Any:
        """
        Convert model instances or QuerySets into JSON-serializable dicts.
        """
        if isinstance(data, Model):
            return self.serialize_instance(data)
        elif isinstance(data, QuerySet):
            return [self.serialize_instance(instance) for instance in data]
        return data

    def serialize_instance(self, instance: Model) -> dict:
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if field.is_relation:
                data[f"{field.name}_id"] = getattr(instance, f"{field.name}_id")
            data[field.name] = value.isoformat() if isinstance(value, datetime) else value
        return data

    def database(
        self,
        model_name: str,
        operation: str,
        instance_id: Optional[Any] = None,
        data: Optional[Union[Dict[str, Any], Q]] = None,
        soft: bool = True,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Perform CRUD operations dynamically based on the model name and operation.
        Supports dict-based and Q-object-based filtering.
        """
        model_class = self.get_model_class(model_name)
        service = self.get_service(model_class)
        data = data or {}

        if operation == 'create':
            return self.serialize_data(service.create(**data))
        elif operation == 'get':
            if not data:
                raise ValueError("Filter criteria must be provided for 'get' operation.")
            return self.serialize_data(service.get(**data))
        elif operation == 'update':
            if instance_id is None:
                raise ValueError("Instance ID is required for 'update' operation.")
            return self.serialize_data(service.update(instance_id, **data))
        elif operation == 'delete':
            if instance_id is None:
                raise ValueError("Instance ID is required for 'delete' operation.")
            return service.delete(instance_id, soft=soft)
        elif operation == 'filter':
            query = Q()
            if isinstance(data, Q):
                query &= data
            elif isinstance(data, dict):
                query &= Q(**data)
            else:
                raise ValueError("Data for 'filter' must be a Q object or dict.")
            if additional_filters:
                query &= Q(**additional_filters)
            return self.serialize_data(service.manager.filter(query))
        elif operation == 'all':
            return self.serialize_data(service.get_all_records())
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def build_queries(
        self,
        model_name: str,
        query: Q,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> QuerySet:
        """
        Advanced filtering using Q objects.
        """
        return self.database(model_name, 'filter', data=query, additional_filters=additional_filters)
