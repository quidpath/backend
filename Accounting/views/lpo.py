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
            transaction_type="PURCHASE_ORDER_TAX_RATE_WARNING",
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
                transaction_type="PURCHASE_ORDER_TAX_RATE_ERROR",
                user=None,
                message=f"Invalid tax rate label format: {label}",
                state_name="Failed",
                request=None
            )
            return Decimal("0")
    TransactionLogBase.log(
        transaction_type="PURCHASE_ORDER_TAX_RATE_WARNING",
        user=None,
        message=f"Could not parse tax rate from label: {label}",
        state_name="Warning",
        request=None
    )
    return Decimal("0")

@csrf_exempt
def update_purchase_order(request):
    """
    Update an existing purchase order for the user's corporate, including its lines, and set status to DRAFT or POSTED.
    Uses quotation_number instead of quotation_id for the quotation reference.
    Does not send an email notification.

    Expected data:
    - id: UUID of the purchase order
    - vendor: UUID of the vendor
    - date: Date of the purchase order (YYYY-MM-DD)
    - number: Purchase order number (unique)
    - expected_delivery: Expected delivery date (YYYY-MM-DD)
    - created_by: UUID of the user updating the purchase order
    - ship_via: Shipping method (optional)
    - terms: Payment terms (optional)
    - fob: FOB terms (optional)
    - comments: Comments (optional)
    - quotation_number: Quotation number (optional)
    - status: DRAFT or POSTED
    - lines: List of dictionaries, each containing fields for PurchaseOrderLine
        - id: UUID of the line (optional, for updates)
        - description: Item description
        - quantity: Quantity of the item
        - unit_price: Price per unit
        - discount: Discount amount
        - taxable_id: Tax rate ID or exempt status
    """
    def normalize_taxable_id(raw):
        """
        Accepts any of:
          - UUID string
          - dict with {'id': ...}
          - stringified dict (including fancy quotes like “{...}”)
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
                except Exception:
                    try:
                        d = ast.literal_eval(s)
                    except Exception:
                        d = None
                if isinstance(d, dict):
                    return d.get("id") or d.get("uuid") or d.get("pk")
            return s
        return str(raw)

    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Validate user corporate association
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
        required_fields = ["id", "vendor", "date", "number", "expected_delivery", "created_by"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate purchase order
        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found", code=404).bad_request()
        purchase_order_id = purchase_orders[0]["id"]

        # Validate vendor
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()

        # Validate created_by user
        created_by_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["created_by"], "corporate_id": corporate_id, "is_active": True}
        )
        if not created_by_users:
            return ResponseProvider(message="Created by user not found or inactive for this corporate", code=404).bad_request()

        # Validate optional quotation by number
        quotation = None
        if "quotation_number" in data:
            quotations = registry.database(
                model_name="Quotation",
                operation="filter",
                data={"number": data["quotation_number"], "corporate_id": corporate_id}
            )
            if not quotations:
                return ResponseProvider(message=f"Quotation with number {data['quotation_number']} not found for this corporate", code=404).bad_request()
            quotation = quotations[0]

        # Normalize status
        normalized_status = str(data.get("status", "DRAFT")).upper()
        if normalized_status not in {"DRAFT", "POSTED"}:
            normalized_status = "DRAFT"

        # Process lines and calculate totals
        submitted_lines = data.get("lines", [])
        if not submitted_lines:
            return ResponseProvider(message="At least one purchase order line is required", code=400).bad_request()

        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in submitted_lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Purchase order line field {field.replace('_', ' ').title()} is required",
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

        # Update purchase order and lines within a transaction
        with transaction.atomic():
            purchase_order_data = {
                "id": data["id"],
                "vendor_id": data["vendor"],
                "corporate_id": corporate_id,
                "quotation_id": quotation["id"] if quotation else None,
                "date": data["date"],
                "number": data["number"],
                "expected_delivery": data["expected_delivery"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "ship_date": data.get("ship_date"),
                "ship_via": data.get("ship_via", ""),
                "fob": data.get("fob", ""),
                "created_by_id": data["created_by"],
                "status": normalized_status,
                "sub_total": float(sub_total),
                "tax_total": float(tax_total),
                "total": float(total),
                "total_discount": float(total_discount),
            }
            purchase_order = registry.database(
                model_name="PurchaseOrder",
                operation="update",
                instance_id=purchase_order_id,
                data=purchase_order_data
            )

            # Delete omitted lines
            existing_lines = registry.database(
                model_name="PurchaseOrderLine",
                operation="filter",
                data={"purchase_order_id": purchase_order["id"]}
            )
            existing_line_ids = {line["id"] for line in existing_lines if line.get("id")}
            submitted_line_ids = {line.get("id") for line in submitted_lines if line.get("id")}

            for line in existing_lines:
                if line["id"] not in submitted_line_ids:
                    registry.database(
                        model_name="PurchaseOrderLine",
                        operation="delete",
                        instance_id=line["id"]
                    )

            # Create or update lines
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
                    "purchase_order_id": purchase_order["id"],
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(discount),
                }

                if line_data.get("id") in existing_line_ids:
                    line_payload["id"] = line_data["id"]
                    registry.database(
                        model_name="PurchaseOrderLine",
                        operation="update",
                        instance_id=line_data["id"],
                        data=line_payload
                    )
                else:
                    registry.database(
                        model_name="PurchaseOrderLine",
                        operation="create",
                        data=line_payload
                    )

        # Log update
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_UPDATED_AND_POSTED",
            user=user,
            message=f"Purchase order {purchase_order['number']} updated and posted for corporate {corporate_id} with status {purchase_order['status']}",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order["id"], "line_count": len(submitted_lines)},
            request=request
        )

        # Fetch fresh lines for response
        db_lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order["id"]}
        )
        purchase_order["lines"] = [
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
                "total_discount": float(line.get("total_discount", 0)),
                "taxable": {
                    "id": str(line.get("taxable_id", "")),
                    "code": str(line.get("taxable_id")),
                    "label": str(line.get("taxable_id"))
                } if line.get("taxable_id") else {
                    "id": "exempt",
                    "code": "exempt",
                    "label": "Exempt (0%)"
                }
            }
            for line in db_lines
        ]

        # Add calculated totals to response
        purchase_order["sub_total"] = float(sub_total)
        purchase_order["tax_total"] = float(tax_total)
        purchase_order["total_discount"] = float(total_discount)
        purchase_order["total"] = float(total)

        return ResponseProvider(
            message="Purchase order updated and posted successfully",
            data=purchase_order,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_UPDATE_AND_POST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating purchase order", code=500).exception()

@csrf_exempt
def save_purchase_order_draft(request):
    """
    Save a new purchase order as draft for the user's corporate, including its lines.
    Calculates sub_total, tax_total, total, and total_discount for the response.

    Expected data:
    - vendor: UUID of the vendor (required)
    - customer: UUID of the customer (optional, for compatibility)
    - corporate_id: UUID of the corporate (required)
    - date: Date of the purchase order (YYYY-MM-DD, required)
    - number: Purchase order number (unique, required)
    - expected_delivery: Expected delivery date (YYYY-MM-DD, required)
    - created_by: UUID of the user creating the purchase order (required)
    - ship_via: Shipping method (optional)
    - terms: Payment terms (optional)
    - fob: FOB terms (optional)
    - comments: Comments (optional)
    - quotation: Quotation number (optional)
    - lines: List of dictionaries, each containing fields for PurchaseOrderLine
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        registry = ServiceRegistry()

        # Verify corporate association
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

        # Handle vendor/customer field
        vendor_id = data.get("vendor") or data.get("customer")
        if not vendor_id:
            return ResponseProvider(message="Vendor is required", code=400).bad_request()

        # Validate vendor
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": vendor_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()

        # Validate required fields
        required_fields = ["vendor", "date", "number", "expected_delivery", "created_by"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate created_by
        buyers = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["created_by"], "corporate_id": corporate_id, "is_active": True}
        )
        if not buyers:
            return ResponseProvider(message="Created by user not found or inactive for this corporate", code=404).bad_request()

        # Validate quotation if provided
        quotation = data.get("quotation", "")

        # Process purchase order lines and calculate totals
        lines = data.get("lines", [])
        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Purchase order line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable_id"))
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

        # Save purchase order with atomic transaction
        with transaction.atomic():
            purchase_order_data = {
                "vendor_id": vendor_id,
                "corporate_id": corporate_id,
                "quotation": quotation,
                "date": data["date"],
                "number": data["number"],
                "expected_delivery": data["expected_delivery"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "ship_date": data.get("ship_date"),
                "ship_via": data.get("ship_via", ""),
                "fob": data.get("fob", ""),
                "created_by_id": data["created_by"],
                "status": "DRAFT",
            }
            purchase_order = registry.database(
                model_name="PurchaseOrder",
                operation="create",
                data=purchase_order_data
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
                    "purchase_order_id": purchase_order["id"],
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(discount),
                }
                registry.database(
                    model_name="PurchaseOrderLine",
                    operation="create",
                    data=line_data_for_creation
                )

        # Log success
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_DRAFT_SAVED",
            user=user,
            message=f"Purchase order draft {purchase_order['number']} saved for corporate {corporate_id}",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order["id"], "line_count": len(lines), "vendor_id": vendor_id},
            request=request
        )

        # Fetch lines for response
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order["id"]}
        )
        purchase_order_response = {
            "id": str(purchase_order.get("id", "")),
            "vendor": str(vendor_id),
            "corporate_id": str(corporate_id),
            "quotation": quotation or "",
            "date": str(data["date"]),
            "number": purchase_order["number"],
            "status": "DRAFT",
            "expected_delivery": str(data["expected_delivery"]),
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "ship_date": str(data.get("ship_date")) if data.get("ship_date") else None,
            "ship_via": data.get("ship_via", ""),
            "fob": data.get("fob", ""),
            "created_by": str(data["created_by"]),
            "sub_total": float(sub_total),
            "tax_total": float(tax_total),
            "total_discount": float(total_discount),
            "total": float(total),
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
                    "total_discount": float(line.get("total_discount", 0)),
                    "taxable": {
                        "id": str(line.get("taxable_id", "")),
                        "code": str(line.get("taxable_id")),
                        "label": str(line.get("taxable_id"))
                    } if line.get("taxable_id") else {
                        "id": "exempt",
                        "code": "exempt",
                        "label": "Exempt (0%)"
                    }
                }
                for line in lines
            ]
        }

        return ResponseProvider(
            message="Purchase order draft saved successfully",
            data=purchase_order_response,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_DRAFT_SAVE_FAILED",
            user=user,
            message=f"Failed to save purchase order draft: {str(e)}",
            state_name="Failed",
            extra={"data": data, "error": str(e)},
            request=request
        )
        return ResponseProvider(message=f"An error occurred while saving purchase order draft: {str(e)}", code=500).exception()

