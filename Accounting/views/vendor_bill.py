# enhanced_vendor_bills.py
from decimal import Decimal, InvalidOperation
import json
import ast
import re
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from collections import Counter
from datetime import datetime, date

from quidpath_backend.core.utils.AccountingService import AccountingService
from quidpath_backend.core.utils.DocsEmail import DocumentNotificationHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


def to_decimal(val, default="0"):
    """Safely convert any incoming value to Decimal."""
    if val is None:
        return Decimal(default)
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def normalize_taxable_id(raw, registry):
    """
    Accepts any of: UUID string, dict with {'id': ...}, stringified dict.
    Returns UUID string or finds default exempt rate.
    """
    if not raw:
        # Find default exempt tax rate
        default_rate = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"name": "exempt"}
        )
        if default_rate:
            return default_rate[0]["id"]
        raise ValueError("No default exempt tax rate found")

    if isinstance(raw, dict) and raw.get("id"):
        return raw.get("id")

    if isinstance(raw, str):
        s = raw.strip().strip('\'"""''')
        if s.startswith("{") and s.endswith("}"):
            try:
                d = json.loads(s.replace("'", '"'))
                if isinstance(d, dict):
                    return d.get("id") or d.get("uuid") or d.get("pk")
            except Exception:
                try:
                    d = ast.literal_eval(s)
                    if isinstance(d, dict):
                        return d.get("id") or d.get("uuid") or d.get("pk")
                except Exception:
                    return None
        return s

    return str(raw) if raw else None


def get_tax_rate_value(tax_rate):
    """
    Convert a TaxRate choice into a Decimal percentage.
    e.g. 'general_rated' -> Decimal('0.16')
    """
    if not tax_rate or not tax_rate.get("name"):
        return Decimal("0")

    rate_map = {
        "exempt": Decimal("0"),
        "zero_rated": Decimal("0"),
        "general_rated": Decimal("0.16"),
    }

    key = tax_rate["name"]
    return rate_map.get(key, Decimal("0"))


