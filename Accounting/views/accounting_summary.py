# accounting_summary.py
"""
Unified accounting summary endpoint for dashboard
"""
from django.views.decorators.csrf import csrf_exempt
from quidpath_backend.core.utils.json_response import ResponseProvider
from .summary_reports import get_sales_summary


@csrf_exempt
def get_accounting_summary(request):
    """
    Get accounting summary for dashboard
    This is a wrapper around get_sales_summary to provide a unified endpoint
    
    Returns:
    - 200: Accounting summary data
    - 400: Bad request
    - 401: Unauthorized
    - 500: Internal server error
    """
    # Call the sales summary which includes all the stat card data
    return get_sales_summary(request)