@csrf_exempt
def create_and_post_purchase_order(request):
    """
    Create a new purchase order for the user's corporate, set status to POSTED, and save it to the database.
    Calculates sub_total, tax_total, total, and total_discount for the purchase order.
    Does not send an email notification. Uses quotation_number instead of quotation_id for the quotation reference.

    Expected data:
    - vendor: UUID of the vendor
    - corporate_id: UUID of the corporate
    - date: Date of the purchase order (YYYY-MM-DD)
    - number: Purchase order number (unique)
    - expected_delivery: Expected delivery date (YYYY-MM-DD)
    - created_by: UUID of the user creating the purchase order
    - ship_via: Shipping method (optional)
    - terms: Payment terms (optional)
    - fob: FOB terms (optional)
    - comments: Comments (optional)
    - quotation_number: Quotation number (optional, instead of quotation_id)
    - lines: List of dictionaries, each containing fields for PurchaseOrderLine
        - description: Line item description
        - quantity: Quantity of the item
        - unit_price: Price per unit
        - discount: Discount amount
        - taxable_id: Tax rate ID or exempt status
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

        # Validate user corporate association
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
        required_fields = ["vendor", "date", "number", "expected_delivery", "created_by"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate vendor
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()
        vendor = vendors[0]

        # Validate created_by user
        buyers = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["created_by"], "corporate_id": corporate_id, "is_active": True}
        )
        if not buyers:
            return ResponseProvider(message="Created by user not found or inactive for this corporate", code=404).bad_request()

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found", code=404).bad_request()
        corporate = corporates[0]

        # Validate optional quotation by number
        quotation = None
        if "quotation_number" in data:
            quotations = registry.database(
                model_name="Quotation",
                operation="filter",
                data={"number": data["quotation_number"], "corporate_id": corporate_id}
            )
            if not quotations:
                return ResponseProvider(message=f"Quotation with number {data['quotation_number']} not found for this corporate", code=404).bad_request()
            quotation = quotations[0]

        # Process purchase order lines and calculate totals
        lines = data.get("lines", [])
        if not lines:
            return ResponseProvider(message="At least one purchase order line is required", code=400).bad_request()

        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable_id"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Purchase order line field {field.replace('_', ' ').title()} is required",
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

        # Create purchase order and lines within a transaction
        with transaction.atomic():
            purchase_order_data = {
                "vendor_id": data["vendor"],
                "corporate_id": corporate_id,
                "quotation": quotation["id"] if quotation else None,
                "date": data["date"],
                "number": data["number"],
                "expected_delivery": data["expected_delivery"],
                "comments": data.get("comments", ""),
                "terms": data.get("terms", ""),
                "ship_date": data.get("ship_date"),
                "ship_via": data.get("ship_via", ""),
                "fob": data.get("fob", ""),
                "created_by_id": data["created_by"],
                "status": "POSTED",
            }
            purchase_order = registry.database(
                model_name="PurchaseOrder",
                operation="create",
                data=purchase_order_data
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
                    "purchase_order_id": purchase_order["id"],
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(discount),
                }
                registry.database(
                    model_name="PurchaseOrderLine",
                    operation="create",
                    data=line_data_for_creation
                )

        # Log the transaction
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_CREATED_AND_POSTED",
            user=user,
            message=f"Purchase order {purchase_order['number']} created and posted for corporate {corporate_id}",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for response
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order["id"]}
        )
        purchase_order["lines"] = [
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
                "total_discount": float(line.get("total_discount", 0)),
                "taxable": {
                    "id": str(line.get("taxable_id", "")),
                    "code": str(line.get("taxable_id")),
                    "label": str(line.get("taxable_id"))
                } if line.get("taxable_id") else {
                    "id": "exempt",
                    "code": "exempt",
                    "label": "Exempt (0%)"
                }
            }
            for line in lines
        ]

        # Add calculated totals to response
        purchase_order["sub_total"] = float(sub_total)
        purchase_order["tax_total"] = float(tax_total)
        purchase_order["total_discount"] = float(total_discount)
        purchase_order["total"] = float(total)

        return ResponseProvider(
            message="Purchase order created and posted successfully",
            data=purchase_order,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_CREATION_AND_POST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating and posting purchase order", code=500).exception()

@csrf_exempt
def list_purchase_orders(request):
    """
    List all purchase orders for the user's corporate, categorized by status.

    Returns:
    - 200: List of purchase orders with total count and status counts
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

        def tax_display(taxable_id_value):
            if not taxable_id_value:
                return "Exempt (0%)"
            tr = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": taxable_id_value}
            )
            return tr[0].get("name", "Exempt (0%)") if tr else "Exempt (0%)"

        serialized_purchase_orders = []
        for po in purchase_orders:
            lines = registry.database(
                model_name="PurchaseOrderLine",
                operation="filter",
                data={"purchase_order_id": po["id"]}
            )
            # Calculate total for the purchase order
            po_total = sum(float(line.get("total", 0)) for line in lines)
            # Fetch user details for created_by
            created_by_id = po.get("created_by_id")
            created_by_name = str(created_by_id)  # Default to ID as fallback
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
                    # Construct full name or fall back to username
                    created_by_name = (
                        f"{first_name} {last_name}".strip() or username or str(created_by_id)
                    )

            serialized_purchase_orders.append({
                "id": str(po["id"]),
                "number": po["number"],
                "vendor": str(po["vendor_id"]),
                "date": po["date"],
                "expected_delivery": po["expected_delivery"],
                "status": po["status"],
                "created_by": created_by_id,
                "ship_date": po.get("ship_date"),
                "ship_via": po["ship_via"],
                "terms": po["terms"],
                "fob": po["fob"],
                "comments": po["comments"],
                "quotation": str(po["quotation"]) if po.get("quotation") else None,
                "total": float(po_total),
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
                        "total_discount": float(line.get("total_discount", 0)),
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

        statuses = [po["status"] for po in purchase_orders]
        status_counts = dict(Counter(statuses))
        total = len(purchase_orders)

        all_statuses = {"DRAFT": 0, "SENT": 0, "CONFIRMED": 0, "RECEIVED": 0, "PARTIALLY_RECEIVED": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} purchase orders for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            data={
                "purchase_orders": serialized_purchase_orders,
                "total": total,
                "status_counts": all_statuses
            },
            message="Purchase orders retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving purchase orders", code=500).exception()

@csrf_exempt
def get_purchase_order(request):
    """
    Get a single purchase order by ID for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the purchase order

    Returns:
    - 200: Purchase order retrieved successfully with lines
    - 400: Bad request (missing ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Purchase order not found for this corporate
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

        purchase_order_id = data.get("id")
        if not purchase_order_id:
            return ResponseProvider(message="Purchase order ID is required", code=400).bad_request()

        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": purchase_order_id, "corporate_id": corporate_id}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()

        purchase_order = purchase_orders[0]
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order_id}
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

        purchase_order["lines"] = [
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
                "total_discount": float(line.get("total_discount", 0)),
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
        purchase_order["total"] = float(sum(to_decimal(line.get("total", 0)) for line in lines))

        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_GET_SUCCESS",
            user=user,
            message=f"Purchase order {purchase_order_id} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"purchase_order_id": purchase_order_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Purchase order retrieved successfully",
            data=purchase_order,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_GET_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving purchase order", code=500).exception()

@csrf_exempt
def delete_purchase_order(request):
    """
    Soft delete a purchase order by setting is_active to False for both the purchase order and its lines.

    Expected data:
    - id: UUID of the purchase order

    Returns:
    - 200: Purchase order deleted successfully
    - 400: Bad request (missing ID or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Purchase order not found for this corporate
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

        purchase_order_id = data.get("id")
        if not purchase_order_id:
            return ResponseProvider(message="Purchase order ID is required", code=400).bad_request()

        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": purchase_order_id, "corporate_id": corporate_id}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()

        with transaction.atomic():
            registry.database(
                model_name="PurchaseOrder",
                operation="delete",
                instance_id=purchase_order_id,
                data={"id": purchase_order_id}
            )

            lines = registry.database(
                model_name="PurchaseOrderLine",
                operation="filter",
                data={"purchase_order_id": purchase_order_id}
            )
            for line in lines:
                registry.database(
                    model_name="PurchaseOrderLine",
                    operation="delete",
                    instance_id=line["id"],
                    data={"id": line["id"]}
                )

        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_DELETED",
            user=user,
            message=f"Purchase order {purchase_order_id} soft-deleted",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Purchase order deleted successfully",
            data={"purchase_order_id": purchase_order_id},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting purchase order", code=500).exception()

@csrf_exempt
def convert_quotation_to_purchase_order(request):
    """
    Convert a quotation to a purchase order, linking to a vendor, and create purchase order lines.

    Expected data:
    - quotation_id: UUID of the quotation
    - vendor_id: UUID of the vendor
    - date: Date of the purchase order
    - number: Purchase order number (unique)
    - expected_delivery: Expected delivery date
    - buyer: UUID of the user creating the purchase order
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - send_email: Boolean to indicate if purchase order should be emailed (default: False)
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

        required_fields = ["quotation_id", "vendor_id", "date", "number", "expected_delivery", "buyer"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        quotations = registry.database(
            model_name="Quotation",
            operation="filter",
            data={"id": data["quotation_id"], "corporate_id": corporate_id}
        )
        if not quotations:
            return ResponseProvider(message="Quotation not found for this corporate", code=404).bad_request()
        quotation = quotations[0]

        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor_id"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()
        vendor = vendors[0]

        buyers = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["buyer"], "corporate_id": corporate_id, "is_active": True}
        )
        if not buyers:
            return ResponseProvider(message="Buyer not found or inactive for this corporate", code=404).bad_request()

        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found", code=404).bad_request()
        corporate = corporates[0]

        quotation_lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        if not quotation_lines:
            return ResponseProvider(message="No lines found for this quotation", code=400).bad_request()

        with transaction.atomic():
            purchase_order_data = {
                "vendor_id": data["vendor_id"],
                "corporate_id": corporate_id,
                "quotation_id": quotation["id"],
                "date": data["date"],
                "number": data["number"],
                "expected_delivery": data["expected_delivery"],
                "comments": data.get("comments", quotation["comments"]),
                "terms": data.get("terms", quotation["terms"]),
                "created_by_id": data["buyer"],
                "ship_date": data.get("ship_date", quotation.get("ship_date")),
                "ship_via": data.get("ship_via", quotation["ship_via"]),
                "fob": data.get("fob", quotation["fob"]),
                "status": "DRAFT",
                "sub_total": float(quotation.get("sub_total", 0.00)),
                "tax_total": float(quotation.get("tax_total", 0.00)),
                "total": float(quotation.get("total", 0.00)),
                "total_discount": float(quotation.get("total_discount", 0.00)),
            }
            purchase_order = registry.database(
                model_name="PurchaseOrder",
                operation="create",
                data=purchase_order_data
            )

            for line in quotation_lines:
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
                    "purchase_order_id": purchase_order["id"],
                    "description": line["description"],
                    "quantity": float(line["quantity"]),
                    "unit_price": float(line["unit_price"]),
                    "amount": float(line_subtotal),
                    "discount": float(line["discount"]),
                    "taxable_id": line["taxable_id"],
                    "tax_amount": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(line["discount"]),
                }
                registry.database(
                    model_name="PurchaseOrderLine",
                    operation="create",
                    data=line_data
                )

        TransactionLogBase.log(
            transaction_type="QUOTATION_CONVERTED_TO_PURCHASE_ORDER",
            user=user,
            message=f"Quotation {quotation['number']} converted to purchase order {purchase_order['number']} for corporate {corporate_id}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "purchase_order_id": purchase_order["id"], "line_count": len(quotation_lines)},
            request=request
        )

        purchase_order_lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order["id"]}
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

        purchase_order["lines"] = [
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
                "total_discount": float(line.get("total_discount", 0)),
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
            for line in purchase_order_lines
        ]

        if data.get("send_email", False):
            to_email = vendor.get("email")
            if not to_email:
                TransactionLogBase.log(
                    transaction_type="PURCHASE_ORDER_SEND_FAILED",
                    user=user,
                    message="Vendor has no email",
                    state_name="Failed",
                    request=request
                )
            else:
                subject = f"Purchase Order {purchase_order['number']} from {corporate['name']}"
                message = f"""
                <html>
                <body>
                <p>Dear {vendor.get('name', 'Vendor')},</p>
                <p>We have issued the following purchase order based on Quotation {quotation['number']}:</p>
                <p><strong>Purchase Order Number:</strong> {purchase_order['number']}</p>
                <p><strong>Date:</strong> {purchase_order['date']}</p>
                <p><strong>Expected Delivery:</strong> {purchase_order['expected_delivery']}</p>
                <p><strong>Ship Via:</strong> {purchase_order['ship_via'] or 'N/A'}</p>
                <p><strong>Terms:</strong> {purchase_order['terms'] or 'N/A'}</p>
                <p><strong>FOB:</strong> {purchase_order['fob'] or 'N/A'}</p>
                <p><strong>Comments:</strong> {purchase_order['comments'] or 'N/A'}</p>
                <p><strong>Sub Total:</strong> KES {purchase_order['sub_total']:.2f}</p>
                <p><strong>Tax Total:</strong> KES {purchase_order['tax_total']:.2f}</p>
                <p><strong>Total Discount:</strong> KES {purchase_order['total_discount']:.2f}</p>
                <p><strong>Total:</strong> KES {purchase_order['total']:.2f}</p>
                <h3>Items:</h3>
                <table border="1" cellpadding="6" cellspacing="0">
                <tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th><th>Discount</th><th>Tax Rate</th><th>Total</th></tr>
                """
                for line in purchase_order_lines:
                    message += f"""
                    <tr>
                    <td>{line['description']}</td>
                    <td>{line['quantity']}</td>
                    <td>KES {line['unit_price']:.2f}</td>
                    <td>KES {line['amount']:.2f}</td>
                    <td>KES {line['discount']:.2f}</td>
                    <td>{tax_display(line.get('taxable_id'))}</td>
                    <td>KES {line['total']:.2f}</td>
                    </tr>
                    """
                message += f"""
                </table>
                <p>Thank you for your business!</p>
                <p>Best regards,<br>{corporate['name']}</p>
                </body>
                </html>
                """
                notification_handler = DocumentNotificationHandler()
                notifications = [{
                    "message_type": "EMAIL",
                    "organisation_id": corporate_id,
                    "destination": to_email,
                    "message": message,
                    "subject": subject,
                }]
                send_result = notification_handler.send_document_notification(notifications, trans=None, attachment=None, cc=None)
                if send_result != "success":
                    TransactionLogBase.log(
                        transaction_type="PURCHASE_ORDER_SEND_FAILED",
                        user=user,
                        message="Failed to send purchase order email",
                        state_name="Failed",
                        request=request
                    )
                else:
                    registry.database(
                        model_name="PurchaseOrder",
                        operation="update",
                        instance_id=purchase_order["id"],
                        data={"id": purchase_order["id"], "status": "SENT"}
                    )
                    purchase_order["status"] = "SENT"

        return ResponseProvider(
            message="Purchase order created successfully",
            data=purchase_order,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_CONVERT_TO_PURCHASE_ORDER_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while converting quotation to purchase order", code=500).exception()