from abc import ABC, abstractmethod

from app.domain.entities.workflow import Workflow


class IWorkflowRepository(ABC):
    @abstractmethod
    async def list_all(self) -> list[Workflow]:
        ...

    @abstractmethod
    async def get_by_id(self, workflow_id: str) -> Workflow | None:
        ...
