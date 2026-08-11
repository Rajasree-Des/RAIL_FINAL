"""Pydantic schemas for application settings API."""

from typing import Any

from pydantic import BaseModel, Field


class SettingOptionSchema(BaseModel):
    label: str
    value: Any


class SettingItemSchema(BaseModel):
    id: str
    category: str
    key: str
    label: str
    description: str | None = None
    value_type: str
    value: Any
    default_value: Any
    validation: dict[str, Any] | None = None
    options: list[SettingOptionSchema] | None = None
    sort_order: int
    is_editable: bool
    is_modified: bool = False


class SettingCategorySchema(BaseModel):
    slug: str
    label: str
    description: str | None = None
    settings: list[SettingItemSchema]


class SettingsResponse(BaseModel):
    version: str = "1.0"
    categories: list[SettingCategorySchema]
    total: int


class SettingUpdateItem(BaseModel):
    category: str = Field(..., min_length=1, max_length=32)
    key: str = Field(..., min_length=1, max_length=64)
    value: Any


class SettingsUpdateRequest(BaseModel):
    settings: list[SettingUpdateItem]


class SettingsUpdateResponse(BaseModel):
    updated: int
    settings: list[SettingItemSchema]


class SettingsImportRequest(BaseModel):
    version: str = "1.0"
    settings: dict[str, Any] = Field(
        ...,
        description="Map of 'category.key' to value",
    )
    merge: bool = True


class SettingsImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class SettingsExportResponse(BaseModel):
    version: str = "1.0"
    exported_at: str
    settings: dict[str, Any]


class DisplaySettingsResponse(BaseModel):
    """Resolved display/notification preferences for any signed-in user."""

    organization_name: str = "South Central Railway"
    timezone: str = "Asia/Kolkata"
    date_format: str = "DD/MM/YYYY"
    time_format: str = "12h"
    default_page_size: int = 50
    enable_notifications: bool = True
    notify_on_completion: bool = True
    notify_on_failure: bool = True
    notification_sound: bool = False