@csrf_exempt
def create_vendor_bill(request):
    """
    Create a new vendor bill for the user's corporate, set status to DRAFT or POSTED,
    calculate totals, and create journal entries if posted.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        accounting_service = AccountingService(registry)

        # Get user's corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Validate required fields
        required_fields = ["vendor", "date", "number", "due_date"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        # Normalize and validate status
        normalized_status = str(data.get("status", "DRAFT")).upper()
        if normalized_status not in {"DRAFT", "POSTED"}:
            return ResponseProvider(message="Invalid status. Must be 'DRAFT' or 'POSTED'", code=400).bad_request()

        # Validate vendor
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()

        # Validate purchase order if provided
        purchase_order_id = None
        purchase_order_input = data.get("purchase_order")
        if purchase_order_input:
            purchase_orders = registry.database(
                model_name="PurchaseOrder",
                operation="filter",
                data={"number": purchase_order_input, "corporate_id": corporate_id, "status": "POSTED"}
            )
            if not purchase_orders:
                return ResponseProvider(
                    message=f"Purchase order {purchase_order_input} not found or not in POSTED status",
                    code=404
                ).bad_request()
            purchase_order_id = purchase_orders[0]["id"]

        # Process and validate lines
        lines = data.get("lines", [])
        if not lines:
            return ResponseProvider(message="At least one vendor bill line is required", code=400).bad_request()

        # Calculate totals and validate line data
        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        validated_lines = []
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Vendor bill line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            # Normalize and validate tax rate
            taxable_id = normalize_taxable_id(line_data.get("taxable_id"), registry)
            tax_rate_value = Decimal('0')
            if taxable_id:
                tax_rates = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id}
                )
                if not tax_rates:
                    return ResponseProvider(message=f"Tax rate {taxable_id} not found", code=404).bad_request()
                tax_rate_value = get_tax_rate_value(tax_rates[0])

            # Calculate line amounts
            qty = to_decimal(line_data["quantity"])
            unit_price = to_decimal(line_data["unit_price"])
            discount = to_decimal(line_data["discount"])

            line_subtotal = qty * unit_price
            line_taxable_amount = line_subtotal - discount
            line_tax_amount = line_taxable_amount * tax_rate_value
            line_total = line_taxable_amount + line_tax_amount

            # Accumulate totals
            sub_total += line_subtotal
            tax_total += line_tax_amount
            total_discount += discount
            total += line_total

            # Store validated line data
            validated_lines.append({
                "description": line_data["description"],
                "quantity": float(qty),
                "unit_price": float(unit_price),
                "amount": float(line_subtotal),
                "discount": float(discount),
                "taxable_id": taxable_id,
                "tax_amount": float(line_tax_amount),
                "sub_total": float(line_taxable_amount),
                "total": float(line_total),
                "purchase_order_line_id": line_data.get("purchase_order_line")
            })

        # Create vendor bill and lines within transaction
        with transaction.atomic():
            # Create vendor bill
            vendor_bill_data = {
                "vendor_id": data["vendor"],
                "corporate_id": corporate_id,
                "purchase_order_id": purchase_order_id,
                "date": data["date"],
                "number": data["number"],
                "due_date": data["due_date"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "status": normalized_status,
                "sub_total": float(sub_total),
                "tax_total": float(tax_total),
                "total_discount": float(total_discount),
                "total": float(total),
                "created_by_id": user_id,  # Added this line
            }

            vendor_bill = registry.database(
                model_name="VendorBill",
                operation="create",
                data=vendor_bill_data
            )

            # Create vendor bill lines
            for line_data in validated_lines:
                line_data["vendor_bill_id"] = vendor_bill["id"]
                registry.database(
                    model_name="VendorBillLine",
                    operation="create",
                    data=line_data
                )

            # Create journal entry if posted
            if normalized_status == "POSTED":
                journal_entry = accounting_service.create_vendor_bill_journal_entry(vendor_bill["id"], user)
                registry.database(
                    model_name="VendorBill",
                    operation="update",
                    instance_id=vendor_bill["id"],
                    data={"journal_entry_id": journal_entry["id"]}
                )
                vendor_bill["journal_entry_id"] = journal_entry["id"]

        # Format response data
        def get_tax_display(taxable_id_value):
            if not taxable_id_value:
                return {"id": "", "code": "exempt", "label": "Exempt (0%)"}
            tax_rates = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": taxable_id_value}
            )
            if tax_rates:
                tax_rate = tax_rates[0]
                return {
                    "id": str(taxable_id_value),
                    "code": tax_rate.get("name", "exempt"),
                    "label": f"{tax_rate.get('name', 'exempt').replace('_', ' ').title()} ({float(get_tax_rate_value(tax_rate) * 100):.0f}%)"
                }
            return {"id": str(taxable_id_value), "code": "exempt", "label": "Exempt (0%)"}

        # Get lines for response
        vendor_bill_lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill["id"]}
        )

        vendor_bill["lines"] = [
            {
                "id": str(line["id"]),
                "description": line["description"],
                "quantity": float(line["quantity"]),
                "unit_price": float(line["unit_price"]),
                "amount": float(line["amount"]),
                "discount": float(line["discount"]),
                "taxable_id": str(line.get("taxable_id", "")),
                "tax_amount": float(line["tax_amount"]),
                "sub_total": float(line["sub_total"]),
                "total": float(line["total"]),
                "purchase_order_line": str(line.get("purchase_order_line_id", "")),
                "taxable": get_tax_display(line.get("taxable_id"))
            }
            for line in vendor_bill_lines
        ]

        # Log success
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_CREATED",
            user=user,
            message=f"Vendor bill {vendor_bill['number']} {'posted' if normalized_status == 'POSTED' else 'created as draft'} for corporate {corporate_id}",
            state_name="Success",
            extra={
                "vendor_bill_id": vendor_bill["id"],
                "status": normalized_status,
                "total": float(total),
                "line_count": len(validated_lines)
            },
            request=request
        )

        return ResponseProvider(
            message=f"Vendor bill {'posted' if normalized_status == 'POSTED' else 'created as draft'} successfully",
            data=vendor_bill,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating vendor bill", code=500).exception()

@csrf_exempt
def update_vendor_bill(request):
    """
    Update an existing vendor bill for the user's corporate, including its lines,
    set status to DRAFT or POSTED, and update journal entries accordingly.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        accounting_service = AccountingService(registry)

        # Get user's corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Validate required fields
        required_fields = ["id", "vendor", "date", "number", "due_date"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        # Get existing vendor bill
        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found", code=404).bad_request()

        existing_vendor_bill = vendor_bills[0]
        vendor_bill_id = existing_vendor_bill["id"]

        # Validate vendor
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()

        # Normalize status
        normalized_status = str(data.get("status", "DRAFT")).upper()
        if normalized_status not in {"DRAFT", "POSTED"}:
            return ResponseProvider(message="Invalid status. Must be 'DRAFT' or 'POSTED'", code=400).bad_request()

        # Process lines
        submitted_lines = data.get("lines", [])
        if not submitted_lines:
            return ResponseProvider(message="At least one vendor bill line is required", code=400).bad_request()

        # Calculate totals
        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in submitted_lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Vendor bill line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable_id"), registry)
            tax_rate_value = Decimal('0')
            if taxable_id:
                tax_rates = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id}
                )
                if not tax_rates:
                    return ResponseProvider(message=f"Tax rate {taxable_id} not found", code=404).bad_request()
                tax_rate_value = get_tax_rate_value(tax_rates[0])

            qty = to_decimal(line_data["quantity"])
            unit_price = to_decimal(line_data["unit_price"])
            discount = to_decimal(line_data["discount"])

            line_subtotal = qty * unit_price
            line_taxable_amount = line_subtotal - discount
            line_tax_amount = line_taxable_amount * tax_rate_value
            line_total = line_taxable_amount + line_tax_amount

            sub_total += line_subtotal
            tax_total += line_tax_amount
            total_discount += discount
            total += line_total

        # Update vendor bill and lines within transaction
        with transaction.atomic():
            # Update vendor bill
            vendor_bill_data = {
                "vendor_id": data["vendor"],
                "date": data["date"],
                "number": data["number"],
                "due_date": data["due_date"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "status": normalized_status,
                "sub_total": float(sub_total),
                "tax_total": float(tax_total),
                "total_discount": float(total_discount),
                "total": float(total),
            }

            vendor_bill = registry.database(
                model_name="VendorBill",
                operation="update",
                instance_id=vendor_bill_id,
                data=vendor_bill_data
            )

            # Handle line updates
            existing_lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vendor_bill_id}
            )
            existing_line_ids = {line["id"] for line in existing_lines}
            submitted_line_ids = {line.get("id") for line in submitted_lines if line.get("id")}

            # Delete removed lines
            for line in existing_lines:
                if line["id"] not in submitted_line_ids:
                    registry.database(
                        model_name="VendorBillLine",
                        operation="delete",
                        instance_id=line["id"]
                    )

            # Create or update lines
            for line_data in submitted_lines:
                taxable_id = normalize_taxable_id(line_data.get("taxable_id"), registry)
                tax_rate_value = Decimal('0')
                if taxable_id:
                    tax_rates = registry.database(
                        model_name="TaxRate",
                        operation="filter",
                        data={"id": taxable_id}
                    )
                    tax_rate_value = get_tax_rate_value(tax_rates[0]) if tax_rates else Decimal('0')

                qty = to_decimal(line_data["quantity"])
                unit_price = to_decimal(line_data["unit_price"])
                discount = to_decimal(line_data["discount"])

                line_subtotal = qty * unit_price
                line_taxable_amount = line_subtotal - discount
                line_tax_amount = line_taxable_amount * tax_rate_value
                line_total = line_taxable_amount + line_tax_amount

                line_payload = {
                    "vendor_bill_id": vendor_bill_id,
                    "purchase_order_line_id": line_data.get("purchase_order_line"),
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_taxable_amount),
                    "total": float(line_total),
                }

                if line_data.get("id") in existing_line_ids:
                    registry.database(
                        model_name="VendorBillLine",
                        operation="update",
                        instance_id=line_data["id"],
                        data=line_payload
                    )
                else:
                    registry.database(
                        model_name="VendorBillLine",
                        operation="create",
                        data=line_payload
                    )

            # Handle journal entry updates
            if normalized_status == "POSTED":
                # Delete old journal entry if exists
                if existing_vendor_bill.get("journal_entry_id"):
                    old_je_lines = registry.database(
                        model_name="JournalEntryLine",
                        operation="filter",
                        data={"journal_entry_id": existing_vendor_bill["journal_entry_id"]}
                    )
                    for line in old_je_lines:
                        registry.database(
                            model_name="JournalEntryLine",
                            operation="delete",
                            instance_id=line["id"]
                        )
                    registry.database(
                        model_name="JournalEntry",
                        operation="delete",
                        instance_id=existing_vendor_bill["journal_entry_id"]
                    )

                # Create new journal entry
                journal_entry = accounting_service.create_vendor_bill_journal_entry(vendor_bill_id, user)
                registry.database(
                    model_name="VendorBill",
                    operation="update",
                    instance_id=vendor_bill_id,
                    data={"journal_entry_id": journal_entry["id"]}
                )
                vendor_bill["journal_entry_id"] = journal_entry["id"]

            elif normalized_status == "DRAFT" and existing_vendor_bill.get("journal_entry_id"):
                # If changing from POSTED to DRAFT, remove journal entry
                old_je_lines = registry.database(
                    model_name="JournalEntryLine",
                    operation="filter",
                    data={"journal_entry_id": existing_vendor_bill["journal_entry_id"]}
                )
                for line in old_je_lines:
                    registry.database(
                        model_name="JournalEntryLine",
                        operation="delete",
                        instance_id=line["id"]
                    )
                registry.database(
                    model_name="JournalEntry",
                    operation="delete",
                    instance_id=existing_vendor_bill["journal_entry_id"]
                )
                registry.database(
                    model_name="VendorBill",
                    operation="update",
                    instance_id=vendor_bill_id,
                    data={"journal_entry_id": None}
                )

        # Log success
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_UPDATED",
            user=user,
            message=f"Vendor bill {vendor_bill['number']} updated with status {normalized_status} for corporate {corporate_id}",
            state_name="Success",
            extra={
                "vendor_bill_id": vendor_bill_id,
                "status": normalized_status,
                "total": float(total),
                "line_count": len(submitted_lines)
            },
            request=request
        )

        # Return updated vendor bill with lines
        return get_vendor_bill_response(vendor_bill_id, registry)

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating vendor bill", code=500).exception()


