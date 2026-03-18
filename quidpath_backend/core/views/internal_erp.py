"""
Internal API views for inter-microservice communication.

These endpoints are authenticated via X-Service-Key headers, not JWT.
They provide the following capabilities to ERP microservices:
  - User & corporate data lookup
  - Invoice creation (from CRM Sales orders or Projects billable hours)
  - Journal entry creation (from HRM payroll)
  - Billable hours import (from Projects)
"""

import json
import logging
from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Authentication.models import CustomUser
from OrgAuth.models import Corporate, CorporateUser

logger = logging.getLogger(__name__)


def _get_allowed_keys():
    return set(filter(None, settings.SERVICE_API_KEYS.values()))


def _authenticate_service(request):
    key = request.headers.get("X-Service-Key")
    if not key or key not in _get_allowed_keys():
        return False
    return True


def _json_body(request):
    try:
        return json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# User & Corporate lookups (used by all microservices' UserCacheService)
# ---------------------------------------------------------------------------

@csrf_exempt
def get_user(request, user_id):
    """GET /api/internal/users/<user_id>/"""
    if not _authenticate_service(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        user = CustomUser.objects.get(pk=user_id)
        corporate_id = request.headers.get("X-Corporate-Id")
        role = None
        if corporate_id:
            cu = CorporateUser.objects.filter(pk=user_id, corporate_id=corporate_id).first()
            if cu and cu.role:
                role = cu.role.name
        return JsonResponse({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": getattr(user, "phone_number", ""),
            "is_active": user.is_active,
            "role": role,
        })
    except CustomUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)


