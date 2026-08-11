from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Railway Report Automation Platform"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    environment: str = Field(default="development", description="development, staging, production")
    debug: bool = False

    # Database
    database_url: str = "postgresql://railway:railway@localhost:5432/railway"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security - JWT
    jwt_secret_key: str = Field(
        default="CHANGE-THIS-SECRET-KEY-IN-PRODUCTION-MIN-32-CHARS",
        description="Secret key for JWT signing - MUST be changed in production",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_refresh_token_expire_days_remember: int = 30

    # Security - Cookies
    cookie_secure: bool = Field(default=False, description="Set to True in production (HTTPS)")
    cookie_samesite: str = "strict"
    cookie_httponly: bool = True
    cookie_domain: str | None = None

    # Security - CSRF
    csrf_secret_key: str = Field(
        default="CHANGE-THIS-CSRF-SECRET-KEY-IN-PRODUCTION",
        description="Secret key for CSRF token generation",
    )

    # File Upload Security
    max_upload_size_mb: int = Field(default=50, description="Maximum file upload size in MB")
    allowed_file_extensions: list[str] = Field(
        default=[".xlsx", ".xls", ".csv"],
        description="Allowed file extensions for upload",
    )
    upload_directory: str = "uploads"

    # CORS
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # AI Summary Generator
    openai_api_key: str = Field(default="", description="OpenAI or compatible API key")
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    summary_max_dataset_rows: int = 50
    summary_max_input_rows: int = 10000
    summary_max_tokens: int = 2048
    summary_use_mock_llm: bool = Field(
        default=True,
        description="Use mock LLM when no API key is set (default True in development)",
    )

    # Automation Engine (standalone Playwright service)
    automation_engine_url: str = Field(
        default="http://127.0.0.1:8003",
        description="URL of the standalone automation-engine service",
    )
    automation_service_token: str = Field(
        default="dev-automation-service-token-change-in-production",
        description="Shared secret for backend ↔ automation-engine communication",
    )
    automation_encryption_key: str = Field(
        default="",
        description="Fernet key source for credential encryption (falls back to JWT secret)",
    )
    automation_downloads_dir: str = Field(
        default="downloads",
        description="Root directory for automation downloads",
    )

    # Dashboard
    dashboard_expected_minutes_default: int = Field(
        default=15,
        description="Default 'Expected Time' shown when no successful run history exists",
    )

    # Logging
    log_level: str = "INFO"

    # Default admin seed (set via .env only — no credentials in source)
    default_admin_username: str | None = Field(
        default=None,
        description="Username for the default admin account created on first startup",
    )
    default_admin_password: str | None = Field(
        default=None,
        description="Password for the default admin account (set via .env only)",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def enable_api_docs(self) -> bool:
        """Expose interactive API docs when DEBUG is enabled."""
        return self.debug


settings = Settings()
