import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="refresh_tokens")

    @property
    def is_expired(self) -> bool:
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) > expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


class WorkflowModel(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    variant: Mapped[str] = mapped_column(String(32), nullable=False)
    icon: Mapped[str] = mapped_column(String(32), nullable=False)
    upload_label: Mapped[str | None] = mapped_column(String(128))
    report_source_id: Mapped[str | None] = mapped_column(String(64))
    accepted_files: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    settings: Mapped[list["WorkflowSettingModel"]] = relationship(
        "WorkflowSettingModel", back_populates="workflow", cascade="all, delete-orphan"
    )
    column_mappings: Mapped[list["ColumnMappingModel"]] = relationship(
        "ColumnMappingModel", back_populates="workflow", cascade="all, delete-orphan"
    )
    business_rules: Mapped[list["BusinessRuleModel"]] = relationship(
        "BusinessRuleModel", back_populates="workflow", cascade="all, delete-orphan"
    )
    templates: Mapped[list["ReportTemplateModel"]] = relationship(
        "ReportTemplateModel", back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowSettingModel(Base):
    __tablename__ = "workflow_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflows.id", ondelete="CASCADE")
    )
    setting_id: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    placeholder: Mapped[str | None] = mapped_column(String(256))
    default_value: Mapped[str | None] = mapped_column(Text)
    options_json: Mapped[str | None] = mapped_column(Text)
    help_text: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="settings")


class ColumnMappingModel(Base):
    __tablename__ = "column_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflows.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    column_type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    source_column: Mapped[str | None] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    workflow: Mapped["WorkflowModel"] = relationship(
        "WorkflowModel", back_populates="column_mappings"
    )


class BusinessRuleModel(Base):
    __tablename__ = "business_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflows.id", ondelete="CASCADE")
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="error")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    workflow: Mapped["WorkflowModel"] = relationship(
        "WorkflowModel", back_populates="business_rules"
    )


class ReportTemplateModel(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflows.id", ondelete="CASCADE")
    )
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), nullable=False)

    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="templates")


# =============================================================================
# Report Configuration Engine Models
# =============================================================================


class ReportConfigTemplateModel(Base):
    """Master configuration for a report type - the core entity of the config engine."""

    __tablename__ = "report_config_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_report_id: Mapped[str | None] = mapped_column(String(64))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    input_config: Mapped["InputConfigurationModel | None"] = relationship(
        "InputConfigurationModel",
        back_populates="template",
        uselist=False,
        cascade="all, delete-orphan",
    )
    column_mappings: Mapped[list["TemplateColumnMappingModel"]] = relationship(
        "TemplateColumnMappingModel",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateColumnMappingModel.sort_order",
    )
    sorting_rules: Mapped[list["SortingRuleModel"]] = relationship(
        "SortingRuleModel",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="SortingRuleModel.priority",
    )
    filtering_rules: Mapped[list["FilteringRuleModel"]] = relationship(
        "FilteringRuleModel",
        back_populates="template",
        cascade="all, delete-orphan",
    )
    row_rule: Mapped["RowRuleModel | None"] = relationship(
        "RowRuleModel",
        back_populates="template",
        uselist=False,
        cascade="all, delete-orphan",
    )
    highlight_rules: Mapped[list["HighlightRuleModel"]] = relationship(
        "HighlightRuleModel",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="HighlightRuleModel.priority",
    )
    output_config: Mapped["OutputConfigurationModel | None"] = relationship(
        "OutputConfigurationModel",
        back_populates="template",
        uselist=False,
        cascade="all, delete-orphan",
    )


class InputConfigurationModel(Base):
    """Define what files the report accepts and how to parse them."""

    __tablename__ = "input_configurations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    accepted_file_types: Mapped[str | None] = mapped_column(Text)
    required_sheets: Mapped[str | None] = mapped_column(Text)
    header_row: Mapped[int] = mapped_column(Integer, default=1)
    validation_rules: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="input_config"
    )


class TemplateColumnMappingModel(Base):
    """Map source data columns to internal fields and output columns."""

    __tablename__ = "template_column_mappings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_column: Mapped[str] = mapped_column(String(128), nullable=False)
    internal_field: Mapped[str] = mapped_column(String(64), nullable=False)
    output_column: Mapped[str] = mapped_column(String(128), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), default="text")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[str | None] = mapped_column(String(256))
    transform: Mapped[str] = mapped_column(String(32), default="none")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="column_mappings"
    )


class SortingRuleModel(Base):
    """Define how output data should be sorted."""

    __tablename__ = "sorting_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(4), default="asc")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="sorting_rules"
    )


class FilteringRuleModel(Base):
    """Define row filtering conditions."""

    __tablename__ = "filtering_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String(128), nullable=False)
    operator: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(16), default="string")
    logic_group: Mapped[str] = mapped_column(String(16), default="AND")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="filtering_rules"
    )


class RowRuleModel(Base):
    """Limit output rows (Top N, Bottom N, etc.)."""

    __tablename__ = "row_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(String(32), default="none")
    limit_value: Mapped[int | None] = mapped_column(Integer)
    limit_column: Mapped[str | None] = mapped_column(String(128))
    custom_expression: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="row_rule"
    )


