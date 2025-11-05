# chart_of_accounts.py (full corrected code)
from decimal import Decimal, InvalidOperation
import json, ast, re
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from collections import Counter
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data

@csrf_exempt
def create_account_type(request):
    """
    Create a new account type.

    Expected data:
    - name: Account type name (e.g., 'ASSET', unique)
    - description: Account type description (optional)
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

        required_fields = ["name"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate account type name uniqueness
        existing_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"name": data["name"]}
        )
        if existing_types:
            return ResponseProvider(message="Account type name already exists", code=400).bad_request()

        account_type_data = {
            "name": data["name"],
            "description": data.get("description", "")
        }
        account_type = registry.database(
            model_name="AccountType",
            operation="create",
            data=account_type_data
        )

        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_CREATED",
            user=user,
            message=f"Account type {account_type['name']} created",
            state_name="Completed",
            extra={"account_type_id": account_type["id"]},
            request=request
        )

        serialized_account_type = {
            "id": str(account_type["id"]),
            "name": account_type["name"],
            "description": account_type.get("description", "")
        }

        return ResponseProvider(
            message="Account type created successfully",
            data=serialized_account_type,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating account type", code=500).exception()

@csrf_exempt
def list_account_types(request):
    """
    List all account types.

    Returns:
    - 200: List of account types with total count
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        print("No user authenticated")  # Debug log
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()

        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={}
        )
        print(f"Fetched account_types: {account_types}")  # Debug log

        serialized_account_types = [
            {
                "id": str(acc_type["id"]),
                "name": acc_type["name"],
                "description": acc_type.get("description", "")
            }
            for acc_type in account_types
        ]

        total = len(account_types)
        print(f"Serialized response: {serialized_account_types}, total: {total}")  # Debug log

        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} account types",
            state_name="Success",
            extra={"total": total},
            request=request
        )

        return ResponseProvider(
            data={
                "account_types": serialized_account_types,
                "total": total
            },
            message="Account types retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        print(f"Error in list_account_types: {str(e)}")  # Debug log
        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving account types", code=500).exception()

@csrf_exempt
def get_account_type(request):
    """
    Get a single account type by ID.

    Expected data:
    - id: UUID of the account type

    Returns:
    - 200: Account type retrieved successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Account type not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        account_type_id = data.get("id")
        if not account_type_id:
            return ResponseProvider(message="Account type ID is required", code=400).bad_request()

        registry = ServiceRegistry()

        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": account_type_id}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()

        account_type = account_types[0]

        serialized_account_type = {
            "id": str(account_type["id"]),
            "name": account_type["name"],
            "description": account_type.get("description", "")
        }

        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_GET_SUCCESS",
            user=user,
            message=f"Account type {account_type_id} retrieved",
            state_name="Success",
            extra={"account_type_id": account_type_id},
            request=request
        )

        return ResponseProvider(
            message="Account type retrieved successfully",
            data=serialized_account_type,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_GET_FAILED",
            user=user if 'user' in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving account type", code=500).exception()

@csrf_exempt
def update_account_type(request):
    """
    Update an existing account type.

    Expected data:
    - id: UUID of the account type
    - name: Account type name
    - description: Account type description (optional)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()

        required_fields = ["id", "name"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate account type existence
        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": data["id"]}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()
        account_type_id = account_types[0]["id"]

        # Validate account type name uniqueness if changed
        if data["name"] != account_types[0]["name"]:
            existing_types = registry.database(
                model_name="AccountType",
                operation="filter",
                data={"name": data["name"]}
            )
            if existing_types:
                return ResponseProvider(message="Account type name already exists", code=400).bad_request()

        with transaction.atomic():
            account_type_data = {
                "name": data["name"],
                "description": data.get("description", "")
            }
            account_type = registry.database(
                model_name="AccountType",
                operation="update",
                instance_id=account_type_id,
                data=account_type_data
            )

        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_UPDATED",
            user=user,
            message=f"Account type {account_type['name']} updated",
            state_name="Completed",
            extra={"account_type_id": account_type["id"]},
            request=request
        )

        serialized_account_type = {
            "id": str(account_type["id"]),
            "name": account_type["name"],
            "description": account_type.get("description", "")
        }

        return ResponseProvider(
            message="Account type updated successfully",
            data=serialized_account_type,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating account type", code=500).exception()

@csrf_exempt
def delete_account_type(request):
    """
    Delete an account type by ID.

    Expected data:
    - id: UUID of the account type

    Returns:
    - 200: Account type deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Account type not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        account_type_id = data.get("id")
        if not account_type_id:
            return ResponseProvider(message="Account type ID is required", code=400).bad_request()

        registry = ServiceRegistry()

        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": account_type_id}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()

        with transaction.atomic():
            registry.database(
                model_name="AccountType",
                operation="delete",
                instance_id=account_type_id
            )

            TransactionLogBase.log(
                transaction_type="ACCOUNT_TYPE_DELETED",
                user=user,
                message=f"Account type {account_type_id} deleted",
                state_name="Completed",
                extra={"account_type_id": account_type_id},
                request=request
            )

        return ResponseProvider(
            message="Account type deleted successfully",
            data={"account_type_id": account_type_id},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_TYPE_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting account type", code=500).exception()

@csrf_exempt
def create_account_sub_type(request):
    """
    Create a new account sub-type.

    Expected data:
    - account_type_id: UUID of the account type
    - name: Account sub-type name (unique)
    - description: Account sub-type description (optional)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()

        required_fields = ["account_type_id", "name"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate account type existence
        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": data["account_type_id"]}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()

        # Validate account sub-type name uniqueness
        existing_sub_types = registry.database(
            model_name="AccountSubType",
            operation="filter",
            data={"name": data["name"]}
        )
        if existing_sub_types:
            return ResponseProvider(message="Account sub-type name already exists", code=400).bad_request()

        account_sub_type_data = {
            "account_type_id": data["account_type_id"],
            "name": data["name"],
            "description": data.get("description", "")
        }
        account_sub_type = registry.database(
            model_name="AccountSubType",
            operation="create",
            data=account_sub_type_data
        )

        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_CREATED",
            user=user,
            message=f"Account sub-type {account_sub_type['name']} created",
            state_name="Completed",
            extra={"account_sub_type_id": account_sub_type["id"]},
            request=request
        )

        serialized_account_sub_type = {
            "id": str(account_sub_type["id"]),
            "account_type_id": str(account_sub_type["account_type_id"]),
            "name": account_sub_type["name"],
            "description": account_sub_type.get("description", "")
        }

        return ResponseProvider(
            message="Account sub-type created successfully",
            data=serialized_account_sub_type,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating account sub-type", code=500).exception()

@csrf_exempt
def list_account_sub_types(request):
    """
    List all account sub-types, optionally filtered by account type.

    Expected data (optional):
    - account_type_id: UUID of the account type to filter by

    Returns:
    - 200: List of account sub-types with total count
    - 401: Unauthorized (user not authenticated)
    - 404: Account type not found (if account_type_id provided)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()

        filter_data = {}
        if "account_type_id" in data:
            account_types = registry.database(
                model_name="AccountType",
                operation="filter",
                data={"id": data["account_type_id"]}
            )
            if not account_types:
                return ResponseProvider(message="Account type not found", code=404).bad_request()
            filter_data["account_type_id"] = data["account_type_id"]

        account_sub_types = registry.database(
            model_name="AccountSubType",
            operation="filter",
            data=filter_data
        )

        serialized_account_sub_types = [
            {
                "id": str(acc_sub_type["id"]),
                "account_type_id": str(acc_sub_type["account_type_id"]),
                "name": acc_sub_type["name"],
                "description": acc_sub_type.get("description", "")
            }
            for acc_sub_type in account_sub_types
        ]

        total = len(account_sub_types)

        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} account sub-types",
            state_name="Success",
            extra={"total": total},
            request=request
        )

        return ResponseProvider(
            data={
                "account_sub_types": serialized_account_sub_types,
                "total": total
            },
            message="Account sub-types retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving account sub-types", code=500).exception()

@csrf_exempt
def get_account_sub_type(request):
    """
    Get a single account sub-type by ID.

    Expected data:
    - id: UUID of the account sub-type

    Returns:
    - 200: Account sub-type retrieved successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Account sub-type not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        account_sub_type_id = data.get("id")
        if not account_sub_type_id:
            return ResponseProvider(message="Account sub-type ID is required", code=400).bad_request()

        registry = ServiceRegistry()

        account_sub_types = registry.database(
            model_name="AccountSubType",
            operation="filter",
            data={"id": account_sub_type_id}
        )
        if not account_sub_types:
            return ResponseProvider(message="Account sub-type not found", code=404).bad_request()

        account_sub_type = account_sub_types[0]

        serialized_account_sub_type = {
            "id": str(account_sub_type["id"]),
            "account_type_id": str(account_sub_type["account_type_id"]),
            "name": account_sub_type["name"],
            "description": account_sub_type.get("description", "")
        }

        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_GET_SUCCESS",
            user=user,
            message=f"Account sub-type {account_sub_type_id} retrieved",
            state_name="Success",
            extra={"account_sub_type_id": account_sub_type_id},
            request=request
        )

        return ResponseProvider(
            message="Account sub-type retrieved successfully",
            data=serialized_account_sub_type,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_GET_FAILED",
            user=user if 'user' in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving account sub-type", code=500).exception()

@csrf_exempt
def update_account_sub_type(request):
    """
    Update an existing account sub-type.

    Expected data:
    - id: UUID of the account sub-type
    - account_type_id: UUID of the account type
    - name: Account sub-type name
    - description: Account sub-type description (optional)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        registry = ServiceRegistry()

        required_fields = ["id", "account_type_id", "name"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate account type existence
        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": data["account_type_id"]}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()

        # Validate account sub-type existence
        account_sub_types = registry.database(
            model_name="AccountSubType",
            operation="filter",
            data={"id": data["id"]}
        )
        if not account_sub_types:
            return ResponseProvider(message="Account sub-type not found", code=404).bad_request()
        account_sub_type_id = account_sub_types[0]["id"]

        # Validate account sub-type name uniqueness if changed
        if data["name"] != account_sub_types[0]["name"]:
            existing_sub_types = registry.database(
                model_name="AccountSubType",
                operation="filter",
                data={"name": data["name"]}
            )
            if existing_sub_types:
                return ResponseProvider(message="Account sub-type name already exists", code=400).bad_request()

        with transaction.atomic():
            account_sub_type_data = {
                "account_type_id": data["account_type_id"],
                "name": data["name"],
                "description": data.get("description", "")
            }
            account_sub_type = registry.database(
                model_name="AccountSubType",
                operation="update",
                instance_id=account_sub_type_id,
                data=account_sub_type_data
            )

        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_UPDATED",
            user=user,
            message=f"Account sub-type {account_sub_type['name']} updated",
            state_name="Completed",
            extra={"account_sub_type_id": account_sub_type["id"]},
            request=request
        )

        serialized_account_sub_type = {
            "id": str(account_sub_type["id"]),
            "account_type_id": str(account_sub_type["account_type_id"]),
            "name": account_sub_type["name"],
            "description": account_sub_type.get("description", "")
        }

        return ResponseProvider(
            message="Account sub-type updated successfully",
            data=serialized_account_sub_type,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating account sub-type", code=500).exception()

@csrf_exempt
def delete_account_sub_type(request):
    """
    Delete an account sub-type by ID.

    Expected data:
    - id: UUID of the account sub-type

    Returns:
    - 200: Account sub-type deleted successfully
    - 400: Bad request (missing ID)
    - 401: Unauthorized (user not authenticated)
    - 404: Account sub-type not found
    - 500: Internal server error
    """
    try:
        data, metadata = get_clean_data(request)
        user = metadata.get("user")
        if not user:
            return ResponseProvider(message="User not authenticated", code=401).unauthorized()

        account_sub_type_id = data.get("id")
        if not account_sub_type_id:
            return ResponseProvider(message="Account sub-type ID is required", code=400).bad_request()

        registry = ServiceRegistry()

        account_sub_types = registry.database(
            model_name="AccountSubType",
            operation="filter",
            data={"id": account_sub_type_id}
        )
        if not account_sub_types:
            return ResponseProvider(message="Account sub-type not found", code=404).bad_request()

        with transaction.atomic():
            registry.database(
                model_name="AccountSubType",
                operation="delete",
                instance_id=account_sub_type_id
            )

            TransactionLogBase.log(
                transaction_type="ACCOUNT_SUB_TYPE_DELETED",
                user=user,
                message=f"Account sub-type {account_sub_type_id} deleted",
                state_name="Completed",
                extra={"account_sub_type_id": account_sub_type_id},
                request=request
            )

        return ResponseProvider(
            message="Account sub-type deleted successfully",
            data={"account_sub_type_id": account_sub_type_id},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_SUB_TYPE_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting account sub-type", code=500).exception()

@csrf_exempt
def create_account(request):
    """
    Create a new chart of account entry for the user's corporate.

    Expected data:
    - code: Account code (unique within corporate, e.g., '1001')
    - name: Account name
    - account_type_id: UUID of the account type
    - account_sub_type_id: UUID of the account sub-type (optional)
    - description: Account description (optional)
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

        required_fields = ["code", "name", "account_type_id"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate account code uniqueness within corporate
        existing_accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"code": data["code"], "corporate_id": corporate_id}
        )
        if existing_accounts:
            return ResponseProvider(message="Account code already exists for this corporate", code=400).bad_request()

        # Validate account type existence
        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": data["account_type_id"]}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()

        # Validate account sub-type existence if provided
        if "account_sub_type_id" in data and data["account_sub_type_id"]:
            account_sub_types = registry.database(
                model_name="AccountSubType",
                operation="filter",
                data={"id": data["account_sub_type_id"], "account_type_id": data["account_type_id"]}
            )
            if not account_sub_types:
                return ResponseProvider(message="Account sub-type not found or does not belong to the specified account type", code=404).bad_request()

        account_data = {
            "corporate_id": corporate_id,
            "code": data["code"],
            "name": data["name"],
            "account_type_id": data["account_type_id"],
            "account_sub_type_id": data.get("account_sub_type_id", None),
            "description": data.get("description", ""),
            "is_active": True
        }
        account = registry.database(
            model_name="Account",
            operation="create",
            data=account_data
        )

        TransactionLogBase.log(
            transaction_type="ACCOUNT_CREATED",
            user=user,
            message=f"Account {account['code']} created for corporate {corporate_id}",
            state_name="Completed",
            extra={"account_id": account["id"]},
            request=request
        )

        serialized_account = {
            "id": str(account["id"]),
            "code": account["code"],
            "name": account["name"],
            "account_type_id": str(account["account_type_id"]),
            "account_sub_type_id": str(account["account_sub_type_id"]) if account["account_sub_type_id"] else None,
            "description": account.get("description", ""),
            "is_active": account.get("is_active", True)
        }

        return ResponseProvider(
            message="Account created successfully",
            data=serialized_account,
            code=201
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_CREATION_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while creating account", code=500).exception()

@csrf_exempt
def list_accounts(request):
    """
    List all chart of account entries for the user's corporate, categorized by type.

    Expected data (optional):
    - include_balances: Boolean (default: False) - Include current balance for each account

    Returns:
    - 200: List of accounts with total count and type counts
    - 400: Bad request (missing corporate)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")

    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0].get("corporate_id")
        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        include_balances = data.get("include_balances", False)

        # Accounts
        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"corporate_id": corporate_id}
        )

        # Calculate balances if requested
        account_balances = {}
        if include_balances:
            from datetime import date
            from collections import defaultdict
            from decimal import Decimal

            # Get all posted journal entries
            journal_entries = registry.database(
                model_name="JournalEntry",
                operation="filter",
                data={"corporate_id": corporate_id, "is_posted": True}
            )

            je_ids = {je["id"] for je in journal_entries}

            # Get all journal entry lines
            all_lines = registry.database(
                model_name="JournalEntryLine",
                operation="filter",
                data={}
            )

            lines = [line for line in all_lines if line["journal_entry_id"] in je_ids]

            # Calculate balances per account
            balances = defaultdict(lambda: {"debit": Decimal("0.00"), "credit": Decimal("0.00")})
            for line in lines:
                account_id = line["account_id"]
                balances[account_id]["debit"] += Decimal(str(line.get("debit", 0)))
                balances[account_id]["credit"] += Decimal(str(line.get("credit", 0)))

            # Get account types for normal balance
            account_type_map = {}
            for acc in accounts:
                if acc.get("account_type_id"):
                    account_types = registry.database(
                        model_name="AccountType",
                        operation="filter",
                        data={"id": acc.get("account_type_id")}
                    )
                    if account_types:
                        normal_balance = account_types[0].get("normal_balance", "DEBIT")
                        account_type_map[acc["id"]] = normal_balance

            # Calculate final balances
            for account_id, bal in balances.items():
                debit = bal["debit"]
                credit = bal["credit"]
                normal_balance = account_type_map.get(account_id, "DEBIT")
                
                if normal_balance == "DEBIT":
                    balance = debit - credit
                else:
                    balance = credit - debit
                
                account_balances[account_id] = str(balance)

        serialized_accounts = []
        for acc in accounts:
            account_data = {
                "id": str(acc.get("id")),
                "code": acc.get("code"),
                "name": acc.get("name"),
                "account_type_id": str(acc.get("account_type_id")) if acc.get("account_type_id") else None,
                "account_sub_type_id": str(acc.get("account_sub_type_id")) if acc.get("account_sub_type_id") else None,
                "description": acc.get("description", ""),
                "is_active": acc.get("is_active", True),
            }
            if include_balances:
                account_data["balance"] = account_balances.get(acc.get("id"), "0.00")
            serialized_accounts.append(account_data)

        # Type counts
        type_counts = {}
        for acc in accounts:
            account_type_id = acc.get("account_type_id")
            if not account_type_id:
                continue  # skip accounts without a type

            account_type_list = registry.database(
                model_name="AccountType",
                operation="filter",
                data={"id": account_type_id}
            )

            if not account_type_list:
                continue  # skip if type not found

            account_type = account_type_list[0]
            type_name = account_type.get("name", "Unknown")
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        total = len(accounts)

        TransactionLogBase.log(
            transaction_type="ACCOUNT_LIST_SUCCESS",
            user=user,
            message=f"Retrieved {total} accounts for corporate {corporate_id}",
            state_name="Success",
            extra={"type_counts": type_counts},
            request=request,
        )

        return ResponseProvider(
            data={
                "accounts": serialized_accounts,
                "total": total,
                "type_counts": type_counts,
            },
            message="Accounts retrieved successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_LIST_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(message="An error occurred while retrieving accounts", code=500).exception()

@csrf_exempt
def get_account(request):
    """
    Get a single chart of account entry by ID for the user's corporate.

    Expected data:
    - id: UUID of the account

    Returns:
    - 200: Account retrieved successfully
    - 400: Bad request (missing ID or invalid corporate)
    - 401: Unauthorized (user not authenticated)
    - 404: Account not found for this corporate
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
            data={"customuser_ptr_id": user_id, "is_active": True}
        )

        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        if not corporate_id:
            return ResponseProvider(message="Corporate ID not found", code=400).bad_request()

        account_id = data.get("id")
        if not account_id:
            return ResponseProvider(message="Account ID is required", code=400).bad_request()

        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"id": account_id, "corporate_id": corporate_id}
        )
        if not accounts:
            return ResponseProvider(message="Account not found for this corporate", code=404).bad_request()

        account = accounts[0]

        serialized_account = {
            "id": str(account["id"]),
            "code": account["code"],
            "name": account["name"],
            "account_type_id": str(account["account_type_id"]),
            "account_sub_type_id": str(account["account_sub_type_id"]) if account["account_sub_type_id"] else None,
            "description": account.get("description", ""),
            "is_active": account.get("is_active", True)
        }

        TransactionLogBase.log(
            transaction_type="ACCOUNT_GET_SUCCESS",
            user=user,
            message=f"Account {account['code']} retrieved for corporate {corporate_id}",
            state_name="Success",
            request=request
        )

        return ResponseProvider(
            message="Account retrieved successfully",
            data=serialized_account,
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_GET_FAILED",
            user=user if 'user' in locals() else None,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while retrieving account", code=500).exception()

@csrf_exempt
def update_account(request):
    """
    Update an existing chart of account entry for the user's corporate.

    Expected data:
    - id: UUID of the account
    - code: Account code (unique within corporate, e.g., '1001')
    - name: Account name
    - account_type_id: UUID of the account type
    - account_sub_type_id: UUID of the account sub-type (optional)
    - description: Account description (optional)
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
        required_fields = ["id", "code", "name", "account_type_id"]
        for field in required_fields:
            if field not in data:
                return ResponseProvider(message=f"{field.replace('_', ' ').title()} is required", code=400).bad_request()

        # Validate account existence
        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"id": data["id"], "corporate_id": corporate_id}
        )
        if not accounts:
            return ResponseProvider(message="Account not found", code=404).bad_request()
        account_id = accounts[0]["id"]

        # Validate account code uniqueness if changed
        if data["code"] != accounts[0]["code"]:
            existing_accounts = registry.database(
                model_name="Account",
                operation="filter",
                data={"code": data["code"], "corporate_id": corporate_id}
            )
            if existing_accounts:
                return ResponseProvider(message="Account code already exists for this corporate", code=400).bad_request()

        # Validate account type existence
        account_types = registry.database(
            model_name="AccountType",
            operation="filter",
            data={"id": data["account_type_id"]}
        )
        if not account_types:
            return ResponseProvider(message="Account type not found", code=404).bad_request()

        # Validate account sub-type existence if provided
        if "account_sub_type_id" in data and data["account_sub_type_id"]:
            account_sub_types = registry.database(
                model_name="AccountSubType",
                operation="filter",
                data={"id": data["account_sub_type_id"], "account_type_id": data["account_type_id"]}
            )
            if not account_sub_types:
                return ResponseProvider(message="Account sub-type not found or does not belong to the specified account type", code=404).bad_request()

        # Update account within a transaction
        with transaction.atomic():
            account_data = {
                "code": data["code"],
                "name": data["name"],
                "account_type_id": data["account_type_id"],
                "account_sub_type_id": data.get("account_sub_type_id", None),
                "description": data.get("description", "")
            }
            account = registry.database(
                model_name="Account",
                operation="update",
                instance_id=account_id,
                data=account_data
            )

        # Log update
        TransactionLogBase.log(
            transaction_type="ACCOUNT_UPDATED",
            user=user,
            message=f"Account {account['code']} updated for corporate {corporate_id}",
            state_name="Completed",
            extra={"account_id": account["id"]},
            request=request
        )

        serialized_account = {
            "id": str(account["id"]),
            "code": account["code"],
            "name": account["name"],
            "account_type_id": str(account["account_type_id"]),
            "account_sub_type_id": str(account["account_sub_type_id"]) if account["account_sub_type_id"] else None,
            "description": account.get("description", ""),
            "is_active": account.get("is_active", True)
        }

        return ResponseProvider(message="Account updated successfully", data=serialized_account, code=200).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_UPDATE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while updating account", code=500).exception()

@csrf_exempt
def delete_account(request):
    """
    Soft delete a chart of account entry by setting is_active to False.

    Expected data:
    - id: UUID of the account (in POST body)

    Returns:
    - 200: Account deleted successfully
    - 400: Bad request (missing ID or invalid data)
    - 401: Unauthorized (user not authenticated)
    - 404: Account not found for this corporate
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

        account_id = data.get("id")
        if not account_id:
            return ResponseProvider(message="Account ID is required", code=400).bad_request()

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

        accounts = registry.database(
            model_name="Account",
            operation="filter",
            data={"id": account_id, "corporate_id": corporate_id}
        )
        if not accounts:
            return ResponseProvider(message="Account not found for this corporate", code=404).bad_request()

        with transaction.atomic():
            registry.database(
                model_name="Account",
                operation="update",
                instance_id=account_id,
                data={"is_active": False}
            )

            TransactionLogBase.log(
                transaction_type="ACCOUNT_DELETED",
                user=user,
                message=f"Account {account_id} soft-deleted",
                state_name="Completed",
                extra={"account_id": account_id},
                request=request
            )

        return ResponseProvider(
            message="Account deleted successfully",
            data={"account_id": account_id},
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="ACCOUNT_DELETE_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request
        )
        return ResponseProvider(message="An error occurred while deleting account", code=500).exception()