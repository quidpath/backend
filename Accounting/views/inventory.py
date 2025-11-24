# Inventory management views
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from decimal import Decimal
import logging

from Accounting.models.inventory import InventoryItem, Warehouse, StockMovement
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from Accounting.models.audit import AuditLog

logger = logging.getLogger(__name__)


# ========== Warehouse APIs ==========

@csrf_exempt
def create_warehouse(request):
    """Create a warehouse."""
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
        
        warehouse_data = {
            "corporate_id": corporate_id,
            "name": data.get("name"),
            "code": data.get("code"),
            "address": data.get("address"),
            "city": data.get("city"),
            "state": data.get("state"),
            "country": data.get("country"),
            "is_active": data.get("is_active", True),
            "is_default": data.get("is_default", False)
        }
        
        if not warehouse_data["name"]:
            return ResponseProvider(message="Warehouse name is required", code=400).bad_request()
        
        # If setting as default, unset other defaults
        if warehouse_data["is_default"]:
            existing_defaults = registry.database(
                model_name="Warehouse",
                operation="filter",
                data={"corporate_id": corporate_id, "is_default": True}
            )
            for w in existing_defaults:
                registry.database("Warehouse", "update", instance_id=w.get("id"), data={"is_default": False})
        
        warehouse = registry.database("Warehouse", "create", data=warehouse_data)
        
        AuditLog.objects.create(
            corporate_id=corporate_id,
            user_id=user_id,
            action_type="CREATE",
            model_name="Warehouse",
            object_id=warehouse.get("id"),
            description=f"Created warehouse: {warehouse_data['name']}",
            ip_address=metadata.get("ip_address")
        )
        
        return ResponseProvider(data=warehouse, message="Warehouse created successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error creating warehouse: {e}")
        return ResponseProvider(message=f"Error creating warehouse: {str(e)}", code=500).exception()


@csrf_exempt
def list_warehouses(request):
    """List warehouses for a corporate."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        warehouses = registry.database(
            model_name="Warehouse",
            operation="filter",
            data={"corporate_id": corporate_id, "is_active": True}
        )
        
        return ResponseProvider(data={"warehouses": warehouses}, message="Warehouses retrieved successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error listing warehouses: {e}")
        return ResponseProvider(message=f"Error listing warehouses: {str(e)}", code=500).exception()


@csrf_exempt
def update_warehouse(request, warehouse_id):
    """Update a warehouse."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        
        warehouse = registry.database("Warehouse", "get", data={"id": warehouse_id})
        if not warehouse:
            return ResponseProvider(message="Warehouse not found", code=404).bad_request()
        
        corporate_id = warehouse.get("corporate_id")
        
        # Verify user has access
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="Warehouse not found", code=404).bad_request()
        
        update_data = {
            k: v for k, v in data.items()
            if k in ["name", "code", "address", "city", "state", "country", "is_active", "is_default"]
        }
        
        # Handle default warehouse logic
        if update_data.get("is_default"):
            existing_defaults = registry.database(
                model_name="Warehouse",
                operation="filter",
                data={"corporate_id": corporate_id, "is_default": True}
            )
            for w in existing_defaults:
                if w.get("id") != warehouse_id:
                    registry.database("Warehouse", "update", instance_id=w.get("id"), data={"is_default": False})
        
        updated_warehouse = registry.database("Warehouse", "update", instance_id=warehouse_id, data=update_data)
        
        AuditLog.objects.create(
            corporate_id=corporate_id,
            user_id=user_id,
            action_type="UPDATE",
            model_name="Warehouse",
            object_id=warehouse_id,
            description=f"Updated warehouse: {warehouse.get('name')}",
            ip_address=metadata.get("ip_address")
        )
        
        return ResponseProvider(data=updated_warehouse, message="Warehouse updated successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error updating warehouse: {e}")
        return ResponseProvider(message=f"Error updating warehouse: {str(e)}", code=500).exception()


