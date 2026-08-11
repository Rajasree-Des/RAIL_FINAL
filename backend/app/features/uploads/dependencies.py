"""Dependency injection for uploads feature."""

from app.features.uploads.service import UploadService


def get_upload_service() -> UploadService:
    return UploadService()
