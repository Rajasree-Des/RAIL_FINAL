"""Add content_checksum to report_datasets for idempotent ingestion.

Revision ID: 011
Revises: 010
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    # Column may already exist if create_all / a prior partial apply ran first.
    if not _has_column("report_datasets", "content_checksum"):
        op.add_column(
            "report_datasets",
            sa.Column("content_checksum", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    if _has_column("report_datasets", "content_checksum"):
        op.drop_column("report_datasets", "content_checksum")
