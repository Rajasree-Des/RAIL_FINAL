from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.datasets.service import DatasetService
from app.features.uploads.dependencies import get_upload_service
from app.features.uploads.service import UploadService
from app.infrastructure.database.session import get_db_session


def get_dataset_service(
    session: AsyncSession = Depends(get_db_session),
    upload_service: UploadService = Depends(get_upload_service),
) -> DatasetService:
    return DatasetService(session, upload_service)
