# Audit log views
from django.views.decorators.csrf import csrf_exempt
import logging

from Accounting.models.audit import AuditLog
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry

logger = logging.getLogger(__name__)


@csrf_exempt
def list_audit_logs(request):
    """List audit logs for a corporate."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        # Build filter
        filter_kwargs = {"corporate_id": corporate_id}
        if data.get("action_type"):
            filter_kwargs["action_type"] = data.get("action_type")
        if data.get("model_name"):
            filter_kwargs["model_name"] = data.get("model_name")
        if data.get("user_id"):
            filter_kwargs["user_id"] = data.get("user_id")
        
        # Get logs
        logs = AuditLog.objects.filter(**filter_kwargs).order_by('-created_at')[:100]  # Limit to 100 most recent
        
        # Serialize logs
        logs_data = []
        for log in logs:
            logs_data.append({
                "id": str(log.id),
                "action_type": log.action_type,
                "model_name": log.model_name,
                "object_id": str(log.object_id) if log.object_id else None,
                "description": log.description,
                "user": {
                    "id": str(log.user.id) if log.user else None,
                    "username": log.user.username if log.user else None,
                    "email": log.user.email if log.user else None,
                } if log.user else None,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "changes": log.changes,
                "metadata": log.metadata,
            })
        
        return ResponseProvider(data={"logs": logs_data}, message="Audit logs retrieved successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error listing audit logs: {e}")
        return ResponseProvider(message=f"Error listing audit logs: {str(e)}", code=500).exception()








