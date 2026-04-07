"""
Conftest for integration tests (no Django imports)
"""
import pytest


@pytest.fixture
def main_backend_url():
    return "http://localhost:8000"


@pytest.fixture
def billing_url():
    return "http://localhost:8007"


@pytest.fixture
def inventory_url():
    return "http://localhost:8010"


@pytest.fixture
def pos_url():
    return "http://localhost:8011"


@pytest.fixture
def crm_url():
    return "http://localhost:8012"


@pytest.fixture
def hrm_url():
    return "http://localhost:8013"


@pytest.fixture
def projects_url():
    return "http://localhost:8020"
