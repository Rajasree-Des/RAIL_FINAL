from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    size: int
    content_type: str | None
    uploaded_at: datetime
    uploaded_by: str


class UploadListResponse(BaseModel):
    uploads: list[UploadResponse]
    total: int