@csrf_exempt
def delete_warehouse(request, warehouse_id):
    """Delete a warehouse (soft delete)."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        
        warehouse = registry.database("Warehouse", "get", data={"id": warehouse_id})
        if not warehouse:
            return ResponseProvider(message="Warehouse not found", code=404).bad_request()
        
        corporate_id = warehouse.get("corporate_id")
        
        # Verify user has access
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="Warehouse not found", code=404).bad_request()
        
        # Soft delete
        registry.database("Warehouse", "update", instance_id=warehouse_id, data={"is_active": False})
        
        AuditLog.objects.create(
            corporate_id=corporate_id,
            user_id=user_id,
            action_type="DELETE",
            model_name="Warehouse",
            object_id=warehouse_id,
            description=f"Deleted warehouse: {warehouse.get('name')}",
            ip_address=metadata.get("ip_address")
        )
        
        return ResponseProvider(message="Warehouse deleted successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error deleting warehouse: {e}")
        return ResponseProvider(message=f"Error deleting warehouse: {str(e)}", code=500).exception()


# ========== Inventory Item APIs ==========

@csrf_exempt
def create_inventory_item(request):
    """Create an inventory item."""
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
        
        item_data = {
            "corporate_id": corporate_id,
            "name": data.get("name"),
            "sku": data.get("sku"),
            "barcode": data.get("barcode"),
            "description": data.get("description"),
            "category": data.get("category"),
            "inventory_account_id": data.get("inventory_account_id"),
            "cost_of_goods_sold_account_id": data.get("cost_of_goods_sold_account_id"),
            "income_account_id": data.get("income_account_id"),
            "unit_cost": Decimal(str(data.get("unit_cost", 0))),
            "standard_cost": Decimal(str(data.get("standard_cost", 0))),
            "selling_price": Decimal(str(data.get("selling_price", 0))),
            "valuation_method": data.get("valuation_method", "fifo"),
            "track_quantity": data.get("track_quantity", True),
            "quantity_on_hand": Decimal(str(data.get("quantity_on_hand", 0))),
            "reorder_point": Decimal(str(data.get("reorder_point", 0))),
            "reorder_quantity": Decimal(str(data.get("reorder_quantity", 0))),
            "unit_of_measure": data.get("unit_of_measure", "pcs"),
            "is_active": data.get("is_active", True),
            "is_tracked": data.get("is_tracked", True)
        }
        
        if not item_data["name"] or not item_data["sku"]:
            return ResponseProvider(message="Item name and SKU are required", code=400).bad_request()
        
        # Check if SKU already exists
        existing = registry.database("InventoryItem", "filter", data={"sku": item_data["sku"]})
        if existing:
            return ResponseProvider(message="SKU already exists", code=400).bad_request()
        
        item = registry.database("InventoryItem", "create", data=item_data)
        
        AuditLog.objects.create(
            corporate_id=corporate_id,
            user_id=user_id,
            action_type="CREATE",
            model_name="InventoryItem",
            object_id=item.get("id"),
            description=f"Created inventory item: {item_data['name']} (SKU: {item_data['sku']})",
            ip_address=metadata.get("ip_address")
        )
        
        return ResponseProvider(data=item, message="Inventory item created successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error creating inventory item: {e}")
        return ResponseProvider(message=f"Error creating inventory item: {str(e)}", code=500).exception()


@csrf_exempt
def list_inventory_items(request):
    """List inventory items for a corporate."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        filter_data = {"corporate_id": corporate_id}
        if data.get("is_active") is not None:
            filter_data["is_active"] = data.get("is_active")
        if data.get("category"):
            filter_data["category"] = data.get("category")
        
        items = registry.database("InventoryItem", "filter", data=filter_data)
        
        return ResponseProvider(data={"items": items}, message="Inventory items retrieved successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error listing inventory items: {e}")
        return ResponseProvider(message=f"Error listing inventory items: {str(e)}", code=500).exception()


@csrf_exempt
def update_inventory_item(request, item_id):
    """Update an inventory item."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        
        item = registry.database("InventoryItem", "get", data={"id": item_id})
        if not item:
            return ResponseProvider(message="Inventory item not found", code=404).bad_request()
        
        corporate_id = item.get("corporate_id")
        
        # Verify user has access
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="Inventory item not found", code=404).bad_request()
        
        update_data = {}
        allowed_fields = [
            "name", "barcode", "description", "category", "inventory_account_id",
            "cost_of_goods_sold_account_id", "income_account_id", "unit_cost", "standard_cost",
            "selling_price", "valuation_method", "track_quantity", "reorder_point",
            "reorder_quantity", "unit_of_measure", "is_active", "is_tracked"
        ]
        
        for field in allowed_fields:
            if field in data:
                if field in ["unit_cost", "standard_cost", "selling_price", "reorder_point", "reorder_quantity"]:
                    update_data[field] = Decimal(str(data[field]))
                else:
                    update_data[field] = data[field]
        
        # Check SKU uniqueness if changing
        if "sku" in data and data["sku"] != item.get("sku"):
            existing = registry.database("InventoryItem", "filter", data={"sku": data["sku"]})
            if existing:
                return ResponseProvider(message="SKU already exists", code=400).bad_request()
            update_data["sku"] = data["sku"]
        
        updated_item = registry.database("InventoryItem", "update", instance_id=item_id, data=update_data)
        
        AuditLog.objects.create(
            corporate_id=corporate_id,
            user_id=user_id,
            action_type="UPDATE",
            model_name="InventoryItem",
            object_id=item_id,
            description=f"Updated inventory item: {item.get('name')}",
            ip_address=metadata.get("ip_address")
        )
        
        return ResponseProvider(data=updated_item, message="Inventory item updated successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error updating inventory item: {e}")
        return ResponseProvider(message=f"Error updating inventory item: {str(e)}", code=500).exception()


@csrf_exempt
def delete_inventory_item(request, item_id):
    """Delete an inventory item (soft delete)."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        
        item = registry.database("InventoryItem", "get", data={"id": item_id})
        if not item:
            return ResponseProvider(message="Inventory item not found", code=404).bad_request()
        
        corporate_id = item.get("corporate_id")
        
        # Verify user has access
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "corporate_id": corporate_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="Inventory item not found", code=404).bad_request()
        
        # Soft delete
        registry.database("InventoryItem", "update", instance_id=item_id, data={"is_active": False})
        
        AuditLog.objects.create(
            corporate_id=corporate_id,
            user_id=user_id,
            action_type="DELETE",
            model_name="InventoryItem",
            object_id=item_id,
            description=f"Deleted inventory item: {item.get('name')}",
            ip_address=metadata.get("ip_address")
        )
        
        return ResponseProvider(message="Inventory item deleted successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error deleting inventory item: {e}")
        return ResponseProvider(message=f"Error deleting inventory item: {str(e)}", code=500).exception()


