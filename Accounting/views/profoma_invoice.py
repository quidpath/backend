from django.views.decorators.csrf import csrf_exempt
from collections import Counter
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_proforma_invoice(request):
    """
    Create a new proforma invoice for the user's corporate, including its lines.

    Expected data:
    - customer: UUID of the customer
    - date: Date of the proforma invoice
    - number: Proforma invoice number (must be unique)
    - valid_until: Validity date of the proforma invoice
    - salesperson: UUID of the salesperson
    - quotation: UUID of the quotation (optional)
    - status: Proforma invoice status (optional, defaults to "DRAFT")
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - sub_total: Subtotal (optional, defaults to 0.00)
    - tax_total: Tax total (optional, defaults to 0.00)
    - total: Total (optional, defaults to 0.00)
    - total_discount: Total discount (optional, defaults to 0.00)
    - lines: List of dictionaries, each containing fields for ProformaInvoiceLine (e.g., description, quantity, etc.)

    Returns:
    - 201: Proforma invoice created successfully with lines
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Customer, salesperson, quotation, or taxable not found
    - 409: Proforma invoice number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    required_fields = ["customer", "date", "number", "valid_until", "salesperson"]
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

        # Validate quotation if provided
        if "quotation" in data and data["quotation"]:
            quotations = registry.database(
                model_name="Quotation",
                operation="filter",
                data={"id": data["quotation"], "corporate_id": corporate_id, "is_active": True}
            )
            if not quotations:
                return ResponseProvider(message="Quotation not found or inactive for this corporate", code=404).bad_request()

        # Check if proforma invoice number is unique
        existing_proforma_invoices = registry.database(
            model_name="ProformaInvoice",
            operation="filter",
            data={"number": data["number"]}
        )
        if existing_proforma_invoices:
            return ResponseProvider(message="Proforma invoice number already exists", code=409).bad_request()

        # Create proforma invoice
        proforma_invoice_data = {
            "customer_id": data["customer"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "valid_until": data["valid_until"],
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
        if "quotation" in data and data["quotation"]:
            proforma_invoice_data["quotation_id"] = data["quotation"]

        proforma_invoice = registry.database(
            model_name="ProformaInvoice",
            operation="create",
            data=proforma_invoice_data
        )

        # Create proforma invoice lines
        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable", "tax_amount", "sub_total", "total"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(message=f"Proforma invoice line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

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

            line_data["proforma_invoice_id"] = proforma_invoice["id"]
            registry.database(
                model_name="ProformaInvoiceLine",
                operation="create",
                data=line_data
            )

        # Log creation
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_CREATED",
            user=user,
            message=f"Proforma invoice {proforma_invoice['number']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={"proforma_invoice_id": proforma_invoice["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for the response
        lines = registry.database(
            model_name="ProformaInvoiceLine",
            operation="filter",
            data={"proforma_invoice_id": proforma_invoice["id"], "is_active": True}
        )
        proforma_invoice["lines"] = lines

        return ResponseProvider(
            message="Proforma invoice created successfully",
            data=proforma_invoice,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating proforma invoice", code=500).exception()


@csrf_exempt
def list_proforma_invoices(request):
    """
    List all proforma invoices for the user's corporate, categorized by status.

    Returns:
    - 200: List of proforma invoices with total count and status counts
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
        proforma_invoices = registry.database(
            model_name="ProformaInvoice",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        # Calculate status counts
        statuses = [pi["status"] for pi in proforma_invoices]
        status_counts = dict(Counter(statuses))
        total = len(proforma_invoices)

        # Ensure all possible statuses are included
        all_statuses = {"DRAFT": 0, "SENT": 0, "APPROVED": 0, "REJECTED": 0}
        all_statuses.update(status_counts)

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} proforma invoices for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            message="Proforma invoices retrieved successfully",
            data={
                "proforma_invoices": proforma_invoices,
                "total": total,
                "status_counts": all_statuses
            },
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving proforma invoices", code=500).exception()


