# invoice_payments.py (full corrected code)
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from Payments.models import RecordPayment
from quidpath_backend.core.utils.AccountingService import AccountingService
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase, logger


def validate_decimal_precision(value, field_name, max_decimal_places=2):
    """Validate decimal precision for monetary values"""
    try:
        decimal_val = Decimal(str(value))
        # Check if it has more than max_decimal_places
        if decimal_val.as_tuple().exponent < -max_decimal_places:
            raise ValueError(f"{field_name} cannot have more than {max_decimal_places} decimal places")
        return decimal_val
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid {field_name}: {str(e)}")


def validate_payment_allocations(allocations, available_amount, invoices_dict):
    """Validate payment allocations before processing"""
    errors = []
    total_allocated = Decimal("0")

    for i, alloc in enumerate(allocations):
        invoice_id = alloc.get("invoice_id")
        if not invoice_id:
            errors.append(f"Allocation {i + 1}: invoice_id is required")
            continue

        if str(invoice_id) not in invoices_dict:
            errors.append(f"Allocation {i + 1}: Invalid invoice_id {invoice_id}")
            continue

        try:
            amount_applied = Decimal(str(alloc.get("amount_applied", 0)))
            if amount_applied <= 0:
                errors.append(f"Allocation {i + 1}: amount_applied must be greater than 0")
                continue
            total_allocated += amount_applied
        except (InvalidOperation, ValueError):
            errors.append(f"Allocation {i + 1}: Invalid amount_applied format")
            continue

    if total_allocated > available_amount:
        errors.append(
            f"Total allocated amount ({total_allocated}) exceeds available payment amount ({available_amount})")

    return errors


