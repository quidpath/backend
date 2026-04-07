"""
Quotation draft/post state machine views.
"""
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.decorators import require_module_permission
from Accounting.models.sales import Quotation, QuotationLine


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
def save_quotation_draft(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, corp_user_id = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    qid = data.get("id")
    try:
        with transaction.atomic():
            if qid:
                qs = Quotation.objects.filter(id=qid, corporate_id=corp_id)
                if not qs.exists():
                    return ResponseProvider(message="Quotation not found", code=404).bad_request()
                q = qs.first()
                if q.status == "POSTED":
                    return ResponseProvider(message="Posted quotations cannot be edited", code=403).bad_request()
                for f in ["comments","T_and_C","ship_via","terms","fob"]:
                    if f in data: setattr(q, f, data[f])
                if not q.drafted_at:
                    q.drafted_at = timezone.now()
                q.status = "DRAFT"
                q.save()
            else:
                from Accounting.views.Quote import resolve_tax_rate, to_decimal
                salesperson_id = data.get("salesperson") or corp_user_id
                q = Quotation.objects.create(
                    corporate_id=corp_id,
                    customer_id=data.get("customer"),
                    date=data.get("date"),
                    number=data.get("number"),
                    valid_until=data.get("valid_until"),
                    comments=data.get("comments", ""),
                    T_and_C=data.get("T_and_C", ""),
                    salesperson_id=salesperson_id,
                    ship_date=data.get("ship_date") or data.get("valid_until"),
                    ship_via=data.get("ship_via", ""),
                    terms=data.get("terms", ""),
                    fob=data.get("fob", ""),
                    status="DRAFT",
                    drafted_at=timezone.now(),
                )
                qid = str(q.id)
                for ld in data.get("lines", []):
                    taxable_id, tax_rate = resolve_tax_rate(ld.get("taxable"), registry)
                    qty = to_decimal(ld.get("quantity", 1))
                    price = to_decimal(ld.get("unit_price", 0))
                    disc = to_decimal(ld.get("discount", 0))
                    sub = qty * price
                    tax_amt = (sub - disc) * tax_rate
                    total = (sub - disc) + tax_amt
                    QuotationLine.objects.create(
                        quotation=q, description=ld.get("description", ""),
                        quantity=int(qty), unit_price=float(price),
                        amount=float(sub), discount=float(disc),
                        taxable_id=taxable_id, tax_amount=float(tax_amt),
                        sub_total=float(sub), total=float(total), grand_total=float(total),
                    )
        lines = list(QuotationLine.objects.filter(quotation_id=qid).values())
        result = {"id": str(q.id), "number": q.number, "status": q.status,
                  "drafted_at": q.drafted_at.isoformat() if q.drafted_at else None,
                  "posted_at": q.posted_at.isoformat() if q.posted_at else None, "lines": lines}
        return ResponseProvider(message="Quotation draft saved", data=result, code=201).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()


@csrf_exempt
@require_module_permission("finance")
def post_quotation(request, quotation_id):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, corp_user_id = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    try:
        qs = Quotation.objects.filter(id=quotation_id, corporate_id=corp_id)
        if not qs.exists():
            return ResponseProvider(message="Quotation not found", code=404).bad_request()
        q = qs.first()
        if q.status == "POSTED":
            return ResponseProvider(message="Already posted", code=400).bad_request()
        errors = []
        if not q.customer_id: errors.append("Customer required.")
        if not QuotationLine.objects.filter(quotation=q).exists(): errors.append("No line items.")
        if errors:
            return ResponseProvider(message="; ".join(errors), code=400).bad_request()
        with transaction.atomic():
            q.status = "POSTED"
            q.posted_at = timezone.now()
            q.posted_by_id = corp_user_id
            q.save()
        result = {"id": str(q.id), "number": q.number, "status": q.status,
                  "posted_at": q.posted_at.isoformat(), "posted_by": str(q.posted_by_id)}
        return ResponseProvider(message="Quotation posted", data=result, code=200).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()


@csrf_exempt
@require_module_permission("finance")
def auto_save_quotation(request, quotation_id):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, _ = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    try:
        qs = Quotation.objects.filter(id=quotation_id, corporate_id=corp_id)
        if not qs.exists():
            return ResponseProvider(message="Quotation not found", code=404).bad_request()
        q = qs.first()
        if q.status == "POSTED":
            return ResponseProvider(message="Cannot edit posted quotation", code=403).bad_request()
        changed = []
        for f in ["comments","T_and_C","ship_via","terms","fob"]:
            if f in data:
                setattr(q, f, data[f])
                changed.append(f)
        if changed:
            q.save(update_fields=changed)
        return ResponseProvider(message="Auto-save successful", code=200).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()


@csrf_exempt
@require_module_permission("finance")
def list_draft_quotations(request):
    data, metadata = get_clean_data(request)
    registry = ServiceRegistry()
    uid, corp_id, _ = _corp_user(metadata, registry)
    if not uid:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    try:
        drafts = list(Quotation.objects.filter(corporate_id=corp_id, status="DRAFT")
                      .values("id","number","date","valid_until","status","drafted_at","customer_id"))
        return ResponseProvider(message="OK", data={"quotations": drafts, "total": len(drafts)}, code=200).success()
    except Exception as e:
        return ResponseProvider(message=f"Error: {e}", code=500).exception()
