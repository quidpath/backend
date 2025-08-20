from decimal import Decimal, InvalidOperation
from django.views.decorators.csrf import csrf_exempt
from collections import Counter
import json, ast, re
from django.db import transaction

from quidpath_backend import settings
from quidpath_backend.core.utils.DocsEmail import DocumentNotificationHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

from decimal import Decimal, InvalidOperation
import json, ast


def normalize_taxable_id(raw, registry):
    """Normalize taxable_id and ensure it's a valid TaxRate ID."""
    if not raw:
        default_rate = registry.database(
            model_name="TaxRate",
            operation="filter",
            data={"code": "exempt"}
        )
        if default_rate:
            return default_rate[0]["id"]
        raise ValueError("No default exempt tax rate found")
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
        return s
    return str(raw)


@csrf_exempt
def save_invoice_draft(request):
    """
    Save a new invoice as draft for the user's corporate, including its lines. Optionally from a quotation.
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

        required_fields = ["customer", "date", "number", "due_date"]
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
            data={"id": data.get("salesperson"), "corporate_id": corporate_id, "is_active": True} if data.get(
                "salesperson") else {}
        )
        if data.get("salesperson") and not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate",
                                    code=404).bad_request()

        quotation = None
        quotation_lines = []
        if "quotation" in data:
            quotations = registry.database(
                model_name="Quotation",
                operation="filter",
                data={"id": data["quotation"], "corporate_id": corporate_id}
            )
            if not quotations:
                return ResponseProvider(message="Quotation not found for this corporate", code=404).bad_request()
            quotation = quotations[0]
            quotation_lines = registry.database(
                model_name="QuotationLine",
                operation="filter",
                data={"quotation_id": quotation["id"]}
            )

        if quotation:
            data["customer"] = quotation["customer_id"]
            data["date"] = data.get("date", quotation["date"])
            data["due_date"] = data.get("due_date", quotation["valid_until"])
            data["salesperson"] = quotation["salesperson_id"]
            data["ship_date"] = quotation["ship_date"]
            data["ship_via"] = quotation["ship_via"]
            data["terms"] = quotation["terms"]
            data["fob"] = quotation["fob"]
            data["comments"] = quotation["comments"]
            data["purchase_order"] = data.get("purchase_order", quotation.get("purchase_order", ""))

        invoice_data = {
            "customer_id": data["customer"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "due_date": data["due_date"],
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "ship_date": data.get("ship_date"),
            "ship_via": data.get("ship_via"),
            "fob": data.get("fob"),
            "salesperson_id": data.get("salesperson"),
            "quotation_id": data.get("quotation") if "quotation" in data else None,
            "purchase_order": data.get("purchase_order", ""),
            "status": "DRAFT",
        }
        invoice = registry.database(
            model_name="Invoices",
            operation="create",
            data=invoice_data
        )

        lines = data.get("lines", [])
        if quotation and not lines:
            lines = [
                {
                    "description": ql["description"],
                    "quantity": ql["quantity"],
                    "unit_price": ql["unit_price"],
                    "amount": ql["amount"],
                    "discount": ql["discount"],
                    "taxable": ql["taxable_id"],
                    "tax_amount": ql["tax_amount"],
                    "sub_total": ql["sub_total"],
                    "total": ql["total"],
                    "quotation_line": ql["id"]
                } for ql in quotation_lines
            ]

        sub_total = Decimal('0')
        tax_total = Decimal('0')
        total = Decimal('0')
        total_discount = Decimal('0')

        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "tax_amount",
                                    "sub_total", "total"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Invoice line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable = line_data.get("taxable_id") or line_data.get("taxable")
            taxable_id = normalize_taxable_id(taxable, registry)

            # Validate taxable_id
            tax_rates = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": taxable_id}
            )
            if not tax_rates:
                return ResponseProvider(
                    message=f"Tax rate {taxable_id} not found",
                    code=404
                ).bad_request()

            line_data_for_creation = {
                "invoice_id": invoice["id"],
                "description": line_data["description"],
                "quantity": float(Decimal(str(line_data["quantity"]))),
                "unit_price": float(Decimal(str(line_data["unit_price"]))),
                "amount": float(Decimal(str(line_data["amount"]))),
                "discount": float(Decimal(str(line_data["discount"]))),
                "taxable_id": taxable_id,
                "tax_amount": float(Decimal(str(line_data["tax_amount"]))),
                "sub_total": float(Decimal(str(line_data["sub_total"]))),
                "total": float(Decimal(str(line_data["total"]))),
                "quotation_line_id": line_data.get("quotation_line")
            }
            created_line = registry.database(
                model_name="InvoiceLine",
                operation="create",
                data=line_data_for_creation
            )

            sub_total += Decimal(str(created_line["sub_total"]))
            tax_total += Decimal(str(created_line["tax_amount"]))
            total += Decimal(str(created_line["total"]))
            total_discount += Decimal(str(created_line["discount"]))

        invoice_update_data = {
            "sub_total": str(sub_total),
            "tax_total": str(tax_total),
            "total": str(total),
            "total_discount": str(total_discount)
        }
        registry.database(
            model_name="Invoices",
            operation="update",
            instance_id=invoice["id"],
            data=invoice_update_data
        )
        invoice.update(invoice_update_data)

        if quotation:
            registry.database(
                model_name="Quotation",
                operation="update",
                instance_id=quotation["id"],
                data={"status": "INVOICED"}
            )

        TransactionLogBase.log(
            transaction_type="INVOICE_DRAFT_SAVED",
            user=user,
            message=f"Invoice draft {invoice['number']} saved for corporate {corporate_id}",
            state_name="Completed",
            extra={"invoice_id": invoice["id"], "line_count": len(lines)},
            request=request
        )

        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice["id"]}
        )
        invoice["lines"] = lines

        return ResponseProvider(
            message="Invoice draft saved successfully",
            data=invoice,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_DRAFT_SAVE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while saving invoice draft", code=500).exception()


@csrf_exempt
def create_and_send_invoice(request):
    """
    Create a new invoice for the user's corporate, including its lines, set status to ISSUED, and send email to customer.
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

        required_fields = ["customer", "date", "number", "due_date"]
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
        customer = customers[0]

        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data.get("salesperson"), "corporate_id": corporate_id, "is_active": True} if data.get(
                "salesperson") else {}
        )
        if data.get("salesperson") and not salespersons:
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

        quotation = None
        quotation_lines = []
        if "quotation" in data:
            quotations = registry.database(
                model_name="Quotation",
                operation="filter",
                data={"id": data["quotation"], "corporate_id": corporate_id}
            )
            if not quotations:
                return ResponseProvider(message="Quotation not found for this corporate", code=404).bad_request()
            quotation = quotations[0]
            quotation_lines = registry.database(
                model_name="QuotationLine",
                operation="filter",
                data={"quotation_id": quotation["id"]}
            )

        if quotation:
            data["customer"] = quotation["customer_id"]
            data["date"] = data.get("date", quotation["date"])
            data["due_date"] = data.get("due_date", quotation["valid_until"])
            data["salesperson"] = quotation["salesperson_id"]
            data["ship_date"] = quotation["ship_date"]
            data["ship_via"] = quotation["ship_via"]
            data["terms"] = quotation["terms"]
            data["fob"] = quotation["fob"]
            data["comments"] = quotation["comments"]
            data["purchase_order"] = data.get("purchase_order", quotation.get("purchase_order", ""))

        invoice_data = {
            "customer_id": data["customer"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "due_date": data["due_date"],
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "ship_date": data.get("ship_date"),
            "ship_via": data.get("ship_via"),
            "fob": data.get("fob"),
            "salesperson_id": data.get("salesperson"),
            "status": "ISSUED",
            "quotation_id": data.get("quotation") if "quotation" in data else None,
            "purchase_order": data.get("purchase_order", ""),
        }
        invoice = registry.database(
            model_name="Invoices",
            operation="create",
            data=invoice_data
        )

        lines = data.get("lines", [])
        if quotation and not lines:
            lines = [
                {
                    "description": ql["description"],
                    "quantity": ql["quantity"],
                    "unit_price": ql["unit_price"],
                    "amount": ql["amount"],
                    "discount": ql["discount"],
                    "taxable": ql["taxable_id"],
                    "tax_amount": ql["tax_amount"],
                    "sub_total": ql["sub_total"],
                    "total": ql["total"],
                    "quotation_line": ql["id"]
                } for ql in quotation_lines
            ]

        sub_total = Decimal('0')
        tax_total = Decimal('0')
        total = Decimal('0')
        total_discount = Decimal('0')

        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "tax_amount",
                                    "sub_total", "total"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Invoice line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            taxable = line_data.get("taxable_id") or line_data.get("taxable")
            taxable_id = normalize_taxable_id(taxable, registry)

            # Validate taxable_id
            tax_rates = registry.database(
                model_name="TaxRate",
                operation="filter",
                data={"id": taxable_id}
            )
            if not tax_rates:
                return ResponseProvider(
                    message=f"Tax rate {taxable_id} not found",
                    code=404
                ).bad_request()

            line_data_for_creation = {
                "invoice_id": invoice["id"],
                "description": line_data["description"],
                "quantity": float(Decimal(str(line_data["quantity"]))),
                "unit_price": float(Decimal(str(line_data["unit_price"]))),
                "amount": float(Decimal(str(line_data["amount"]))),
                "discount": float(Decimal(str(line_data["discount"]))),
                "taxable_id": taxable_id,
                "tax_amount": float(Decimal(str(line_data["tax_amount"]))),
                "sub_total": float(Decimal(str(line_data["sub_total"]))),
                "total": float(Decimal(str(line_data["total"]))),
                "quotation_line_id": line_data.get("quotation_line")
            }
            created_line = registry.database(
                model_name="InvoiceLine",
                operation="create",
                data=line_data_for_creation
            )

            sub_total += Decimal(str(created_line["sub_total"]))
            tax_total += Decimal(str(created_line["tax_amount"]))
            total += Decimal(str(created_line["total"]))
            total_discount += Decimal(str(created_line["discount"]))

        invoice_update_data = {
            "sub_total": str(sub_total),
            "tax_total": str(tax_total),
            "total": str(total),
            "total_discount": str(total_discount)
        }
        registry.database(
            model_name="Invoices",
            operation="update",
            instance_id=invoice["id"],
            data=invoice_update_data
        )
        invoice.update(invoice_update_data)

        if quotation:
            registry.database(
                model_name="Quotation",
                operation="update",
                instance_id=quotation["id"],
                data={"status": "INVOICED"}
            )

        TransactionLogBase.log(
            transaction_type="INVOICE_CREATED_AND_SENT",
            user=user,
            message=f"Invoice {invoice['number']} created and sent for corporate {corporate_id}",
            state_name="Completed",
            extra={"invoice_id": invoice["id"], "line_count": len(lines)},
            request=request
        )

        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice["id"]}
        )
        invoice["lines"] = lines

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
            def tax_display(taxable_id_value):
                if not taxable_id_value:
                    return ""
                tr = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id_value}
                )
                return tr[0].get("label", "") if tr else ""

            subject = f"Invoice {invoice['number']} from {corporate['name']}"
            message = f"""
            <html>
            <body>
            <p>Dear {customer.get('name', 'Customer')},</p>
            <p>We are pleased to send you the following invoice:</p>
            <p><strong>Invoice Number:</strong> {invoice['number']}</p>
            <p><strong>Purchase Order:</strong> {invoice.get('purchase_order', '')}</p>
            <p><strong>Date:</strong> {invoice['date']}</p>
            <p><strong>Due Date:</strong> {invoice['due_date']}</p>
            <p><strong>Ship Date:</strong> {invoice.get('ship_date', '')}</p>
            <p><strong>Ship Via:</strong> {invoice.get('ship_via', '')}</p>
            <p><strong>Terms:</strong> {invoice.get('terms', '')}</p>
            <p><strong>FOB:</strong> {invoice.get('fob', '')}</p>
            <p><strong>Comments:</strong> {invoice.get('comments', '')}</p>
            <h3>Lines:</h3>
            <table border="1">
            <tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th><th>Discount</th><th>Taxable</th><th>Total</th></tr>
            """
            for line in lines:
                message += f"""
                <tr>
                <td>{line['description']}</td>
                <td>{line['quantity']}</td>
                <td>{line['unit_price']}</td>
                <td>{line['amount']}</td>
                <td>{line['discount']}</td>
                <td>{tax_display(line.get('taxable_id'))}</td>
                <td>{line['total']}</td>
                </tr>
                """
            message += f"""
            </table>
            <p><strong>Sub Total:</strong> {invoice['sub_total']}</p>
            <p><strong>Tax Total:</strong> {invoice['tax_total']}</p>
            <p><strong>Total:</strong> {invoice['total']}</p>
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
            send_result = notification_handler.send_document_notification(notifications, trans=None, attachment=None,
                                                                          cc=None)
            if send_result != "success":
                TransactionLogBase.log(
                    transaction_type="INVOICE_SEND_FAILED",
                    user=user,
                    message="Failed to send email",
                    state_name="Failed",
                    request=request
                )

        return ResponseProvider(
            message="Invoice created and sent successfully",
            data=invoice,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_CREATION_AND_SEND_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating and sending invoice", code=500).exception()

@csrf_exempt
def list_invoices(request):
    """
    List all invoices for the user's corporate, categorized by status.

    Returns:
    - 200: List of invoices with total count and status counts
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
            data={"customuser_ptr_id": user_id}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        invoices = registry.database(
            model_name="Invoices",
            operation="filter",
            data={"corporate_id": corporate_id}
        )


        for inv in invoices:
            lines = registry.database(
                model_name="invoiceline",
                operation="filter",
                data={"invoice_id": inv["id"]}
            )
            inv["lines"] = lines

        serialized_invoices = [
            {
                "id": str(inv["id"]),
                "number": inv["number"],
                "customer": str(inv["customer_id"]),
                "date": inv["date"],
                "due_date": inv["due_date"],
                "status": inv["status"],
                "salesperson": str(inv.get("salesperson_id", "")),
                "ship_date": inv.get("ship_date", ""),
                "ship_via": inv.get("ship_via", ""),
                "terms": inv.get("terms", ""),
                "fob": inv.get("fob", ""),
                "comments": inv.get("comments", ""),
                "purchase_order": inv.get("purchase_order", ""),
                "sub_total": float(inv.get("sub_total", 0)),
                "tax_total": float(inv.get("tax_total", 0)),
                "total": float(inv.get("total", 0)),
                "total_discount": float(inv.get("total_discount", 0)),
                "lines": [
                    {
                        "id": str(line.get("id", "")),
                        "description": line.get("description", ""),
                        "quantity": line.get("quantity", 0),
                        "unit_price": float(line.get("unit_price", 0)),
                        "amount": float(line.get("amount", 0)),
                        "discount": float(line.get("discount", 0)),
                        "taxable": str(line.get("taxable_id", "")),
                        "tax_amount": float(line.get("tax_amount", 0)),
                        "sub_total": float(line.get("sub_total", 0)),
                        "total": float(line.get("total", 0))
                    }
                    for line in inv.get("lines", [])
                ]
            }
            for inv in invoices
        ]

        statuses = [inv["status"] for inv in invoices]
        status_counts = dict(Counter(statuses))
        total = len(invoices)

        all_statuses = {"DRAFT": 0, "ISSUED": 0, "PAID": 0, "PARTIALLY_PAID": 0, "OVERDUE": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        TransactionLogBase.log(
            transaction_type="INVOICE_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} invoices for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            data={
                "invoices": serialized_invoices,
                "total": total,
                "status_counts": all_statuses
            },
            message="Invoices retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving invoices", code=500).exception()

