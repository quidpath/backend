"""
Payment recording views for invoices and vendor bills.
Supports partial and bulk payments with account reconciliation.
"""
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def _to_decimal(val, default=Decimal("0")):
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return default


@csrf_exempt
@require_http_methods(["POST"])
def record_invoice_payment(request):
    """
    Record payment(s) against one or more invoices for the same customer.

    Body:
    {
        "payment_date": "2026-04-09",
        "payment_method": "bank_transfer",   // bank_transfer | cash | cheque | mobile_money
        "account_id": "<bank-account-uuid>", // account money was deposited to
        "reference": "TXN-001",
        "notes": "...",
        "payments": [
            {"invoice_id": "<uuid>", "amount": 5000.00},
            {"invoice_id": "<uuid>", "amount": 2500.00}
        ]
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)

    payments_list = data.get("payments", [])
    if not payments_list:
        return ResponseProvider(message="payments list is required", code=400).bad_request()

    payment_date = data.get("payment_date")
    payment_method = data.get("payment_method", "bank_transfer")
    account_id = data.get("account_id")
    reference = data.get("reference", "")
    notes = data.get("notes", "")

    if not payment_date:
        return ResponseProvider(message="payment_date is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        results = []
        with transaction.atomic():
            for item in payments_list:
                invoice_id = item.get("invoice_id")
                amount = _to_decimal(item.get("amount", 0))

                if not invoice_id or amount <= 0:
                    continue

                # Fetch invoice
                from Accounting.models.sales import Invoices
                try:
                    invoice = Invoices.objects.select_for_update().get(
                        id=invoice_id, corporate_id=corporate_id
                    )
                except Invoices.DoesNotExist:
                    return ResponseProvider(
                        message=f"Invoice {invoice_id} not found", code=404
                    ).bad_request()

                if invoice.status not in ("POSTED", "PARTIALLY_PAID", "OVERDUE"):
                    return ResponseProvider(
                        message=f"Invoice {invoice.number} cannot be paid (status: {invoice.status})",
                        code=400,
                    ).bad_request()

                invoice_total = _to_decimal(invoice.total)
                # Calculate already paid amount from payment_reference field (stored as paid_amount)
                already_paid = _to_decimal(getattr(invoice, "paid_amount", None) or 0)
                remaining = invoice_total - already_paid

                if amount > remaining:
                    amount = remaining  # cap at remaining balance

                new_paid = already_paid + amount

                # Update status
                if new_paid >= invoice_total:
                    invoice.status = "PAID"
                    invoice.payment_status = "paid"
                else:
                    invoice.status = "PARTIALLY_PAID"
                    invoice.payment_status = "partial"

                # Store paid amount — use payment_reference to store JSON-like ref
                # We persist paid_amount via a dedicated field if it exists, else track via status
                if hasattr(invoice, "paid_amount"):
                    invoice.paid_amount = new_paid

                invoice.payment_reference = reference or invoice.payment_reference
                invoice.is_reconciled = True

                from django.utils import timezone
                if invoice.status == "PAID":
                    invoice.paid_at = timezone.now()

                invoice.save()

                # Create a journal entry line for the payment if account provided
                if account_id:
                    try:
                        _create_payment_journal_entry(
                            registry=registry,
                            corporate_id=corporate_id,
                            document=invoice,
                            document_type="invoice",
                            amount=amount,
                            account_id=account_id,
                            payment_date=payment_date,
                            reference=reference,
                            notes=notes,
                            user_id=user_id,
                        )
                    except Exception:
                        pass  # Journal entry failure should not block payment recording

                results.append({
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.number,
                    "amount_paid": str(amount),
                    "new_status": invoice.status,
                    "payment_status": invoice.payment_status,
                })

        return ResponseProvider(
            data={"payments": results},
            message="Payment(s) recorded successfully",
            code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred: {str(e)}", code=500
        ).exception()


@csrf_exempt
@require_http_methods(["POST"])
def record_bill_payment(request):
    """
    Record payment(s) against one or more vendor bills.

    Body:
    {
        "payment_date": "2026-04-09",
        "payment_method": "bank_transfer",
        "account_id": "<bank-account-uuid>",
        "reference": "TXN-001",
        "notes": "...",
        "payments": [
            {"bill_id": "<uuid>", "amount": 5000.00},
            {"bill_id": "<uuid>", "amount": 2500.00}
        ]
    }
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)

    payments_list = data.get("payments", [])
    if not payments_list:
        return ResponseProvider(message="payments list is required", code=400).bad_request()

    payment_date = data.get("payment_date")
    payment_method = data.get("payment_method", "bank_transfer")
    account_id = data.get("account_id")
    reference = data.get("reference", "")
    notes = data.get("notes", "")

    if not payment_date:
        return ResponseProvider(message="payment_date is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        results = []
        with transaction.atomic():
            for item in payments_list:
                bill_id = item.get("bill_id")
                amount = _to_decimal(item.get("amount", 0))

                if not bill_id or amount <= 0:
                    continue

                from Accounting.models.sales import VendorBill
                try:
                    bill = VendorBill.objects.select_for_update().get(
                        id=bill_id, corporate_id=corporate_id
                    )
                except VendorBill.DoesNotExist:
                    return ResponseProvider(
                        message=f"Bill {bill_id} not found", code=404
                    ).bad_request()

                if bill.status not in ("POSTED", "PARTIALLY_PAID", "OVERDUE"):
                    return ResponseProvider(
                        message=f"Bill {bill.number} cannot be paid (status: {bill.status})",
                        code=400,
                    ).bad_request()

                bill_total = _to_decimal(bill.total)
                already_paid = _to_decimal(getattr(bill, "paid_amount", None) or 0)
                remaining = bill_total - already_paid

                if amount > remaining:
                    amount = remaining

                new_paid = already_paid + amount

                if new_paid >= bill_total:
                    bill.status = "PAID"
                else:
                    bill.status = "PARTIALLY_PAID"

                if hasattr(bill, "paid_amount"):
                    bill.paid_amount = new_paid

                bill.save()

                if account_id:
                    try:
                        _create_payment_journal_entry(
                            registry=registry,
                            corporate_id=corporate_id,
                            document=bill,
                            document_type="bill",
                            amount=amount,
                            account_id=account_id,
                            payment_date=payment_date,
                            reference=reference,
                            notes=notes,
                            user_id=user_id,
                        )
                    except Exception:
                        pass

                results.append({
                    "bill_id": str(bill.id),
                    "bill_number": bill.number,
                    "amount_paid": str(amount),
                    "new_status": bill.status,
                })

        return ResponseProvider(
            data={"payments": results},
            message="Payment(s) recorded successfully",
            code=200,
        ).success()

    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred: {str(e)}", code=500
        ).exception()


