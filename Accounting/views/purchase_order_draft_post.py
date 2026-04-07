"""
Purchase Order draft/post state machine views.
"""
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.decorators import require_module_permission
from Accounting.models.sales import PurchaseOrder, PurchaseOrderLine


def _corp_user(metadata, registry):
    user = metadata.get("user")
    if not user:
        return None, None, None
    uid = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    rows = registry.database(model_name="CorporateUser", operation="filter",
                              data={"customuser_ptr_id": uid, "is_active": True})
    if not rows:
        return None, None, None
    return uid, rows[0]["corporate_id"], rows[0]["id"]


@csrf_exempt
@require_module_permission("finance")
def post_purchase_order(request, po_id):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, corp_user_id = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    try:
        qs = PurchaseOrder.objects.filter(id=po_id, corporate_id=corp_id)
        if not qs.exists():
            return ResponseProvider(message="Purchase order not found", code=404).bad_request()
        po = qs.first()
        if po.status == "POSTED":
            return ResponseProvider(message="Already posted", code=400).bad_request()
        errors = []
        if not po.vendor_id: errors.append("Vendor required.")
        if not PurchaseOrderLine.objects.filter(purchase_order=po).exists(): errors.append("No line items.")
        if errors:
            return ResponseProvider(message="; ".join(errors), code=400).bad_request()
        with transaction.atomic():
            po.status = "POSTED"
            po.posted_at = timezone.now()
            po.posted_by_id = corp_user_id
            po.save()
        result = {"id": str(po.id), "number": po.number, "status": po.status,
                  "posted_at": po.posted_at.isoformat()}
        return ResponseProvider(message="Purchase order posted", data=result, code=200).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()


@csrf_exempt
@require_module_permission("finance")
def auto_save_purchase_order(request, po_id):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, _ = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    try:
        qs = PurchaseOrder.objects.filter(id=po_id, corporate_id=corp_id)
        if not qs.exists():
            return ResponseProvider(message="PO not found", code=404).bad_request()
        po = qs.first()
        if po.status == "POSTED":
            return ResponseProvider(message="Cannot edit posted PO", code=403).bad_request()
        changed = []
        for f in ["comments","terms","ship_via","fob"]:
            if f in data:
                setattr(po, f, data[f])
                changed.append(f)
        if changed:
            po.save(update_fields=changed)
        return ResponseProvider(message="Auto-save successful", code=200).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()


@csrf_exempt
@require_module_permission("finance")
def list_draft_purchase_orders(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, _ = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    try:
        drafts = list(PurchaseOrder.objects.filter(corporate_id=corp_id, status="DRAFT")
                      .values("id","number","date","expected_delivery","status","drafted_at","vendor_id"))
        return ResponseProvider(message="OK", data={"purchase_orders": drafts, "total": len(drafts)}, code=200).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()
