from django.db import connection
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider


@csrf_exempt
def health_check(request):
    """
    Health check endpoint for container orchestration.
    Returns 200 if the service is healthy, 503 otherwise.
    """
    if request.method != "GET":
        return ResponseProvider.method_not_allowed(["GET"])
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return ResponseProvider.success_response(
            data={"status": "healthy", "database": "connected"}, status=200
        )
    except Exception as e:
        return ResponseProvider.raw_response(
            {"status": "unhealthy", "error": str(e)}, status=503
        )
