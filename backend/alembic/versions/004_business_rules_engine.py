"""Business Rules Engine - configurable_rules table

Revision ID: 004
Revises: 003
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "configurable_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("report_config_templates.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(32), nullable=False, index=True),
        sa.Column("rule_type", sa.String(64), nullable=False),
        sa.Column("config_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("group_id", sa.String(64), nullable=True, index=True),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("is_global", sa.Boolean, server_default="false", index=True),
        sa.Column("conditions_json", sa.Text, nullable=True),
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
        "ix_configurable_rules_template_category",
        "configurable_rules",
        ["template_id", "category"],
    )
    op.create_index(
        "ix_configurable_rules_template_priority",
        "configurable_rules",
        ["template_id", "priority"],
    )
    op.create_index(
        "ix_configurable_rules_enabled",
        "configurable_rules",
        ["is_enabled", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_configurable_rules_enabled", table_name="configurable_rules")
    op.drop_index("ix_configurable_rules_template_priority", table_name="configurable_rules")
    op.drop_index("ix_configurable_rules_template_category", table_name="configurable_rules")
    op.drop_table("configurable_rules")
