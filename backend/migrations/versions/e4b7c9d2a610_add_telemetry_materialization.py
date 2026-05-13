"""add telemetry materialization

Revision ID: e4b7c9d2a610
Revises: 9a7e4d2c1f30
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e4b7c9d2a610"
down_revision: Union[str, None] = "9a7e4d2c1f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telemetry_cache_segments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "session_entry_id",
            "kind",
            "scope",
            "lap_number",
            name="uq_telemetry_cache_segment_key",
        ),
    )
    op.create_index(
        "ix_telemetry_cache_segments_entry_kind",
        "telemetry_cache_segments",
        ["session_entry_id", "kind"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_cache_segments_session_id",
        "telemetry_cache_segments",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_cache_segments_session_entry_id",
        "telemetry_cache_segments",
        ["session_entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_cache_segments_session_status",
        "telemetry_cache_segments",
        ["session_id", "status"],
        unique=False,
    )

    op.create_table(
        "telemetry_materialization_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("entry_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kinds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress_stage", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("force_refresh", sa.Boolean(), nullable=False),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("rows_written", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_jobs_heartbeat",
        "telemetry_materialization_jobs",
        ["heartbeat_at"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_jobs_session_id",
        "telemetry_materialization_jobs",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_jobs_session_status",
        "telemetry_materialization_jobs",
        ["session_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_jobs_status_created",
        "telemetry_materialization_jobs",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_jobs_status_created", table_name="telemetry_materialization_jobs")
    op.drop_index("ix_telemetry_jobs_session_status", table_name="telemetry_materialization_jobs")
    op.drop_index("ix_telemetry_jobs_session_id", table_name="telemetry_materialization_jobs")
    op.drop_index("ix_telemetry_jobs_heartbeat", table_name="telemetry_materialization_jobs")
    op.drop_table("telemetry_materialization_jobs")

    op.drop_index("ix_telemetry_cache_segments_session_status", table_name="telemetry_cache_segments")
    op.drop_index("ix_telemetry_cache_segments_session_entry_id", table_name="telemetry_cache_segments")
    op.drop_index("ix_telemetry_cache_segments_session_id", table_name="telemetry_cache_segments")
    op.drop_index("ix_telemetry_cache_segments_entry_kind", table_name="telemetry_cache_segments")
    op.drop_table("telemetry_cache_segments")
