"""
Test suite for HRM Service
Tests Employees, Departments, Attendance, Leaves, Payroll, Recruitment
"""
import uuid

import pytest
import requests
from rest_framework import status


@pytest.mark.django_db
class TestEmployeeEndpoints:
    """Test Employee CRUD endpoints"""

    def test_list_employees_requires_auth(self, hrm_url):
        """Test listing employees requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/employees/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_employee_requires_auth(self, hrm_url):
        """Test creating employee requires authentication"""
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@test.com",
            "employee_number": "EMP001",
        }
        response = requests.post(f"{hrm_url}/api/hrm/employees/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_employee_detail_requires_auth(self, hrm_url):
        """Test retrieving employee detail requires authentication"""
        employee_id = str(uuid.uuid4())
        response = requests.get(f"{hrm_url}/api/hrm/employees/{employee_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_employee_requires_auth(self, hrm_url):
        """Test updating employee requires authentication"""
        employee_id = str(uuid.uuid4())
        data = {"first_name": "Jane"}
        response = requests.patch(
            f"{hrm_url}/api/hrm/employees/{employee_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_employee_requires_auth(self, hrm_url):
        """Test deleting employee requires authentication"""
        employee_id = str(uuid.uuid4())
        response = requests.delete(f"{hrm_url}/api/hrm/employees/{employee_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestDepartmentEndpoints:
    """Test Department endpoints"""

    def test_list_departments_requires_auth(self, hrm_url):
        """Test listing departments requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/org/departments/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_department_requires_auth(self, hrm_url):
        """Test creating department requires authentication"""
        data = {"name": "Engineering"}
        response = requests.post(f"{hrm_url}/api/hrm/org/departments/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPositionEndpoints:
    """Test Position endpoints"""

    def test_list_positions_requires_auth(self, hrm_url):
        """Test listing positions requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/org/positions/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_position_requires_auth(self, hrm_url):
        """Test creating position requires authentication"""
        data = {
            "title": "Software Engineer",
            "department_id": str(uuid.uuid4()),
        }
        response = requests.post(f"{hrm_url}/api/hrm/org/positions/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAttendanceEndpoints:
    """Test Attendance endpoints"""

    def test_list_attendance_requires_auth(self, hrm_url):
        """Test listing attendance requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/attendance/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_attendance_requires_auth(self, hrm_url):
        """Test creating attendance record requires authentication"""
        data = {
            "employee_id": str(uuid.uuid4()),
            "date": "2026-04-04",
            "check_in": "09:00:00",
            "check_out": "17:00:00",
        }
        response = requests.post(f"{hrm_url}/api/hrm/attendance/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLeaveEndpoints:
    """Test Leave endpoints"""

    def test_list_leaves_requires_auth(self, hrm_url):
        """Test listing leaves requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/leaves/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_leave_requires_auth(self, hrm_url):
        """Test creating leave requires authentication"""
        data = {
            "employee_id": str(uuid.uuid4()),
            "leave_type": "annual",
            "start_date": "2026-04-10",
            "end_date": "2026-04-15",
        }
        response = requests.post(f"{hrm_url}/api/hrm/leaves/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLeaveRequestEndpoints:
    """Test Leave Request endpoints"""

    def test_list_leave_requests_requires_auth(self, hrm_url):
        """Test listing leave requests requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/leaves/requests/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_leave_request_requires_auth(self, hrm_url):
        """Test creating leave request requires authentication"""
        data = {
            "leave_type": "sick",
            "start_date": "2026-04-05",
            "end_date": "2026-04-06",
            "reason": "Medical appointment",
        }
        response = requests.post(f"{hrm_url}/api/hrm/leaves/requests/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_approve_leave_request_requires_auth(self, hrm_url):
        """Test approving leave request requires authentication"""
        request_id = str(uuid.uuid4())
        response = requests.post(
            f"{hrm_url}/api/hrm/leaves/requests/{request_id}/approve/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPayrollStructureEndpoints:
    """Test Payroll Structure endpoints"""

    def test_list_payroll_structures_requires_auth(self, hrm_url):
        """Test listing payroll structures requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/payroll/structures/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_payroll_structure_requires_auth(self, hrm_url):
        """Test creating payroll structure requires authentication"""
        data = {
            "name": "Standard Payroll",
            "pay_frequency": "monthly",
        }
        response = requests.post(f"{hrm_url}/api/hrm/payroll/structures/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPayslipEndpoints:
    """Test Payslip endpoints"""

    def test_list_payslips_requires_auth(self, hrm_url):
        """Test listing payslips requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/payroll/payslips/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_payslip_requires_auth(self, hrm_url):
        """Test creating payslip requires authentication"""
        data = {
            "employee_id": str(uuid.uuid4()),
            "period_start": "2026-04-01",
            "period_end": "2026-04-30",
            "gross_salary": "50000.00",
        }
        response = requests.post(f"{hrm_url}/api/hrm/payroll/payslips/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_payslip_detail_requires_auth(self, hrm_url):
        """Test retrieving payslip detail requires authentication"""
        payslip_id = str(uuid.uuid4())
        response = requests.get(f"{hrm_url}/api/hrm/payroll/payslips/{payslip_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestJobPostingEndpoints:
    """Test Job Posting endpoints"""

    def test_list_jobs_requires_auth(self, hrm_url):
        """Test listing job postings requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/recruitment/jobs/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_job_requires_auth(self, hrm_url):
        """Test creating job posting requires authentication"""
        data = {
            "title": "Software Engineer",
            "department_id": str(uuid.uuid4()),
            "description": "We are hiring",
        }
        response = requests.post(f"{hrm_url}/api/hrm/recruitment/jobs/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestJobApplicationEndpoints:
    """Test Job Application endpoints"""

    def test_list_applications_requires_auth(self, hrm_url):
        """Test listing job applications requires authentication"""
        response = requests.get(f"{hrm_url}/api/hrm/recruitment/applications/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_application_requires_auth(self, hrm_url):
        """Test creating job application requires authentication"""
        data = {
            "job_id": str(uuid.uuid4()),
            "applicant_name": "John Doe",
            "applicant_email": "john@test.com",
        }
        response = requests.post(
            f"{hrm_url}/api/hrm/recruitment/applications/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
