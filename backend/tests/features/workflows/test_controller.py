import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import WorkflowModel


@pytest.fixture
async def seed_workflow(test_session: AsyncSession):
    workflow = WorkflowModel(
        id="test-workflow",
        name="Test Workflow",
        order=1,
        description="Test description",
        variant="report",
        icon="FileCheck",
        accepted_files=".xlsx,.csv",
    )
    test_session.add(workflow)
    await test_session.commit()
    return workflow


async def test_list_workflows_empty(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert data["workflows"] == []


async def test_list_workflows_with_data(authenticated_client: AsyncClient, seed_workflow):
    response = await authenticated_client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert len(data["workflows"]) == 1
    assert data["workflows"][0]["id"] == "test-workflow"
    assert data["workflows"][0]["name"] == "Test Workflow"


async def test_get_workflow_by_id(authenticated_client: AsyncClient, seed_workflow):
    response = await authenticated_client.get("/api/v1/workflows/test-workflow")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-workflow"
    assert data["variant"] == "report"


async def test_get_workflow_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/workflows/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"


async def test_get_workflow_invalid_id(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/workflows/Invalid_ID!")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"


async def test_list_workflows_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/workflows")
    assert response.status_code == 401
