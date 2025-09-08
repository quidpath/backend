import traceback

from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from Accounting.models.vendor import Vendor
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider

from OrgAuth.models import Corporate


@csrf_exempt
def create_vendor(request):
    data, metadata = get_clean_data(request)
    category = data.get("category")
    corporate_id = data.get("corporate")

    if not category or not corporate_id:
        return ResponseProvider(message="Category and corporate ID are required", code=400).bad_request()

    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except ObjectDoesNotExist:
        return ResponseProvider(message="Corporate not found", code=404).bad_request()

    try:
        vendor = Vendor(
            category=category,
            corporate=corporate,
            company_name=data.get("company_name"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            zip_code=data.get("zip_code"),
            country=data.get("country"),
            tax_id=data.get("tax_id"),
            is_active=data.get("is_active", True),
            notes=data.get("notes")
        )
        vendor.clean()  # run validation
        vendor.save()
        return ResponseProvider(message="Vendor created successfully", data={"id": str(vendor.id)}).success()
    except ValidationError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to create vendor: {str(e)}", code=500).exception()


@csrf_exempt
def list_vendors(request):
    """
    List all vendors for the user's corporate.

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
            data={"corporate_id": corporate_id}
        )

        serialized_vendors = [
            {
                "id": str(vendor["id"]),
                "name": vendor.get("name", ""),
                "company_name": vendor.get("company_name", ""),
                "email": vendor.get("email", ""),
                "phone": vendor.get("phone", ""),
                "address": vendor.get("address", ""),
                "city": vendor.get("city", ""),
                "state": vendor.get("state", ""),
                "zip_code": vendor.get("zip_code", ""),
                "country": vendor.get("country", ""),
                "tax_id": vendor.get("tax_id", ""),
                "is_active": vendor.get("is_active", True),
                "notes": vendor.get("notes", "")
            }
            for vendor in vendors
        ]

        return ResponseProvider(
            data={"vendors": serialized_vendors},
            message="Vendors retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(message=str(e), code=500).exception()

@csrf_exempt
def get_vendor(request):
    data, metadata = get_clean_data(request)
    vendor_id = data.get("id")
    corporate_id = data.get("corporate")

    if not vendor_id or not corporate_id:
        return ResponseProvider(message="Vendor ID and corporate ID are required", code=400).bad_request()

    try:
        vendor = Vendor.objects.get(id=vendor_id, corporate_id=corporate_id, is_active=True)
        vendor_data = {
            "id": str(vendor.id),
            "category": vendor.category,
            "company_name": vendor.company_name,
            "first_name": vendor.first_name,
            "last_name": vendor.last_name,
            "email": vendor.email,
            "phone": vendor.phone,
            "address": vendor.address,
            "city": vendor.city,
            "state": vendor.state,
            "zip_code": vendor.zip_code,
            "country": vendor.country,
            "tax_id": vendor.tax_id,
            "is_active": vendor.is_active,
            "notes": vendor.notes,
            "created_at": vendor.created_at.isoformat() if hasattr(vendor, 'created_at') else None,
            "updated_at": vendor.updated_at.isoformat() if hasattr(vendor, 'updated_at') else None,
        }
        return ResponseProvider(message="Vendor fetched successfully", data=vendor_data).success()
    except ObjectDoesNotExist:
        return ResponseProvider(message="Vendor not found", code=404).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to fetch vendor: {str(e)}", code=500).exception()


@csrf_exempt
def update_vendor(request):
    data, metadata = get_clean_data(request)
    vendor_id = data.get("id")
    corporate_id = data.get("corporate")

    if not vendor_id or not corporate_id:
        return ResponseProvider(message="Vendor ID and corporate ID are required", code=400).bad_request()

    try:
        vendor = Vendor.objects.get(id=vendor_id, corporate_id=corporate_id, is_active=True)
    except ObjectDoesNotExist:
        return ResponseProvider(message="Vendor not found", code=404).bad_request()

    try:
        for field in [
            "category", "company_name", "first_name", "last_name", "email", "phone",
            "address", "city", "state", "zip_code", "country", "tax_id", "is_active", "notes"
        ]:
            if field in data:
                setattr(vendor, field, data.get(field))

        vendor.clean()  # validation
        vendor.save()
        return ResponseProvider(message="Vendor updated successfully").success()
    except ValidationError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to update vendor: {str(e)}", code=500).exception()


@csrf_exempt
def delete_vendor(request):
    data, metadata = get_clean_data(request)
    vendor_id = data.get("id")
    corporate_id = data.get("corporate")

    if not vendor_id or not corporate_id:
        return ResponseProvider(message="Vendor ID and corporate ID are required", code=400).bad_request()

    try:
        vendor = Vendor.objects.get(id=vendor_id, corporate_id=corporate_id, is_active=True)
        vendor.is_active = False
        vendor.save()
        return ResponseProvider(message="Vendor deleted successfully").success()
    except ObjectDoesNotExist:
        return ResponseProvider(message="Vendor not found", code=404).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to delete vendor: {str(e)}", code=500).exception()


@csrf_exempt
def search_vendors(request):
    """Search vendors by name, email, company, or phone"""
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate")
    search_term = data.get("search", "").strip()

    if not corporate_id:
        return ResponseProvider(message="Corporate ID is required", code=400).bad_request()

    if not search_term:
        return ResponseProvider(message="Search term is required", code=400).bad_request()

    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except ObjectDoesNotExist:
        return ResponseProvider(message="Corporate not found", code=404).bad_request()

    try:
        from django.db.models import Q

        vendors = Vendor.objects.filter(
            Q(corporate=corporate) & Q(is_active=True) & (
                    Q(company_name__icontains=search_term) |
                    Q(first_name__icontains=search_term) |
                    Q(last_name__icontains=search_term) |
                    Q(email__icontains=search_term) |
                    Q(phone__icontains=search_term)
            )
        )

        vendor_list = [
            {
                "id": str(v.id),
                "category": v.category,
                "company_name": v.company_name,
                "first_name": v.first_name,
                "last_name": v.last_name,
                "email": v.email,
                "phone": v.phone,
                "address": v.address,
                "city": v.city,
                "state": v.state,
                "zip_code": v.zip_code,
                "country": v.country,
                "tax_id": v.tax_id,
                "is_active": v.is_active,
                "notes": v.notes,
            }
            for v in vendors
        ]

        response_data = {
            "vendors": vendor_list,
            "count": len(vendor_list),
            "search_term": search_term
        }
        return ResponseProvider(message="Vendors search completed", data=response_data).success()

    except Exception as e:
        print(f"Full error traceback: {traceback.format_exc()}")
        return ResponseProvider(message=f"Failed to search vendors: {str(e)}", code=500).exception()