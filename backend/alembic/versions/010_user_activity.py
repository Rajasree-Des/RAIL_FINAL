"""Create user_activity table for account-scoped activity feed.

Revision ID: 010
Revises: 009
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_activity",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False, index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="info", index=True),
        sa.Column("report_slug", sa.String(length=64), nullable=True, index=True),
        sa.Column("run_id", sa.String(length=36), nullable=True, index=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_user_activity_dedupe"),
    )


def downgrade() -> None:
    op.drop_table("user_activity")