class HighlightRuleModel(Base):
    """Conditional formatting for output."""

    __tablename__ = "highlight_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String(128), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_value: Mapped[str | None] = mapped_column(Text)
    highlight_color: Mapped[str] = mapped_column(String(7), default="#FFFF00")
    text_color: Mapped[str | None] = mapped_column(String(7))
    is_bold: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="highlight_rules"
    )


class OutputConfigurationModel(Base):
    """Define output formats and delivery options."""

    __tablename__ = "output_configurations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    excel_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    excel_config: Mapped[str | None] = mapped_column(Text)
    pdf_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pdf_config: Mapped[str | None] = mapped_column(Text)
    ai_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_config: Mapped[str | None] = mapped_column(Text)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_config: Mapped[str | None] = mapped_column(Text)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_config: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel"] = relationship(
        "ReportConfigTemplateModel", back_populates="output_config"
    )


# =============================================================================
# Business Rules Engine Models
# =============================================================================


class ConfigurableRuleModel(Base):
    """Enhanced business rule model for the configurable rules engine.
    
    Supports 8 rule categories: column, conditional, sorting, filter,
    top, highlight, calculation, merge.
    """

    __tablename__ = "configurable_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[str | None] = mapped_column(String(64), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    conditions_json: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template: Mapped["ReportConfigTemplateModel | None"] = relationship(
        "ReportConfigTemplateModel",
        foreign_keys=[template_id],
    )


# =============================================================================
# AI Summary Generator Models
# =============================================================================


class AiPromptTemplateModel(Base):
    """Configurable prompt templates for AI summary generation."""

    __tablename__ = "ai_prompt_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    summary_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String(32), default="markdown")
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_config_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GeneratedSummaryModel(Base):
    """Persisted AI or deterministic daily briefing summary output."""

    __tablename__ = "generated_summaries"
    __table_args__ = (
        Index("ix_generated_summaries_created_by_run", "created_by", "run_id"),
        Index("ix_generated_summaries_created_by_created", "created_by", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    prompt_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_prompt_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[str | None] = mapped_column(Text)
    statistics_json: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(64))
    token_usage_json: Mapped[str | None] = mapped_column(Text)
    generation_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    error_message: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("automation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# =============================================================================
# Application Settings (schema-driven, centralized configuration)
# =============================================================================


class AppSettingDefinitionModel(Base):
    """Metadata for a configurable application setting."""

    __tablename__ = "app_setting_definitions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False)
    default_value: Mapped[str] = mapped_column(Text, nullable=False, default="null")
    validation_json: Mapped[str | None] = mapped_column(Text)
    options_json: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    value: Mapped["AppSettingValueModel | None"] = relationship(
        "AppSettingValueModel",
        back_populates="definition",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AppSettingValueModel(Base):
    """Stored value override for a setting definition."""

    __tablename__ = "app_setting_values"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    definition_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("app_setting_definitions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    definition: Mapped["AppSettingDefinitionModel"] = relationship(
        "AppSettingDefinitionModel", back_populates="value"
    )


# =============================================================================
# Automation Engine (orchestration — Playwright runs in separate service)
# =============================================================================


class AutomationProfileModel(Base):
    """Configurable automation profile for portal downloads."""

    __tablename__ = "automation_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    portal_url: Mapped[str] = mapped_column(String(512), nullable=False)
    username_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    download_folder: Mapped[str] = mapped_column(String(512), default="downloads/railmadad")
    browser: Mapped[str] = mapped_column(String(32), default="chromium")
    headless: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=60000)
    retry_count: Mapped[int] = mapped_column(Integer, default=3)
    delay_seconds: Mapped[int] = mapped_column(Integer, default=5)
    report_sequence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    session_state_encrypted: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list["AutomationRunModel"]] = relationship(
        "AutomationRunModel", back_populates="profile"
    )


class AutomationRunModel(Base):
    """A single automation execution run."""

    __tablename__ = "automation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("automation_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    current_report_index: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    profile: Mapped["AutomationProfileModel"] = relationship(
        "AutomationProfileModel", back_populates="runs"
    )
    logs: Mapped[list["AutomationLogModel"]] = relationship(
        "AutomationLogModel", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["AutomationArtifactModel"]] = relationship(
        "AutomationArtifactModel", back_populates="run", cascade="all, delete-orphan"
    )


class AutomationLogModel(Base):
    """Structured log entry for an automation run."""

    __tablename__ = "automation_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("automation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    run: Mapped["AutomationRunModel"] = relationship(
        "AutomationRunModel", back_populates="logs"
    )


class AutomationArtifactModel(Base):
    """Downloaded files and failure screenshots."""

    __tablename__ = "automation_artifacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("automation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    report_name: Mapped[str | None] = mapped_column(String(128))
    report_slug: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["AutomationRunModel"] = relationship(
        "AutomationRunModel", back_populates="artifacts"
    )


class ReportDatasetModel(Base):
    """Cached metadata for original RailMadad source datasets per report."""

    __tablename__ = "report_datasets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    report_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(256), nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(String(1024))
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    header_row: Mapped[int] = mapped_column(Integer, default=1)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserActivityModel(Base):
    """Per-user activity feed entries (account-scoped, never secrets)."""

    __tablename__ = "user_activity"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_user_activity_dedupe"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    report_slug: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
