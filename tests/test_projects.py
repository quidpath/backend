"""
Test suite for Projects Service
Tests Projects, Tasks, Sprints, Time Logs, Issues
"""
import uuid

import pytest
import requests
from rest_framework import status


@pytest.mark.django_db
class TestProjectEndpoints:
    """Test Project CRUD endpoints"""

    def test_list_projects_requires_auth(self, projects_url):
        """Test listing projects requires authentication"""
        response = requests.get(f"{projects_url}/api/projects/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_project_requires_auth(self, projects_url):
        """Test creating project requires authentication"""
        data = {
            "name": "Test Project",
            "description": "Test Description",
        }
        response = requests.post(f"{projects_url}/api/projects/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_project_detail_requires_auth(self, projects_url):
        """Test retrieving project detail requires authentication"""
        project_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/projects/{project_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_project_requires_auth(self, projects_url):
        """Test updating project requires authentication"""
        project_id = str(uuid.uuid4())
        data = {"name": "Updated Project"}
        response = requests.patch(
            f"{projects_url}/api/projects/{project_id}/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_project_requires_auth(self, projects_url):
        """Test deleting project requires authentication"""
        project_id = str(uuid.uuid4())
        response = requests.delete(f"{projects_url}/api/projects/{project_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestProjectMemberEndpoints:
    """Test Project Member endpoints"""

    def test_list_project_members_requires_auth(self, projects_url):
        """Test listing project members requires authentication"""
        project_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/projects/{project_id}/members/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_add_project_member_requires_auth(self, projects_url):
        """Test adding project member requires authentication"""
        project_id = str(uuid.uuid4())
        data = {"user_id": str(uuid.uuid4()), "role": "developer"}
        response = requests.post(
            f"{projects_url}/api/projects/{project_id}/members/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTaskEndpoints:
    """Test Task CRUD endpoints"""

    def test_list_tasks_requires_auth(self, projects_url):
        """Test listing tasks requires authentication"""
        response = requests.get(f"{projects_url}/api/tasks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_task_requires_auth(self, projects_url):
        """Test creating task requires authentication"""
        data = {
            "title": "Test Task",
            "project_id": str(uuid.uuid4()),
        }
        response = requests.post(f"{projects_url}/api/tasks/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_task_detail_requires_auth(self, projects_url):
        """Test retrieving task detail requires authentication"""
        task_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/tasks/{task_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_task_requires_auth(self, projects_url):
        """Test updating task requires authentication"""
        task_id = str(uuid.uuid4())
        data = {"title": "Updated Task"}
        response = requests.patch(f"{projects_url}/api/tasks/{task_id}/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_task_requires_auth(self, projects_url):
        """Test deleting task requires authentication"""
        task_id = str(uuid.uuid4())
        response = requests.delete(f"{projects_url}/api/tasks/{task_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTaskAssignmentEndpoints:
    """Test Task Assignment endpoints"""

    def test_list_task_assignments_requires_auth(self, projects_url):
        """Test listing task assignments requires authentication"""
        task_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/tasks/{task_id}/assignments/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_assign_task_requires_auth(self, projects_url):
        """Test assigning task requires authentication"""
        task_id = str(uuid.uuid4())
        data = {"user_id": str(uuid.uuid4())}
        response = requests.post(
            f"{projects_url}/api/tasks/{task_id}/assignments/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTaskDependencyEndpoints:
    """Test Task Dependency endpoints"""

    def test_list_task_dependencies_requires_auth(self, projects_url):
        """Test listing task dependencies requires authentication"""
        task_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/tasks/{task_id}/dependencies/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_add_task_dependency_requires_auth(self, projects_url):
        """Test adding task dependency requires authentication"""
        task_id = str(uuid.uuid4())
        data = {"depends_on_task_id": str(uuid.uuid4())}
        response = requests.post(
            f"{projects_url}/api/tasks/{task_id}/dependencies/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestSprintEndpoints:
    """Test Sprint endpoints"""

    def test_list_sprints_requires_auth(self, projects_url):
        """Test listing sprints requires authentication"""
        response = requests.get(f"{projects_url}/api/projects/sprints/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_sprint_requires_auth(self, projects_url):
        """Test creating sprint requires authentication"""
        data = {
            "name": "Sprint 1",
            "project_id": str(uuid.uuid4()),
            "start_date": "2026-04-01",
            "end_date": "2026-04-14",
        }
        response = requests.post(f"{projects_url}/api/projects/sprints/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMilestoneEndpoints:
    """Test Milestone endpoints"""

    def test_list_milestones_requires_auth(self, projects_url):
        """Test listing milestones requires authentication"""
        response = requests.get(f"{projects_url}/api/projects/milestones/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_milestone_requires_auth(self, projects_url):
        """Test creating milestone requires authentication"""
        data = {
            "name": "Milestone 1",
            "project_id": str(uuid.uuid4()),
            "due_date": "2026-05-01",
        }
        response = requests.post(f"{projects_url}/api/projects/milestones/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTimeEntryEndpoints:
    """Test Time Entry endpoints"""

    def test_list_time_entries_requires_auth(self, projects_url):
        """Test listing time entries requires authentication"""
        response = requests.get(f"{projects_url}/api/timelog/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_time_entry_requires_auth(self, projects_url):
        """Test creating time entry requires authentication"""
        data = {
            "task_id": str(uuid.uuid4()),
            "hours": "2.5",
            "date": "2026-04-04",
        }
        response = requests.post(f"{projects_url}/api/timelog/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestIssueEndpoints:
    """Test Issue endpoints"""

    def test_list_issues_requires_auth(self, projects_url):
        """Test listing issues requires authentication"""
        response = requests.get(f"{projects_url}/api/issues/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_issue_requires_auth(self, projects_url):
        """Test creating issue requires authentication"""
        data = {
            "title": "Test Issue",
            "project_id": str(uuid.uuid4()),
            "type": "bug",
        }
        response = requests.post(f"{projects_url}/api/issues/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_issue_detail_requires_auth(self, projects_url):
        """Test retrieving issue detail requires authentication"""
        issue_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/issues/{issue_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_issue_requires_auth(self, projects_url):
        """Test updating issue requires authentication"""
        issue_id = str(uuid.uuid4())
        data = {"title": "Updated Issue"}
        response = requests.patch(f"{projects_url}/api/issues/{issue_id}/", json=data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_issue_requires_auth(self, projects_url):
        """Test deleting issue requires authentication"""
        issue_id = str(uuid.uuid4())
        response = requests.delete(f"{projects_url}/api/issues/{issue_id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestIssueCommentEndpoints:
    """Test Issue Comment endpoints"""

    def test_list_issue_comments_requires_auth(self, projects_url):
        """Test listing issue comments requires authentication"""
        issue_id = str(uuid.uuid4())
        response = requests.get(f"{projects_url}/api/issues/{issue_id}/comments/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_issue_comment_requires_auth(self, projects_url):
        """Test creating issue comment requires authentication"""
        issue_id = str(uuid.uuid4())
        data = {"content": "Test comment"}
        response = requests.post(
            f"{projects_url}/api/issues/{issue_id}/comments/", json=data
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
