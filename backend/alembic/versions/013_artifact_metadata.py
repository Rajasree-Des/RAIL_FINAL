"""Add metadata_json to automation_artifacts for dual-output column snapshots.

Revision ID: 013
Revises: 012
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("automation_artifacts", "metadata_json"):
        op.add_column(
            "automation_artifacts",
            sa.Column("metadata_json", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("automation_artifacts", "metadata_json"):
        op.drop_column("automation_artifacts", "metadata_json")
