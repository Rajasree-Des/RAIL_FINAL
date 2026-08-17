"""In-process browser automation configuration from environment variables."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AutomationConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    chrome_debug_url: str = Field(
        default="http://127.0.0.1:9222",
        description="Chrome DevTools Protocol endpoint for attach mode",
    )
    download_folder: str = Field(
        default="downloads",
        description="Directory for downloaded reports",
    )
    timeout: int = Field(
        default=300,
        ge=1,
        description="Operation timeout in seconds",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        description="Number of retries for failed operations",
    )
    railmadad_url: str = Field(
        default="https://railmadad.indianrail.gov.in",
        description="RailMadad portal base URL",
    )
    screenshots_dir: str = Field(
        default="storage/automation-screenshots",
        description="Directory for automation failure screenshots",
    )
    debug_screenshots_dir: str = Field(
        default="storage/debug",
        description="Directory for Phase 4 debug verification screenshots",
    )
    downloads_dir: str = Field(
        default="storage/downloads/report1",
        validation_alias=AliasChoices("DOWNLOAD_DIR", "DOWNLOADS_DIR"),
        description="Project download directory (never system Downloads folder)",
    )
    filter_interaction_delay_ms: int = Field(
        default=80,
        ge=0,
        description="Delay between filter field interactions in milliseconds",
    )
    date_format: str = Field(
        default="%d/%m/%Y",
        description="strftime format for portal date fields",
    )
    pdf_archive_dir: str = Field(
        default="storage/downloads",
        validation_alias=AliasChoices("PDF_ARCHIVE_DIR"),
        description="Base directory for archived PDFs",
    )
    extracted_data_dir: str = Field(
        default="storage/extracted",
        validation_alias=AliasChoices("EXTRACTED_DATA_DIR"),
        description="Directory for extracted HTML/CSV data",
    )
    output_excel_dir: str = Field(
        default="storage/output/excel",
        validation_alias=AliasChoices("OUTPUT_EXCEL_DIR"),
        description="Directory for processed Excel output",
    )
    output_pdf_dir: str = Field(
        default="storage/output/pdf",
        validation_alias=AliasChoices("OUTPUT_PDF_DIR"),
        description="Directory for processed PDF output",
    )
    railmadad_normal_load_timeout: float = Field(
        default=20.0,
        ge=1.0,
        validation_alias=AliasChoices("RAILMADAD_NORMAL_LOAD_TIMEOUT"),
        description="Normal adaptive wait before entering slow-load extension (seconds)",
    )
    railmadad_slow_load_timeout: float = Field(
        default=70.0,
        ge=1.0,
        validation_alias=AliasChoices("RAILMADAD_SLOW_LOAD_TIMEOUT"),
        description="Maximum total adaptive wait for slow RailMadad data loads (seconds)",
    )
    railmadad_poll_interval_ms: int = Field(
        default=500,
        ge=100,
        le=2000,
        validation_alias=AliasChoices("RAILMADAD_POLL_INTERVAL_MS"),
        description="Poll interval for adaptive RailMadad result waits (milliseconds)",
    )
    railmadad_stability_interval_ms: int = Field(
        default=750,
        ge=200,
        le=2000,
        validation_alias=AliasChoices("RAILMADAD_STABILITY_INTERVAL_MS"),
        description="Pause between fingerprint reads for table stability (milliseconds)",
    )


config = AutomationConfig()
