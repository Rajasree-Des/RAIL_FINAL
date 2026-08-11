import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflows.repository import WorkflowRepository
from app.infrastructure.database.models import WorkflowModel


@pytest.fixture
async def repository(test_session: AsyncSession):
    return WorkflowRepository(test_session)


@pytest.fixture
async def seed_workflows(test_session: AsyncSession):
    workflows = [
        WorkflowModel(
            id="workflow-1",
            name="First Workflow",
            order=1,
            description="Description 1",
            variant="merge",
            icon="Layers",
            accepted_files=".xlsx",
        ),
        WorkflowModel(
            id="workflow-2",
            name="Second Workflow",
            order=2,
            description="Description 2",
            variant="report",
            icon="FileCheck",
            accepted_files=".csv",
        ),
    ]
    test_session.add_all(workflows)
    await test_session.commit()
    return workflows


async def test_list_all_empty(repository: WorkflowRepository):
    result = await repository.list_all()
    assert result == []


async def test_list_all_with_data(
    repository: WorkflowRepository, seed_workflows
):
    result = await repository.list_all()
    assert len(result) == 2
    assert result[0].id == "workflow-1"
    assert result[1].id == "workflow-2"


async def test_list_all_ordered(
    repository: WorkflowRepository, seed_workflows
):
    result = await repository.list_all()
    assert result[0].order < result[1].order


async def test_get_by_id_found(
    repository: WorkflowRepository, seed_workflows
):
    result = await repository.get_by_id("workflow-1")
    assert result is not None
    assert result.id == "workflow-1"
    assert result.name == "First Workflow"


async def test_get_by_id_not_found(repository: WorkflowRepository):
    result = await repository.get_by_id("nonexistent")
    assert result is None


async def test_entity_conversion(
    repository: WorkflowRepository, seed_workflows
):
    result = await repository.get_by_id("workflow-1")
    assert result is not None
    assert result.accepted_files == (".xlsx",)
    assert result.variant == "merge"
