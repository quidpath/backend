# Compatibility shim — BillingServiceClient lives in Services/billing_service.py
from quidpath_backend.core.Services.billing_service import BillingServiceClient

__all__ = ["BillingServiceClient"]