def _create_payment_journal_entry(
    registry, corporate_id, document, document_type, amount,
    account_id, payment_date, reference, notes, user_id
):
    """Create a journal entry for a payment, crediting/debiting the appropriate accounts."""
    from Accounting.models.accounts import Account, JournalEntry, JournalEntryLine
    from django.utils import timezone

    try:
        account = Account.objects.get(id=account_id, corporate_id=corporate_id)
    except Account.DoesNotExist:
        return

    description = (
        f"Payment for {document_type} {document.number}"
        if hasattr(document, "number") else f"Payment for {document_type}"
    )
    if reference:
        description += f" - Ref: {reference}"

    je = JournalEntry.objects.create(
        corporate_id=corporate_id,
        date=payment_date,
        reference=reference or f"PAY-{str(document.id)[:8]}",
        description=description,
        is_posted=True,
        created_by_id=user_id,
        source_type="payment",
        source_id=document.id,
    )

    if document_type == "invoice":
        # Debit: Bank/Cash account (money received)
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=account,
            description=description,
            debit=amount,
            credit=Decimal("0"),
        )
        # Credit: Accounts Receivable (reduce AR)
        if hasattr(document, "receivable_account") and document.receivable_account:
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=document.receivable_account,
                description=description,
                debit=Decimal("0"),
                credit=amount,
            )
    else:
        # Credit: Bank/Cash account (money paid out)
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=account,
            description=description,
            debit=Decimal("0"),
            credit=amount,
        )
        # Debit: Accounts Payable (reduce AP)
        if hasattr(document, "payable_account") and document.payable_account:
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=document.payable_account,
                description=description,
                debit=amount,
                credit=Decimal("0"),
            )
