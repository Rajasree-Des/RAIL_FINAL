"""Automation engine configuration — secrets from environment only."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    host: str = "0.0.0.0"
    port: int = 8003
    service_token: str = Field(
        default="dev-automation-service-token-change-in-production",
        description="Bearer token for internal API",
    )
    backend_url: str = "http://127.0.0.1:8000"
    backend_api_prefix: str = "/api/v1"
    downloads_root: str = "downloads"
    screenshots_dir: str = "screenshots"
    sessions_dir: str = "sessions"
    demo_mode: bool = Field(
        default=True,
        description="Use demo download flow when portal unavailable",
    )
    log_level: str = "INFO"
    encryption_key: str = Field(
        default="",
        description="Key for encrypting session storage files",
    )


settings = EngineSettings()