def get_vendor_bill_response(vendor_bill_id, registry):
    """Helper function to format vendor bill response with lines"""
    vendor_bills = registry.database(
        model_name="VendorBill",
        operation="filter",
        data={"id": vendor_bill_id}
    )

    if not vendor_bills:
        return ResponseProvider(message="Vendor bill not found", code=404).bad_request()

    vendor_bill = vendor_bills[0]

    def get_tax_display(taxable_id_value):
        if not taxable_id_value:
            return {"id": "", "code": "exempt", "label": "Exempt (0%)"}
        tax_rates = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"id": taxable_id_value}
        )
        if tax_rates:
            tax_rate = tax_rates[0]
            return {
                "id": str(taxable_id_value),
                "code": tax_rate.get("name", "exempt"),
                "label": f"{tax_rate.get('name', 'exempt').replace('_', ' ').title()} ({float(get_tax_rate_value(tax_rate) * 100):.0f}%)"
            }
        return {"id": str(taxable_id_value), "code": "exempt", "label": "Exempt (0%)"}

    vendor_bill_lines = registry.database(
        model_name="VendorBillLine",
        operation="filter",
        data={"vendor_bill_id": vendor_bill_id}
    )

    vendor_bill["lines"] = [
        {
            "id": str(line["id"]),
            "description": line["description"],
            "quantity": float(line["quantity"]),
            "unit_price": float(line["unit_price"]),
            "amount": float(line["amount"]),
            "discount": float(line["discount"]),
            "taxable_id": str(line.get("taxable_id", "")),
            "tax_amount": float(line["tax_amount"]),
            "sub_total": float(line["sub_total"]),
            "total": float(line["total"]),
            "purchase_order_line": str(line.get("purchase_order_line_id", "")),
            "taxable": get_tax_display(line.get("taxable_id"))
        }
        for line in vendor_bill_lines
    ]

    return ResponseProvider(
        message="Vendor bill retrieved successfully",
        data=vendor_bill,
        code=200
    ).success()


