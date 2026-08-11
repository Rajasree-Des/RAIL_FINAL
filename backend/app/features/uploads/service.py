import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.audit import audit_logger
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.security.file_validator import file_validator
from app.domain.entities.user import User
from app.features.uploads.schemas import UploadResponse

logger = logging.getLogger(__name__)


class UploadService:
    def __init__(self) -> None:
        self._upload_dir = Path(settings.upload_directory)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_file(
        self,
        filename: str,
        content: bytes,
        content_type: str | None,
        user: User,
        ip_address: str | None,
    ) -> UploadResponse:
        logger.info("Upload attempt: %s by user %s", filename, user.username)

        try:
            safe_filename = file_validator.validate_upload(
                filename=filename,
                size=len(content),
                content_type=content_type,
            )
        except ValidationError as e:
            audit_logger.log_upload(
                user_id=user.id,
                username=user.username,
                filename=filename,
                file_size=len(content),
                ip_address=ip_address,
                success=False,
                rejection_reason=str(e.message),
            )
            raise

        file_id = str(uuid.uuid4())
        ext = Path(safe_filename).suffix
        stored_filename = f"{file_id}{ext}"
        file_path = self._upload_dir / stored_filename

        try:
            file_path.write_bytes(content)
        except OSError as e:
            logger.error("Failed to write file: %s", e)
            raise ValidationError("Failed to save uploaded file") from e

        audit_logger.log_upload(
            user_id=user.id,
            username=user.username,
            filename=filename,
            file_size=len(content),
            ip_address=ip_address,
            success=True,
        )

        return UploadResponse(
            id=file_id,
            filename=stored_filename,
            original_filename=safe_filename,
            size=len(content),
            content_type=content_type,
            uploaded_at=datetime.now(UTC),
            uploaded_by=user.username,
        )

    async def get_file_path(self, file_id: str, extension: str) -> Path:
        if ".." in file_id or "/" in file_id or "\\" in file_id:
            raise ValidationError("Invalid file ID")

        file_path = (self._upload_dir / f"{file_id}{extension}").resolve()

        if not str(file_path).startswith(str(self._upload_dir.resolve())):
            raise ValidationError("Invalid file path")

        if not file_path.exists():
            raise ValidationError("File not found")

        return file_path

    async def delete_file(self, file_id: str, extension: str) -> None:
        file_path = await self.get_file_path(file_id, extension)

        try:
            os.remove(file_path)
        except OSError as e:
            logger.error("Failed to delete file: %s", e)
            raise ValidationError("Failed to delete file") from e
