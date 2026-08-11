import logging

from fastapi import APIRouter, Depends

from app.domain.entities.user import User
from app.features.auth.dependencies import get_current_active_user
from app.features.workflows.dependencies import get_workflow_service
from app.features.workflows.schemas import WorkflowListResponse, WorkflowResponse
from app.features.workflows.service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    service: WorkflowService = Depends(get_workflow_service),
    user: User = Depends(get_current_active_user),
) -> WorkflowListResponse:
    workflows = await service.list_workflows()
    return WorkflowListResponse(workflows=workflows)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    user: User = Depends(get_current_active_user),
) -> WorkflowResponse:
    return await service.get_workflow(workflow_id)