@csrf_exempt
def list_vendor_bills(request):
    """List all vendor bills for the user's corporate, categorized by status."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"corporate_id": corporate_id}
        )

        def get_tax_display(taxable_id_value):
            if not taxable_id_value:
                return {"id": "", "code": "exempt", "label": "Exempt (0%)"}
            tax_rates = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": taxable_id_value}
            )
            if tax_rates:
                tax_rate = tax_rates[0]
                return {
                    "id": str(taxable_id_value),
                    "code": tax_rate.get("name", "exempt"),
                    "label": f"{tax_rate.get('name', 'exempt').replace('_', ' ').title()} ({float(get_tax_rate_value(tax_rate) * 100):.0f}%)"
                }
            return {"id": str(taxable_id_value), "code": "exempt", "label": "Exempt (0%)"}

        serialized_vendor_bills = []
        for vb in vendor_bills:
            lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vb["id"]}
            )

            serialized_vendor_bills.append({
                "id": str(vb["id"]),
                "number": vb["number"],
                "vendor": str(vb["vendor_id"]),
                "date": vb["date"],
                "due_date": vb["due_date"],
                "status": vb["status"],
                "purchase_order": str(vb.get("purchase_order_id", "")),
                "comments": vb.get("comments", ""),
                "terms": vb.get("terms", ""),
                "sub_total": float(vb.get("sub_total", 0)),
                "tax_total": float(vb.get("tax_total", 0)),
                "total_discount": float(vb.get("total_discount", 0)),
                "total": float(vb.get("total", 0)),
                "has_journal_entry": bool(vb.get("journal_entry_id")),
                "lines": [
                    {
                        "id": str(line["id"]),
                        "description": line["description"],
                        "quantity": float(line["quantity"]),
                        "unit_price": float(line["unit_price"]),
                        "amount": float(line["amount"]),
                        "discount": float(line["discount"]),
                        "taxable_id": str(line.get("taxable_id", "")),
                        "tax_amount": float(line["tax_amount"]),
                        "sub_total": float(line["sub_total"]),
                        "total": float(line["total"]),
                        "purchase_order_line": str(line.get("purchase_order_line_id", "")),
                        "taxable": get_tax_display(line.get("taxable_id"))
                    }
                    for line in lines
                ]
            })

        statuses = [vb["status"] for vb in vendor_bills]
        status_counts = dict(Counter(statuses))
        total_count = len(vendor_bills)

        all_statuses = {"DRAFT": 0, "POSTED": 0, "PAID": 0, "PARTIALLY_PAID": 0, "OVERDUE": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total_count} vendor bills for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses, "corporate_id": corporate_id},
            request=request
        )

        return ResponseProvider(
            data={
                "vendor_bills": serialized_vendor_bills,
                "total": total_count,
                "status_counts": all_statuses
            },
            message="Vendor bills retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving vendor bills", code=500).exception()

@csrf_exempt
def get_vendor_bill(request):
    """Get a single vendor bill by ID for the user's corporate, including its lines."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        vendor_bill_id = data.get("id")
        if not vendor_bill_id:
            return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found or not associated with this corporate", code=404).bad_request()

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_GET_SUCCESS",
            user=user,
            message=f"Retrieved vendor bill {vendor_bill_id} for corporate {corporate_id}",
            state_name="Success",
            extra={"vendor_bill_id": vendor_bill_id, "corporate_id": corporate_id},
            request=request
        )

        return get_vendor_bill_response(vendor_bill_id, registry)

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_GET_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving vendor bill", code=500).exception()


