from django.views.decorators.csrf import csrf_exempt
from collections import Counter
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def create_purchase_order(request):
    """
    Create a new purchase order for the user's corporate, including its lines.

    Expected data:
    - vendor: UUID of the vendor
    - date: Date of the purchase order
    - number: Purchase order number (must be unique)
    - expected_delivery: Expected delivery date
    - created_by: UUID of the user creating the purchase order
    - status: Purchase order status (optional, defaults to "DRAFT")
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - lines: List of dictionaries, each containing fields for PurchaseOrderLine (e.g., description, quantity, etc.)

    Returns:
    - 201: Purchase order created successfully with lines
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor, created_by, or taxable not found
    - 409: Purchase order number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    required_fields = ["vendor", "date", "number", "expected_delivery", "created_by"]
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

        # Check if purchase order number is unique
        existing_purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"number": data["number"]}
        )
        if existing_purchase_orders:
            return ResponseProvider(message="Purchase order number already exists", code=409).bad_request()

        # Create purchase order
        purchase_order_data = {
            "vendor_id": data["vendor"],
            "corporate_id": corporate_id,
            "date": data["date"],
            "number": data["number"],
            "expected_delivery": data["expected_delivery"],
            "status": data.get("status", "DRAFT"),
            "comments": data.get("comments", ""),
            "terms": data.get("terms", ""),
            "created_by_id": data["created_by"],
            "ship_date": data.get("ship_date"),
            "ship_via": data.get("ship_via", ""),
            "fob": data.get("fob", ""),
        }
        purchase_order = registry.database(
            model_name="PurchaseOrder",
            operation="create",
            data=purchase_order_data
        )

        # Create purchase order lines
        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable", "tax_amount", "sub_total", "total", "total_discount"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(message=f"Purchase order line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

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

            line_data["purchase_order_id"] = purchase_order["id"]
            registry.database(
                model_name="PurchaseOrderLine",
                operation="create",
                data=line_data
            )

        # Log creation
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_CREATED",
            user=user,
            message=f"Purchase order {purchase_order['number']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for the response
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order["id"], "is_active": True}
        )
        purchase_order["lines"] = lines

        return ResponseProvider(
            message="Purchase order created successfully",
            data=purchase_order,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating purchase order", code=500).exception()


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

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        # Calculate status counts
        statuses = [po["status"] for po in purchase_orders]
        status_counts = dict(Counter(statuses))
        total = len(purchase_orders)

        # Ensure all possible statuses are included
        all_statuses = {"DRAFT": 0, "SENT": 0, "CONFIRMED": 0, "RECEIVED": 0, "PARTIALLY_RECEIVED": 0, "CANCELLED": 0}
        all_statuses.update(status_counts)

        # Log successful retrieval
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} purchase orders for corporate {corporate_id}",
            state_name="Success",
            extra={"status_counts": all_statuses},
            request=request
        )

        return ResponseProvider(
            message="Purchase orders retrieved successfully",
            data={
                "purchase_orders": purchase_orders,
                "total": total,
                "status_counts": all_statuses
            },
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
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Purchase order not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    purchase_order_id = data.get("id")
    if not purchase_order_id:
        return ResponseProvider(message="Purchase order ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": purchase_order_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()

        purchase_order = purchase_orders[0]

        # Fetch lines
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order_id, "is_active": True}
        )
        purchase_order["lines"] = lines

        # Log successful retrieval
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
def update_purchase_order(request):
    """
    Update an existing purchase order for the user's corporate, including its lines.

    Expected data:
    - id: UUID of the purchase order
    - vendor: UUID of the vendor (optional)
    - date: Date of the purchase order (optional)
    - number: Purchase order number (optional, must be unique if changed)
    - expected_delivery: Expected delivery date (optional)
    - status: Purchase order status (optional)
    - comments: Comments (optional)
    - terms: Payment terms (optional)
    - created_by: UUID of the user creating the purchase order (optional)
    - ship_date: Shipping date (optional)
    - ship_via: Shipping method (optional)
    - fob: FOB terms (optional)
    - lines: List of dictionaries for PurchaseOrderLine (optional), each with optional "id" for existing lines

    Returns:
    - 200: Purchase order updated successfully with lines
    - 400: Bad request (missing ID or no valid fields)
    - 401: Unauthorized (user not authenticated)
    - 404: Purchase order, vendor, created_by, or taxable not found
    - 409: Purchase order number already exists
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    purchase_order_id = data.get("id")
    if not purchase_order_id:
        return ResponseProvider(message="Purchase order ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if purchase order exists for this corporate
        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": purchase_order_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()

        # Prepare update fields for purchase order header
        allowed_fields = ["vendor", "date", "number", "status", "expected_delivery", "comments", "terms", "created_by", "ship_date", "ship_via", "fob"]
        update_fields = {}
        for field in allowed_fields:
            if field in data and data[field] is not None:
                if field in ["vendor", "created_by"]:
                    # Validate belongs to corporate
                    model_name = "Vendor" if field == "vendor" else "CorporateUser"
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
        if "number" in update_fields and update_fields["number"] != purchase_orders[0]["number"]:
            existing_purchase_orders = registry.database(
                model_name="PurchaseOrder",
                operation="filter",
                data={"number": update_fields["number"]}
            )
            if existing_purchase_orders:
                return ResponseProvider(message="Purchase order number already exists", code=409).bad_request()

        # Convert ForeignKey fields to _id
        fk_fields = ["vendor", "created_by"]
        for fk in fk_fields:
            if fk in update_fields:
                update_fields[fk + "_id"] = update_fields.pop(fk)

        update_fields["id"] = purchase_order_id

        # Update purchase order header
        updated_purchase_order = registry.database(
            model_name="PurchaseOrder",
            operation="update",
            instance_id=purchase_order_id,
            data=update_fields
        )

        # Handle lines if provided
        if "lines" in data:
            provided_lines = data["lines"]
            provided_line_ids = [line.get("id") for line in provided_lines if "id" in line]

            # Get existing line IDs
            existing_lines = registry.database(
                model_name="PurchaseOrderLine",
                operation="filter",
                data={"purchase_order_id": purchase_order_id, "is_active": True},
                fields=["id"]
            )
            existing_line_ids = [line["id"] for line in existing_lines]

            # Lines to delete: those not in provided_line_ids
            lines_to_delete = [id for id in existing_line_ids if id not in provided_line_ids]

            # Update or create lines
            for line_data in provided_lines:
                required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable", "tax_amount", "sub_total", "total", "total_discount"]
                for field in required_line_fields:
                    if field not in line_data:
                        return ResponseProvider(message=f"Purchase order line field {field.replace('_', ' ').title()} is required", code=400).bad_request()

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

                if "id" in line_data:
                    # Update existing line
                    line_id = line_data["id"]
                    line_update_data = {k: v for k, v in line_data.items() if k != "id"}
                    registry.database(
                        model_name="PurchaseOrderLine",
                        operation="update",
                        instance_id=line_id,
                        data=line_update_data
                    )
                else:
                    # Create new line
                    line_data["purchase_order_id"] = purchase_order_id
                    registry.database(
                        model_name="PurchaseOrderLine",
                        operation="create",
                        data=line_data
                    )

            # Soft delete lines not in provided list
            for line_id in lines_to_delete:
                registry.database(
                    model_name="PurchaseOrderLine",
                    operation="update",
                    instance_id=line_id,
                    data={"id": line_id, "is_active": False}
                )

        # Log update
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_UPDATED",
            user=user,
            message=f"Purchase order {purchase_order_id} updated",
            state_name="Completed",
            extra={"purchase_order_id": purchase_order_id, "updated_fields": list(update_fields.keys())},
            request=request
        )

        # Fetch updated purchase order with lines
        updated_purchase_order = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": purchase_order_id}
        )[0]
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order_id, "is_active": True}
        )
        updated_purchase_order["lines"] = lines

        return ResponseProvider(
            message="Purchase order updated successfully",
            data=updated_purchase_order,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PURCHASE_ORDER_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating purchase order", code=500).exception()


@csrf_exempt
def delete_purchase_order(request):
    """
    Soft delete a purchase order by setting is_active to False for both the purchase order and its lines.

    Expected data:
    - id: UUID of the purchase order

    Returns:
    - 200: Purchase order deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Purchase order not found for this corporate
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    corporate_id = user.get("corporate_id")
    if not corporate_id:
        return ResponseProvider(message="User has no corporate", code=400).bad_request()

    purchase_order_id = data.get("id")
    if not purchase_order_id:
        return ResponseProvider(message="Purchase order ID is required", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        # Check if purchase order exists for this corporate
        purchase_orders = registry.database(
            model_name="PurchaseOrder",
            operation="filter",
            data={"id": purchase_order_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not purchase_orders:
            return ResponseProvider(message="Purchase order not found for this corporate", code=404).bad_request()

        # Soft delete purchase order
        registry.database(
            model_name="PurchaseOrder",
            operation="update",
            instance_id=purchase_order_id,
            data={"id": purchase_order_id, "is_active": False}
        )

        # Soft delete all its lines
        lines = registry.database(
            model_name="PurchaseOrderLine",
            operation="filter",
            data={"purchase_order_id": purchase_order_id, "is_active": True}
        )
        for line in lines:
            registry.database(
                model_name="PurchaseOrderLine",
                operation="update",
                instance_id=line["id"],
                data={"id": line["id"], "is_active": False}
            )

        # Log deletion
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
            data={"purchase_order_id": purchase_order_id, "status": "inactive"},
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