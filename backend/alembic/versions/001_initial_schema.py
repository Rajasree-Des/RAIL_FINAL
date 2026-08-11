"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-04

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("order", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("variant", sa.String(32), nullable=False),
        sa.Column("icon", sa.String(32), nullable=False),
        sa.Column("upload_label", sa.String(128)),
        sa.Column("report_source_id", sa.String(64)),
        sa.Column("accepted_files", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "workflow_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflows.id", ondelete="CASCADE")),
        sa.Column("setting_id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("required", sa.Boolean, default=False),
        sa.Column("placeholder", sa.String(256)),
        sa.Column("default_value", sa.Text),
        sa.Column("options_json", sa.Text),
        sa.Column("help_text", sa.Text),
        sa.Column("sort_order", sa.Integer, default=0),
    )

    op.create_table(
        "column_mappings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflows.id", ondelete="CASCADE")),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("column_type", sa.String(32), nullable=False),
        sa.Column("required", sa.Boolean, default=False),
        sa.Column("source_column", sa.String(128)),
        sa.Column("sort_order", sa.Integer, default=0),
    )

    op.create_table(
        "business_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflows.id", ondelete="CASCADE")),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("rule_type", sa.String(64), nullable=False),
        sa.Column("expression", sa.Text, nullable=False),
        sa.Column("severity", sa.String(16), default="error"),
        sa.Column("enabled", sa.Boolean, default=True),
    )

    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.String(64), sa.ForeignKey("workflows.id", ondelete="CASCADE")),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("template_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("output_format", sa.String(16), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("report_templates")
    op.drop_table("business_rules")
    op.drop_table("column_mappings")
    op.drop_table("workflow_settings")
    op.drop_table("workflows")
