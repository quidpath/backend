"""
Test suite for Inventory Service
Tests Products, Stock, Warehouses, Pricelists, Categories, UOM
"""
import uuid

import pytest
import requests
from rest_framework import status


@pytest.mark.django_db
class TestProductEndpoints:
    """Test Product CRUD endpoints"""

    def test_list_products_requires_auth(self, inventory_url):
        """Test listing products requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/products/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_product_requires_auth(self, inventory_url):
        """Test creating product requires authentication"""
        data = {
            "name": "Test Product",
            "sku": "TEST-001",
            "price": "100.00",
        }
        response = requests.post(f"{inventory_url}/api/inventory/products/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_product_detail_requires_auth(self, inventory_url):
        """Test retrieving product detail requires authentication"""
        product_id = str(uuid.uuid4())
        response = requests.get(
            f"{inventory_url}/api/inventory/products/{product_id}/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_product_requires_auth(self, inventory_url):
        """Test updating product requires authentication"""
        product_id = str(uuid.uuid4())
        data = {"name": "Updated Product"}
        response = requests.patch(
            f"{inventory_url}/api/inventory/products/{product_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_product_requires_auth(self, inventory_url):
        """Test deleting product requires authentication"""
        product_id = str(uuid.uuid4())
        response = requests.delete(
            f"{inventory_url}/api/inventory/products/{product_id}/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestProductVariantEndpoints:
    """Test Product Variant endpoints"""

    def test_list_variants_requires_auth(self, inventory_url):
        """Test listing product variants requires authentication"""
        product_id = str(uuid.uuid4())
        response = requests.get(
            f"{inventory_url}/api/inventory/products/{product_id}/variants/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCategoryEndpoints:
    """Test Category endpoints"""

    def test_list_categories_requires_auth(self, inventory_url):
        """Test listing categories requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/products/categories/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_category_requires_auth(self, inventory_url):
        """Test creating category requires authentication"""
        data = {"name": "Test Category"}
        response = requests.post(
            f"{inventory_url}/api/inventory/products/categories/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestWarehouseEndpoints:
    """Test Warehouse CRUD endpoints"""

    def test_list_warehouses_requires_auth(self, inventory_url):
        """Test listing warehouses requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/warehouse/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_warehouse_requires_auth(self, inventory_url):
        """Test creating warehouse requires authentication"""
        data = {
            "name": "Test Warehouse",
            "location": "Test Location",
        }
        response = requests.post(
            f"{inventory_url}/api/inventory/warehouse/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestStockEndpoints:
    """Test Stock management endpoints"""

    def test_list_stock_requires_auth(self, inventory_url):
        """Test listing stock requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/stock/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_stock_adjustment_requires_auth(self, inventory_url):
        """Test creating stock adjustment requires authentication"""
        data = {
            "product_id": str(uuid.uuid4()),
            "warehouse_id": str(uuid.uuid4()),
            "quantity": 10,
            "type": "adjustment",
        }
        response = requests.post(f"{inventory_url}/api/inventory/stock/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestStockMoveEndpoints:
    """Test Stock Move endpoints"""

    def test_list_stock_moves_requires_auth(self, inventory_url):
        """Test listing stock moves requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/stock/moves/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPricelistEndpoints:
    """Test Pricelist endpoints"""

    def test_list_pricelists_requires_auth(self, inventory_url):
        """Test listing pricelists requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/products/pricelists/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_pricelist_requires_auth(self, inventory_url):
        """Test creating pricelist requires authentication"""
        data = {
            "name": "Test Pricelist",
            "currency": "KES",
        }
        response = requests.post(
            f"{inventory_url}/api/inventory/products/pricelists/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUOMEndpoints:
    """Test Unit of Measure endpoints"""

    def test_list_uom_requires_auth(self, inventory_url):
        """Test listing UOM requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/products/uom/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_uom_requires_auth(self, inventory_url):
        """Test creating UOM requires authentication"""
        data = {
            "name": "Kilogram",
            "abbreviation": "kg",
        }
        response = requests.post(
            f"{inventory_url}/api/inventory/products/uom/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestValuationEndpoints:
    """Test Inventory Valuation endpoints"""

    def test_get_valuation_requires_auth(self, inventory_url):
        """Test getting inventory valuation requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/valuation/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCountingEndpoints:
    """Test Stock Counting endpoints"""

    def test_list_stock_counts_requires_auth(self, inventory_url):
        """Test listing stock counts requires authentication"""
        response = requests.get(f"{inventory_url}/api/inventory/counting/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_stock_count_requires_auth(self, inventory_url):
        """Test creating stock count requires authentication"""
        data = {
            "warehouse_id": str(uuid.uuid4()),
            "date": "2026-04-04",
        }
        response = requests.post(f"{inventory_url}/api/inventory/counting/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
