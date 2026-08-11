"""Add result_json / report_slug / status for CDP run artifacts.

Revision ID: 009
Revises: 008
Create Date: 2026-07-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("automation_runs", sa.Column("result_json", sa.Text(), nullable=True))
    op.add_column(
        "automation_artifacts",
        sa.Column("report_slug", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "automation_artifacts",
        sa.Column("status", sa.String(length=32), server_default="ready", nullable=False),
    )
    op.create_index(
        "ix_automation_artifacts_report_slug",
        "automation_artifacts",
        ["report_slug"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_artifacts_report_slug", table_name="automation_artifacts")
    op.drop_column("automation_artifacts", "status")
    op.drop_column("automation_artifacts", "report_slug")
    op.drop_column("automation_runs", "result_json")
