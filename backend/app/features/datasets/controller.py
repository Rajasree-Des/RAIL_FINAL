from fastapi import APIRouter, Depends

from app.domain.entities.user import User
from app.features.auth.dependencies import get_current_active_user, require_officer_or_admin, validate_csrf_token
from app.features.datasets.dependencies import get_dataset_service
from app.features.datasets.schemas import DatasetMetadataResponse, IngestDatasetRequest
from app.features.datasets.service import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/{report_id}/metadata", response_model=DatasetMetadataResponse)
async def get_dataset_metadata(
    report_id: str,
    service: DatasetService = Depends(get_dataset_service),
    _user: User = Depends(get_current_active_user),
) -> DatasetMetadataResponse:
    return await service.get_metadata(report_id)


@router.post("/{report_id}/ingest", response_model=DatasetMetadataResponse)
async def ingest_dataset(
    report_id: str,
    body: IngestDatasetRequest,
    service: DatasetService = Depends(get_dataset_service),
    _user: User = Depends(require_officer_or_admin),
    _csrf: None = Depends(validate_csrf_token),
) -> DatasetMetadataResponse:
    return await service.ingest_upload(
        report_id,
        upload_id=body.upload_id,
        header_row=body.header_row,
        sheet_name=body.sheet_name,
    )
