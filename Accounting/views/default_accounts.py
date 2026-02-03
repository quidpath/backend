# default_accounts.py
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from quidpath_backend.core.utils.AccountingService import AccountingService
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def seed_default_accounts(request):
    """
    Seed default accounts for the user's corporate.

    Expected data (optional):
    - force: Boolean (default: False) - If True, recreate accounts even if they exist

    Returns:
    - 200: Default accounts seeded successfully
    - 400: Bad request (invalid data)
    - 401: Unauthorized (user not authenticated)
    - 500: Internal server error
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(
            message="User not authenticated", code=401
        ).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate
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

        force = data.get("force", False)

        # Initialize accounting service
        accounting_service = AccountingService(registry=registry)

        # Seed default accounts
        with transaction.atomic():
            accounts = accounting_service.get_or_create_default_accounts(corporate_id)

        # Serialize accounts
        serialized_accounts = []
        for key, account_id in accounts.items():
            account_data = registry.database(
                model_name="Account",
                operation="filter",
                data={"id": account_id, "corporate_id": corporate_id},
            )
            if account_data:
                account = account_data[0]
                serialized_accounts.append(
                    {
                        "key": key,
                        "id": str(account["id"]),
                        "code": account.get("code", ""),
                        "name": account.get("name", ""),
                        "account_type_id": str(account.get("account_type_id", "")),
                        "is_active": account.get("is_active", True),
                    }
                )

        TransactionLogBase.log(
            transaction_type="DEFAULT_ACCOUNTS_SEEDED",
            user=user,
            message=f"Default accounts seeded for corporate {corporate_id}",
            state_name="Completed",
            extra={
                "corporate_id": corporate_id,
                "accounts_created": len(serialized_accounts),
            },
            request=request,
        )

        return ResponseProvider(
            data={
                "accounts": serialized_accounts,
                "total": len(serialized_accounts),
                "message": "Default accounts seeded successfully",
            },
            message="Default accounts seeded successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="DEFAULT_ACCOUNTS_SEEDING_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while seeding default accounts", code=500
        ).exception()
