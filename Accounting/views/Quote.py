from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from collections import Counter

from quidpath_backend import settings
from quidpath_backend.core.utils.DocsEmail import DocumentNotificationHandler
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def save_quotation_draft(request):
    """
    Save a new quotation as draft for the user's corporate, including its lines.

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
    - lines: List of dictionaries, each containing fields for QuotationLine (e.g., description, quantity, etc.)

    Returns:
    - 201: Quotation draft saved successfully with lines
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Customer, salesperson, or taxable not found
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
            data={"customuser_ptr_id": user_id, "is_active": True}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        required_fields = ["customer", "date", "number", "valid_until", "ship_date", "ship_via", "terms", "fob"]
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

        # Validate salesperson
        salespersons = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"id": data["salesperson"], "corporate_id": corporate_id, "is_active": True}
        )
        if not salespersons:
            return ResponseProvider(message="Salesperson not found or inactive for this corporate",
                                    code=404).bad_request()

        # Create quotation as draft (status defaults to DRAFT in model)
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
        }
        quotation = registry.database(
            model_name="Quotation",
            operation="create",
            data=quotation_data
        )

        # Create quotation lines
        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable",
                                    "grand_total", "tax_amount", "tax_total", "sub_total", "total", "total_discount"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Quotation line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            # Validate taxable
            taxable = line_data.get("taxable")
            taxable_id = None
            if taxable:
                # Handle case where frontend sends full object
                if isinstance(taxable, dict):
                    taxable_id = taxable.get("id")
                else:
                    taxable_id = taxable

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

            # Prepare line data for creation
            line_data_for_creation = {
                "quotation_id": quotation["id"],
                "description": line_data["description"],
                "quantity": line_data["quantity"],
                "unit_price": line_data["unit_price"],
                "amount": line_data["amount"],
                "discount": line_data["discount"],
                "taxable_id": taxable_id,
                "grand_total": line_data["grand_total"],
                "tax_amount": line_data["tax_amount"],
                "tax_total": line_data["tax_total"],
                "sub_total": line_data["sub_total"],
                "total": line_data["total"],
                "total_discount": line_data["total_discount"],
            }
            registry.database(
                model_name="QuotationLine",
                operation="create",
                data=line_data_for_creation
            )

        # Log creation
        TransactionLogBase.log(
            transaction_type="QUOTATION_DRAFT_SAVED",
            user=user,
            message=f"Quotation draft {quotation['number']} saved for corporate {corporate_id}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for the response
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
def create_and_send_quotation(request):
    """
    Create a new quotation for the user's corporate, including its lines, set status to SENT, and send email to customer.

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
    - lines: List of dictionaries, each containing fields for QuotationLine (e.g., description, quantity, etc.)

    Returns:
    - 201: Quotation created and sent successfully with lines
    - 400: Bad request (missing required fields or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Customer, salesperson, or taxable not found
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
            data={"customuser_ptr_id": user_id, "is_active": True}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        required_fields = ["customer", "date", "number", "valid_until", "ship_date", "ship_via", "terms", "fob"]
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

        # Fetch corporate for email
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id}
        )
        if not corporates:
            return ResponseProvider(message="Corporate not found", code=404).bad_request()
        corporate = corporates[0]

        # Create quotation with status SENT
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
            "status": "SENT",
        }
        quotation = registry.database(
            model_name="Quotation",
            operation="create",
            data=quotation_data
        )

        # Create quotation lines
        lines = data.get("lines", [])
        for line_data in lines:
            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount", "taxable",
                                    "grand_total", "tax_amount", "tax_total", "sub_total", "total", "total_discount"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Quotation line field {field.replace('_', ' ').title()} is required",
                        code=400).bad_request()

            # Validate taxable
            taxable = line_data.get("taxable")
            taxable_id = None
            if taxable:
                # Handle case where frontend sends full object
                if isinstance(taxable, dict):
                    taxable_id = taxable.get("id")
                else:
                    taxable_id = taxable

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

            # Prepare line data for creation
            line_data_for_creation = {
                "quotation_id": quotation["id"],
                "description": line_data["description"],
                "quantity": line_data["quantity"],
                "unit_price": line_data["unit_price"],
                "amount": line_data["amount"],
                "discount": line_data["discount"],
                "taxable_id": taxable_id,
                "grand_total": line_data["grand_total"],
                "tax_amount": line_data["tax_amount"],
                "tax_total": line_data["tax_total"],
                "sub_total": line_data["sub_total"],
                "total": line_data["total"],
                "total_discount": line_data["total_discount"],
            }
            registry.database(
                model_name="QuotationLine",
                operation="create",
                data=line_data_for_creation
            )

        # Log creation
        TransactionLogBase.log(
            transaction_type="QUOTATION_CREATED_AND_SENT",
            user=user,
            message=f"Quotation {quotation['number']} created and sent for corporate {corporate_id}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "line_count": len(lines)},
            request=request
        )

        # Fetch lines for the response and email
        lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        quotation["lines"] = lines

        # Send email to customer using DocumentNotificationHandler
        to_email = customer.get("email")
        if not to_email:
            TransactionLogBase.log(
                transaction_type="QUOTATION_SEND_FAILED",
                user=user,
                message="Customer has no email",
                state_name="Failed",
                request=request
            )
        else:
            subject = f"Quotation {quotation['number']} from {corporate['name']}"
            message = f"""
            <html>
            <body>
            <p>Dear {customer.get('name', 'Customer')},</p>
            <p>We are pleased to send you the following quotation:</p>
            <p><strong>Quotation Number:</strong> {quotation['number']}</p>
            <p><strong>Date:</strong> {quotation['date']}</p>
            <p><strong>Valid Until:</strong> {quotation['valid_until']}</p>
            <p><strong>Ship Date:</strong> {quotation['ship_date']}</p>
            <p><strong>Ship Via:</strong> {quotation['ship_via']}</p>
            <p><strong>Terms:</strong> {quotation['terms']}</p>
            <p><strong>FOB:</strong> {quotation['fob']}</p>
            <p><strong>Comments:</strong> {quotation['comments']}</p>
            <p><strong>Terms and Conditions:</strong> {quotation['T_and_C']}</p>
            <h3>Lines:</h3>
            <table border="1">
            <tr><th>Description</th><th>Quantity</th><th>Unit Price</th><th>Amount</th><th>Discount</th><th>Taxable</th><th>Grand Total</th></tr>
            """
            for line in lines:
                message += f"""
                <tr>
                <td>{line['description']}</td>
                <td>{line['quantity']}</td>
                <td>{line['unit_price']}</td>
                <td>{line['amount']}</td>
                <td>{line['discount']}</td>
                <td>{line.get('taxable_id', '')}</td>
                <td>{line['grand_total']}</td>
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
            send_result = notification_handler.send_document_notification(notifications, trans=None, attachment=None,
                                                                          cc=None)
            if send_result != "success":
                TransactionLogBase.log(
                    transaction_type="QUOTATION_SEND_FAILED",
                    user=user,
                    message="Failed to send email",
                    state_name="Failed",
                    request=request
                )

        return ResponseProvider(
            message="Quotation created and sent successfully",
            data=quotation,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_CREATION_AND_SEND_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating and sending quotation", code=500).exception()



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
    Update an existing quotation for the user's corporate, including its lines, and set status to DRAFT or SENT.
    """
    from decimal import Decimal, InvalidOperation
    import json, ast, re

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

    def get_tax_rate_value(tax_rate):
        """Extract tax rate percentage from TaxRate label (e.g., 'VAT (16%)' -> 0.16)."""
        if not tax_rate or not tax_rate.get("label"):
            TransactionLogBase.log(
                transaction_type="QUOTATION_TAX_RATE_WARNING",
                user=user,
                message="Tax rate label missing or empty",
                state_name="Warning",
                request=request
            )
            return Decimal("0")
        label = tax_rate["label"]
        match = re.search(r'\((\d+)%\)', label)
        if match:
            try:
                rate = Decimal(match.group(1)) / Decimal("100")
                return rate
            except (InvalidOperation, ValueError):
                TransactionLogBase.log(
                    transaction_type="QUOTATION_TAX_RATE_ERROR",
                    user=user,
                    message=f"Invalid tax rate label format: {label}",
                    state_name="Failed",
                    request=request
                )
                return Decimal("0")
        TransactionLogBase.log(
            transaction_type="QUOTATION_TAX_RATE_WARNING",
            user=user,
            message=f"Could not parse tax rate from label: {label}",
            state_name="Warning",
            request=request
        )
        return Decimal("0")

    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Corporate lookup
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

        # Required fields
        required_fields = ["id", "customer", "date", "number", "valid_until", "ship_date", "ship_via", "terms", "fob"]
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
        customer = customers[0]

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
        if normalized_status not in {"DRAFT", "SENT"}:
            normalized_status = "DRAFT"

        # Fetch corporate for email if sending
        corporate = None
        if normalized_status == "SENT":
            corporates = registry.database(
                model_name="Corporate",
                operation="filter",
                data={"id": corporate_id}
            )
            if not corporates:
                return ResponseProvider(message="Corporate not found", code=404).bad_request()
            corporate = corporates[0]

        # Update quotation
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
        }
        quotation = registry.database(
            model_name="Quotation",
            operation="update",
            instance_id=quotation_id,
            data=quotation_data
        )

        # ----- Lines handling -----
        submitted_lines = data.get("lines", []) or []
        existing_lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        existing_line_ids = {line["id"] for line in existing_lines if line.get("id")}
        submitted_line_ids = {line.get("id") for line in submitted_lines if line.get("id")}

        # Delete omitted lines
        for line in existing_lines:
            if line["id"] not in submitted_line_ids:
                registry.database(
                    model_name="QuotationLine",
                    operation="delete",
                    instance_id=line["id"]
                )

        # Create or update lines
        for line_data in submitted_lines:
            raw_taxable = line_data.get("taxable_id") or line_data.get("taxable")
            taxable_id = normalize_taxable_id(raw_taxable)

            required_line_fields = ["description", "quantity", "unit_price", "amount", "discount",
                                    "grand_total", "tax_amount", "tax_total", "sub_total", "total", "total_discount"]
            for field in required_line_fields:
                if field not in line_data:
                    return ResponseProvider(
                        message=f"Quotation line field {field.replace('_', ' ').title()} is required",
                        code=400
                    ).bad_request()

            tax_rate_value = Decimal("0")
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
            client_tax_amount = to_decimal(line_data["tax_amount"])

            line_subtotal = qty * unit_price
            line_taxable_amount = line_subtotal - discount
            expected_tax_amount = line_taxable_amount * tax_rate_value

            # Log for debugging
            TransactionLogBase.log(
                transaction_type="QUOTATION_LINE_DEBUG",
                user=user,
                message=f"Line '{line_data.get('description', '')}': client_tax_amount={client_tax_amount}, expected_tax_amount={expected_tax_amount}, tax_rate_value={tax_rate_value}, taxable_id={taxable_id}",
                state_name="Debug",
                request=request
            )

            line_payload = {
                "quotation_id": quotation["id"],
                "description": line_data["description"],
                "quantity": float(qty),
                "unit_price": float(unit_price),
                "amount": float(to_decimal(line_data["amount"])),
                "discount": float(discount),
                "taxable_id": taxable_id,
                "grand_total": float(to_decimal(line_data["grand_total"])),
                "tax_amount": float(client_tax_amount),
                "tax_total": float(to_decimal(line_data["tax_total"])),
                "sub_total": float(to_decimal(line_data["sub_total"])),
                "total": float(to_decimal(line_data["total"])),
                "total_discount": float(to_decimal(line_data["total_discount"])),
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
            transaction_type="QUOTATION_UPDATED",
            user=user,
            message=f"Quotation {quotation['number']} updated for corporate {corporate_id} with status {quotation['status']}",
            state_name="Completed",
            extra={"quotation_id": quotation["id"], "line_count": len(submitted_lines)},
            request=request
        )

        # Send email if SENT
        if quotation["status"] == "SENT":
            to_email = customer.get("email")
            if not to_email:
                TransactionLogBase.log(
                    transaction_type="QUOTATION_SEND_FAILED",
                    user=user,
                    message="Customer has no email",
                    state_name="Failed",
                    request=request
                )
            else:
                email_lines = registry.database(
                    model_name="QuotationLine",
                    operation="filter",
                    data={"quotation_id": quotation["id"]}
                )

                def tax_display(taxable_id_value):
                    if not taxable_id_value:
                        return ""
                    tr = registry.database(
                        model_name="TaxRate",
                        operation="filter",
                        data={"id": taxable_id_value}
                    )
                    return tr[0].get("label", "") if tr else ""

                subject = f"Updated Quotation {quotation['number']} from {corporate['name']}"
                message = f"""
                <html><body>
                <p>Dear {customer.get('name') or customer.get('first_name') or 'Customer'},</p>
                <p>We have updated the following quotation:</p>
                <p><strong>Quotation Number:</strong> {quotation['number']}</p>
                <p><strong>Date:</strong> {quotation['date']}</p>
                <p><strong>Valid Until:</strong> {quotation['valid_until']}</p>
                <p><strong>Ship Date:</strong> {quotation['ship_date']}</p>
                <p><strong>Ship Via:</strong> {quotation['ship_via']}</p>
                <p><strong>Terms:</strong> {quotation['terms']}</p>
                <p><strong>FOB:</strong> {quotation['fob']}</p>
                <p><strong>Comments:</strong> {quotation.get('comments','')}</p>
                <p><strong>Terms and Conditions:</strong> {quotation.get('T_and_C','')}</p>
                <h3>Lines:</h3>
                <table border="1" cellpadding="6" cellspacing="0">
                <tr>
                    <th>Description</th><th>Quantity</th><th>Unit Price</th>
                    <th>Amount</th><th>Discount</th><th>Taxable</th><th>Grand Total</th>
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
                      <td>{l.get('grand_total','')}</td>
                    </tr>
                    """
                message += f"""
                </table>
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
                        transaction_type="QUOTATION_SEND_FAILED",
                        user=user,
                        message="Failed to send email",
                        state_name="Failed",
                        request=request
                    )

        # Fetch fresh lines for response
        db_lines = registry.database(
            model_name="QuotationLine",
            operation="filter",
            data={"quotation_id": quotation["id"]}
        )
        quotation["lines"] = db_lines

        quotation["total"] = float(sum(
            to_decimal(line.get("total", 0) or 0) for line in db_lines
        ))

        return ResponseProvider(message="Quotation updated successfully", data=quotation, code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="QUOTATION_UPDATE_FAILED",
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