from decimal import Decimal, InvalidOperation
import json
import ast
import re
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from collections import Counter
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

def normalize_taxable_id(raw):
    """
    Accepts any of: UUID string, dict with {'id': ...}, stringified dict.
    Returns UUID string or None.
    """
    if not raw:
        return None
    if isinstance(raw, dict) and raw.get("id"):
        return raw.get("id")
    if isinstance(raw, str):
        s = raw.strip().strip('\'"“”‘’')
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
    return None

def get_tax_rate_value(tax_rate):
    """Extract tax rate percentage from TaxRate label (e.g., 'VAT (16%)' -> 0.16)."""
    if not tax_rate or not tax_rate.get("name"):
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_TAX_RATE_WARNING",
            user=None,
            message="Tax rate name missing or empty",
            state_name="Warning",
            request=None
        )
        return Decimal("0")
    label = tax_rate["name"]
    match = re.search(r'\((\d+)%\)', label)
    if match:
        try:
            rate = Decimal(match.group(1)) / Decimal("100")
            return rate
        except (InvalidOperation, ValueError):
            TransactionLogBase.log(
                transaction_type="VENDOR_BILL_TAX_RATE_ERROR",
                user=None,
                message=f"Invalid tax rate label format: {label}",
                state_name="Failed",
                request=None
            )
            return Decimal("0")
    TransactionLogBase.log(
        transaction_type="VENDOR_BILL_TAX_RATE_WARNING",
        user=None,
        message=f"Could not parse tax rate from label: {label}",
        state_name="Warning",
        request=None
    )
    return Decimal("0")

