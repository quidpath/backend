import traceback

from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from Accounting.models.customer import Customer
from Accounting.models.sales import TaxRate
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider

from OrgAuth.models import Corporate


@csrf_exempt
def create_customer(request):
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
        customer = Customer(
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
        customer.clean()  # run validation
        customer.save()
        return ResponseProvider(message="Customer created successfully", data={"id": str(customer.id)}).success()
    except ValidationError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to create customer: {str(e)}", code=500).exception()


@csrf_exempt
def list_customers(request):
    data, metadata = get_clean_data(request)
    corporate_id = data.get("corporate")

    if not corporate_id:
        return ResponseProvider(message="Corporate ID is required", code=400).bad_request()

    try:
        corporate = Corporate.objects.get(id=corporate_id)
    except ObjectDoesNotExist:
        return ResponseProvider(message="Corporate not found", code=404).bad_request()

    try:
        customers = Customer.objects.filter(corporate=corporate, is_active=True)
        customer_list = [
            {
                "id": str(c.id),
                "category": c.category,
                "company_name": c.company_name,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "email": c.email,
                "phone": c.phone,
                "address": c.address,
                "city": c.city,
                "state": c.state,
                "zip_code": c.zip_code,
                "country": c.country,
                "tax_id": c.tax_id,
                "is_active": c.is_active,
                "notes": c.notes,
            }
            for c in customers
        ]

        # Wrap the list in a dictionary structure
        response_data = {"customers": customer_list}
        return ResponseProvider(message="Customers fetched successfully", data=response_data).success()

    except Exception as e:
        print(f"Full error traceback: {traceback.format_exc()}")  # Add this import
        return ResponseProvider(message=f"Failed to fetch customers: {str(e)}", code=500).exception()

@csrf_exempt
def update_customer(request):
    data, metadata = get_clean_data(request)
    customer_id = data.get("id")
    corporate_id = data.get("corporate")

    if not customer_id or not corporate_id:
        return ResponseProvider(message="Customer ID and corporate ID are required", code=400).bad_request()

    try:
        customer = Customer.objects.get(id=customer_id, corporate_id=corporate_id, is_active=True)
    except ObjectDoesNotExist:
        return ResponseProvider(message="Customer not found", code=404).bad_request()

    try:
        for field in [
            "category", "company_name", "first_name", "last_name", "email", "phone",
            "address", "city", "state", "zip_code", "country", "tax_id", "is_active", "notes"
        ]:
            if field in data:
                setattr(customer, field, data.get(field))

        customer.clean()  # validation
        customer.save()
        return ResponseProvider(message="Customer updated successfully").success()
    except ValidationError as e:
        return ResponseProvider(message=str(e), code=400).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to update customer: {str(e)}", code=500).exception()


@csrf_exempt
def delete_customer(request):
    data, metadata = get_clean_data(request)
    customer_id = data.get("id")
    corporate_id = data.get("corporate")

    if not customer_id or not corporate_id:
        return ResponseProvider(message="Customer ID and corporate ID are required", code=400).bad_request()

    try:
        customer = Customer.objects.get(id=customer_id, corporate_id=corporate_id, is_active=True)
        customer.is_active = False
        customer.save()
        return ResponseProvider(message="Customer deleted successfully").success()
    except ObjectDoesNotExist:
        return ResponseProvider(message="Customer not found", code=404).bad_request()
    except Exception as e:
        return ResponseProvider(message=f"Failed to delete customer: {str(e)}", code=500).exception()


@csrf_exempt
def get_tax_rate(request):
    try:
        data, metadata = get_clean_data(request)

        registry = ServiceRegistry()

        # Fetch tax rates
        tax_rates = TaxRate.objects.filter(**data)

        # Convert to JSON-friendly format
        serialized_tax_rates = [
            {
                "id": str(tr.id),   # UUID to string
                "code": tr.name,    # e.g. "general_rated"
                "label": dict(TaxRate.TAX_CHOICES).get(tr.name, tr.name)  # e.g. "VAT (16%)"
            }
            for tr in tax_rates
        ]

        return ResponseProvider(serialized_tax_rates, code=200).success()

    except Exception as e:
        return ResponseProvider(
            {"error": f"Failed to fetch tax rates: {str(e)}"},
            code=500
        ).exception()