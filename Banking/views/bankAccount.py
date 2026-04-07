import traceback

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.email import NotificationServiceHandler
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.corporate_helper import get_corporate_id_from_data


@csrf_exempt
def add_bank_account(request):
    """
    Create a new bank account for a corporate entity.

    Expected data:
    - corporate: UUID of the corporate entity
    - bank_name: Name of the bank
    - account_number: Bank account number
    - account_name: Name on the account
    - currency: Account currency
    - is_default: Whether this is the default account (optional)

    Returns:
    - 201: Bank account created successfully
    - 400: Bad request (missing required fields)
    - 404: Corporate not found
    - 409: Duplicate account
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        registry = ServiceRegistry()

        # Debug logging
        print(f"[DEBUG] Received data: {data}")
        print(f"[DEBUG] Metadata: {metadata}")

        # Extract corporate_id using helper (checks both 'corporate' and 'corporate_id')
        corporate_id = get_corporate_id_from_data(data)
        
        if not corporate_id:
            error_msg = "Corporate ID is required"
            print(f"[DEBUG] {error_msg}")
            return ResponseProvider(
                message=error_msg, code=400
            ).bad_request()

        # Validate other required fields
        required_items = [
            "bank_name",
            "account_number",
            "account_name",
            "currency",
        ]
        missing_fields = [item for item in required_items if item not in data]
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print(f"[DEBUG] {error_msg}")
            return ResponseProvider(
                message=error_msg, code=400
            ).bad_request()

        # Check if corporate exists and is active
        corporates = registry.database(
            model_name="Corporate",
            operation="filter",
            data={"id": corporate_id, "is_active": True},
        )

        if not corporates or len(corporates) == 0:
            return ResponseProvider(
                message="Corporate not found or inactive", code=404
            ).bad_request()

        corporate = corporates[0]

        # Check for existing bank account with same account number and corporate
        existing_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={
                "corporate": corporate_id,
                "account_number": data.get("account_number"),
                "bank_name": data.get("bank_name"),
                "is_active": True,
            },
        )

        if existing_accounts and len(existing_accounts) > 0:
            return ResponseProvider(
                message="Bank account with the same account number and bank already exists for this corporate.",
                code=409,
            ).bad_request()

        # Create bank account - Try corporate_id field name
        new_account = registry.database(
            model_name="BankAccount",
            operation="create",
            data={
                "corporate_id": corporate_id,  # Use corporate_id instead of corporate
                "bank_name": data.get("bank_name"),
                "account_name": data.get("account_name"),
                "account_number": data.get("account_number"),
                "currency": data.get("currency"),
                "is_default": data.get("is_default", False),
                "is_active": True,
            },
        )

        # Prepare email notification
        destination_email = corporate.get("email")
        notif_response = {"status": "skipped", "message": "No email on file"}

        if destination_email:
            notification_payload = [
                {
                    "message_type": "EMAIL",
                    "organisation_id": str(corporate["id"]),
                    "destination": destination_email,
                    "message": f"""
                    Dear {corporate.get("name", "Corporate")},
                    <br/><br/>
                    A new bank account has been successfully added:
                    <ul>
                        <li><strong>Bank Name:</strong> {new_account["bank_name"]}</li>
                        <li><strong>Account Name:</strong> {new_account["account_name"]}</li>
                        <li><strong>Account Number:</strong> {new_account["account_number"]}</li>
                        <li><strong>Currency:</strong> {new_account["currency"]}</li>
                    </ul>
                    <br/>
                    Regards,<br/>ERP Team
                """,
                }
            ]
            try:
                notif_response = NotificationServiceHandler().send_notification(
                    notification_payload
                )
            except Exception as email_error:
                notif_response = {"status": "failed", "message": str(email_error)}

        # Log transaction
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_CREATED",
            user=metadata.get("user"),
            message=f"Bank account created for corporate {corporate.get('name', corporate_id)}",
            state_name="Completed",
            extra={"bank_account_id": str(new_account["id"])},
            notification_resp=notif_response,
            request=request,
        )

        # Handle notification response safely - works with any return type
        try:
            if isinstance(notif_response, dict):
                notification_status = notif_response.get("status", "unknown")
            elif isinstance(notif_response, str):
                notification_status = notif_response
            else:
                notification_status = (
                    str(notif_response) if notif_response else "unknown"
                )
        except:
            notification_status = "unknown"

        return ResponseProvider(
            message="Bank account created successfully",
            data={
                "account": new_account,
                "corporate_id": corporate_id,
                "notification_status": notification_status,
            },
            code=201,
        ).success()

    except ValueError as ve:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_CREATION_VALIDATION_ERROR",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Validation error: {str(ve)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"Validation error: {str(ve)}", code=400
        ).bad_request()

    except Exception as e:
        error_trace = traceback.format_exc()
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_CREATION_FAILED",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=error_trace,
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while creating bank account", code=500
        ).exception()


from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def list_bank_accounts(request):
    """
    Retrieve a list of active bank accounts for the user's corporate.

    Returns:
    - 200: List of bank accounts
    - 400: Bad request (user not linked to a corporate)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(
                message="User not authenticated", code=401
            ).unauthorized()

        # Get user_id safely
        user_id = (
            user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        )
        if not user_id:
            return ResponseProvider(message="User ID not found", code=400).bad_request()

        registry = ServiceRegistry()

        # Get corporate linked to this user
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True},
        )
        if not corporate_users:
            return ResponseProvider(
                message="User has no corporate association", code=400
            ).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]
        if not corporate_id:
            return ResponseProvider(
                message="Corporate ID not found", code=400
            ).bad_request()

        # Get list of active bank accounts for the corporate
        accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True},
        )

        # Log success
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {len(accounts)} bank accounts for corporate {corporate_id}",
            state_name="Success",
            extra={"account_count": len(accounts)},
            request=request,
        )

        return ResponseProvider(
            message="Bank accounts retrieved successfully",
            data={
                "results": accounts,  # Changed from "accounts" to "results" for frontend compatibility
                "count": len(accounts),
                "corporate_id": corporate_id,
            },
            code=200,
        ).success()

    except ValueError as ve:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_LIST_VALIDATION_ERROR",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Validation error: {str(ve)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"Validation error: {str(ve)}", code=400
        ).bad_request()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_LIST_FAILED",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Unexpected error: {str(e)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving bank accounts", code=500
        ).exception()


