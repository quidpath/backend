"""
Test suite for CRM Service
Tests Companies, Contacts, Leads, Opportunities, Activities, Campaigns, Pipeline
"""
import uuid

import pytest
import requests
from rest_framework import status


@pytest.mark.django_db
class TestCompanyEndpoints:
    """Test Company CRUD endpoints"""

    def test_list_companies_requires_auth(self, crm_url):
        """Test listing companies requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/contacts/companies/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_company_requires_auth(self, crm_url):
        """Test creating company requires authentication"""
        data = {
            "name": "Test Company",
            "industry": "Technology",
        }
        response = requests.post(f"{crm_url}/api/crm/contacts/companies/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_company_detail_requires_auth(self, crm_url):
        """Test retrieving company detail requires authentication"""
        company_id = str(uuid.uuid4())
        response = requests.get(f"{crm_url}/api/crm/contacts/companies/{company_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_company_requires_auth(self, crm_url):
        """Test updating company requires authentication"""
        company_id = str(uuid.uuid4())
        data = {"name": "Updated Company"}
        response = requests.patch(
            f"{crm_url}/api/crm/contacts/companies/{company_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_company_requires_auth(self, crm_url):
        """Test deleting company requires authentication"""
        company_id = str(uuid.uuid4())
        response = requests.delete(
            f"{crm_url}/api/crm/contacts/companies/{company_id}/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestContactEndpoints:
    """Test Contact CRUD endpoints"""

    def test_list_contacts_requires_auth(self, crm_url):
        """Test listing contacts requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/contacts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_contact_requires_auth(self, crm_url):
        """Test creating contact requires authentication"""
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@test.com",
        }
        response = requests.post(f"{crm_url}/api/crm/contacts/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_contact_detail_requires_auth(self, crm_url):
        """Test retrieving contact detail requires authentication"""
        contact_id = str(uuid.uuid4())
        response = requests.get(f"{crm_url}/api/crm/contacts/{contact_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_contact_requires_auth(self, crm_url):
        """Test updating contact requires authentication"""
        contact_id = str(uuid.uuid4())
        data = {"first_name": "Jane"}
        response = requests.patch(
            f"{crm_url}/api/crm/contacts/{contact_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_contact_requires_auth(self, crm_url):
        """Test deleting contact requires authentication"""
        contact_id = str(uuid.uuid4())
        response = requests.delete(f"{crm_url}/api/crm/contacts/{contact_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTagEndpoints:
    """Test Tag endpoints"""

    def test_list_tags_requires_auth(self, crm_url):
        """Test listing tags requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/contacts/tags/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_tag_requires_auth(self, crm_url):
        """Test creating tag requires authentication"""
        data = {"name": "VIP"}
        response = requests.post(f"{crm_url}/api/crm/contacts/tags/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLeadEndpoints:
    """Test Lead endpoints"""

    def test_list_leads_requires_auth(self, crm_url):
        """Test listing leads requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/pipeline/leads/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_lead_requires_auth(self, crm_url):
        """Test creating lead requires authentication"""
        data = {
            "title": "Test Lead",
            "contact_id": str(uuid.uuid4()),
        }
        response = requests.post(f"{crm_url}/api/crm/pipeline/leads/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_lead_detail_requires_auth(self, crm_url):
        """Test retrieving lead detail requires authentication"""
        lead_id = str(uuid.uuid4())
        response = requests.get(f"{crm_url}/api/crm/pipeline/leads/{lead_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_lead_requires_auth(self, crm_url):
        """Test updating lead requires authentication"""
        lead_id = str(uuid.uuid4())
        data = {"title": "Updated Lead"}
        response = requests.patch(
            f"{crm_url}/api/crm/pipeline/leads/{lead_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_lead_requires_auth(self, crm_url):
        """Test deleting lead requires authentication"""
        lead_id = str(uuid.uuid4())
        response = requests.delete(f"{crm_url}/api/crm/pipeline/leads/{lead_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOpportunityEndpoints:
    """Test Opportunity endpoints"""

    def test_list_opportunities_requires_auth(self, crm_url):
        """Test listing opportunities requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/pipeline/opportunities/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_opportunity_requires_auth(self, crm_url):
        """Test creating opportunity requires authentication"""
        data = {
            "name": "Test Opportunity",
            "value": "10000.00",
        }
        response = requests.post(f"{crm_url}/api/crm/pipeline/opportunities/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPipelineStageEndpoints:
    """Test Pipeline Stage endpoints"""

    def test_list_pipeline_stages_requires_auth(self, crm_url):
        """Test listing pipeline stages requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/pipeline/stages/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_pipeline_stage_requires_auth(self, crm_url):
        """Test creating pipeline stage requires authentication"""
        data = {
            "name": "Qualification",
            "order": 1,
        }
        response = requests.post(f"{crm_url}/api/crm/pipeline/stages/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestActivityEndpoints:
    """Test Activity endpoints"""

    def test_list_activities_requires_auth(self, crm_url):
        """Test listing activities requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/sales/activities/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_activity_requires_auth(self, crm_url):
        """Test creating activity requires authentication"""
        data = {
            "type": "call",
            "subject": "Follow-up call",
            "contact_id": str(uuid.uuid4()),
        }
        response = requests.post(f"{crm_url}/api/crm/sales/activities/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCampaignEndpoints:
    """Test Campaign endpoints"""

    def test_list_campaigns_requires_auth(self, crm_url):
        """Test listing campaigns requires authentication"""
        response = requests.get(f"{crm_url}/api/crm/campaigns/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_campaign_requires_auth(self, crm_url):
        """Test creating campaign requires authentication"""
        data = {
            "name": "Test Campaign",
            "type": "email",
        }
        response = requests.post(f"{crm_url}/api/crm/campaigns/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_campaign_detail_requires_auth(self, crm_url):
        """Test retrieving campaign detail requires authentication"""
        campaign_id = str(uuid.uuid4())
        response = requests.get(f"{crm_url}/api/crm/campaigns/{campaign_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_campaign_requires_auth(self, crm_url):
        """Test updating campaign requires authentication"""
        campaign_id = str(uuid.uuid4())
        data = {"name": "Updated Campaign"}
        response = requests.patch(
            f"{crm_url}/api/crm/campaigns/{campaign_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_campaign_requires_auth(self, crm_url):
        """Test deleting campaign requires authentication"""
        campaign_id = str(uuid.uuid4())
        response = requests.delete(f"{crm_url}/api/crm/campaigns/{campaign_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