@csrf_exempt
def get_proforma_invoice(request):
    """
    Get a single proforma invoice by ID for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the proforma invoice

    Returns:
    - 200: Proforma invoice retrieved successfully with lines
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Proforma invoice not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    proforma_invoice_id = data.get("id")
    if not proforma_invoice_id:
        return ResponseProvider(message="Proforma invoice ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        proforma_invoices = registry.database(
            model_name="ProformaInvoice",
            operation="filter",
            data={"id": proforma_invoice_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not proforma_invoices:
            return ResponseProvider(message="Proforma invoice not found for this corporate", code=404).bad_request()

        proforma_invoice = proforma_invoices[0]

        # Fetch lines
        lines = registry.database(
            model_name="ProformaInvoiceLine",
            operation="filter",
            data={"proforma_invoice_id": proforma_invoice_id, "is_active": True}
        )
        proforma_invoice["lines"] = lines

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_GET_SUCCESS",
            user=user,
            message=f"Proforma invoice {proforma_invoice_id} retrieved for corporate {corporate_id}",
            state_name="Success",
            extra={"proforma_invoice_id": proforma_invoice_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Proforma invoice retrieved successfully",
            data=proforma_invoice,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_GET_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving proforma invoice", code=500).exception()


@csrf_exempt
def update_proforma_invoice(request):
    """
    Update an existing proforma invoice for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the proforma invoice
    - customer: UUID of the customer (optional)
    - date: Date of the proforma invoice (optional)
    - number: Proforma invoice number (optional, must be unique if changed)
    - valid_until: Validity date of the proforma invoice (optional)
    - status: Proforma invoice status (optional)
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - salesperson: UUID of the salesperson (optional)
    - quotation: UUID of the quotation (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - sub_total: Subtotal (optional)
    - tax_total: Tax total (optional)
    - total: Total (optional)
    - total_discount: Total discount (optional)
    - lines: List of dictionaries for ProformaInvoiceLine (optional), each with optional "id" for existing lines

    Returns:
    - 200: Proforma invoice updated successfully with lines
    - 400: Bad request (missing ID or no valid fields)
    - 401: Unauthorized (user not authenticated)
    - 404: Proforma invoice, customer, salesperson, quotation, or taxable not found
    - 409: Proforma invoice number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    proforma_invoice_id = data.get("id")
    if not proforma_invoice_id:
        return ResponseProvider(message="Proforma invoice ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if proforma invoice exists for this corporate
        proforma_invoices = registry.database(
            model_name="ProformaInvoice",
            operation="filter",
            data={"id": proforma_invoice_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not proforma_invoices:
            return ResponseProvider(message="Proforma invoice not found for this corporate", code=404).bad_request()

        # Prepare update fields for proforma invoice header
        allowed_fields = ["customer", "date", "number", "status", "valid_until", "comments", "terms", "salesperson", "quotation", "ship_date", "ship_via", "fob", "sub_total", "tax_total", "total", "total_discount"]
        update_fields = {}
        for field in allowed_fields:
            if field in data and data[field] is not None:
                if field in ["customer", "salesperson", "quotation"]:
                    # Validate belongs to corporate
                    model_name = {"customer": "Customer", "salesperson": "CorporateUser", "quotation": "Quotation"}.get(field)
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
        if "number" in update_fields and update_fields["number"] != proforma_invoices[0]["number"]:
            existing_proforma_invoices = registry.database(
                model_name="ProformaInvoice",
                operation="filter",
                data={"number": update_fields["number"]}
            )
            if existing_proforma_invoices:
                return ResponseProvider(message="Proforma invoice number already exists", code=409).bad_request()

        # Convert ForeignKey fields to _id
        fk_fields = ["customer", "salesperson", "quotation"]
        for fk in fk_fields:
            if fk in update_fields:
                update_fields[fk + "_id"] = update_fields.pop(fk)

        update_fields["id"] = proforma_invoice_id

        # Update proforma invoice header
        updated_proforma_invoice = registry.database(
            model_name="ProformaInvoice",
            operation="update",
            instance_id=proforma_invoice_id,
            data=update_fields
        )

        # Handle lines if provided
        if "lines" in data:
            provided_lines = data["lines"]
            provided_line_ids = [line.get("id") for line in provided_lines if "id" in line]

            # Get existing line IDs
            existing_lines = registry.database(
                model_name="ProformaInvoiceLine",
                operation="filter",
                data={"proforma_invoice_id": proforma_invoice_id, "is_active": True},
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
                        return ResponseProvider(message=f"Proforma invoice line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

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
                        model_name="ProformaInvoiceLine",
                        operation="update",
                        instance_id=line_id,
                        data=line_update_data
                    )
                else:
                    # Create new line
                    line_data["proforma_invoice_id"] = proforma_invoice_id
                    registry.database(
                        model_name="ProformaInvoiceLine",
                        operation="create",
                        data=line_data
                    )

            # Soft delete lines not in provided list
            for line_id in lines_to_delete:
                registry.database(
                    model_name="ProformaInvoiceLine",
                    operation="update",
                    instance_id=line_id,
                    data={"id": line_id, "is_active": False}
                )

        # Log update
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_UPDATED",
            user=user,
            message=f"Proforma invoice {proforma_invoice_id} updated",
            state_name="Completed",
            extra={"proforma_invoice_id": proforma_invoice_id, "updated_fields": list(update_fields.keys())},
            request=request
        )

        # Fetch updated proforma invoice with lines
        updated_proforma_invoice = registry.database(
            model_name="ProformaInvoice",
            operation="filter",
            data={"id": proforma_invoice_id}
        )[0]
        lines = registry.database(
            model_name="ProformaInvoiceLine",
            operation="filter",
            data={"proforma_invoice_id": proforma_invoice_id, "is_active": True}
        )
        updated_proforma_invoice["lines"] = lines

        return ResponseProvider(
            message="Proforma invoice updated successfully",
            data=updated_proforma_invoice,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating proforma invoice", code=500).exception()


@csrf_exempt
def delete_proforma_invoice(request):
    """
    Soft delete a proforma invoice by setting is_active to False for both the proforma invoice and its lines.

    Expected data:
    - id: UUID of the proforma invoice

    Returns:
    - 200: Proforma invoice deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Proforma invoice not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    proforma_invoice_id = data.get("id")
    if not proforma_invoice_id:
        return ResponseProvider(message="Proforma invoice ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if proforma invoice exists for this corporate
        proforma_invoices = registry.database(
            model_name="ProformaInvoice",
            operation="filter",
            data={"id": proforma_invoice_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not proforma_invoices:
            return ResponseProvider(message="Proforma invoice not found for this corporate", code=404).bad_request()

        # Soft delete proforma invoice
        registry.database(
            model_name="ProformaInvoice",
            operation="update",
            instance_id=proforma_invoice_id,
            data={"id": proforma_invoice_id, "is_active": False}
        )

        # Soft delete all its lines
        lines = registry.database(
            model_name="ProformaInvoiceLine",
            operation="filter",
            data={"proforma_invoice_id": proforma_invoice_id, "is_active": True}
        )
        for line in lines:
            registry.database(
                model_name="ProformaInvoiceLine",
                operation="update",
                instance_id=line["id"],
                data={"id": line["id"], "is_active": False}
            )

        # Log deletion
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_DELETED",
            user=user,
            message=f"Proforma invoice {proforma_invoice_id} soft-deleted",
            state_name="Completed",
            extra={"proforma_invoice_id": proforma_invoice_id, "line_count": len(lines)},
            request=request
        )

        return ResponseProvider(
            message="Proforma invoice deleted successfully",
            data={"proforma_invoice_id": proforma_invoice_id, "status": "inactive"},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROFORMA_INVOICE_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting proforma invoice", code=500).exception()