@csrf_exempt
def update_bank_account(request):
    """
    Update an existing bank account.

    Expected data:
    - id: UUID of the bank account to update
    - bank_name: Name of the bank (optional)
    - account_name: Name on the account (optional)
    - account_number: Bank account number (optional)
    - currency: Account currency (optional)
    - is_default: Whether this is the default account (optional)

    Returns:
    - 200: Bank account updated successfully
    - 400: Bad request (missing ID)
    - 404: Bank account not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        registry = ServiceRegistry()

        # Validate required fields
        account_id = data.get("id")
        if not account_id:
            return ResponseProvider(
                message="Bank account ID is required", code=400
            ).bad_request()

        # Check if bank account exists and is active
        existing_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": account_id, "is_active": True},
        )

        if not existing_accounts or len(existing_accounts) == 0:
            return ResponseProvider(
                message="Bank account not found or inactive", code=404
            ).bad_request()

        existing_account = existing_accounts[0]

        # Prepare update fields - only include allowed fields that are present
        allowed_fields = [
            "bank_name",
            "account_name",
            "account_number",
            "currency",
            "is_default",
        ]
        update_fields = {
            key: value
            for key, value in data.items()
            if key in allowed_fields and value is not None
        }

        if not update_fields:
            return ResponseProvider(
                message="No valid fields provided for update", code=400
            ).bad_request()

        # Perform update
        updated_account = registry.database(
            model_name="BankAccount",
            operation="update",
            instance_id=account_id,
            data=update_fields,
        )

        # Log successful update
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_UPDATED",
            user=metadata.get("user"),
            message=f"Bank account {account_id} updated successfully",
            state_name="Completed",
            extra={
                "bank_account_id": str(account_id),
                "updated_fields": list(update_fields.keys()),
            },
            request=request,
        )

        return ResponseProvider(
            message="Bank account updated successfully",
            data={
                "account": updated_account,
                "updated_fields": list(update_fields.keys()),
            },
            code=200,
        ).success()

    except ValueError as ve:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_UPDATE_VALIDATION_ERROR",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Validation error: {str(ve)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"Validation error: {str(ve)}", code=400
        ).bad_request()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_UPDATE_FAILED",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Unexpected error: {str(e)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while updating bank account", code=500
        ).exception()


@csrf_exempt
def delete_bank_account(request):
    """
    Soft delete a bank account (set is_active to False).

    Expected data:
    - id: UUID of the bank account to delete

    Returns:
    - 200: Bank account deleted successfully
    - 400: Bad request (missing ID)
    - 404: Bank account not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        registry = ServiceRegistry()

        # Validate required fields
        account_id = data.get("id")
        if not account_id:
            return ResponseProvider(
                message="Bank account ID is required", code=400
            ).bad_request()

        # Check if bank account exists and is active
        existing_accounts = registry.database(
            model_name="BankAccount",
            operation="filter",
            data={"id": account_id, "is_active": True},
        )

        if not existing_accounts or len(existing_accounts) == 0:
            return ResponseProvider(
                message="Bank account not found or already inactive", code=404
            ).bad_request()

        existing_account = existing_accounts[0]

        # Perform soft delete
        deleted_account = registry.database(
            model_name="BankAccount",
            operation="delete",
            instance_id=account_id,
            data={"id": account_id, "is_active": False},
        )

        # Log successful deletion
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_DELETED",
            user=metadata.get("user"),
            message=f"Bank account {account_id} soft-deleted successfully",
            state_name="Completed",
            extra={
                "bank_account_id": str(account_id),
                "account_number": existing_account.get("account_number"),
                "bank_name": existing_account.get("bank_name"),
            },
            request=request,
        )

        return ResponseProvider(
            message="Bank account deleted successfully",
            data={"account_id": account_id, "status": "inactive"},
            code=200,
        ).success()

    except ValueError as ve:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_DELETE_VALIDATION_ERROR",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Validation error: {str(ve)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"Validation error: {str(ve)}", code=400
        ).bad_request()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="BANK_ACCOUNT_DELETE_FAILED",
            user=metadata.get("user") if "metadata" in locals() else None,
            message=f"Unexpected error: {str(e)}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while deleting bank account", code=500
        ).exception()