# ========== Stock Movement APIs ==========

@csrf_exempt
def create_stock_movement(request):
    """Create a stock movement."""
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
        
        movement_data = {
            "corporate_id": corporate_id,
            "warehouse_id": data.get("warehouse_id"),
            "item_id": data.get("item_id"),
            "movement_type": data.get("movement_type"),
            "quantity": Decimal(str(data.get("quantity", 0))),
            "unit_cost": Decimal(str(data.get("unit_cost", 0))),
            "total_cost": Decimal(str(data.get("quantity", 0))) * Decimal(str(data.get("unit_cost", 0))),
            "invoice_id": data.get("invoice_id"),
            "bill_id": data.get("bill_id"),
            "purchase_order_id": data.get("purchase_order_id"),
            "reference_number": data.get("reference_number"),
            "notes": data.get("notes"),
            "created_by_id": user_id,
            "movement_date": data.get("movement_date"),
            "status": data.get("status", "draft")
        }
        
        if not all([movement_data["warehouse_id"], movement_data["item_id"], movement_data["movement_type"]]):
            return ResponseProvider(message="Warehouse, item, and movement type are required", code=400).bad_request()
        
        with transaction.atomic():
            movement = registry.database("StockMovement", "create", data=movement_data)
            
            # Update inventory item quantity if posted
            if movement_data["status"] == "posted":
                item = registry.database("InventoryItem", "get", data={"id": movement_data["item_id"]})
                if item:
                    current_qty = Decimal(str(item.get("quantity_on_hand", 0)))
                    new_qty = current_qty + movement_data["quantity"]
                    
                    # Update average cost if applicable
                    if item.get("valuation_method") == "average_cost":
                        current_avg = Decimal(str(item.get("average_cost", 0)))
                        current_total = current_qty * current_avg
                        new_total = current_total + movement_data["total_cost"]
                        new_avg = new_total / new_qty if new_qty > 0 else Decimal('0')
                        registry.database("InventoryItem", "update", instance_id=movement_data["item_id"], data={
                            "quantity_on_hand": new_qty,
                            "average_cost": new_avg
                        })
                    else:
                        registry.database("InventoryItem", "update", instance_id=movement_data["item_id"], data={
                            "quantity_on_hand": new_qty
                        })
            
            AuditLog.objects.create(
                corporate_id=corporate_id,
                user_id=user_id,
                action_type="CREATE",
                model_name="StockMovement",
                object_id=movement.get("id"),
                description=f"Created stock movement: {movement_data['movement_type']}",
                ip_address=metadata.get("ip_address")
            )
        
        return ResponseProvider(data=movement, message="Stock movement created successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error creating stock movement: {e}")
        return ResponseProvider(message=f"Error creating stock movement: {str(e)}", code=500).exception()


@csrf_exempt
def list_stock_movements(request):
    """List stock movements."""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        filter_data = {"corporate_id": corporate_id}
        if data.get("item_id"):
            filter_data["item_id"] = data.get("item_id")
        if data.get("warehouse_id"):
            filter_data["warehouse_id"] = data.get("warehouse_id")
        if data.get("movement_type"):
            filter_data["movement_type"] = data.get("movement_type")
        if data.get("status"):
            filter_data["status"] = data.get("status")
        
        movements = registry.database("StockMovement", "filter", data=filter_data)
        
        return ResponseProvider(data={"movements": movements}, message="Stock movements retrieved successfully", code=200).success()
        
    except Exception as e:
        logger.exception(f"Error listing stock movements: {e}")
        return ResponseProvider(message=f"Error listing stock movements: {str(e)}", code=500).exception()








