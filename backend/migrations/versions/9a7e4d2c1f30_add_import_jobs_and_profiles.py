"""add import jobs and profiles

Revision ID: 9a7e4d2c1f30
Revises: 8f4c8a6a1c92
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9a7e4d2c1f30"
down_revision: Union[str, None] = "8f4c8a6a1c92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_sessions",
        sa.Column("import_profile", sa.String(length=32), nullable=False, server_default="full"),
    )
    op.add_column(
        "event_sessions",
        sa.Column("telemetry_status", sa.String(length=32), nullable=False, server_default="loaded"),
    )
    op.add_column(
        "event_sessions",
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "event_sessions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sessions_deleted_expires",
        "event_sessions",
        ["deleted_at", "expires_at"],
        unique=False,
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_session_key", sa.String(length=255), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("session_name", sa.String(length=128), nullable=False),
        sa.Column("import_profile", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress_stage", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("force_refresh", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("rows_written", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_heartbeat", "import_jobs", ["heartbeat_at"], unique=False)
    op.create_index("ix_import_jobs_session_id", "import_jobs", ["session_id"], unique=False)
    op.create_index(
        "ix_import_jobs_source_session_profile_status",
        "import_jobs",
        ["source", "source_session_key", "import_profile", "status"],
        unique=False,
    )
    op.create_index(
        "ix_import_jobs_status_created",
        "import_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_import_jobs_user_created",
        "import_jobs",
        ["created_by_user_id", "created_at"],
        unique=False,
    )

    op.add_column("ingestion_runs", sa.Column("job_id", sa.String(length=64), nullable=True))
    op.add_column("ingestion_runs", sa.Column("import_profile", sa.String(length=32), nullable=True))
    op.add_column("ingestion_runs", sa.Column("duration_ms", sa.BigInteger(), nullable=True))
    op.create_index("ix_ingestion_runs_job_id", "ingestion_runs", ["job_id"], unique=False)
    op.create_foreign_key(
        "fk_ingestion_runs_job_id_import_jobs",
        "ingestion_runs",
        "import_jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ingestion_runs_job_id_import_jobs", "ingestion_runs", type_="foreignkey")
    op.drop_index("ix_ingestion_runs_job_id", table_name="ingestion_runs")
    op.drop_column("ingestion_runs", "duration_ms")
    op.drop_column("ingestion_runs", "import_profile")
    op.drop_column("ingestion_runs", "job_id")

    op.drop_index("ix_import_jobs_user_created", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status_created", table_name="import_jobs")
    op.drop_index("ix_import_jobs_source_session_profile_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_session_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_heartbeat", table_name="import_jobs")
    op.drop_table("import_jobs")

    op.drop_index("ix_sessions_deleted_expires", table_name="event_sessions")
    op.drop_column("event_sessions", "deleted_at")
    op.drop_column("event_sessions", "pinned_at")
    op.drop_column("event_sessions", "telemetry_status")
    op.drop_column("event_sessions", "import_profile")