@csrf_exempt
def get_invoice(request):
    """
    Get a single invoice by ID for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the invoice

    Returns:
    - 200: Invoice retrieved successfully with lines
    - 400: Bad request (missing ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Invoice not found for this corporate
    - 500: Internal server error
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

        invoice_id = data.get("id")
        if not invoice_id:
            return ResponseProvider(message="Invoice ID is required", code=400).bad_request()

        invoices = registry.database(
            model_name="Invoices",
            operation="filter",
            data={"id": invoice_id, "corporate_id": corporate_id}
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found for this corporate", code=404).bad_request()

        invoice = invoices[0]

        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice_id}
        )
        invoice["lines"] = lines

        serialized_invoice = {
            "id": str(invoice["id"]),
            "number": invoice["number"],
            "customer": str(invoice["customer_id"]),
            "date": invoice["date"],
            "due_date": invoice["due_date"],
            "status": invoice["status"],
            "salesperson": str(invoice.get("salesperson_id", "")),
            "ship_date": invoice.get("ship_date", ""),
            "ship_via": invoice.get("ship_via", ""),
            "terms": invoice.get("terms", ""),
            "fob": invoice.get("fob", ""),
            "comments": invoice.get("comments", ""),
            "purchase_order": invoice.get("purchase_order", ""),
            "sub_total": float(invoice.get("sub_total", 0)),
            "tax_total": float(invoice.get("tax_total", 0)),
            "total": float(invoice.get("total", 0)),
            "total_discount": float(invoice.get("total_discount", 0)),
            "lines": [
                {
                    "id": str(line.get("id", "")),
                    "description": line.get("description", ""),
                    "quantity": line.get("quantity", 0),
                    "unit_price": float(line.get("unit_price", 0)),
                    "amount": float(line.get("amount", 0)),
                    "discount": float(line.get("discount", 0)),
                    "taxable": str(line.get("taxable_id", "")),
                    "tax_amount": float(line.get("tax_amount", 0)),
                    "sub_total": float(line.get("sub_total", 0)),
                    "total": float(line.get("total", 0))
                }
                for line in invoice.get("lines", [])
            ]
        }

        TransactionLogBase.log(
            transaction_type="INVOICE_GET_SUCCESS",
            user=user,
            message=f"Invoice {invoice_id} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"invoice_id": invoice_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Invoice retrieved successfully",
            data=serialized_invoice,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_GET_FAILED",
            user=user if 'user' in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving invoice", code=500).exception()

@csrf_exempt
def update_invoice(request):
    """
    Update an existing invoice for the user's corporate, including its lines, and set status to DRAFT or ISSUED.
    """
    def to_decimal(val, default="0"):
        if val is None:
            return Decimal(default)
        try:
            return Decimal(str(val))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    def normalize_taxable_id(raw):
        if not raw:
            return None

        if isinstance(raw, dict) and raw.get("id"):
            return raw.get("id")

        if isinstance(raw, str):
            s = raw.strip()
            s = s.strip('\'"“”‘’')
            if (s.startswith("{") and s.endswith("}")):
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

        required_fields = ["id", "customer", "date", "number", "due_date"]
        invoice_number = data["number"]
        pattern = r"^INV-\d{6}$"
        if not re.match(pattern, invoice_number):
            return ResponseProvider(
                message="Invoice number must be in format INV-<6 digits> (e.g., INV-123456)",
                code=400
            ).bad_request()
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        invoices = registry.database(
            model_name="Invoices",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id}
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found", code=404).bad_request()
        invoice_id = invoices[0]["id"]

        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": data["customer"], "corporate_id": corporate_id, "is_active": True}
        )
        if not customers:
            return ResponseProvider(message="Customer not found or inactive for this corporate", code=404).bad_request()
        customer = customers[0]

        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data.get("salesperson"), "corporate_id": corporate_id, "is_active": True} if data.get("salesperson") else {}
        )
        if data.get("salesperson") and not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate", code=404).bad_request()

        normalized_status = str(data.get("status", "DRAFT")).upper()
        if normalized_status not in {"DRAFT", "ISSUED"}:
            normalized_status = "DRAFT"

        corporate = None
        if normalized_status == "ISSUED":
            corporates = registry.database(
                model_name="Corporate",
                operation="filter",
                data={"id": corporate_id}
            )
            if not corporates:
                return ResponseProvider(message="Corporate not found", code=404).bad_request()
            corporate = corporates[0]

        invoice_data = {
            "id": data["id"],
            "customer_id": data["customer"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "due_date": data["due_date"],
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "ship_date": data.get("ship_date"),
            "ship_via": data.get("ship_via"),
            "fob": data.get("fob"),
            "salesperson_id": data.get("salesperson"),
            "status": normalized_status,
            "purchase_order": data.get("purchase_order", ""),
        }
        invoice = registry.database(
            model_name="Invoices",
            operation="update",
            instance_id=invoice_id,
            data=invoice_data
        )

        submitted_lines = data.get("lines", []) or []

        existing_lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice["id"]}
        )
        existing_line_ids = {line["id"] for line in existing_lines if line.get("id")}
        submitted_line_ids = {line.get("id") for line in submitted_lines if line.get("id")}

        for line in existing_lines:
            if line["id"] not in submitted_line_ids:
                registry.database(
                    model_name="InvoiceLine",
                    operation="delete",
                    instance_id=line["id"]
                )

        sub_total = Decimal('0')
        tax_total = Decimal('0')
        total = Decimal('0')
        total_discount = Decimal('0')

        for line_data in submitted_lines:
            raw_taxable = line_data.get("taxable_id") or line_data.get("taxable")
            taxable_id = normalize_taxable_id(raw_taxable)

            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount",
                                    "tax_amount", "sub_total", "total"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Invoice line field {field.replace('_', ' ').title()} is required",
                        code=400
                    ).bad_request()

            tax_rate_value = Decimal("0")  # default

            if taxable_id:
                tax_rates = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id}
                )
                if not tax_rates:
                    return ResponseProvider(
                        message=f"Tax rate {taxable_id} not found",
                        code=404
                    ).bad_request()

                tax_rate_code = tax_rates[0][
                    "name"]  # stored field in your model: "general_rated", "zero_rated", "exempt"

                if tax_rate_code == "general_rated":
                    tax_rate_value = Decimal("0.16")
                else:
                    tax_rate_value = Decimal("0")

            qty = to_decimal(line_data["quantity"])
            unit_price = to_decimal(line_data["unit_price"])
            discount = to_decimal(line_data["discount"])
            client_tax_amount = to_decimal(line_data["tax_amount"])

            line_subtotal = qty * unit_price
            line_taxable_amount = line_subtotal - discount
            expected_tax_amount = (line_taxable_amount * tax_rate_value)

            if (client_tax_amount - expected_tax_amount).copy_abs() > Decimal("0.01"):
                return ResponseProvider(
                    message=f"Invalid tax_amount for line {line_data.get('description', '')}",
                    code=400
                ).bad_request()

            line_payload = {
                "invoice_id": invoice["id"],
                "description": line_data["description"],
                "quantity": float(qty),
                "unit_price": float(unit_price),
                "amount": float(to_decimal(line_data["amount"])),
                "discount": float(discount),
                "taxable_id": taxable_id,
                "tax_amount": float(client_tax_amount),
                "sub_total": float(to_decimal(line_data["sub_total"])),
                "total": float(to_decimal(line_data["total"])),
            }

            if line_data.get("id") in existing_line_ids:
                line_payload["id"] = line_data["id"]
                updated_line = registry.database(
                    model_name="InvoiceLine",
                    operation="update",
                    instance_id=line_data["id"],
                    data=line_payload
                )
            else:
                updated_line = registry.database(
                    model_name="InvoiceLine",
                    operation="create",
                    data=line_payload
                )

            sub_total += to_decimal(updated_line["sub_total"])
            tax_total += to_decimal(updated_line["tax_amount"])
            total += to_decimal(updated_line["total"])  # Fixed: Accumulate total correctly
            total_discount += to_decimal(updated_line["discount"])

        invoice_update_data = {
            "sub_total": str(sub_total),
            "tax_total": str(tax_total),
            "total": str(total),
            "total_discount": str(total_discount)
        }
        registry.database(
            model_name="Invoices",  # Fixed: Correct model name
            operation="update",
            instance_id=invoice["id"],
            data=invoice_update_data
        )
        invoice.update(invoice_update_data)

        TransactionLogBase.log(
            transaction_type="INVOICE_UPDATED",
            user=user,
            message=f"Invoice {invoice['number']} updated for corporate {corporate_id} with status {invoice['status']}",
            state_name="Completed",
            extra={"invoice_id": invoice["id"], "line_count": len(submitted_lines)},
            request=request
        )

        if invoice["status"] == "ISSUED":
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
                email_lines = registry.database(
                    model_name="InvoiceLine",
                    operation="filter",
                    data={"invoice_id": invoice["id"]}
                )

                def tax_display(taxable_id_value):
                    if not taxable_id_value:
                        return ""
                    tr = registry.database(
                        model_name="TaxRate",
                        operation="filter",
                        data={"id": taxable_id_value}
                    )
                    return tr[0].get("name", "") if tr else ""

                subject = f"Updated Invoice {invoice['number']} from {corporate['name']}"
                message = f"""
                <html><body>
                <p>Dear {customer.get('name') or customer.get('first_name') or 'Customer'},</p>
                <p>We have updated the following invoice:</p>
                <p><strong>Invoice Number:</strong> {invoice['number']}</p>
                <p><strong>Purchase Order:</strong> {invoice.get('purchase_order', '')}</p>
                <p><strong>Date:</strong> {invoice['date']}</p>
                <p><strong>Due Date:</strong> {invoice['due_date']}</p>
                <p><strong>Ship Date:</strong> {invoice.get('ship_date','')}</p>
                <p><strong>Ship Via:</strong> {invoice.get('ship_via','')}</p>
                <p><strong>Terms:</strong> {invoice.get('terms','')}</p>
                <p><strong>FOB:</strong> {invoice.get('fob','')}</p>
                <p><strong>Comments:</strong> {invoice.get('comments','')}</p>
                <h3>Lines:</h3>
                <table border="1" cellpadding="6" cellspacing="0">
                <tr>
                    <th>Description</th><th>Quantity</th><th>Unit Price</th>
                    <th>Amount</th><th>Discount</th><th>Taxable</th><th>Total</th>
                </tr>
                """
                for l in email_lines:
                    message += f"""
                    <tr>
                      <td>{l.get('description','')}</td>
                      <td>{l.get('quantity','')}</td>
                      <td>{l.get('unit_price','')}</td>
                      <td>{l.get('amount','')}</td>
                      <td>{l.get('discount','')}</td>
                      <td>{tax_display(l.get('taxable_id'))}</td>
                      <td>{l.get('total','')}</td>
                    </tr>
                    """
                message += f"""
                </table>
                <p><strong>Sub Total:</strong> {invoice['sub_total']}</p>
                <p><strong>Tax Total:</strong> {invoice['tax_total']}</p>
                <p><strong>Total:</strong> {invoice['total']}</p>
                <p>Thank you for your business!</p>
                <p>Best regards,<br>{corporate['name']}</p>
                </body></html>
                """

                notification_handler = DocumentNotificationHandler()
                send_result = notification_handler.send_document_notification(
                    [{
                        "message_type": "EMAIL",
                        "organisation_id": corporate_id,
                        "destination": to_email,
                        "message": message,
                        "subject": subject,
                    }],
                    trans=None
                )
                if send_result != "success":
                    TransactionLogBase.log(
                        transaction_type="INVOICE_SEND_FAILED",
                        user=user,
                        message="Failed to send email",
                        state_name="Failed",
                        request=request
                    )

        db_lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice["id"]}
        )
        invoice["lines"] = db_lines

        return ResponseProvider(message="Invoice updated successfully", data=invoice, code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating invoice", code=500).exception()

@csrf_exempt
def delete_invoice(request):
    """
    Soft delete an invoice by setting is_active to False for both the invoice and its lines.

    Expected data:
    - id: UUID of the invoice (in POST body)

    Returns:
    - 200: Invoice deleted successfully
    - 400: Bad request (missing ID or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Invoice not found for this corporate
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        invoice_id = data.get("id")
        if not invoice_id:
            return ResponseProvider(message="Invoice ID is required", code=400).bad_request()

        registry = ServiceRegistry()

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

        invoices = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"id": invoice_id, "corporate_id": corporate_id}
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found for this corporate", code=404).bad_request()

        with transaction.atomic():
            registry.database(
                model_name="Invoice",
                operation="delete",
                instance_id=invoice_id,
                data={"id": invoice_id}
            )

            lines = registry.database(
                model_name="InvoiceLine",
                operation="filter",
                data={"invoice_id": invoice_id}
            )
            for line in lines:
                registry.database(
                    model_name="InvoiceLine",
                    operation="delete",
                    instance_id=line["id"],
                    data={"id": line["id"]}
                )

            TransactionLogBase.log(
                transaction_type="INVOICE_DELETED",
                user=user,
                message=f"Invoice {invoice_id} soft-deleted",
                state_name="Completed",
                extra={"invoice_id": invoice_id, "line_count": len(lines)},
                request=request
            )

        return ResponseProvider(
            message="Invoice deleted successfully",
            data={"invoice_id": invoice_id},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting invoice", code=500).exception()