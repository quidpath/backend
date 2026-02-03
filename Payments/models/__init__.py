# Payments models package
# This package contains organization billing models
# Main models are in Payments.models (models.py)
# We need to import from the parent models.py file

import importlib.util
import os

# Get the path to the parent models.py file
_payments_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_models_py_path = os.path.join(_payments_dir, "models.py")

# Load models.py as a module
_spec = importlib.util.spec_from_file_location(
    "Payments.models_module", _models_py_path
)
_models_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_models_module)

# Re-export models from models.py
RecordPayment = _models_module.RecordPayment
RecordPaymentLine = _models_module.RecordPaymentLine
VendorPayment = _models_module.VendorPayment
VendorPaymentLine = _models_module.VendorPaymentLine
PaymentProvider = _models_module.PaymentProvider

# Import organization billing models from this package
from .organization_billing import (OrganizationInvoice, OrganizationPayment,
                                   OrganizationSubscription)

__all__ = [
    "RecordPayment",
    "RecordPaymentLine",
    "VendorPayment",
    "VendorPaymentLine",
    "PaymentProvider",
    "OrganizationSubscription",
    "OrganizationInvoice",
    "OrganizationPayment",
]