@csrf_exempt
def delete_vendor_bill(request):
    """
    Delete a vendor bill for the user's corporate. If the bill is posted, delete associated journal entries.
    Only allows deletion if the bill is in DRAFT or POSTED status (for POSTED, reverses accounting impact by deleting journal).
    Does not allow deletion if already PAID, PARTIALLY_PAID, OVERDUE, or CANCELLED.
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        vendor_bill_id = data.get("id")
        if not vendor_bill_id:
            return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found or not associated with this corporate", code=404).bad_request()

        vendor_bill = vendor_bills[0]
        current_status = vendor_bill["status"]

        if current_status in {"PAID", "PARTIALLY_PAID", "OVERDUE", "CANCELLED"}:
            return ResponseProvider(
                message=f"Cannot delete vendor bill in {current_status} status. Consider cancelling instead.",
                code=400
            ).bad_request()

        with transaction.atomic():
            # Delete associated journal entry if exists (for POSTED bills)
            if vendor_bill.get("journal_entry_id"):
                je_lines = registry.database(
                    model_name="JournalEntryLine",
                    operation="filter",
                    data={"journal_entry_id": vendor_bill["journal_entry_id"]}
                )
                for line in je_lines:
                    registry.database(
                        model_name="JournalEntryLine",
                        operation="delete",
                        instance_id=line["id"]
                    )
                registry.database(
                    model_name="JournalEntry",
                    operation="delete",
                    instance_id=vendor_bill["journal_entry_id"]
                )

            # Delete vendor bill lines
            vb_lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vendor_bill_id}
            )
            for line in vb_lines:
                registry.database(
                    model_name="VendorBillLine",
                    operation="delete",
                    instance_id=line["id"]
                )

            # Delete the vendor bill
            registry.database(
                model_name="VendorBill",
                operation="delete",
                instance_id=vendor_bill_id
            )

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_DELETED",
            user=user,
            message=f"Vendor bill {vendor_bill['number']} deleted for corporate {corporate_id}",
            state_name="Success",
            extra={
                "vendor_bill_id": vendor_bill_id,
                "previous_status": current_status,
                "corporate_id": corporate_id
            },
            request=request
        )

        return ResponseProvider(
            message="Vendor bill deleted successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting vendor bill", code=500).exception()

@csrf_exempt
def convert_purchase_order_to_vendor_bill(request):
    """
    Convert a purchase order to a vendor bill, linking to a vendor, and create vendor bill lines.

    Expected data:
    - purchase_order_id: UUID of the purchase order
    - vendor_id: UUID of the vendor
    - date: Date of the vendor bill
    - number: Vendor bill number (unique)
    - due_date: Due date of the vendor bill
    - created_by: UUID of the user creating the vendor bill
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        accounting_service = AccountingService(registry)

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        required_fields = ["purchase_order_id", "vendor_id", "date", "number", "due_date", "created_by"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": data["purchase_order_id"], "corporate_id": corporate_id}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()
        purchase_order = purchase_orders[0]

        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor_id"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()

        created_by_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["created_by"], "corporate_id": corporate_id, "is_active": True}
        )
        if not created_by_users:
            return ResponseProvider(message="Created by user not found or inactive for this corporate", code=404).bad_request()

        purchase_order_lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order["id"]}
        )
        if not purchase_order_lines:
            return ResponseProvider(message="No lines found for this purchase order", code=400).bad_request()

        with transaction.atomic():
            vendor_bill_data = {
                "vendor_id": data["vendor_id"],
                "corporate_id": corporate_id,
                "purchase_order_id": purchase_order["id"],
                "date": data["date"],
                "number": data["number"],
                "due_date": data["due_date"],
                "comments": data.get("comments", purchase_order["comments"]),
                "terms": data.get("terms", purchase_order["terms"]),
                "created_by_id": data["created_by"],
                "status": "DRAFT",
                "sub_total": float(purchase_order.get("sub_total", 0.00)),
                "tax_total": float(purchase_order.get("tax_total", 0.00)),
                "total_discount": float(purchase_order.get("total_discount", 0.00)),
                "total": float(purchase_order.get("total", 0.00)),
            }
            vendor_bill = registry.database(
                model_name="VendorBill",
                operation="create",
                data=vendor_bill_data
            )

            for line in purchase_order_lines:
                taxable_id = normalize_taxable_id(line.get("taxable_id"))
                tax_rate_value = Decimal('0')
                if taxable_id:
                    tax_rates = registry.database(
                        model_name="TaxRate",
                        operation="filter",
                        data={"id": taxable_id}
                    )
                    tax_rate_value = get_tax_rate_value(tax_rates[0]) if tax_rates else Decimal('0')

                qty = to_decimal(line["quantity"])
                unit_price = to_decimal(line["unit_price"])
                discount = to_decimal(line["discount"])
                line_subtotal = qty * unit_price
                line_taxable_amount = line_subtotal - discount
                line_tax_amount = line_taxable_amount * tax_rate_value
                line_total = line_taxable_amount + line_tax_amount

                line_data = {
                    "vendor_bill_id": vendor_bill["id"],
                    "purchase_order_line_id": line["id"],
                    "description": line["description"],
                    "quantity": float(line["quantity"]),
                    "unit_price": float(line["unit_price"]),
                    "amount": float(line_subtotal),
                    "discount": float(line["discount"]),
                    "taxable_id": line["taxable_id"],
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                }
                registry.database(
                    model_name="VendorBillLine",
                    operation="create",
                    data=line_data
                )

            # If we want to post it immediately, but the code sets "DRAFT", so no journal yet

        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_CONVERTED_TO_VENDOR_BILL",
            user=user,
            message=f"Purchase order {purchase_order['number']} converted to vendor bill {vendor_bill['number']} for corporate {corporate_id}",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order["id"], "vendor_bill_id": vendor_bill["id"], "line_count": len(purchase_order_lines)},
            request=request
        )

        def tax_display(taxable_id_value):
            if not taxable_id_value:
                return "Exempt (0%)"
            tr = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": taxable_id_value}
            )
            return tr[0].get("name", "Exempt (0%)") if tr else "Exempt (0%)"

        vendor_bill_lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill["id"]}
        )
        vendor_bill["lines"] = [
            {
                "id": str(line.get("id", "")),
                "description": line.get("description", ""),
                "quantity": float(line.get("quantity", 0)),
                "unit_price": float(line.get("unit_price", 0)),
                "amount": float(line.get("amount", 0)),
                "discount": float(line.get("discount", 0)),
                "taxable_id": str(line.get("taxable_id", "")),
                "tax_amount": float(line.get("tax_amount", 0)),
                "sub_total": float(line.get("sub_total", 0)),
                "total": float(line.get("total", 0)),
                "purchase_order_line": str(line.get("purchase_order_line_id", "")),
                "taxable": {
                    "id": str(line.get("taxable_id", "")),
                    "code": tax_display(line.get("taxable_id")),
                    "label": tax_display(line.get("taxable_id"))
                } if line.get("taxable_id") else {
                    "id": "exempt",
                    "code": "exempt",
                    "label": "Exempt (0%)"
                }
            }
            for line in vendor_bill_lines
        ]

        return ResponseProvider(
            message="Vendor bill created successfully",
            data=vendor_bill,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_CONVERT_TO_VENDOR_BILL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while converting purchase order to vendor bill", code=500).exception()

@csrf_exempt
def list_po(request):
    """
    List all purchase orders for the user's corporate.

    Returns:
    - 200: List of purchase orders
    - 400: Bad request (missing corporate)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"corporate_id": corporate_id}
        )

        serialized_purchase_orders = [
            {
                "id": str(po["id"]),
                "number": po.get("number", ""),
                "po_number": po.get("po_number", po.get("number", ""))
            }
            for po in purchase_orders
        ]

        return ResponseProvider(
            data={"purchase_orders": serialized_purchase_orders},
            message="Purchase orders retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(message=str(e), code=500).exception()