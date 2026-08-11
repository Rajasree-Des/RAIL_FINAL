"""Report Configuration Engine tables

Revision ID: 003
Revises: 002
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ReportConfigTemplates - Master configuration entity
    op.create_table(
        "report_config_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_report_id", sa.String(64), nullable=True),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, server_default="false", index=True),
        sa.Column(
            "created_by",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # InputConfigurations - File input settings (1:1 with template)
    op.create_table(
        "input_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("accepted_file_types", sa.Text, nullable=True),
        sa.Column("required_sheets", sa.Text, nullable=True),
        sa.Column("header_row", sa.Integer, server_default="1"),
        sa.Column("validation_rules", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # TemplateColumnMappings - Column mapping rules (1:N with template)
    op.create_table(
        "template_column_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("source_column", sa.String(128), nullable=False),
        sa.Column("internal_field", sa.String(64), nullable=False),
        sa.Column("output_column", sa.String(128), nullable=False),
        sa.Column("data_type", sa.String(32), server_default="text"),
        sa.Column("is_required", sa.Boolean, server_default="false"),
        sa.Column("default_value", sa.String(256), nullable=True),
        sa.Column("transform", sa.String(32), server_default="none"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # SortingRules - Sorting configuration (1:N with template)
    op.create_table(
        "sorting_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("direction", sa.String(4), server_default="asc"),
        sa.Column("priority", sa.Integer, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # FilteringRules - Row filtering conditions (1:N with template)
    op.create_table(
        "filtering_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("operator", sa.String(32), nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("value_type", sa.String(16), server_default="string"),
        sa.Column("logic_group", sa.String(16), server_default="AND"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # RowRules - Row limiting rules (1:1 with template)
    op.create_table(
        "row_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("rule_type", sa.String(32), server_default="none"),
        sa.Column("limit_value", sa.Integer, nullable=True),
        sa.Column("limit_column", sa.String(128), nullable=True),
        sa.Column("custom_expression", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # HighlightRules - Conditional formatting (1:N with template)
    op.create_table(
        "highlight_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("condition_type", sa.String(32), nullable=False),
        sa.Column("condition_value", sa.Text, nullable=True),
        sa.Column("highlight_color", sa.String(7), server_default="'#FFFF00'"),
        sa.Column("text_color", sa.String(7), nullable=True),
        sa.Column("is_bold", sa.Boolean, server_default="false"),
        sa.Column("priority", sa.Integer, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # OutputConfigurations - Output format settings (1:1 with template)
    op.create_table(
        "output_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("excel_enabled", sa.Boolean, server_default="true"),
        sa.Column("excel_config", sa.Text, nullable=True),
        sa.Column("pdf_enabled", sa.Boolean, server_default="false"),
        sa.Column("pdf_config", sa.Text, nullable=True),
        sa.Column("ai_summary_enabled", sa.Boolean, server_default="false"),
        sa.Column("ai_config", sa.Text, nullable=True),
        sa.Column("whatsapp_enabled", sa.Boolean, server_default="false"),
        sa.Column("whatsapp_config", sa.Text, nullable=True),
        sa.Column("email_enabled", sa.Boolean, server_default="false"),
        sa.Column("email_config", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create additional indexes for common queries
    op.create_index(
        "ix_report_config_templates_enabled",
        "report_config_templates",
        ["is_enabled", "is_deleted"],
    )
    op.create_index(
        "ix_template_column_mappings_order",
        "template_column_mappings",
        ["template_id", "sort_order"],
    )
    op.create_index(
        "ix_sorting_rules_priority",
        "sorting_rules",
        ["template_id", "priority"],
    )
    op.create_index(
        "ix_highlight_rules_priority",
        "highlight_rules",
        ["template_id", "priority"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_highlight_rules_priority", table_name="highlight_rules")
    op.drop_index("ix_sorting_rules_priority", table_name="sorting_rules")
    op.drop_index("ix_template_column_mappings_order", table_name="template_column_mappings")
    op.drop_index("ix_report_config_templates_enabled", table_name="report_config_templates")

    # Drop tables in reverse order (child tables first)
    op.drop_table("output_configurations")
    op.drop_table("highlight_rules")
    op.drop_table("row_rules")
    op.drop_table("filtering_rules")
    op.drop_table("sorting_rules")
    op.drop_table("template_column_mappings")
    op.drop_table("input_configurations")
    op.drop_table("report_config_templates")
