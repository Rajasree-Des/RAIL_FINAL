"""Report dataset metadata cache

Revision ID: 008
Revises: 007
Create Date: 2026-07-08

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(64), nullable=False),
        sa.Column("source_filename", sa.String(256), nullable=False),
        sa.Column("source_file_path", sa.String(1024), nullable=True),
        sa.Column("header_row", sa.Integer, server_default="1"),
        sa.Column("row_count", sa.Integer, server_default="0"),
        sa.Column("columns_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("parsed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_datasets_report_id", "report_datasets", ["report_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_report_datasets_report_id", table_name="report_datasets")
    op.drop_table("report_datasets")