@csrf_exempt
def create_vendor_bill(request):
    """
    Create a new vendor bill for the user's corporate, set status to DRAFT, and calculate totals.

    Expected data:
    - vendor: UUID of the vendor
    - corporate_id: UUID of the corporate
    - purchase_order: Purchase order number (string, optional)
    - date: Date of the vendor bill (YYYY-MM-DD)
    - number: Vendor bill number (unique)
    - due_date: Due date of the vendor bill (YYYY-MM-DD)
    - created_by: UUID of the user creating the vendor bill
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - lines: List of dictionaries, each containing fields for VendorBillLine
      - description
      - quantity
      - unit_price
      - discount
      - taxable_id
      - purchase_order_line: UUID of the purchase order line (optional)
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

        required_fields = ["vendor", "date", "number", "due_date", "created_by"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
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

        purchase_order_number = data.get("purchase_order")
        purchase_order_id = None
        if purchase_order_number:
            purchase_orders = registry.database(
                model_name="PurchaseOrder",
                operation="filter",
                data={"number": purchase_order_number, "corporate_id": corporate_id}
            )
            if not purchase_orders:
                return ResponseProvider(message=f"Purchase order with number {purchase_order_number} not found for this corporate", code=404).bad_request()
            purchase_order_id = purchase_orders[0]["id"]

        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Vendor bill line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable_id"))
            if taxable_id:
                tax_rates = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id}
                )
                if not tax_rates:
                    return ResponseProvider(message=f"Tax rate {taxable_id} not found", code=404).bad_request()
                tax_rate_value = get_tax_rate_value(tax_rates[0])
            else:
                tax_rate_value = Decimal('0')

            purchase_order_line_id = line_data.get("purchase_order_line")
            if purchase_order_line_id and purchase_order_id:
                po_lines = registry.database(
                    model_name="PurchaseOrderLine",
                    operation="filter",
                    data={"id": purchase_order_line_id, "purchase_order_id": purchase_order_id}
                )
                if not po_lines:
                    return ResponseProvider(message=f"Purchase order line {purchase_order_line_id} not found", code=404).bad_request()

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

        with transaction.atomic():
            vendor_bill_data = {
                "vendor_id": data["vendor"],
                "corporate_id": corporate_id,
                "purchase_order_id": purchase_order_id,
                "date": data["date"],
                "number": data["number"],
                "due_date": data["due_date"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "created_by_id": data["created_by"],
                "status": "DRAFT",
                "sub_total": float(sub_total),
                "tax_total": float(tax_total),
                "total_discount": float(total_discount),
                "total": float(total),
            }
            vendor_bill = registry.database(
                model_name="VendorBill",
                operation="create",
                data=vendor_bill_data
            )

            for line_data in lines:
                taxable_id = normalize_taxable_id(line_data.get("taxable_id"))
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

                line_data_for_creation = {
                    "vendor_bill_id": vendor_bill["id"],
                    "purchase_order_line_id": line_data.get("purchase_order_line"),
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                }
                registry.database(
                    model_name="VendorBillLine",
                    operation="create",
                    data=line_data_for_creation
                )

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_CREATED",
            user=user,
            message=f"Vendor bill {vendor_bill['number']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={"vendor_bill_id": vendor_bill["id"], "line_count": len(lines)},
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

        lines = registry.database(
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
            for line in lines
        ]

        return ResponseProvider(
            message="Vendor bill created successfully",
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
    Update an existing vendor bill for the user's corporate, including its lines, and set status to DRAFT or POSTED.

    Expected data:
    - id: UUID of the vendor bill
    - vendor: UUID of the vendor
    - corporate_id: UUID of the corporate
    - purchase_order: UUID of the purchase order (optional)
    - date: Date of the vendor bill (YYYY-MM-DD)
    - number: Vendor bill number (unique)
    - due_date: Due date of the vendor bill (YYYY-MM-DD)
    - created_by: UUID of the user creating/updating the vendor bill
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - status: DRAFT or POSTED
    - lines: List of dictionaries, each containing fields for VendorBillLine
      - id: UUID of the line (optional, for updates)
      - description ○ quantity ○ unit_price ○ discount ○ taxable_id
      - purchase_order_line: UUID of the purchase order line (optional)
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

        required_fields = ["id", "vendor", "date", "number", "due_date", "created_by"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found", code=404).bad_request()
        vendor_bill_id = vendor_bills[0]["id"]

        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
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

        purchase_order_id = data.get("purchase_order")
        if purchase_order_id:
            purchase_orders = registry.database(
                model_name="PurchaseOrder",
                operation="filter",
                data={"id": purchase_order_id, "corporate_id": corporate_id}
            )
            if not purchase_orders:
                return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()

        normalized_status = str(data.get("status", "DRAFT")).upper()
        if normalized_status not in {"DRAFT", "POSTED"}:
            normalized_status = "DRAFT"

        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        submitted_lines = data.get("lines", [])
        for line_data in submitted_lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Vendor bill line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable_id"))
            if taxable_id:
                tax_rates = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id}
                )
                if not tax_rates:
                    return ResponseProvider(message=f"Tax rate {taxable_id} not found", code=404).bad_request()
                tax_rate_value = get_tax_rate_value(tax_rates[0])
            else:
                tax_rate_value = Decimal('0')

            purchase_order_line_id = line_data.get("purchase_order_line")
            if purchase_order_line_id:
                po_lines = registry.database(
                    model_name="PurchaseOrderLine",
                    operation="filter",
                    data={"id": purchase_order_line_id, "purchase_order_id": purchase_order_id}
                )
                if not po_lines:
                    return ResponseProvider(message=f"Purchase order line {purchase_order_line_id} not found", code=404).bad_request()

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

        with transaction.atomic():
            vendor_bill_data = {
                "id": data["id"],
                "vendor_id": data["vendor"],
                "corporate_id": corporate_id,
                "purchase_order_id": purchase_order_id,
                "date": data["date"],
                "number": data["number"],
                "due_date": data["due_date"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "created_by_id": data["created_by"],
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

            existing_lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vendor_bill["id"]}
            )
            existing_line_ids = {line["id"] for line in existing_lines if line.get("id")}
            submitted_line_ids = {line.get("id") for line in submitted_lines if line.get("id")}

            for line in existing_lines:
                if line["id"] not in submitted_line_ids:
                    registry.database(
                        model_name="VendorBillLine",
                        operation="delete",
                        instance_id=line["id"]
                    )

            for line_data in submitted_lines:
                taxable_id = normalize_taxable_id(line_data.get("taxable_id"))
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
                    "vendor_bill_id": vendor_bill["id"],
                    "purchase_order_line_id": line_data.get("purchase_order_line"),
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                }

                if line_data.get("id") in existing_line_ids:
                    line_payload["id"] = line_data["id"]
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

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_UPDATED",
            user=user,
            message=f"Vendor bill {vendor_bill['number']} updated for corporate {corporate_id} with status {vendor_bill['status']}",
            state_name="Completed",
            extra={"vendor_bill_id": vendor_bill["id"], "line_count": len(submitted_lines)},
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

        db_lines = registry.database(
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
            for line in db_lines
        ]

        return ResponseProvider(
            message="Vendor bill updated successfully",
            data=vendor_bill,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating vendor bill", code=500).exception()

@csrf_exempt
def list_vendor_bills(request):
    """
    List all vendor bills for the user's corporate, categorized by status.

    Returns:
    - 200: List of vendor bills with total count and status counts
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

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"corporate_id": corporate_id}
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

        serialized_vendor_bills = []
        for vb in vendor_bills:
            lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vb["id"]}
            )
            vb_total = sum(float(line.get("total", 0)) for line in lines)
            created_by_id = vb.get("created_by_id")
            created_by_name = str(created_by_id)
            if created_by_id:
                user_data = registry.database(
                    model_name="CustomUser",
                    operation="filter",
                    data={"id": created_by_id}
                )
                if user_data:
                    user = user_data[0]
                    first_name = user.get("first_name", "")
                    last_name = user.get("last_name", "")
                    username = user.get("username", "")
                    created_by_name = (
                        f"{first_name} {last_name}".strip() or username or str(created_by_id)
                    )

            serialized_vendor_bills.append({
                "id": str(vb["id"]),
                "number": vb["number"],
                "vendor": str(vb["vendor_id"]),
                "date": vb["date"],
                "due_date": vb["due_date"],
                "status": vb["status"],
                "created_by": created_by_id,
                "purchase_order": str(vb.get("purchase_order_id", "")),
                "comments": vb["comments"],
                "terms": vb["terms"],
                "total": float(vb_total),
                "sub_total": float(vb.get("sub_total", 0)),
                "tax_total": float(vb.get("tax_total", 0)),
                "total_discount": float(vb.get("total_discount", 0)),
                "lines": [
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
                    for line in lines
                ]
            })

        statuses = [vb["status"] for vb in vendor_bills]
        status_counts = dict(Counter(statuses))
        total = len(vendor_bills)

        all_statuses = {"DRAFT": 0, "POSTED": 0, "PAID": 0, "PARTIALLY_PAID": 0, "OVERDUE": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} vendor bills for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            data={
                "vendor_bills": serialized_vendor_bills,
                "total": total,
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
    """
    Get a single vendor bill by ID for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the vendor bill

    Returns:
    - 200: Vendor bill retrieved successfully with lines
    - 400: Bad request (missing ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor bill not found for this corporate
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

        vendor_bill_id = data.get("id")
        if not vendor_bill_id:
            return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found for this corporate", code=404).bad_request()

        vendor_bill = vendor_bills[0]
        lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill_id}
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
            for line in lines
        ]
        vendor_bill["total"] = float(sum(to_decimal(line.get("total", 0)) for line in lines))

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_GET_SUCCESS",
            user=user,
            message=f"Vendor bill {vendor_bill_id} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"vendor_bill_id": vendor_bill_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Vendor bill retrieved successfully",
            data=vendor_bill,
            code=200
        ).success()

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
    Soft delete a vendor bill by setting is_active to False for both the vendor bill and its lines.

    Expected data:
    - id: UUID of the vendor bill

    Returns:
    - 200: Vendor bill deleted successfully
    - 400: Bad request (missing ID or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor bill not found for this corporate
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

        vendor_bill_id = data.get("id")
        if not vendor_bill_id:
            return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found for this corporate", code=404).bad_request()

        with transaction.atomic():
            registry.database(
                model_name="VendorBill",
                operation="delete",
                instance_id=vendor_bill_id,
                data={"id": vendor_bill_id}
            )

            lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vendor_bill_id}
            )
            for line in lines:
                registry.database(
                    model_name="VendorBillLine",
                    operation="delete",
                    instance_id=line["id"],
                    data={"id": line["id"]}
                )

        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_DELETED",
            user=user,
            message=f"Vendor bill {vendor_bill_id} soft-deleted",
            state_name="Completed",
            extra={"vendor_bill_id": vendor_bill_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Vendor bill deleted successfully",
            data={"vendor_bill_id": vendor_bill_id},
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