@csrf_exempt
def get_corporate(request, corporate_id):
    """GET /api/internal/corporates/<corporate_id>/"""
    if not _authenticate_service(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        corp = Corporate.objects.get(pk=corporate_id)
        return JsonResponse({
            "id": corp.id,
            "name": corp.name,
            "email": corp.email,
            "phone": corp.phone,
            "address": corp.address,
            "city": corp.city,
            "country": corp.country,
            "tax_id": corp.tax_id,
            "is_active": corp.is_active,
        })
    except Corporate.DoesNotExist:
        return JsonResponse({"error": "Corporate not found"}, status=404)


# ---------------------------------------------------------------------------
# Invoice creation (CRM Sales → ERP Accounting)
# ---------------------------------------------------------------------------

@csrf_exempt
def create_invoice(request):
    """
    POST /api/internal/invoices/

    Creates a draft invoice in the ERP Accounting module.
    Called by: CRM (on sales order confirmation), Projects (billable hours export).

    Body:
    {
        "corporate_id": 1,
        "customer_ref": "customer name or CRM contact name",
        "source": "crm_sales_order | projects_billable",
        "source_ref": "SO-001",
        "due_date": "2026-04-01",          # optional, defaults to 30 days
        "currency": "KES",                  # optional
        "lines": [
            {
                "description": "Consulting Services",
                "quantity": 1,
                "unit_price": "50000.00",
                "tax_rate": "exempt"         # exempt | zero_rated | general_rated
            }
        ]
    }
    """
    if not _authenticate_service(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    corporate_id = data.get("corporate_id")
    lines = data.get("lines", [])
    if not corporate_id or not lines:
        return JsonResponse({"error": "corporate_id and lines are required"}, status=400)

    try:
        from Accounting.models.sales import Invoices, InvoiceLine, TaxRate
        from Accounting.models.customer import Customer

        corp = Corporate.objects.get(pk=corporate_id)

        # Find a matching customer (best-effort by name)
        customer_ref = data.get("customer_ref", "")
        customer = None
        if customer_ref:
            customer = Customer.objects.filter(
                corporate=corp, name__icontains=customer_ref
            ).first()
        if not customer:
            customer = Customer.objects.filter(corporate=corp).first()
        if not customer:
            return JsonResponse({"error": "No customer found for this corporate"}, status=400)

        # Find a salesperson (use first CorporateUser or None)
        salesperson = CorporateUser.objects.filter(corporate=corp, is_active=True).first()
        if not salesperson:
            return JsonResponse({"error": "No active user found for this corporate"}, status=400)

        due_days = 30
        due_date = data.get("due_date") or str(
            (timezone.now() + timezone.timedelta(days=due_days)).date()
        )

        ref_suffix = data.get("source_ref", timezone.now().strftime("%Y%m%d%H%M%S"))
        invoice_number = f"EXT-{ref_suffix}"
        # Ensure uniqueness
        counter = 1
        while Invoices.objects.filter(number=invoice_number).exists():
            invoice_number = f"EXT-{ref_suffix}-{counter}"
            counter += 1

        invoice = Invoices.objects.create(
            corporate=corp,
            customer=customer,
            salesperson=salesperson,
            date=timezone.now().date(),
            due_date=due_date,
            status="DRAFT",
            number=invoice_number,
            currency=data.get("currency", "KES"),
            comments=f"Auto-created by {data.get('source', 'microservice')}: {data.get('source_ref', '')}",
        )

        sub_total = Decimal("0")
        tax_total = Decimal("0")

        for line in lines:
            tax_name = line.get("tax_rate", "exempt")
            tax_rate = TaxRate.objects.filter(corporate=corp, name=tax_name).first()
            if not tax_rate:
                tax_rate = TaxRate.objects.filter(name=tax_name).first()

            qty = Decimal(str(line.get("quantity", 1)))
            unit_price = Decimal(str(line.get("unit_price", "0")))
            amount = qty * unit_price
            tax_amount = amount * (tax_rate.rate / 100) if tax_rate else Decimal("0")
            line_total = amount + tax_amount

            InvoiceLine.objects.create(
                invoice=invoice,
                description=line.get("description", ""),
                quantity=int(qty),
                unit_price=unit_price,
                amount=amount,
                taxable=tax_rate,
                tax_amount=tax_amount,
                sub_total=amount,
                total=line_total,
            )
            sub_total += amount
            tax_total += tax_amount

        invoice.sub_total = sub_total
        invoice.tax_total = tax_total
        invoice.total = sub_total + tax_total
        invoice.save(update_fields=["sub_total", "tax_total", "total"])

        return JsonResponse({
            "id": str(invoice.id),
            "number": invoice.number,
            "status": invoice.status,
            "customer": str(customer),
            "total": str(invoice.total),
            "currency": invoice.currency,
        }, status=201)

    except Corporate.DoesNotExist:
        return JsonResponse({"error": "Corporate not found"}, status=404)
    except Exception as e:
        logger.exception(f"Invoice creation failed: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# Journal Entry creation (HRM Payroll → ERP Accounting)
# ---------------------------------------------------------------------------

@csrf_exempt
def create_journal_entry(request):
    """
    POST /api/internal/journal-entries/

    Creates a journal entry in the ERP Accounting module.
    Called by: HRM (payroll run posting).

    Body:
    {
        "corporate_id": 1,
        "date": "2026-03-31",
        "reference": "PAYROLL-2026-03",
        "description": "March 2026 Payroll",
        "source_type": "hrm_payroll",
        "lines": [
            {"account_code": "5001", "debit": "500000", "credit": "0", "description": "Gross salaries"},
            {"account_code": "2101", "debit": "0", "credit": "450000", "description": "Net pay payable"},
            {"account_code": "2102", "debit": "0", "credit": "50000", "description": "PAYE payable"}
        ]
    }
    """
    if not _authenticate_service(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    corporate_id = data.get("corporate_id")
    lines = data.get("lines", [])
    if not corporate_id or not lines:
        return JsonResponse({"error": "corporate_id and lines are required"}, status=400)

    try:
        from Accounting.models.accounts import Account, JournalEntry, JournalEntryLine

        corp = Corporate.objects.get(pk=corporate_id)
        date_str = data.get("date", str(timezone.now().date()))
        reference = data.get("reference", f"EXT-{timezone.now().strftime('%Y%m%d%H%M%S')}")

        # Ensure unique reference per corporate
        counter = 1
        base_ref = reference
        while JournalEntry.objects.filter(corporate=corp, reference=reference).exists():
            reference = f"{base_ref}-{counter}"
            counter += 1

        journal = JournalEntry.objects.create(
            corporate=corp,
            date=date_str,
            reference=reference,
            description=data.get("description", ""),
            source_type=data.get("source_type", "microservice"),
            is_posted=False,
        )

        for line in lines:
            account_code = line.get("account_code")
            account = Account.objects.filter(corporate=corp, code=account_code).first()
            if not account:
                logger.warning(f"Account {account_code} not found for corporate {corporate_id}")
                continue

            debit = Decimal(str(line.get("debit", "0")))
            credit = Decimal(str(line.get("credit", "0")))

            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=account,
                description=line.get("description", ""),
                debit=debit,
                credit=credit,
            )

        # Attempt to post if balanced
        if journal.is_balanced() and journal.lines.exists():
            journal.is_posted = True
            journal.save(update_fields=["is_posted"])

        return JsonResponse({
            "id": str(journal.id),
            "reference": journal.reference,
            "is_posted": journal.is_posted,
            "is_balanced": journal.is_balanced(),
            "corporate_id": str(corp.id),
            "line_count": journal.lines.count(),
        }, status=201)

    except Corporate.DoesNotExist:
        return JsonResponse({"error": "Corporate not found"}, status=404)
    except Exception as e:
        logger.exception(f"Journal entry creation failed: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# Billable hours import (Projects → ERP invoice)
# ---------------------------------------------------------------------------

@csrf_exempt
def import_billable_hours(request):
    """
    POST /api/internal/billable-hours/

    Receives a billable hours export from the Projects service and
    creates an invoice for the client.

    Body:
    {
        "corporate_id": 1,
        "project_id": 5,
        "project_name": "Website Redesign",
        "client_id": 12,
        "total_hours": 40.5,
        "total_amount": 202500.00,
        "currency": "KES",
        "entries": [
            {"date": "2026-03-01", "description": "UI Design", "hours": 8, "rate": 5000}
        ]
    }
    """
    if not _authenticate_service(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    invoice_payload = {
        "corporate_id": data.get("corporate_id"),
        "customer_ref": str(data.get("client_id", "")),
        "source": "projects_billable",
        "source_ref": data.get("project_name", f"project-{data.get('project_id')}"),
        "currency": data.get("currency", "KES"),
        "lines": [
            {
                "description": (
                    f"Billable hours – {data.get('project_name')} "
                    f"({data.get('total_hours')}h)"
                ),
                "quantity": 1,
                "unit_price": str(data.get("total_amount", "0")),
                "tax_rate": "exempt",
            }
        ],
    }

    class _FakeRequest:
        method = "POST"
        headers = request.headers
        body = json.dumps(invoice_payload).encode()

    return create_invoice(_FakeRequest())
