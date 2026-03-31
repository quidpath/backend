# Payment gateway views - DEPRECATED
# All payment processing has been migrated to the billing service
# This file is kept for reference only

import logging

from quidpath_backend.core.utils.json_response import ResponseProvider

logger = logging.getLogger(__name__)


def deprecated_endpoint(request):
    """
    All payment endpoints have been migrated to the billing service.
    Please use the billing service API endpoints instead.
    """
    return ResponseProvider(
        message="This endpoint has been deprecated. Please use the billing service API.",
        code=410,
    ).error()
