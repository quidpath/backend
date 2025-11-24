# Inventory management models
from django.db import models
from decimal import Decimal

from OrgAuth.models import Corporate, CorporateUser
from quidpath_backend.core.base_models.base import BaseModel
from Accounting.models.accounts import Account


class Warehouse(BaseModel):
    """
    Warehouse/Location for inventory storage.
    """
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="warehouses")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)  # Default warehouse for this org

    class Meta:
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"
        unique_together = [['corporate', 'code']]

    def __str__(self):
        return f"{self.name} ({self.corporate.name})"


class InventoryItem(BaseModel):
    """
    Inventory items/products.
    """
    VALUATION_METHODS = [
        ("fifo", "FIFO (First In, First Out)"),
        ("average_cost", "Average Cost"),
        ("standard_cost", "Standard Cost"),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="inventory_items")
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)  # Stock Keeping Unit
    barcode = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    
    # Accounting
    inventory_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="inventory_items", blank=True, null=True)
    cost_of_goods_sold_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="cogs_items", blank=True, null=True)
    income_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="income_items", blank=True, null=True)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    standard_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    average_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Inventory tracking
    valuation_method = models.CharField(max_length=20, choices=VALUATION_METHODS, default="fifo")
    track_quantity = models.BooleanField(default=True)
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))  # Reserved for pending orders
    quantity_available = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))  # on_hand - reserved
    reorder_point = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reorder_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Units
    unit_of_measure = models.CharField(max_length=50, default="pcs")  # pcs, kg, m, etc.
    
    # Status
    is_active = models.BooleanField(default=True)
    is_tracked = models.BooleanField(default=True)  # Track inventory movements

    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        indexes = [
            models.Index(fields=['corporate', 'sku']),
            models.Index(fields=['corporate', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        # Calculate available quantity
        if self.track_quantity:
            self.quantity_available = self.quantity_on_hand - self.quantity_reserved
        super().save(*args, **kwargs)


class StockMovement(BaseModel):
    """
    Stock movements (incoming/outgoing) for inventory tracking.
    """
    MOVEMENT_TYPES = [
        ("purchase", "Purchase"),
        ("sale", "Sale"),
        ("adjustment", "Adjustment"),
        ("transfer", "Transfer"),
        ("return", "Return"),
        ("damage", "Damage"),
        ("loss", "Loss"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, related_name="stock_movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_movements")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    quantity = models.DecimalField(max_digits=12, decimal_places=2)  # Positive for incoming, negative for outgoing
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)  # Cost at time of movement
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)  # quantity * unit_cost
    
    # References to related transactions
    invoice_id = models.UUIDField(null=True, blank=True)  # If from sale
    bill_id = models.UUIDField(null=True, blank=True)  # If from purchase
    purchase_order_id = models.UUIDField(null=True, blank=True)
    
    reference_number = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(CorporateUser, on_delete=models.PROTECT, related_name="created_stock_movements")
    
    movement_date = models.DateField()
    journal_entry = models.ForeignKey("Accounting.JournalEntry", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        indexes = [
            models.Index(fields=['corporate', 'movement_date']),
            models.Index(fields=['item', 'movement_date']),
            models.Index(fields=['warehouse', 'movement_date']),
            models.Index(fields=['status', 'movement_date']),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.item.name} ({self.quantity} {self.item.unit_of_measure})"








