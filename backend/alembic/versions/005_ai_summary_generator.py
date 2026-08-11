"""AI Summary Generator - ai_prompt_templates and generated_summaries

Revision ID: 005
Revises: 004
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("summary_type", sa.String(32), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_prompt_template", sa.Text, nullable=False),
        sa.Column("output_format", sa.String(32), server_default="markdown"),
        sa.Column("max_tokens", sa.Integer, server_default="1024"),
        sa.Column("temperature", sa.Float, server_default="0.3"),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("is_default", sa.Boolean, server_default="false", index=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
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

    op.create_index(
        "ix_ai_prompt_templates_type_enabled",
        "ai_prompt_templates",
        ["summary_type", "is_enabled"],
    )
    op.create_index(
        "ix_ai_prompt_templates_default_type",
        "ai_prompt_templates",
        ["is_default", "summary_type"],
    )

    op.create_table(
        "generated_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "prompt_template_id",
            sa.String(36),
            sa.ForeignKey("ai_prompt_templates.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("summary_type", sa.String(32), nullable=False, index=True),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("statistics_json", sa.Text, nullable=True),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("token_usage_json", sa.Text, nullable=True),
        sa.Column("generation_time_ms", sa.Float, nullable=True),
        sa.Column("status", sa.String(16), server_default="completed"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("generated_summaries")
    op.drop_index("ix_ai_prompt_templates_default_type", table_name="ai_prompt_templates")
    op.drop_index("ix_ai_prompt_templates_type_enabled", table_name="ai_prompt_templates")
    op.drop_table("ai_prompt_templates")
