from decimal import Decimal, InvalidOperation
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from Payments.models import VendorPayment, VendorPaymentLine
from quidpath_backend.core.utils.Logbase import logger, TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry

@csrf_exempt
def list_vendors(request):
    """
    List all active vendors for the user's corporate.

    Returns:
    - 200: List of vendors
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

        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        serialized_vendors = [
            {
                "id": str(vendor["id"]),
                "name": (
                    vendor["company_name"]
                    if vendor.get("company_name")
                    else vendor.get("name", "")
                ),
                "email": vendor.get("email", ""),
                "phone": vendor.get("phone", ""),
                "billing_address": vendor.get("address", ""),
                "city": vendor.get("city", ""),
                "state": vendor.get("state", ""),
                "zip_code": vendor.get("zip_code", ""),
                "country": vendor.get("country", "")
            }
            for vendor in vendors
        ]

        TransactionLogBase.log(
            transaction_type="VENDOR_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {len(vendors)} vendors for corporate {corporate_id}",
            state_name="Success",
            extra={"vendor_count": len(vendors)},
            request=request
        )

        return ResponseProvider(
            data={"vendors": serialized_vendors, "total": len(vendors)},
            message="Vendors retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="VENDOR_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving vendors", code=500).exception()

@csrf_exempt
def list_unpaid_bills(request):
    """
    List all unpaid or partially paid bills for a selected vendor.

    Expected data:
    - vendor_id: UUID of the vendor
    - corporate_id: UUID of the corporate

    Returns:
    - 200: List of unpaid/partially paid bills with outstanding amounts
    - 400: Bad request (missing vendor ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        TransactionLogBase.log(
            transaction_type="UNPAID_BILLS_LIST_FAILED",
            user=user,
            message="User not authenticated",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        TransactionLogBase.log(
            transaction_type="UNPAID_BILLS_LIST_FAILED",
            user=user,
            message="User ID not found",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    vendor_id = data.get("vendor_id")
    corporate_id = data.get("corporate_id")
    if not vendor_id or not corporate_id:
        TransactionLogBase.log(
            transaction_type="UNPAID_BILLS_LIST_FAILED",
            user=user,
            message="Vendor ID and Corporate ID are required",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="Vendor ID and Corporate ID are required", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not corporate_users:
            TransactionLogBase.log(
                transaction_type="UNPAID_BILLS_LIST_FAILED",
                user=user,
                message="User has no corporate association",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": vendor_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not vendors:
            TransactionLogBase.log(
                transaction_type="UNPAID_BILLS_LIST_FAILED",
                user=user,
                message="Vendor not found or inactive",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Vendor not found or inactive", code=404).bad_request()

        bills = registry.database(
            model_name="VendorBill",
            operation="filter",
            data={"vendor_id": vendor_id, "corporate_id": corporate_id, "status__in": ["POSTED", "PARTIALLY_PAID"]}
        )

        serialized_bills = []
        for bill in bills:
            payments = registry.database(
                model_name="VendorPaymentLine",
                operation="filter",
                data={"bill_id": bill["id"]}
            )
            total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
            outstanding_amount = Decimal(str(bill.get("total", 0))) - total_paid

            if outstanding_amount > 0:
                serialized_bills.append({
                    "id": str(bill["id"]),
                    "number": bill["number"],
                    "date": bill["date"],
                    "due_date": bill["due_date"],
                    "total": float(bill.get("total", 0)),
                    "outstanding_amount": float(outstanding_amount),
                    "status": bill["status"],
                    "currency": bill.get("currency", "USD")
                })

        TransactionLogBase.log(
            transaction_type="UNPAID_BILLS_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {len(serialized_bills)} unpaid bills for vendor {vendor_id}",
            state_name="Success",
            extra={"vendor_id": vendor_id, "bill_count": len(serialized_bills)},
            request=request
        )

        return ResponseProvider(
            data={"bills": serialized_bills, "total": len(serialized_bills)},
            message="Unpaid bills retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="UNPAID_BILLS_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving unpaid bills", code=500).exception()


@csrf_exempt
def record_vendor_payment(request):
    """
    Record a payment to a vendor and distribute it across unpaid bills.
    Pre-validates bill IDs in allocations to skip invalid ones and proceed with payment.

    Expected data:
    - vendor_id: UUID of the vendor
    - corporate_id: UUID of the corporate
    - amount_disbursed: Decimal amount of the payment
    - payment_date: Date of the payment
    - payment_method: One of the allowed payment methods (cash, card, bank_transfer, paypal, mpesa, cheque)
    - account_id: UUID of the bank account
    - payment_number: Optional payment reference number
    - bill_number: Optional bill reference number
    - notes: Optional notes
    - bank_charges: Optional bank charges (default 0)
    - allocations: Optional list of {bill_id, amount_applied} to specify manual distribution

    Returns:
    - 201: Payment recorded and distributed successfully
    - 400: Bad request (missing required fields, invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Vendor, account, or bill not found
    - 500: Internal server error
    """
    logger.debug("Received request to /vendor-payment/record/: %s", request.body)
    try:
        data, metadata = get_clean_data(request)
        logger.debug("Parsed data: %s, metadata: %s", data, metadata)
    except Exception as e:
        logger.exception("Failed to parse request data: %s", str(e))
        TransactionLogBase.log(
            transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
            user=None,
            message=f"Invalid request data: {str(e)}",
            state_name="Failed",
            request=request,
            extra={"request_body": str(request.body)}
        )
        return ResponseProvider(message=f"Invalid request data: {str(e)}", code=400).bad_request()

    user = metadata.get("user")
    if not user:
        logger.error("User not authenticated")
        TransactionLogBase.log(
            transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
            user=None,
            message="User not authenticated",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    logger.debug("User ID: %s", user_id)
    if not user_id:
        logger.error("User ID not found")
        TransactionLogBase.log(
            transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
            user=user,
            message="User ID not found",
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        logger.debug("Initialized ServiceRegistry")

        corporate_id = data.get("corporate_id")
        if not corporate_id:
            logger.error("Corporate ID is required")
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Corporate ID is required",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Corporate ID is required", code=400).bad_request()

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        logger.debug("Corporate users: %s", corporate_users)
        if not corporate_users:
            logger.error("No corporate association for user_id: %s", user_id)
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="User has no corporate association",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        required_fields = ["vendor_id", "amount_disbursed", "payment_date", "payment_method", "account_id"]
        for field in required_fields:
            if field not in data:
                logger.error("Missing required field: %s", field)
                TransactionLogBase.log(
                    transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                    user=user,
                    message=f"{field.replace('_', ' ').title()} is required",
                    state_name="Failed",
                    request=request
                )
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        logger.debug("Fetching vendors for vendor_id: %s, corporate_id: %s", data["vendor_id"], corporate_id)
        vendors = registry.database(
            model_name="Vendor",
            operation="filter",
            data={"id": data["vendor_id"], "corporate_id": corporate_id, "is_active": True}
        )
        logger.debug("Vendors: %s", vendors)
        if not vendors:
            logger.error("Vendor not found or inactive: %s", data["vendor_id"])
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Vendor not found or inactive",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Vendor not found or inactive", code=404).bad_request()

        logger.debug("Fetching accounts for account_id: %s, corporate_id: %s", data["account_id"], corporate_id)
        accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": data["account_id"], "corporate_id": corporate_id, "is_active": True}
        )
        logger.debug("Accounts: %s", accounts)
        if not accounts:
            logger.error("Bank account not found or inactive: %s", data["account_id"])
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Bank account not found or inactive",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Bank account not found or inactive", code=404).bad_request()

        try:
            amount_disbursed = Decimal(str(data["amount_disbursed"]))
        except Exception as e:
            logger.error("Invalid amount_disbursed format: %s", str(e))
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Amount disbursed must be a valid decimal",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Amount disbursed must be a valid decimal", code=400).bad_request()
        if amount_disbursed <= 0:
            logger.error("Amount disbursed must be greater than 0: %s", amount_disbursed)
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Amount disbursed must be greater than 0",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Amount disbursed must be greater than 0", code=400).bad_request()

        try:
            bank_charges = Decimal(str(data.get("bank_charges", 0)))
        except Exception as e:
            logger.error("Invalid bank_charges format: %s", str(e))
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Bank charges must be a valid decimal",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Bank charges must be a valid decimal", code=400).bad_request()
        if bank_charges < 0:
            logger.error("Bank charges cannot be negative: %s", bank_charges)
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message="Bank charges cannot be negative",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message="Bank charges cannot be negative", code=400).bad_request()

        payment_method = data["payment_method"]
        valid_methods = ["cash", "card", "bank_transfer", "paypal", "mpesa", "cheque"]
        if payment_method not in valid_methods:
            logger.error("Invalid payment method: %s, valid methods: %s", payment_method, valid_methods)
            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                user=user,
                message=f"Invalid payment method. Must be one of: {', '.join(valid_methods)}",
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message=f"Invalid payment method. Must be one of: {', '.join(valid_methods)}",
                                    code=400).bad_request()

        bill_number = data.get("bill_number")
        if bill_number:
            logger.debug("Validating bill_number: %s for vendor_id: %s", bill_number, data["vendor_id"])
            bills_by_number = registry.database(
                model_name="VendorBill",
                operation="filter",
                data={"number": bill_number, "vendor_id": data["vendor_id"], "corporate_id": corporate_id}
            )
            if not bills_by_number:
                logger.error("Bill number %s not found for vendor %s", bill_number, data["vendor_id"])
                TransactionLogBase.log(
                    transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                    user=user,
                    message=f"Bill number {bill_number} not found for this vendor",
                    state_name="Failed",
                    request=request
                )
                return ResponseProvider(message=f"Bill number {bill_number} not found for this vendor",
                                        code=404).bad_request()

        with transaction.atomic():
            payment_data = {
                "vendor_id": data["vendor_id"],
                "corporate_id": corporate_id,
                "amount_disbursed": str(amount_disbursed),
                "bank_charges": str(bank_charges),
                "payment_date": data["payment_date"],
                "payment_method": payment_method,
                "account_id": data["account_id"],
                "payment_number": data.get("payment_number", ""),
                "bill_number": bill_number or "",
                "notes": data.get("notes", ""),
                "amount_used": "0",
                "amount_refunded": "0",
                "amount_excess": "0",
                "created_by_id": user_id
            }
            logger.debug("Creating vendor payment with data: %s", payment_data)
            payment = registry.database(
                model_name="VendorPayment",
                operation="create",
                data=payment_data
            )
            logger.debug("Vendor payment created: %s", payment)

            logger.debug("Fetching bills for vendor_id: %s, corporate_id: %s", data["vendor_id"], corporate_id)
            bills = registry.database(
                model_name="VendorBill",
                operation="filter",
                data={"vendor_id": data["vendor_id"], "corporate_id": corporate_id,
                      "status__in": ["POSTED", "PARTIALLY_PAID"]}
            )
            logger.debug("Bills: %s", bills)

            # Validate purchase orders for bills
            for bill in bills:
                if bill.get("purchase_order_id"):
                    logger.debug("Validating purchase order for bill: %s", bill["id"])
                    po = registry.database(
                        model_name="PurchaseOrder",
                        operation="filter",
                        data={"id": bill["purchase_order_id"], "status": "POSTED"}
                    )
                    if not po:
                        logger.error("Bill %s linked to invalid or non-POSTED purchase order", bill["number"])
                        TransactionLogBase.log(
                            transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
                            user=user,
                            message=f"Bill {bill['number']} is linked to an invalid or non-POSTED purchase order",
                            state_name="Failed",
                            request=request
                        )
                        return ResponseProvider(
                            message=f"Bill {bill['number']} is linked to an invalid or non-POSTED purchase order",
                            code=400
                        ).bad_request()

            allocations = data.get("allocations", [])
            amount_remaining = amount_disbursed - bank_charges
            amount_used = Decimal("0")
            payment_lines = []
            valid_allocations = []

            # Pre-validate allocations
            if allocations:
                logger.debug("Pre-validating allocations: %s", allocations)
                bill_ids = [alloc.get("bill_id") for alloc in allocations]
                valid_bills = {str(bill["id"]): bill for bill in bills}
                for alloc in allocations:
                    bill_id = alloc.get("bill_id")
                    if str(bill_id) in valid_bills:
                        valid_allocations.append(alloc)
                    else:
                        logger.warning("Skipping invalid bill_id: %s", bill_id)
                logger.debug("Valid allocations: %s", valid_allocations)

            # Manual allocation for valid bills
            if valid_allocations:
                logger.debug("Processing valid allocations: %s", valid_allocations)
                for alloc in valid_allocations:
                    bill_id = alloc.get("bill_id")
                    try:
                        amount_applied = Decimal(str(alloc.get("amount_applied", 0)))
                    except Exception as e:
                        logger.error("Invalid amount_applied format for bill %s: %s", bill_id, str(e))
                        continue
                    if amount_applied <= 0:
                        logger.debug("Skipping allocation with non-positive amount: %s", alloc)
                        continue

                    bill = valid_bills[str(bill_id)]
                    payments = registry.database(
                        model_name="VendorPaymentLine",
                        operation="filter",
                        data={"bill_id": bill_id}
                    )
                    total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
                    outstanding = Decimal(str(bill["total"])) - total_paid

                    if amount_applied > outstanding:
                        logger.warning("Amount applied %s exceeds outstanding %s for bill %s, skipping", amount_applied,
                                       outstanding, bill["number"])
                        continue
                    if amount_applied > amount_remaining:
                        logger.warning("Amount applied %s exceeds remaining payment %s, skipping", amount_applied,
                                       amount_remaining)
                        continue

                    line_data = {
                        "payment_id": payment["id"],
                        "bill_id": bill_id,
                        "bill_date": bill["date"],
                        "bill_amount": str(bill["total"]),
                        "amount_due": str(outstanding),
                        "amount_applied": str(amount_applied)
                    }
                    payment_lines.append(line_data)
                    amount_used += amount_applied
                    amount_remaining -= amount_applied
                    logger.debug("Added payment line: %s", line_data)

            # Automatic allocation if remaining amount
            if amount_remaining > 0:
                logger.debug("Processing automatic allocation with remaining amount: %s", amount_remaining)
                for bill in sorted(bills, key=lambda x: x["due_date"]):  # Oldest first
                    if amount_remaining <= 0:
                        break

                    payments = registry.database(
                        model_name="VendorPaymentLine",
                        operation="filter",
                        data={"bill_id": bill["id"]}
                    )
                    total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
                    outstanding = Decimal(str(bill["total"])) - total_paid

                    if outstanding <= 0:
                        logger.debug("Skipping fully paid bill: %s", bill["id"])
                        continue

                    amount_to_apply = min(outstanding, amount_remaining)
                    line_data = {
                        "payment_id": payment["id"],
                        "bill_id": bill["id"],
                        "bill_date": bill["date"],
                        "bill_amount": str(bill["total"]),
                        "amount_due": str(outstanding),
                        "amount_applied": str(amount_to_apply)
                    }
                    payment_lines.append(line_data)
                    amount_used += amount_to_apply
                    amount_remaining -= amount_to_apply
                    logger.debug("Added automatic payment line: %s", line_data)

            # Create all payment lines first
            for line_data in payment_lines:
                logger.debug("Creating payment line: %s", line_data)
                registry.database(
                    model_name="VendorPaymentLine",
                    operation="create",
                    data=line_data
                )

            # Update bill statuses after all payment lines are created
            processed_bills = set()
            for line_data in payment_lines:
                bill_id = line_data["bill_id"]

                # Skip if we've already processed this bill
                if bill_id in processed_bills:
                    continue
                processed_bills.add(bill_id)

                logger.debug("Updating status for bill_id: %s", bill_id)
                bill = next((b for b in bills if b["id"] == bill_id), None)
                if not bill:
                    logger.error("Bill %s not found during status update", bill_id)
                    continue

                # Fetch all payments for this bill (including the ones just created)
                payments = registry.database(
                    model_name="VendorPaymentLine",
                    operation="filter",
                    data={"bill_id": bill_id}
                )
                total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
                bill_total = Decimal(str(bill["total"]))

                # Determine new status
                if total_paid >= bill_total:
                    new_status = "PAID"
                elif total_paid > 0:
                    new_status = "PARTIALLY_PAID"
                else:
                    new_status = "CANCELLED"  # This shouldn't happen, but just in case

                logger.debug("Updating bill %s to status: %s (total_paid: %s, bill_total: %s)",
                             bill_id, new_status, total_paid, bill_total)

                registry.database(
                    model_name="VendorBill",
                    operation="update",
                    instance_id=bill_id,
                    data={"status": new_status}
                )

            amount_excess = amount_remaining if amount_remaining > 0 else Decimal("0")
            payment_update_data = {
                "amount_used": str(amount_used),
                "amount_excess": str(amount_excess)
            }
            logger.debug("Updating payment with: %s", payment_update_data)
            registry.database(
                model_name="VendorPayment",
                operation="update",
                instance_id=payment["id"],
                data=payment_update_data
            )
            payment.update(payment_update_data)

            payment["lines"] = registry.database(
                model_name="VendorPaymentLine",
                operation="filter",
                data={"payment_id": payment["id"]}
            )
            logger.debug("Payment lines: %s", payment["lines"])

            TransactionLogBase.log(
                transaction_type="VENDOR_PAYMENT_RECORDED",
                user=user,
                message=f"Vendor payment {payment.get('payment_number', payment['id'])} recorded for vendor {data['vendor_id']}",
                state_name="Completed",
                extra={"payment_id": payment["id"], "line_count": len(payment_lines), "amount_used": str(amount_used)},
                request=request
            )
            logger.debug("Vendor payment recorded successfully: %s", payment)

            return ResponseProvider(
                message="Vendor payment recorded and distributed successfully",
                data=payment,
                code=201
            ).success()

    except Exception as e:
        logger.exception("Vendor payment recording failed with exception: %s", str(e))
        TransactionLogBase.log(
            transaction_type="VENDOR_PAYMENT_RECORD_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
            extra={"request_data": data if 'data' in locals() else None}
        )
        return ResponseProvider(message=f"An error occurred while recording vendor payment: {str(e)}",
                                code=500).exception()