@csrf_exempt
def list_customers(request):
    """
    List all active customers for the user's corporate.

    Returns:
    - 200: List of customers
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

        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )

        serialized_customers = [
            {
                "id": str(customer["id"]),
                "name": (
                    customer["company_name"]
                    if customer["category"] == "company"
                    else f"{customer['first_name']} {customer['last_name']}"
                ),
                "email": customer.get("email", ""),
                "phone": customer.get("phone", ""),
                "billing_address": customer.get("address", ""),
                "city": customer.get("city", ""),
                "state": customer.get("state", ""),
                "zip_code": customer.get("zip_code", ""),
                "country": customer.get("country", "")
            }
            for customer in customers
        ]

        TransactionLogBase.log(
            transaction_type="CUSTOMER_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {len(customers)} customers for corporate {corporate_id}",
            state_name="Success",
            extra={"customer_count": len(customers)},
            request=request
        )

        return ResponseProvider(
            data={"customers": serialized_customers, "total": len(customers)},
            message="Customers retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="CUSTOMER_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving customers", code=500).exception()


@csrf_exempt
def list_unpaid_invoices(request):
    """
    List all unpaid, partially paid, or overdue invoices for a selected customer.

    Expected data:
    - customer_id: UUID of the customer

    Returns:
    - 200: List of unpaid/partially paid/overdue invoices with outstanding amounts
    - 400: Bad request (missing customer ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Customer not found
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    customer_id = data.get("customer_id")
    if not customer_id:
        return ResponseProvider(message="Customer ID is required", code=400).bad_request()

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

        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": customer_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not customers:
            return ResponseProvider(message="Customer not found or inactive", code=404).bad_request()

        invoices = registry.database(
            model_name="Invoices",
            operation="filter",
            data={"customer_id": customer_id, "corporate_id": corporate_id,
                  "status__in": ["ISSUED", "PARTIALLY_PAID", "OVERDUE"]}
        )

        serialized_invoices = []
        today = date.today()
        for inv in invoices:
            payments = registry.database(
                model_name="RecordPaymentLine",
                operation="filter",
                data={"invoice_id": inv["id"]}
            )
            total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
            total = Decimal(str(inv.get("total", 0)))
            outstanding_amount = total - total_paid

            # Determine new status
            new_status = inv["status"]
            if outstanding_amount <= 0:
                new_status = "PAID"
            else:
                due_date_value = inv.get("due_date")

                if isinstance(due_date_value, str):
                    due_date = date.fromisoformat(due_date_value)
                elif isinstance(due_date_value, (date, datetime)):
                    due_date = due_date_value.date() if isinstance(due_date_value, datetime) else due_date_value
                else:
                    continue  # skip invoice if due_date is invalid

                if due_date < today and outstanding_amount > 0:
                    new_status = "OVERDUE"
                elif total_paid > 0:
                    new_status = "PARTIALLY_PAID"
                else:
                    new_status = "ISSUED"

            # Update invoice status if changed
            if new_status != inv["status"]:
                registry.database(
                    model_name="Invoices",
                    operation="update",
                    instance_id=inv["id"],
                    data={"status": new_status}
                )

            # Include only invoices with outstanding amounts
            if outstanding_amount > 0:
                serialized_invoices.append({
                    "id": str(inv["id"]),
                    "number": inv["number"],
                    "date": inv["date"],
                    "due_date": inv["due_date"],
                    "total": float(total),
                    "outstanding_amount": float(outstanding_amount),
                    "status": new_status
                })

        # Sort invoices by due_date (ascending)
        serialized_invoices = sorted(serialized_invoices, key=lambda x: x["due_date"])

        TransactionLogBase.log(
            transaction_type="UNPAID_INVOICES_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {len(serialized_invoices)} unpaid invoices for customer {customer_id}",
            state_name="Success",
            extra={"customer_id": customer_id, "invoice_count": len(serialized_invoices)},
            request=request
        )

        return ResponseProvider(
            data={"invoices": serialized_invoices, "total": len(serialized_invoices)},
            message="Unpaid invoices retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="UNPAID_INVOICES_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving unpaid invoices", code=500).exception()


@csrf_exempt
def record_payment(request):
    """
    Record a payment for a customer and distribute it across unpaid invoices.
    Pre-validates invoice IDs in allocations to skip invalid ones and proceed with payment.

    Expected data:
    - customer_id: UUID of the customer
    - amount_received: Decimal amount of the payment
    - payment_date: Date of the payment
    - payment_method: One of the allowed payment methods (cash, card, bank_transfer, paypal, mpesa, cheque, other)
    - account_id: UUID of the bank account
    - payment_number: Optional payment reference number
    - reference_number: Optional additional reference
    - notes: Optional notes
    - bank_charges: Optional bank charges (default 0)
    - allocations: Optional list of {invoice_id, amount_applied} to specify manual distribution

    Returns:
    - 201: Payment recorded and distributed successfully
    - 400: Bad request (missing required fields, invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Customer or account not found
    - 500: Internal server error
    """
    logger.debug("Received request to /record/: %s", request.body)
    try:
        data, metadata = get_clean_data(request)
        logger.debug("Parsed data: %s, metadata: %s", data, metadata)
    except Exception as e:
        logger.exception("Failed to parse request data: %s", str(e))
        TransactionLogBase.log(
            transaction_type="PAYMENT_RECORD_FAILED",
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
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    logger.debug("User ID: %s", user_id)
    if not user_id:
        logger.error("User ID not found")
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()
        logger.debug("Initialized ServiceRegistry")
        accounting_service = AccountingService(registry)

        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        logger.debug("Corporate users: %s", corporate_users)
        if not corporate_users:
            logger.error("No corporate association for user_id: %s", user_id)
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        logger.debug("Corporate ID: %s", corporate_id)
        if not corporate_id:
            logger.error("Corporate ID not found")
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        required_fields = ["customer_id", "amount_received", "payment_date", "payment_method", "account_id"]
        for field in required_fields:
            if field not in data:
                logger.error("Missing required field: %s", field)
                TransactionLogBase.log(
                    transaction_type="PAYMENT_RECORD_FAILED",
                    user=user,
                    message=f"{field.replace('_', ' ').title()} is required",
                    state_name="Failed",
                    request=request
                )
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required",
                                        code=400).bad_request()

        logger.debug("Fetching customers for customer_id: %s, corporate_id: %s", data["customer_id"], corporate_id)
        customers = registry.database(
            model_name="Customer",
            operation="filter",
            data={"id": data["customer_id"], "corporate_id": corporate_id, "is_active": True}
        )
        logger.debug("Customers: %s", customers)
        if not customers:
            logger.error("Customer not found or inactive: %s", data["customer_id"])
            return ResponseProvider(message="Customer not found or inactive", code=404).bad_request()

        logger.debug("Fetching accounts for account_id: %s, corporate_id: %s", data["account_id"], corporate_id)
        accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": data["account_id"], "corporate_id": corporate_id, "is_active": True}
        )
        logger.debug("Accounts: %s", accounts)
        if not accounts:
            logger.error("Bank account not found or inactive: %s", data["account_id"])
            return ResponseProvider(message="Bank account not found or inactive", code=404).bad_request()

        bank_account = accounts[0]

        # Get or create ledger account for this bank account (same logic as above)
        ledger_account_id = bank_account.get("ledger_account_id")
        if not ledger_account_id:
            logger.debug("Creating ledger account for bank_account: %s", bank_account["id"])
            # Get ASSET account type
            type_data = registry.database(
                model_name="AccountType",
                operation="filter",
                data={"name": "ASSET"}
            )
            if not type_data:
                new_type = registry.database(
                    model_name="AccountType",
                    operation="create",
                    data={"name": "ASSET", "description": "Asset accounts"}
                )
                type_id = new_type["id"]
            else:
                type_id = type_data[0]["id"]

            # Find next available code for asset accounts (starting from 1100)
            asset_accounts = registry.database(
                model_name="Account",
                operation="filter",
                data={"corporate_id": corporate_id, "account_type_id": type_id}
            )
            codes = []
            for acc in asset_accounts:
                try:
                    codes.append(int(acc["code"]))
                except ValueError:
                    pass
            max_code = max(codes) if codes else 1099
            new_code = str(max_code + 1)

            new_account_data = {
                "corporate_id": corporate_id,
                "code": new_code,
                "name": f"{bank_account['bank_name']} - {bank_account['account_name']}",
                "account_type_id": type_id,
                "is_active": True,
                "description": f"Ledger account for bank account {bank_account['account_number']}"
            }
            new_account = registry.database(
                model_name="Account",
                operation="create",
                data=new_account_data
            )
            ledger_account_id = new_account["id"]

            # Update bank_account with ledger_account_id
            registry.database(
                model_name="BankAccount",
                operation="update",
                instance_id=bank_account["id"],
                data={"ledger_account_id": ledger_account_id}
            )
            logger.debug("Created and linked ledger account: %s", ledger_account_id)

        # ENHANCED: Use validation function with proper error handling
        try:
            amount_received = validate_decimal_precision(data["amount_received"], "Amount received")
        except ValueError as e:
            logger.error("Amount validation error: %s", str(e))
            TransactionLogBase.log(
                transaction_type="PAYMENT_RECORD_FAILED",
                user=user,
                message=str(e),
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message=str(e), code=400).bad_request()
        if amount_received <= 0:
            logger.error("Amount received must be greater than 0: %s", amount_received)
            return ResponseProvider(message="Amount received must be greater than 0", code=400).bad_request()

        try:
            bank_charges = validate_decimal_precision(data.get("bank_charges", 0), "Bank charges")
        except ValueError as e:
            logger.error("Bank charges validation error: %s", str(e))
            TransactionLogBase.log(
                transaction_type="PAYMENT_RECORD_FAILED",
                user=user,
                message=str(e),
                state_name="Failed",
                request=request
            )
            return ResponseProvider(message=str(e), code=400).bad_request()
        if bank_charges < 0:
            logger.error("Bank charges cannot be negative: %s", bank_charges)
            return ResponseProvider(message="Bank charges cannot be negative", code=400).bad_request()

        payment_method = data["payment_method"]
        valid_methods = [choice[0] for choice in RecordPayment.METHOD_TYPES]
        if payment_method not in valid_methods:
            logger.error("Invalid payment method: %s, valid methods: %s", payment_method, valid_methods)
            return ResponseProvider(message=f"Invalid payment method. Must be one of: {', '.join(valid_methods)}",
                                    code=400).bad_request()

        with transaction.atomic():
            payment_data = {
                "customer_id": data["customer_id"],
                "corporate_id": corporate_id,
                "amount_received": str(amount_received),
                "bank_charges": str(bank_charges),
                "payment_date": data["payment_date"],
                "payment_method": payment_method,
                "account_id": ledger_account_id,  # Use ledger_account_id here
                "payment_number": data.get("payment_number", ""),
                "reference_number": data.get("reference_number", ""),
                "notes": data.get("notes", ""),
                "amount_used": "0",
                "amount_refunded": "0",
                "amount_excess": "0"
            }
            logger.debug("Creating payment with data: %s", payment_data)
            payment = registry.database(
                model_name="RecordPayment",
                operation="create",
                data=payment_data
            )
            logger.debug("Payment created: %s", payment)

            logger.debug("Fetching invoices for customer_id: %s, corporate_id: %s", data["customer_id"], corporate_id)
            invoices = registry.database(
                model_name="Invoices",
                operation="filter",
                data={"customer_id": data["customer_id"], "corporate_id": corporate_id,
                      "status__in": ["ISSUED", "PARTIALLY_PAID", "OVERDUE"]}
            )
            logger.debug("Invoices: %s", invoices)

            allocations = data.get("allocations", [])
            amount_remaining = amount_received - bank_charges
            amount_used = Decimal("0")
            payment_lines = []
            valid_allocations = []
            manually_processed = set()  # ADDED: Track manually processed invoices

            # ADDED: Validate allocations before processing
            if allocations:
                invoices_dict = {str(inv["id"]): inv for inv in invoices}
                validation_errors = validate_payment_allocations(
                    allocations,
                    amount_remaining,
                    invoices_dict
                )
                if validation_errors:
                    error_msg = "; ".join(validation_errors)
                    logger.error("Allocation validation failed: %s", error_msg)
                    TransactionLogBase.log(
                        transaction_type="PAYMENT_RECORD_FAILED",
                        user=user,
                        message=f"Allocation validation failed: {error_msg}",
                        state_name="Failed",
                        request=request
                    )
                    return ResponseProvider(message=f"Allocation validation failed: {error_msg}",
                                            code=400).bad_request()

            # Pre-validate allocations
            if allocations:
                logger.debug("Pre-validating allocations: %s", allocations)
                valid_invoices = {str(inv["id"]): inv for inv in invoices}
                for alloc in allocations:
                    invoice_id = alloc.get("invoice_id")
                    if str(invoice_id) in valid_invoices:
                        valid_allocations.append(alloc)
                    else:
                        logger.warning("Skipping invalid invoice_id: %s", invoice_id)
                logger.debug("Valid allocations: %s", valid_allocations)

            # Manual allocation for valid invoices
            if valid_allocations:
                logger.debug("Processing valid allocations: %s", valid_allocations)
                for alloc in valid_allocations:
                    invoice_id = alloc.get("invoice_id")
                    try:
                        amount_applied = Decimal(str(alloc.get("amount_applied", 0)))
                    except Exception as e:
                        logger.error("Invalid amount_applied format for invoice %s: %s", invoice_id, str(e))
                        continue
                    if amount_applied <= 0:
                        logger.debug("Skipping allocation with non-positive amount: %s", alloc)
                        continue

                    invoice = valid_invoices[str(invoice_id)]
                    payments = registry.database(
                        model_name="RecordPaymentLine",
                        operation="filter",
                        data={"invoice_id": invoice_id}
                    )
                    total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
                    outstanding = Decimal(str(invoice["total"])) - total_paid

                    if amount_applied > outstanding:
                        logger.warning("Amount applied %s exceeds outstanding %s for invoice %s, skipping",
                                       amount_applied, outstanding, invoice["number"])
                        continue

                    if amount_applied > amount_remaining:
                        logger.warning("Amount applied %s exceeds remaining payment %s, skipping", amount_applied,
                                       amount_remaining)
                        continue

                    line_data = {
                        "payment_id": payment["id"],
                        "invoice_id": invoice_id,
                        "invoice_date": invoice["date"],
                        "invoice_amount": str(invoice["total"]),
                        "amount_due": str(outstanding),
                        "amount_applied": str(amount_applied)
                    }
                    payment_lines.append(line_data)
                    amount_used += amount_applied
                    amount_remaining -= amount_applied
                    manually_processed.add(str(invoice_id))  # ADDED: Track processed invoices
                    logger.debug("Added payment line: %s", line_data)

            # FIXED: Automatic allocation excludes manually processed invoices
            if amount_remaining > 0:
                logger.debug("Processing automatic allocation with remaining amount: %s", amount_remaining)
                for invoice in sorted(invoices, key=lambda x: x["due_date"]):  # Oldest first
                    if amount_remaining <= 0:
                        break

                    # ADDED: Skip if already manually processed
                    if str(invoice["id"]) in manually_processed:
                        logger.debug("Skipping manually processed invoice: %s", invoice["id"])
                        continue

                    payments = registry.database(
                        model_name="RecordPaymentLine",
                        operation="filter",
                        data={"invoice_id": invoice["id"]}
                    )
                    total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
                    outstanding = Decimal(str(invoice["total"])) - total_paid

                    if outstanding <= 0:
                        logger.debug("Skipping fully paid invoice: %s", invoice["id"])
                        continue

                    amount_to_apply = min(outstanding, amount_remaining)
                    line_data = {
                        "payment_id": payment["id"],
                        "invoice_id": invoice["id"],
                        "invoice_date": invoice["date"],
                        "invoice_amount": str(invoice["total"]),
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
                    model_name="RecordPaymentLine",
                    operation="create",
                    data=line_data
                )

            # Update invoice statuses after all payment lines are created
            processed_invoices = set()
            today = date.today()
            for line_data in payment_lines:
                invoice_id = line_data["invoice_id"]

                # Skip if we've already processed this invoice
                if invoice_id in processed_invoices:
                    continue
                processed_invoices.add(invoice_id)

                logger.debug("Updating status for invoice_id: %s", invoice_id)
                invoice = next((inv for inv in invoices if inv["id"] == invoice_id), None)
                if not invoice:
                    logger.error("Invoice %s not found during status update", invoice_id)
                    continue

                # Fetch all payments for this invoice (including the ones just created)
                payments = registry.database(
                    model_name="RecordPaymentLine",
                    operation="filter",
                    data={"invoice_id": invoice_id}
                )
                total_paid = sum(Decimal(str(p["amount_applied"])) for p in payments)
                invoice_total = Decimal(str(invoice["total"]))

                # Determine new status
                due_date = date.fromisoformat(invoice["due_date"])
                if total_paid >= invoice_total:
                    new_status = "PAID"
                elif total_paid > 0:
                    new_status = "PARTIALLY_PAID"
                else:
                    new_status = "ISSUED" if due_date >= today else "OVERDUE"

                logger.debug("Updating invoice %s to status: %s (total_paid: %s, invoice_total: %s)",
                             invoice_id, new_status, total_paid, invoice_total)

                registry.database(
                    model_name="Invoices",
                    operation="update",
                    instance_id=invoice_id,
                    data={"status": new_status}
                )

            amount_excess = amount_remaining if amount_remaining > 0 else Decimal("0")
            payment_update_data = {
                "amount_used": str(amount_used),
                "amount_excess": str(amount_excess)
            }
            logger.debug("Updating payment with: %s", payment_update_data)
            registry.database(
                model_name="RecordPayment",
                operation="update",
                instance_id=payment["id"],
                data=payment_update_data
            )
            payment.update(payment_update_data)

            # ENHANCED: Better transaction handling with explicit rollback
            try:
                # Create journal entry for the payment
                journal_entry = accounting_service.create_payment_journal_entry(
                    payment["id"], user, payment_model="RecordPayment"
                )
                registry.database(
                    model_name="RecordPayment",
                    operation="update",
                    instance_id=payment["id"],
                    data={"journal_entry_id": journal_entry["id"], "is_posted": True}
                )
                payment["journal_entry_id"] = journal_entry["id"]
                payment["is_posted"] = True
                logger.info("Journal entry created successfully: %s", journal_entry["id"])

            except Exception as journal_error:
                logger.error("Failed to create journal entry for payment %s: %s",
                             payment["id"], str(journal_error))
                TransactionLogBase.log(
                    transaction_type="PAYMENT_JOURNAL_FAILED",
                    user=user,
                    message=str(journal_error),
                    state_name="Failed",
                    request=request
                )
                raise

                # Log success after successful transaction
            TransactionLogBase.log(
                transaction_type="PAYMENT_RECORD_SUCCESS",
                user=user,
                message=f"Payment recorded successfully for customer {data['customer_id']}",
                state_name="Success",
                extra={
                    "payment_id": payment["id"],
                    "amount_received": str(amount_received),
                    "amount_used": str(amount_used),
                    "amount_excess": str(amount_excess),
                    "invoice_count": len(payment_lines)
                },
                request=request
            )

            # Serialize payment response
            serialized_payment = {
                "id": str(payment["id"]),
                "customer_id": str(payment["customer_id"]),
                "amount_received": float(amount_received),
                "bank_charges": float(bank_charges),
                "payment_date": payment["payment_date"],
                "payment_method": payment["payment_method"],
                "account_id": str(payment["account_id"]),
                "payment_number": payment["payment_number"],
                "reference_number": payment["reference_number"],
                "notes": payment["notes"],
                "amount_used": float(amount_used),
                "amount_excess": float(amount_excess),
                "lines": [
                    {
                        "invoice_id": str(line["invoice_id"]),
                        "amount_applied": float(Decimal(str(line["amount_applied"])))
                    } for line in payment_lines
                ]
            }

            return ResponseProvider(
                data={"payment": serialized_payment},
                message="Payment recorded and distributed successfully",
                code=201
            ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PAYMENT_RECORD_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while recording payment", code=500).exception()