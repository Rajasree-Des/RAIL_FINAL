"""Extend generated_summaries for daily briefing (run_id, report_date, updated_at).

Revision ID: 012
Revises: 011
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column for col in inspector.get_columns(table))


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    if not _has_column("generated_summaries", "run_id"):
        op.add_column(
            "generated_summaries",
            sa.Column("run_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_generated_summaries_run_id",
            "generated_summaries",
            "automation_runs",
            ["run_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _has_column("generated_summaries", "report_date"):
        op.add_column(
            "generated_summaries",
            sa.Column("report_date", sa.String(length=16), nullable=True),
        )
    if not _has_column("generated_summaries", "updated_at"):
        op.add_column(
            "generated_summaries",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )
    if not _has_index("generated_summaries", "ix_generated_summaries_created_by_run"):
        op.create_index(
            "ix_generated_summaries_created_by_run",
            "generated_summaries",
            ["created_by", "run_id"],
        )
    if not _has_index("generated_summaries", "ix_generated_summaries_created_by_created"):
        op.create_index(
            "ix_generated_summaries_created_by_created",
            "generated_summaries",
            ["created_by", "created_at"],
        )


def downgrade() -> None:
    if _has_index("generated_summaries", "ix_generated_summaries_created_by_created"):
        op.drop_index(
            "ix_generated_summaries_created_by_created",
            table_name="generated_summaries",
        )
    if _has_index("generated_summaries", "ix_generated_summaries_created_by_run"):
        op.drop_index(
            "ix_generated_summaries_created_by_run",
            table_name="generated_summaries",
        )
    if _has_column("generated_summaries", "updated_at"):
        op.drop_column("generated_summaries", "updated_at")
    if _has_column("generated_summaries", "report_date"):
        op.drop_column("generated_summaries", "report_date")
    if _has_column("generated_summaries", "run_id"):
        op.drop_constraint(
            "fk_generated_summaries_run_id",
            "generated_summaries",
            type_="foreignkey",
        )
        op.drop_column("generated_summaries", "run_id")
