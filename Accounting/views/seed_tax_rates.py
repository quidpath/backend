"""
Seed Default Tax Rates View
"""
from decimal import Decimal
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from Accounting.models.sales import TaxRate
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data


@csrf_exempt
def seed_default_tax_rates(request):
    """
    Seed default tax rates for the user's corporate.
    Creates three standard tax rates: exempt, zero_rated, and general_rated.

    Returns:
    - 200: Default tax rates seeded successfully
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

        # Get corporate object
        corporate = registry.database(
            model_name="Corporate",
            operation="get",
            data={"id": corporate_id},
        )

        # Define default tax rates
        default_tax_rates = [
            {"name": "exempt", "rate": Decimal("0.00")},
            {"name": "zero_rated", "rate": Decimal("0.00")},
            {"name": "general_rated", "rate": Decimal("16.00")},
        ]

        created_rates = []
        existing_rates = []

        with transaction.atomic():
            for tax_rate_data in default_tax_rates:
                # Check if tax rate already exists
                existing = TaxRate.objects.filter(
                    corporate_id=corporate_id,
                    name=tax_rate_data["name"]
                ).first()

                if existing:
                    existing_rates.append({
                        "id": str(existing.id),
                        "name": existing.name,
                        "rate": float(existing.rate),
                    })
                else:
                    # Create new tax rate
                    tax_rate = registry.database(
                        model_name="TaxRate",
                        operation="create",
                        data={
                            "corporate": corporate,
                            "name": tax_rate_data["name"],
                            "rate": tax_rate_data["rate"],
                        },
                    )
                    created_rates.append({
                        "id": str(tax_rate["id"]),
                        "name": tax_rate["name"],
                        "rate": float(tax_rate["rate"]),
                    })

        total_rates = len(created_rates) + len(existing_rates)

        TransactionLogBase.log(
            transaction_type="DEFAULT_TAX_RATES_SEEDED",
            user=user,
            message=f"Default tax rates seeded for corporate {corporate_id}",
            state_name="Completed",
            extra={
                "corporate_id": corporate_id,
                "created": len(created_rates),
                "existing": len(existing_rates),
            },
            request=request,
        )

        return ResponseProvider(
            data={
                "created": created_rates,
                "existing": existing_rates,
                "total": total_rates,
                "message": f"Seeded {len(created_rates)} new tax rates, {len(existing_rates)} already existed",
            },
            message="Default tax rates seeded successfully",
            code=200,
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="DEFAULT_TAX_RATES_SEEDING_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while seeding default tax rates", code=500
        ).exception()
