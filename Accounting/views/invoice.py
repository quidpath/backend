from django.views.decorators.csrf import csrf_exempt
from collections import Counter
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_invoice(request):
    """
    Create a new invoice for the user's corporate, including its lines.

    Expected data:
    - customer: UUID of the customer
    - date: Date of the invoice
    - number: Invoice number (must be unique)
    - due_date: Due date of the invoice
    - salesperson: UUID of the salesperson
    - profoma_invoice: UUID of the proforma invoice (optional)
    - quotation: UUID of the quotation (optional)
    - purchase_order: UUID of the purchase order (optional)
    - status: Invoice status (optional, defaults to "DRAFT")
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - sub_total: Subtotal (optional, defaults to 0.00)
    - tax_total: Tax total (optional, defaults to 0.00)
    - total: Total (optional, defaults to 0.00)
    - total_discount: Total discount (optional, defaults to 0.00)
    - lines: List of dictionaries, each containing fields for InvoiceLine (e.g., description, quantity, etc.)

    Returns:
    - 201: Invoice created successfully with lines
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Customer, salesperson, profoma_invoice, quotation, purchase_order, or taxable not found
    - 409: Invoice number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    required_fields = ["customer", "date", "number", "due_date", "salesperson"]
    for field in required_fields:
        if field not in data:
            return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

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

        # Validate profoma_invoice if provided
        if "profoma_invoice" in data and data["profoma_invoice"]:
            profoma_invoices = registry.database(
                model_name="ProformaInvoice",
                operation="filter",
                data={"id": data["profoma_invoice"], "corporate_id": corporate_id, "is_active": True}
            )
            if not profoma_invoices:
                return ResponseProvider(message="Proforma invoice not found or inactive for this corporate", code=404).bad_request()

        # Validate quotation if provided
        if "quotation" in data and data["quotation"]:
            quotations = registry.database(
                model_name="Quotation",
                operation="filter",
                data={"id": data["quotation"], "corporate_id": corporate_id, "is_active": True}
            )
            if not quotations:
                return ResponseProvider(message="Quotation not found or inactive for this corporate", code=404).bad_request()

        # Validate purchase_order if provided
        if "purchase_order" in data and data["purchase_order"]:
            purchase_orders = registry.database(
                model_name="PurchaseOrder",
                operation="filter",
                data={"id": data["purchase_order"], "corporate_id": corporate_id, "is_active": True}
            )
            if not purchase_orders:
                return ResponseProvider(message="Purchase order not found or inactive for this corporate", code=404).bad_request()

        # Check if invoice number is unique
        existing_invoices = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"number": data["number"]}
        )
        if existing_invoices:
            return ResponseProvider(message="Invoice number already exists", code=409).bad_request()

        # Create invoice
        invoice_data = {
            "customer_id": data["customer"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "due_date": data["due_date"],
            "status": data.get("status", "DRAFT"),
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "salesperson_id": data["salesperson"],
            "ship_date": data.get("ship_date"),
            "ship_via": data.get("ship_via", ""),
            "fob": data.get("fob", ""),
            "sub_total": data.get("sub_total", 0.00),
            "tax_total": data.get("tax_total", 0.00),
            "total": data.get("total", 0.00),
            "total_discount": data.get("total_discount", 0.00),
        }
        if "profoma_invoice" in data and data["profoma_invoice"]:
            invoice_data["profoma_invoice_id"] = data["profoma_invoice"]
        if "quotation" in data and data["quotation"]:
            invoice_data["quotation_id"] = data["quotation"]
        if "purchase_order" in data and data["purchase_order"]:
            invoice_data["purchase_order_id"] = data["purchase_order"]

        invoice = registry.database(
            model_name="Invoice",
            operation="create",
            data=invoice_data
        )

        # Create invoice lines
        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable", "tax_amount", "sub_total", "total"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(message=f"Invoice line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

            # Validate taxable
            taxable_id = line_data.get("taxable")
            if taxable_id:
                tax_rates = registry.database(
                    model_name="TaxRate",
                    operation="filter",
                    data={"id": taxable_id}
                )
                if not tax_rates:
                    return ResponseProvider(message=f"Tax rate {taxable_id} not found", code=404).bad_request()

            # Validate quotation_line if provided
            if "quotation_line" in data.get("lines", []) and line_data["quotation_line"]:
                quotation_lines = registry.database(
                    model_name="QuotationLine",
                    operation="filter",
                    data={"id": line_data["quotation_line"], "is_active": True}
                )
                if not quotation_lines:
                    return ResponseProvider(message=f"Quotation line {line_data['quotation_line']} not found", code=404).bad_request()

            line_data["invoice_id"] = invoice["id"]
            registry.database(
                model_name="InvoiceLine",
                operation="create",
                data=line_data
            )

        # Log creation
        TransactionLogBase.log(
            transaction_type="INVOICE_CREATED",
            user=user,
            message=f"Invoice {invoice['number']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={"invoice_id": invoice["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for the response
        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice["id"], "is_active": True}
        )
        invoice["lines"] = lines

        return ResponseProvider(
            message="Invoice created successfully",
            data=invoice,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating invoice", code=500).exception()


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

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        invoices = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        # Calculate status counts
        statuses = [inv["status"] for inv in invoices]
        status_counts = dict(Counter(statuses))
        total = len(invoices)

        # Ensure all possible statuses are included
        all_statuses = {"DRAFT": 0, "ISSUED": 0, "PAID": 0, "PARTIALLY_PAID": 0, "OVERDUE": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="INVOICE_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} invoices for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            message="Invoices retrieved successfully",
            data={
                "invoices": invoices,
                "total": total,
                "status_counts": all_statuses
            },
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
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Invoice not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    invoice_id = data.get("id")
    if not invoice_id:
        return ResponseProvider(message="Invoice ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        invoices = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"id": invoice_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found for this corporate", code=404).bad_request()

        invoice = invoices[0]

        # Fetch lines
        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice_id, "is_active": True}
        )
        invoice["lines"] = lines

        # Log successful retrieval
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
            data=invoice,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="INVOICE_GET_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving invoice", code=500).exception()


@csrf_exempt
def update_invoice(request):
    """
    Update an existing invoice for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the invoice
    - customer: UUID of the customer (optional)
    - date: Date of the invoice (optional)
    - number: Invoice number (optional, must be unique if changed)
    - due_date: Due date of the invoice (optional)
    - status: Invoice status (optional)
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - salesperson: UUID of the salesperson (optional)
    - profoma_invoice: UUID of the proforma invoice (optional)
    - quotation: UUID of the quotation (optional)
    - purchase_order: UUID of the purchase order (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - sub_total: Subtotal (optional)
    - tax_total: Tax total (optional)
    - total: Total (optional)
    - total_discount: Total discount (optional)
    - lines: List of dictionaries for InvoiceLine (optional), each with optional "id" for existing lines

    Returns:
    - 200: Invoice updated successfully with lines
    - 400: Bad request (missing ID or no valid fields)
    - 401: Unauthorized (user not authenticated)
    - 404: Invoice, customer, salesperson, profoma_invoice, quotation, purchase_order, or taxable not found
    - 409: Invoice number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    invoice_id = data.get("id")
    if not invoice_id:
        return ResponseProvider(message="Invoice ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if invoice exists for this corporate
        invoices = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"id": invoice_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found for this corporate", code=404).bad_request()

        # Prepare update fields for invoice header
        allowed_fields = ["customer", "date", "number", "status", "due_date", "comments", "terms", "salesperson", "profoma_invoice", "quotation", "purchase_order", "ship_date", "ship_via", "fob", "sub_total", "tax_total", "total", "total_discount"]
        update_fields = {}
        for field in allowed_fields:
            if field in data and data[field] is not None:
                if field in ["customer", "salesperson", "profoma_invoice", "quotation", "purchase_order"]:
                    # Validate belongs to corporate
                    model_name = {
                        "customer": "Customer",
                        "salesperson": "CorporateUser",
                        "profoma_invoice": "ProformaInvoice",
                        "quotation": "Quotation",
                        "purchase_order": "PurchaseOrder"
                    }.get(field)
                    if model_name:
                        entities = registry.database(
                            model_name=model_name,
                            operation="filter",
                            data={"id": data[field], "corporate_id": corporate_id, "is_active": True}
                        )
                        if not entities:
                            return ResponseProvider(message=f"{field.capitalize()} {data[field]} not found for this corporate", code=404).bad_request()
                update_fields[field] = data[field]

        if not update_fields and "lines" not in data:
            return ResponseProvider(message="No valid fields provided for update", code=400).bad_request()

        # Handle number uniqueness if changed
        if "number" in update_fields and update_fields["number"] != invoices[0]["number"]:
            existing_invoices = registry.database(
                model_name="Invoice",
                operation="filter",
                data={"number": update_fields["number"]}
            )
            if existing_invoices:
                return ResponseProvider(message="Invoice number already exists", code=409).bad_request()

        # Convert ForeignKey fields to _id
        fk_fields = ["customer", "salesperson", "profoma_invoice", "quotation", "purchase_order"]
        for fk in fk_fields:
            if fk in update_fields:
                update_fields[fk + "_id"] = update_fields.pop(fk)

        update_fields["id"] = invoice_id

        # Update invoice header
        updated_invoice = registry.database(
            model_name="Invoice",
            operation="update",
            instance_id=invoice_id,
            data=update_fields
        )

        # Handle lines if provided
        if "lines" in data:
            provided_lines = data["lines"]
            provided_line_ids = [line.get("id") for line in provided_lines if "id" in line]

            # Get existing line IDs
            existing_lines = registry.database(
                model_name="InvoiceLine",
                operation="filter",
                data={"invoice_id": invoice_id, "is_active": True},
                fields=["id"]
            )
            existing_line_ids = [line["id"] for line in existing_lines]

            # Lines to delete: those not in provided_line_ids
            lines_to_delete = [id for id in existing_line_ids if id not in provided_line_ids]

            # Update or create lines
            for line_data in provided_lines:
                required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable", "tax_amount", "sub_total", "total"]
                for field in required_line_fields:
                    if field not in line_data:
                        return ResponseProvider(message=f"Invoice line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

                # Validate taxable
                taxable_id = line_data.get("taxable")
                if taxable_id:
                    tax_rates = registry.database(
                        model_name="TaxRate",
                        operation="filter",
                        data={"id": taxable_id}
                    )
                    if not tax_rates:
                        return ResponseProvider(message=f"Tax rate {taxable_id} not found", code=404).bad_request()

                # Validate quotation_line if provided
                if "quotation_line" in line_data and line_data["quotation_line"]:
                    quotation_lines = registry.database(
                        model_name="QuotationLine",
                        operation="filter",
                        data={"id": line_data["quotation_line"], "is_active": True}
                    )
                    if not quotation_lines:
                        return ResponseProvider(message=f"Quotation line {line_data['quotation_line']} not found", code=404).bad_request()

                if "id" in line_data:
                    # Update existing line
                    line_id = line_data["id"]
                    line_update_data = {k: v for k, v in line_data.items() if k != "id"}
                    registry.database(
                        model_name="InvoiceLine",
                        operation="update",
                        instance_id=line_id,
                        data=line_update_data
                    )
                else:
                    # Create new line
                    line_data["invoice_id"] = invoice_id
                    registry.database(
                        model_name="InvoiceLine",
                        operation="create",
                        data=line_data
                    )

            # Soft delete lines not in provided list
            for line_id in lines_to_delete:
                registry.database(
                    model_name="InvoiceLine",
                    operation="update",
                    instance_id=line_id,
                    data={"id": line_id, "is_active": False}
                )

        # Log update
        TransactionLogBase.log(
            transaction_type="INVOICE_UPDATED",
            user=user,
            message=f"Invoice {invoice_id} updated",
            state_name="Completed",
            extra={"invoice_id": invoice_id, "updated_fields": list(update_fields.keys())},
            request=request
        )

        # Fetch updated invoice with lines
        updated_invoice = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"id": invoice_id}
        )[0]
        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice_id, "is_active": True}
        )
        updated_invoice["lines"] = lines

        return ResponseProvider(
            message="Invoice updated successfully",
            data=updated_invoice,
            code=200
        ).success()

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
    - id: UUID of the invoice

    Returns:
    - 200: Invoice deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Invoice not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    invoice_id = data.get("id")
    if not invoice_id:
        return ResponseProvider(message="Invoice ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if invoice exists for this corporate
        invoices = registry.database(
            model_name="Invoice",
            operation="filter",
            data={"id": invoice_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not invoices:
            return ResponseProvider(message="Invoice not found for this corporate", code=404).bad_request()

        # Soft delete invoice
        registry.database(
            model_name="Invoice",
            operation="update",
            instance_id=invoice_id,
            data={"id": invoice_id, "is_active": False}
        )

        # Soft delete all its lines
        lines = registry.database(
            model_name="InvoiceLine",
            operation="filter",
            data={"invoice_id": invoice_id, "is_active": True}
        )
        for line in lines:
            registry.database(
                model_name="InvoiceLine",
                operation="update",
                instance_id=line["id"],
                data={"id": line["id"], "is_active": False}
            )

        # Log deletion
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
            data={"invoice_id": invoice_id, "status": "inactive"},
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