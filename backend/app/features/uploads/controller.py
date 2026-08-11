import logging

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.security.rate_limit import rate_limit_upload
from app.domain.entities.user import User
from app.features.auth.dependencies import get_client_ip, require_officer_or_admin, validate_csrf_token
from app.features.uploads.dependencies import get_upload_service
from app.features.uploads.schemas import UploadResponse
from app.features.uploads.service import UploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(require_officer_or_admin),
    service: UploadService = Depends(get_upload_service),
    ip_address: str | None = Depends(get_client_ip),
    _csrf: None = Depends(validate_csrf_token),
    _rate_limit: None = Depends(rate_limit_upload),
) -> UploadResponse:
    if not file.filename:
        from app.core.exceptions import ValidationError

        raise ValidationError("Filename is required")

    content = await file.read()

    return await service.upload_file(
        filename=file.filename,
        content=content,
        content_type=file.content_type,
        user=user,
        ip_address=ip_address,
    )
