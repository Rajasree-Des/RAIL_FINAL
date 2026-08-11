from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.workflow_repository import IWorkflowRepository
from app.features.workflows.repository import WorkflowRepository
from app.features.workflows.service import WorkflowService
from app.infrastructure.database.session import get_db_session


def get_workflow_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IWorkflowRepository:
    return WorkflowRepository(session)


def get_workflow_service(
    repository: IWorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowService:
    return WorkflowService(repository)
