"""Centralized application settings - definitions and values

Revision ID: 006
Revises: 005
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_setting_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(32), nullable=False, index=True),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("value_type", sa.String(32), nullable=False),
        sa.Column("default_value", sa.Text, nullable=False, server_default="null"),
        sa.Column("validation_json", sa.Text, nullable=True),
        sa.Column("options_json", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("is_editable", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("category", "key", name="uq_app_setting_category_key"),
    )
    op.create_index(
        "ix_app_setting_definitions_category_sort",
        "app_setting_definitions",
        ["category", "sort_order"],
    )

    op.create_table(
        "app_setting_values",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("app_setting_definitions.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        ),
        sa.Column("value_json", sa.Text, nullable=False),
        sa.Column(
            "updated_by",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("app_setting_values")
    op.drop_index(
        "ix_app_setting_definitions_category_sort",
        table_name="app_setting_definitions",
    )
    op.drop_table("app_setting_definitions")
