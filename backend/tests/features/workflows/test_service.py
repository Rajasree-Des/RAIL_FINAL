from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.workflow import Workflow
from app.features.workflows.service import WorkflowService


@pytest.fixture
def mock_repository():
    return AsyncMock()


@pytest.fixture
def workflow_service(mock_repository):
    return WorkflowService(mock_repository)


def create_test_workflow(id: str = "test-workflow") -> Workflow:
    return Workflow(
        id=id,
        name="Test Workflow",
        order=1,
        description="Test description",
        variant="report",
        icon="FileCheck",
        upload_label="Test Upload",
        report_source_id="test",
        accepted_files=(".xlsx", ".csv"),
        settings=(),
        column_mappings=(),
        business_rules=(),
        templates=(),
    )


async def test_list_workflows(workflow_service, mock_repository):
    mock_repository.list_all.return_value = [create_test_workflow()]

    result = await workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "test-workflow"
    mock_repository.list_all.assert_called_once()


async def test_get_workflow_success(workflow_service, mock_repository):
    mock_repository.get_by_id.return_value = create_test_workflow()

    result = await workflow_service.get_workflow("test-workflow")

    assert result.id == "test-workflow"
    mock_repository.get_by_id.assert_called_once_with("test-workflow")


async def test_get_workflow_not_found(workflow_service, mock_repository):
    mock_repository.get_by_id.return_value = None

    with pytest.raises(NotFoundError) as exc_info:
        await workflow_service.get_workflow("nonexistent")

    assert exc_info.value.resource == "Workflow"
    assert exc_info.value.identifier == "nonexistent"


async def test_get_workflow_invalid_id(workflow_service):
    with pytest.raises(ValidationError) as exc_info:
        await workflow_service.get_workflow("Invalid_ID!")

    assert exc_info.value.field == "workflow_id"
