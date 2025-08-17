from django.views.decorators.csrf import csrf_exempt
from collections import Counter
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_vendor_bill(request):
    """
    Create a new vendor bill for the user's corporate, including its lines.

    Expected data:
    - vendor: UUID of the vendor
    - date: Date of the vendor bill
    - number: Vendor bill number (must be unique)
    - due_date: Due date of the vendor bill
    - created_by: UUID of the user creating the vendor bill
    - purchase_order: UUID of the purchase order (optional)
    - status: Vendor bill status (optional, defaults to "DRAFT")
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - sub_total: Subtotal (optional, defaults to 0.00)
    - tax_total: Tax total (optional, defaults to 0.00)
    - total: Total (optional, defaults to 0.00)
    - total_discount: Total discount (optional, defaults to 0.00)
    - lines: List of dictionaries, each containing fields for VendorBillLine (e.g., description, quantity, etc.)

    Returns:
    - 201: Vendor bill created successfully with lines
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor, created_by, purchase_order, purchase_order_line, or taxable not found
    - 409: Vendor bill number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    required_fields = ["vendor", "date", "number", "due_date", "created_by"]
    for field in required_fields:
        if field not in data:
            return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Validate vendor
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor"], "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            return ResponseProvider(message="Vendor not found or inactive for this corporate", code=404).bad_request()

        # Validate created_by
        users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["created_by"], "corporate_id": corporate_id, "is_active": True}
        )
        if not users:
            return ResponseProvider(message="Created by user not found or inactive for this corporate", code=404).bad_request()

        # Validate purchase_order if provided
        if "purchase_order" in data and data["purchase_order"]:
            purchase_orders = registry.database(
                model_name="PurchaseOrder",
                operation="filter",
                data={"id": data["purchase_order"], "corporate_id": corporate_id, "is_active": True}
            )
            if not purchase_orders:
                return ResponseProvider(message="Purchase order not found or inactive for this corporate", code=404).bad_request()

        # Check if vendor bill number is unique
        existing_vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"number": data["number"]}
        )
        if existing_vendor_bills:
            return ResponseProvider(message="Vendor bill number already exists", code=409).bad_request()

        # Create vendor bill
        vendor_bill_data = {
            "vendor_id": data["vendor"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "due_date": data["due_date"],
            "status": data.get("status", "DRAFT"),
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "created_by_id": data["created_by"],
            "sub_total": data.get("sub_total", 0.00),
            "tax_total": data.get("tax_total", 0.00),
            "total": data.get("total", 0.00),
            "total_discount": data.get("total_discount", 0.00),
        }
        if "purchase_order" in data and data["purchase_order"]:
            vendor_bill_data["purchase_order_id"] = data["purchase_order"]

        vendor_bill = registry.database(
            model_name="VendorBill",
            operation="create",
            data=vendor_bill_data
        )

        # Create vendor bill lines
        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable", "tax_amount", "sub_total", "total"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(message=f"Vendor bill line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

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

            # Validate purchase_order_line if provided
            if "purchase_order_line" in line_data and line_data["purchase_order_line"]:
                purchase_order_lines = registry.database(
                    model_name="PurchaseOrderLine",
                    operation="filter",
                    data={"id": line_data["purchase_order_line"], "is_active": True}
                )
                if not purchase_order_lines:
                    return ResponseProvider(message=f"Purchase order line {line_data['purchase_order_line']} not found", code=404).bad_request()

            line_data["vendor_bill_id"] = vendor_bill["id"]
            registry.database(
                model_name="VendorBillLine",
                operation="create",
                data=line_data
            )

        # Log creation
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_CREATED",
            user=user,
            message=f"Vendor bill {vendor_bill['number']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={"vendor_bill_id": vendor_bill["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for the response
        lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill["id"], "is_active": True}
        )
        vendor_bill["lines"] = lines

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

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        # Calculate status counts
        statuses = [vb["status"] for vb in vendor_bills]
        status_counts = dict(Counter(statuses))
        total = len(vendor_bills)

        # Ensure all possible statuses are included
        all_statuses = {"DRAFT": 0, "POSTED": 0, "PAID": 0, "PARTIALLY_PAID": 0, "OVERDUE": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} vendor bills for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            message="Vendor bills retrieved successfully",
            data={
                "vendor_bills": vendor_bills,
                "total": total,
                "status_counts": all_statuses
            },
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
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor bill not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    vendor_bill_id = data.get("id")
    if not vendor_bill_id:
        return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found for this corporate", code=404).bad_request()

        vendor_bill = vendor_bills[0]

        # Fetch lines
        lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill_id, "is_active": True}
        )
        vendor_bill["lines"] = lines

        # Log successful retrieval
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
def update_vendor_bill(request):
    """
    Update an existing vendor bill for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the vendor bill
    - vendor: UUID of the vendor (optional)
    - date: Date of the vendor bill (optional)
    - number: Vendor bill number (optional, must be unique if changed)
    - due_date: Due date of the vendor bill (optional)
    - status: Vendor bill status (optional)
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - created_by: UUID of the user creating the vendor bill (optional)
    - purchase_order: UUID of the purchase order (optional)
    - sub_total: Subtotal (optional)
    - tax_total: Tax total (optional)
    - total: Total (optional)
    - total_discount: Total discount (optional)
    - lines: List of dictionaries for VendorBillLine (optional), each with optional "id" for existing lines

    Returns:
    - 200: Vendor bill updated successfully with lines
    - 400: Bad request (missing ID or no valid fields)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor bill, vendor, created_by, purchase_order, purchase_order_line, or taxable not found
    - 409: Vendor bill number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    vendor_bill_id = data.get("id")
    if not vendor_bill_id:
        return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if vendor bill exists for this corporate
        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found for this corporate", code=404).bad_request()

        # Prepare update fields for vendor bill header
        allowed_fields = ["vendor", "date", "number", "status", "due_date", "comments", "terms", "created_by", "purchase_order", "sub_total", "tax_total", "total", "total_discount"]
        update_fields = {}
        for field in allowed_fields:
            if field in data and data[field] is not None:
                if field in ["vendor", "created_by", "purchase_order"]:
                    # Validate belongs to corporate
                    model_name = {"vendor": "Vendor", "created_by": "CorporateUser", "purchase_order": "PurchaseOrder"}.get(field)
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
        if "number" in update_fields and update_fields["number"] != vendor_bills[0]["number"]:
            existing_vendor_bills = registry.database(
                model_name="VendorBill",
                operation="filter",
                data={"number": update_fields["number"]}
            )
            if existing_vendor_bills:
                return ResponseProvider(message="Vendor bill number already exists", code=409).bad_request()

        # Convert ForeignKey fields to _id
        fk_fields = ["vendor", "created_by", "purchase_order"]
        for fk in fk_fields:
            if fk in update_fields:
                update_fields[fk + "_id"] = update_fields.pop(fk)

        update_fields["id"] = vendor_bill_id

        # Update vendor bill header
        updated_vendor_bill = registry.database(
            model_name="VendorBill",
            operation="update",
            instance_id=vendor_bill_id,
            data=update_fields
        )

        # Handle lines if provided
        if "lines" in data:
            provided_lines = data["lines"]
            provided_line_ids = [line.get("id") for line in provided_lines if "id" in line]

            # Get existing line IDs
            existing_lines = registry.database(
                model_name="VendorBillLine",
                operation="filter",
                data={"vendor_bill_id": vendor_bill_id, "is_active": True},
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
                        return ResponseProvider(message=f"Vendor bill line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

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

                # Validate purchase_order_line if provided
                if "purchase_order_line" in line_data and line_data["purchase_order_line"]:
                    purchase_order_lines = registry.database(
                        model_name="PurchaseOrderLine",
                        operation="filter",
                        data={"id": line_data["purchase_order_line"], "is_active": True}
                    )
                    if not purchase_order_lines:
                        return ResponseProvider(message=f"Purchase order line {line_data['purchase_order_line']} not found", code=404).bad_request()

                if "id" in line_data:
                    # Update existing line
                    line_id = line_data["id"]
                    line_update_data = {k: v for k, v in line_data.items() if k != "id"}
                    registry.database(
                        model_name="VendorBillLine",
                        operation="update",
                        instance_id=line_id,
                        data=line_update_data
                    )
                else:
                    # Create new line
                    line_data["vendor_bill_id"] = vendor_bill_id
                    registry.database(
                        model_name="VendorBillLine",
                        operation="create",
                        data=line_data
                    )

            # Soft delete lines not in provided list
            for line_id in lines_to_delete:
                registry.database(
                    model_name="VendorBillLine",
                    operation="update",
                    instance_id=line_id,
                    data={"id": line_id, "is_active": False}
                )

        # Log update
        TransactionLogBase.log(
            transaction_type="VENDOR_BILL_UPDATED",
            user=user,
            message=f"Vendor bill {vendor_bill_id} updated",
            state_name="Completed",
            extra={"vendor_bill_id": vendor_bill_id, "updated_fields": list(update_fields.keys())},
            request=request
        )

        # Fetch updated vendor bill with lines
        updated_vendor_bill = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id}
        )[0]
        lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill_id, "is_active": True}
        )
        updated_vendor_bill["lines"] = lines

        return ResponseProvider(
            message="Vendor bill updated successfully",
            data=updated_vendor_bill,
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
def delete_vendor_bill(request):
    """
    Soft delete a vendor bill by setting is_active to False for both the vendor bill and its lines.

    Expected data:
    - id: UUID of the vendor bill

    Returns:
    - 200: Vendor bill deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor bill not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    vendor_bill_id = data.get("id")
    if not vendor_bill_id:
        return ResponseProvider(message="Vendor bill ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if vendor bill exists for this corporate
        vendor_bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"id": vendor_bill_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not vendor_bills:
            return ResponseProvider(message="Vendor bill not found for this corporate", code=404).bad_request()

        # Soft delete vendor bill
        registry.database(
            model_name="VendorBill",
            operation="update",
            instance_id=vendor_bill_id,
            data={"id": vendor_bill_id, "is_active": False}
        )

        # Soft delete all its lines
        lines = registry.database(
            model_name="VendorBillLine",
            operation="filter",
            data={"vendor_bill_id": vendor_bill_id, "is_active": True}
        )
        for line in lines:
            registry.database(
                model_name="VendorBillLine",
                operation="update",
                instance_id=line["id"],
                data={"id": line["id"], "is_active": False}
            )

        # Log deletion
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
            data={"vendor_bill_id": vendor_bill_id, "status": "inactive"},
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