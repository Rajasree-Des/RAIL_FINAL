"""Automation profiles, runs, logs, and artifacts

Revision ID: 007
Revises: 006
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("portal_url", sa.String(512), nullable=False),
        sa.Column("username_encrypted", sa.Text, nullable=False),
        sa.Column("password_encrypted", sa.Text, nullable=False),
        sa.Column("download_folder", sa.String(512), server_default="downloads/railmadad"),
        sa.Column("browser", sa.String(32), server_default="chromium"),
        sa.Column("headless", sa.Boolean, server_default="true"),
        sa.Column("timeout_ms", sa.Integer, server_default="60000"),
        sa.Column("retry_count", sa.Integer, server_default="3"),
        sa.Column("delay_seconds", sa.Integer, server_default="5"),
        sa.Column("report_sequence_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("session_state_encrypted", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
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
        ),
    )

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(36),
            sa.ForeignKey("automation_profiles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(32), server_default="pending", index=True),
        sa.Column("trigger_type", sa.String(32), server_default="manual"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("failure_count", sa.Integer, server_default="0"),
        sa.Column("current_report_index", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_table(
        "automation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("automation_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("level", sa.String(16), server_default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    op.create_table(
        "automation_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("automation_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("report_name", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("automation_artifacts")
    op.drop_table("automation_logs")
    op.drop_table("automation_runs")
    op.drop_table("automation_profiles")
