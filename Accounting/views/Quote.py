from decimal import Decimal, InvalidOperation
import json
import ast
import re
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from collections import Counter
from quidpath_backend import settings
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
            except Exception:
                try:
                    d = ast.literal_eval(s)
                except Exception:
                    d = None
                if isinstance(d, dict):
                    return d.get("id") or d.get("uuid") or d.get("pk")
            return s
        return str(raw)


def get_tax_rate_value(tax_rate):
    """Extract tax rate percentage from TaxRate label (e.g., 'VAT (16%)' -> 0.16)."""
    if not tax_rate or not tax_rate.get("name"):
        TransactionLogBase.log(
            transaction_type="QUOTATION_TAX_RATE_WARNING",
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
                transaction_type="QUOTATION_TAX_RATE_ERROR",
                user=None,
                message=f"Invalid tax rate label format: {label}",
                state_name="Failed",
                request=None
            )
            return Decimal("0")
    TransactionLogBase.log(
        transaction_type="QUOTATION_TAX_RATE_WARNING",
        user=None,
        message=f"Could not parse tax rate from label: {label}",
        state_name="Warning",
        request=None
    )
    return Decimal("0")


@csrf_exempt
def save_quotation_draft(request):
    """
    Save a new quotation as draft for the user's corporate, including its lines.
    Calculates sub_total, tax_total, total, and total_discount for the quotation.

    Expected data:
    - customer: UUID of the customer
    - date: Date of the quotation
    - number: Quotation number
    - valid_until: Validity date of the quotation
    - salesperson: UUID of the salesperson
    - ship_date: Shipping date
    - ship_via: Shipping method
    - terms: Payment terms
    - fob: FOB terms
    - comments: Comments (optional)
    - T_and_C: Terms and Conditions (optional)
    - lines: List of dictionaries, each containing fields for QuotationLine
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

        required_fields = ["customer", "date", "number", "valid_until", "ship_date", "ship_via", "terms", "fob",
                           "salesperson"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": data["customer"], "corporate_id": corporate_id, "is_active": True}
        )
        if not customers:
            return ResponseProvider(message="Customer not found or inactive for this corporate", code=404).bad_request()

        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["salesperson"], "corporate_id": corporate_id, "is_active": True}
        )
        if not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate",
                                    code=404).bad_request()

        lines = data.get("lines", [])
        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Quotation line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable"))
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

        with transaction.atomic():
            quotation_data = {
                "customer_id": data["customer"],
                "corporate_id": corporate_id,
                "date": data["date"],
                "number": data["number"],
                "valid_until": data["valid_until"],
                "comments": data.get("comments", ""),
                "T_and_C": data.get("T_and_C", ""),
                "ship_date": data["ship_date"],
                "ship_via": data["ship_via"],
                "terms": data["terms"],
                "fob": data["fob"],
                "salesperson_id": data["salesperson"],
                "status": "DRAFT",
            }
            quotation = registry.database(
                model_name="Quotation",
                operation="create",
                data=quotation_data
            )

            for line_data in lines:
                taxable_id = normalize_taxable_id(line_data.get("taxable"))
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
                    "quotation_id": quotation["id"],
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "grand_total": float(line_total),
                    "tax_amount": float(line_tax_amount),
                    "tax_total": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(discount),
                }
                registry.database(
                    model_name="QuotationLine",
                    operation="create",
                    data=line_data_for_creation
                )

        TransactionLogBase.log(
            transaction_type="QUOTATION_DRAFT_SAVED",
            user=user,
            message=f"Quotation draft {quotation['number']} saved for corporate {corporate_id}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "line_count": len(lines)},
            request=request
        )

        lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        quotation["lines"] = lines

        return ResponseProvider(
            message="Quotation draft saved successfully",
            data=quotation,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_DRAFT_SAVE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while saving quotation draft", code=500).exception()


@csrf_exempt
def create_and_post_quotation(request):
    """
    Create a new quotation for the user's corporate, set status to POSTED, and save it to the database.
    Calculates sub_total, tax_total, total, and total_discount for the quotation.
    Does not send an email notification.

    Expected data:
    - customer: UUID of the customer
    - date: Date of the quotation (YYYY-MM-DD)
    - number: Quotation number (unique)
    - valid_until: Validity date of the quotation (YYYY-MM-DD)
    - salesperson: UUID of the salesperson
    - ship_date: Shipping date (YYYY-MM-DD)
    - ship_via: Shipping method
    - terms: Payment terms
    - fob: FOB terms
    - comments: Comments (optional)
    - T_and_C: Terms and Conditions (optional)
    - lines: List of dictionaries, each containing fields for QuotationLine
        - description: Line item description
        - quantity: Quantity of the item
        - unit_price: Price per unit
        - discount: Discount amount
        - taxable: Tax rate ID or exempt status
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
        required_fields = ["customer", "date", "number", "valid_until", "ship_date", "ship_via", "terms", "fob", "salesperson"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        # Validate customer
        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": data["customer"], "corporate_id": corporate_id, "is_active": True}
        )
        if not customers:
            return ResponseProvider(message="Customer not found or inactive for this corporate", code=404).bad_request()
        customer = customers[0]

        # Validate salesperson
        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["salesperson"], "corporate_id": corporate_id, "is_active": True}
        )
        if not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate",
                                    code=404).bad_request()

        # Validate corporate
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found", code=404).bad_request()
        corporate = corporates[0]

        # Process quotation lines and calculate totals
        lines = data.get("lines", [])
        if not lines:
            return ResponseProvider(message="At least one quotation line is required", code=400).bad_request()

        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Quotation line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable"))
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

        # Create quotation and lines within a transaction
        with transaction.atomic():
            quotation_data = {
                "customer_id": data["customer"],
                "corporate_id": corporate_id,
                "date": data["date"],
                "number": data["number"],
                "valid_until": data["valid_until"],
                "comments": data.get("comments", ""),
                "T_and_C": data.get("T_and_C", ""),
                "ship_date": data["ship_date"],
                "ship_via": data["ship_via"],
                "terms": data["terms"],
                "fob": data["fob"],
                "salesperson_id": data["salesperson"],
                "status": "POSTED",  # Set status to POSTED
            }
            quotation = registry.database(
                model_name="Quotation",
                operation="create",
                data=quotation_data
            )

            for line_data in lines:
                taxable_id = normalize_taxable_id(line_data.get("taxable"))
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
                    "quotation_id": quotation["id"],
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "grand_total": float(line_total),
                    "tax_amount": float(line_tax_amount),
                    "tax_total": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(discount),
                }
                registry.database(
                    model_name="QuotationLine",
                    operation="create",
                    data=line_data_for_creation
                )

        # Log the transaction
        TransactionLogBase.log(
            transaction_type="QUOTATION_CREATED_AND_POSTED",
            user=user,
            message=f"Quotation {quotation['number']} created and posted for corporate {corporate_id}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for response
        lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        quotation["lines"] = [
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
        quotation["sub_total"] = float(sub_total)
        quotation["tax_total"] = float(tax_total)
        quotation["total_discount"] = float(total_discount)
        quotation["total"] = float(total)

        return ResponseProvider(
            message="Quotation created and posted successfully",
            data=quotation,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_CREATION_AND_POST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating and posting quotation", code=500).exception()


@csrf_exempt
def convert_quotation_to_invoice(request):
    """
    Convert a quotation to an invoice, mark the quotation as INVOICED, and create invoice lines.
    Optionally send the invoice to the customer via email.

    Expected data:
    - quotation_id: UUID of the quotation
    - date: Date of the invoice
    - number: Invoice number (unique)
    - due_date: Due date of the invoice
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - send_email: Boolean to indicate if invoice should be emailed (default: False)

    Returns:
    - 201: Invoice created successfully
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Quotation, customer, or salesperson not found
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

        required_fields = ["quotation_id", "date", "number", "due_date"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        quotations = registry.database(
            model_name="Quotation",
            operation="filter",
            data={"id": data["quotation_id"], "corporate_id": corporate_id}
        )
        if not quotations:
            return ResponseProvider(message="Quotation not found for this corporate", code=404).bad_request()
        quotation = quotations[0]

        if quotation["status"] == "INVOICED":
            return ResponseProvider(message="Quotation is already invoiced", code=400).bad_request()

        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": quotation["customer_id"], "corporate_id": corporate_id, "is_active": True}
        )
        if not customers:
            return ResponseProvider(message="Customer not found or inactive for this corporate", code=404).bad_request()
        customer = customers[0]

        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": quotation["salesperson_id"], "corporate_id": corporate_id, "is_active": True}
        )
        if not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate",
                                    code=404).bad_request()

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
            invoice_data = {
                "customer_id": quotation["customer_id"],
                "corporate_id": corporate_id,
                "quotation_id": quotation["id"],
                "date": data["date"],
                "number": data["number"],
                "due_date": data["due_date"],
                "comments": data.get("comments", quotation["comments"]),
                "terms": data.get("terms", quotation["terms"]),
                "salesperson_id": quotation["salesperson_id"],
                "ship_date": quotation["ship_date"],
                "ship_via": quotation["ship_via"],
                "fob": quotation["fob"],
                "status": "DRAFT",
                "sub_total": quotation.get("sub_total", 0.00),
                "tax_total": quotation.get("tax_total", 0.00),
                "total": quotation.get("total", 0.00),
                "total_discount": quotation.get("total_discount", 0.00),
            }
            invoice = registry.database(
                model_name="Invoices",
                operation="create",
                data=invoice_data
            )

            for line in quotation_lines:
                line_data = {
                    "invoice_id": invoice["id"],
                    "quotation_line_id": line["id"],
                    "description": line["description"],
                    "quantity": line["quantity"],
                    "unit_price": line["unit_price"],
                    "amount": line["amount"],
                    "discount": line["discount"],
                    "taxable_id": line["taxable_id"],
                    "tax_amount": line["tax_amount"],
                    "sub_total": line["sub_total"],
                    "total": line["total"],
                }
                registry.database(
                    model_name="InvoiceLine",
                    operation="create",
                    data=line_data
                )

            registry.database(
                model_name="Quotation",
                operation="update",
                instance_id=quotation["id"],
                data={"id": quotation["id"], "status": "INVOICED"}
            )

        TransactionLogBase.log(
            transaction_type="QUOTATION_CONVERTED_TO_INVOICE",
            user=user,
            message=f"Quotation {quotation['number']} converted to invoice {invoice['number']} for corporate {corporate_id}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "invoice_id": invoice["id"], "line_count": len(quotation_lines)},
            request=request
        )

        invoice_lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice["id"]}
        )
        invoice["lines"] = invoice_lines

        if data.get("send_email", False):
            to_email = customer.get("email")
            if not to_email:
                TransactionLogBase.log(
                    transaction_type="INVOICE_SEND_FAILED",
                    user=user,
                    message="Customer has no email",
                    state_name="Failed",
                    request=request
                )
            else:
                subject = f"Invoice {invoice['number']} from {corporate['name']}"
                message = f"""
                <html>
                <body>
                <p>Dear {customer.get('name', 'Customer')},</p>
                <p>We have issued the following invoice based on Quotation {quotation['number']}:</p>
                <p><strong>Invoice Number:</strong> {invoice['number']}</p>
                <p><strong>Date:</strong> {invoice['date']}</p>
                <p><strong>Due Date:</strong> {invoice['due_date']}</p>
                <p><strong>Ship Date:</strong> {invoice['ship_date']}</p>
                <p><strong>Ship Via:</strong> {invoice['ship_via']}</p>
                <p><strong>Terms:</strong> {invoice['terms']}</p>
                <p><strong>FOB:</strong> {invoice['fob']}</p>
                <p><strong>Comments:</strong> {invoice['comments']}</p>
                <p><strong>Sub Total:</strong> {invoice['sub_total']}</p>
                <p><strong>Tax Total:</strong> {invoice['tax_total']}</p>
                <p><strong>Total Discount:</strong> {invoice['total_discount']}</p>
                <p><strong>Total:</strong> {invoice['total']}</p>
                <h3>Lines:</h3>
                <table border="1">
                <tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th><th>Discount</th><th>Taxable</th><th>Total</th></tr>
                """
                for line in invoice_lines:
                    tax_rate = registry.database(
                        model_name="TaxRate",
                        operation="filter",
                        data={"id": line.get("taxable_id")}
                    )
                    tax_label = tax_rate[0]["name"] if tax_rate else "N/A"
                    message += f"""
                    <tr>
                    <td>{line['description']}</td>
                    <td>{line['quantity']}</td>
                    <td>{line['unit_price']}</td>
                    <td>{line['amount']}</td>
                    <td>{line['discount']}</td>
                    <td>{tax_label}</td>
                    <td>{line['total']}</td>
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
                send_result = notification_handler.send_document_notification(notifications, trans=None,
                                                                              attachment=None, cc=None)
                if send_result != "success":
                    TransactionLogBase.log(
                        transaction_type="INVOICE_SEND_FAILED",
                        user=user,
                        message="Failed to send invoice email",
                        state_name="Failed",
                        request=request
                    )
                else:
                    registry.database(
                        model_name="Invoices",
                        operation="update",
                        instance_id=invoice["id"],
                        data={"id": invoice["id"], "status": "ISSUED"}
                    )
                    invoice["status"] = "ISSUED"

        return ResponseProvider(
            message="Invoice created successfully",
            data=invoice,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_CONVERT_TO_INVOICE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while converting quotation to invoice", code=500).exception()

@csrf_exempt
def list_quotations(request):
    """
    List all quotations for the user's corporate, categorized by status.

    Returns:
    - 200: List of quotations with total count and status counts
    - 400: Bad request (missing corporate)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    # Get user ID from metadata
    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Query CorporateUser table to get corporate_id using user_id
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Query quotations for the corporate
        quotations = registry.database(
            model_name="Quotation",
            operation="filter",
            data={"corporate_id": corporate_id}
        )

        # Fetch lines and compute total for each quotation
        for q in quotations:
            lines = registry.database(
                model_name="QuotationLine",
                operation="filter",
                data={"quotation_id": q["id"]}
            )
            q_total = sum(float(line.get("total", 0)) for line in lines)
            q["lines"] = lines  # Include lines if needed, or set to [] to optimize

        # Serialize quotations to match frontend expectations
        serialized_quotations = [
            {
                "id": str(q["id"]),
                "number": q["number"],
                "customer": str(q["customer"]),
                "date": q["date"],
                "valid_until": q["valid_until"],
                "status": q["status"],
                "salesperson": str(q["salesperson"]),
                "ship_date": q["ship_date"],
                "ship_via": q["ship_via"],
                "terms": q["terms"],
                "fob": q["fob"],
                "comments": q["comments"],
                "T_and_C": q["T_and_C"],
                "lines": [
                    {
                        "id": str(line.get("id", "")),
                        "description": line.get("description", ""),
                        "quantity": line.get("quantity", 0),
                        "unit_price": float(line.get("unit_price", 0)),
                        "amount": float(line.get("amount", 0)),
                        "discount": float(line.get("discount", 0)),
                        "taxable": str(line.get("taxable", "")),
                        "grand_total": float(line.get("grand_total", 0)),
                        "tax_amount": float(line.get("tax_amount", 0)),
                        "tax_total": float(line.get("tax_total", 0)),
                        "sub_total": float(line.get("sub_total", 0)),
                        "total": float(line.get("total", 0)),
                        "total_discount": float(line.get("total_discount", 0))
                    }
                    for line in q.get("lines", [])
                ],
                "total": sum(float(line.get("total", 0)) for line in q.get("lines", []))  # Computed total
            }
            for q in quotations
        ]

        # Calculate status counts
        statuses = [q["status"] for q in quotations]
        status_counts = dict(Counter(statuses))
        total = len(quotations)

        # Ensure all possible statuses are included in counts
        all_statuses = {"DRAFT": 0, "SENT": 0, "INVOICED": 0, "REJECTED": 0}
        all_statuses.update(status_counts)

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="QUOTATION_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} quotations for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            data={
                "quotations": serialized_quotations,
                "total": total,
                "status_counts": all_statuses
            },
            message="Quotations retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving quotations", code=500).exception()

# urls.py (relevant endpoints with corrections)
@csrf_exempt
def get_quotation(request):
    """
    Get a single quotation by ID for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the quotation

    Returns:
    - 200: Quotation retrieved successfully with lines
    - 400: Bad request (missing ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Quotation not found for this corporate
    - 500: Internal server error
    """
    try:
        # Parse request data and metadata
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        # Get user ID from metadata
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        registry = ServiceRegistry()

        # Query CorporateUser table to get corporate_id using user_id
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        quotation_id = data.get("id")
        if not quotation_id:
            return ResponseProvider(message="Quotation ID is required", code=400).bad_request()

        # Initialize service registry
        registry = ServiceRegistry()

        # Fetch quotation
        quotations = registry.database(
            model_name="Quotation",
            operation="filter",
            data={"id": quotation_id, "corporate_id": corporate_id}
        )
        if not quotations:
            return ResponseProvider(message="Quotation not found for this corporate", code=404).bad_request()

        quotation = quotations[0]

        # Fetch quotation lines
        lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation_id}
        )
        quotation["lines"] = lines
        quotation["total"] = sum(Decimal(str(line["total"])) for line in lines)

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="QUOTATION_GET_SUCCESS",
            user=user,
            message=f"Quotation {quotation_id} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"quotation_id": quotation_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Quotation retrieved successfully",
            data=quotation,
            code=200
        ).success()

    except Exception as e:
        # Log error
        TransactionLogBase.log(
            transaction_type="QUOTATION_GET_FAILED",
            user=user if 'user' in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving quotation", code=500).exception()

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def update_quotation(request):
    """
    Update an existing quotation for the user's corporate, including its lines, and set status to DRAFT or POSTED.
    Does not send an email notification.

    Expected data:
    - id: UUID of the quotation
    - customer: UUID of the customer
    - date: Date of the quotation (YYYY-MM-DD)
    - number: Quotation number (unique)
    - valid_until: Validity date of the quotation (YYYY-MM-DD)
    - salesperson: UUID of the salesperson
    - ship_date: Shipping date (YYYY-MM-DD)
    - ship_via: Shipping method
    - terms: Payment terms
    - fob: FOB terms
    - comments: Comments (optional)
    - T_and_C: Terms and Conditions (optional)
    - status: DRAFT or POSTED
    - lines: List of dictionaries, each containing fields for QuotationLine
        - id: UUID of the line (optional, for updates)
        - description: Line item description
        - quantity: Quantity of the item
        - unit_price: Price per unit
        - discount: Discount amount
        - taxable: Tax rate ID or exempt status
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
        required_fields = ["id", "customer", "date", "number", "valid_until", "ship_date", "ship_via", "terms", "fob", "salesperson"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate quotation
        quotations = registry.database(
            model_name="Quotation",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id}
        )
        if not quotations:
            return ResponseProvider(message="Quotation not found", code=404).bad_request()
        quotation_id = quotations[0]["id"]

        # Validate customer
        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": data["customer"], "corporate_id": corporate_id, "is_active": True}
        )
        if not customers:
            return ResponseProvider(message="Customer not found or inactive for this corporate", code=404).bad_request()

        # Validate salesperson
        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["salesperson"], "corporate_id": corporate_id, "is_active": True}
        )
        if not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate", code=404).bad_request()

        # Normalize status
        normalized_status = str(data.get("status", "DRAFT")).upper()
        if normalized_status not in {"DRAFT", "POSTED"}:
            normalized_status = "DRAFT"

        # Process lines and calculate totals
        submitted_lines = data.get("lines", [])
        if not submitted_lines:
            return ResponseProvider(message="At least one quotation line is required", code=400).bad_request()

        sub_total = Decimal('0.00')
        tax_total = Decimal('0.00')
        total_discount = Decimal('0.00')
        total = Decimal('0.00')

        for line_data in submitted_lines:
            required_line_fields = ["description", "quantity", "unit_price", "discount", "taxable"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Quotation line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable_id = normalize_taxable_id(line_data.get("taxable"))
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

        # Update quotation and lines within a transaction
        with transaction.atomic():
            quotation_data = {
                "id": data["id"],
                "customer_id": data["customer"],
                "corporate_id": corporate_id,
                "date": data["date"],
                "number": data["number"],
                "valid_until": data["valid_until"],
                "comments": data.get("comments", ""),
                "T_and_C": data.get("T_and_C", ""),
                "ship_date": data["ship_date"],
                "ship_via": data["ship_via"],
                "terms": data["terms"],
                "fob": data["fob"],
                "salesperson_id": data["salesperson"],
                "status": normalized_status,
                "sub_total": float(sub_total),
                "tax_total": float(tax_total),
                "total": float(total),
                "total_discount": float(total_discount),
            }
            quotation = registry.database(
                model_name="Quotation",
                operation="update",
                instance_id=quotation_id,
                data=quotation_data
            )

            # Delete omitted lines
            existing_lines = registry.database(
                model_name="QuotationLine",
                operation="filter",
                data={"quotation_id": quotation["id"]}
            )
            existing_line_ids = {line["id"] for line in existing_lines if line.get("id")}
            submitted_line_ids = {line.get("id") for line in submitted_lines if line.get("id")}

            for line in existing_lines:
                if line["id"] not in submitted_line_ids:
                    registry.database(
                        model_name="QuotationLine",
                        operation="delete",
                        instance_id=line["id"]
                    )

            # Create or update lines
            for line_data in submitted_lines:
                taxable_id = normalize_taxable_id(line_data.get("taxable"))
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
                    "quotation_id": quotation["id"],
                    "description": line_data["description"],
                    "quantity": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(line_subtotal),
                    "discount": float(discount),
                    "taxable_id": taxable_id,
                    "grand_total": float(line_total),
                    "tax_amount": float(line_tax_amount),
                    "tax_total": float(line_tax_amount),
                    "sub_total": float(line_subtotal),
                    "total": float(line_total),
                    "total_discount": float(discount),
                }

                if line_data.get("id") in existing_line_ids:
                    line_payload["id"] = line_data["id"]
                    registry.database(
                        model_name="QuotationLine",
                        operation="update",
                        instance_id=line_data["id"],
                        data=line_payload
                    )
                else:
                    registry.database(
                        model_name="QuotationLine",
                        operation="create",
                        data=line_payload
                    )

        # Log update
        TransactionLogBase.log(
            transaction_type="QUOTATION_UPDATED_AND_POSTED",
            user=user,
            message=f"Quotation {quotation['number']} updated and posted for corporate {corporate_id} with status {quotation['status']}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "line_count": len(submitted_lines)},
            request=request
        )

        # Fetch fresh lines for response
        db_lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        quotation["lines"] = [
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
        quotation["sub_total"] = float(sub_total)
        quotation["tax_total"] = float(tax_total)
        quotation["total_discount"] = float(total_discount)
        quotation["total"] = float(total)

        return ResponseProvider(message="Quotation updated and posted successfully", data=quotation, code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_UPDATE_AND_POST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating quotation", code=500).exception()

from django.db import transaction

@csrf_exempt
def delete_quotation(request):
    """
    Soft delete a quotation by setting is_active to False for both the quotation and its lines.

    Expected data:
    - id: UUID of the quotation (in POST body)

    Returns:
    - 200: Quotation deleted successfully
    - 400: Bad request (missing ID or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Quotation not found for this corporate
    - 500: Internal server error
    """
    try:
        # Assuming get_clean_data extracts JSON body and metadata
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        # Get user ID
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        # Get quotation ID from request data
        quotation_id = data.get("id")
        if not quotation_id:
            return ResponseProvider(message="Quotation ID is required", code=400).bad_request()

        # Initialize ServiceRegistry
        registry = ServiceRegistry()

        # Get corporate_id from CorporateUser
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        # Check if quotation exists for this corporate
        quotations = registry.database(
            model_name="Quotation",
            operation="filter",
            data={"id": quotation_id, "corporate_id": corporate_id}
        )
        if not quotations:
            return ResponseProvider(message="Quotation not found for this corporate", code=404).bad_request()

        # Soft delete quotation and its lines within a transaction
        with transaction.atomic():
            # Soft delete quotation
            registry.database(
                model_name="Quotation",
                operation="delete",
                instance_id=quotation_id,
                data={"id": quotation_id}
            )

            # Soft delete all quotation lines
            lines = registry.database(
                model_name="QuotationLine",
                operation="filter",
                data={"quotation_id": quotation_id}
            )
            for line in lines:
                registry.database(
                    model_name="QuotationLine",
                    operation="delete",
                    instance_id=line["id"],
                    data={"id": line["id"]}
                )

            # Log successful deletion
            TransactionLogBase.log(
                transaction_type="QUOTATION_DELETED",
                user=user,
                message=f"Quotation {quotation_id} soft-deleted",
                state_name="Completed",
                extra={"quotation_id": quotation_id, "line_count": len(lines)},
                request=request
            )

        return ResponseProvider(
            message="Quotation deleted successfully",
            data={"quotation_id": quotation_id},
            code=200
        ).success()

    except Exception as e:
        # Log failure
        TransactionLogBase.log(
            transaction_type="QUOTATION_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting quotation", code=500).exception()