"""Expose durable worker availability for materialization diagnostics."""

from alembic import op
import sqlalchemy as sa

revision = "c9f604e1d723"
down_revision = "b8e5f3d0c612"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "telemetry_worker_heartbeats",
        sa.Column("worker_id", sa.String(320), primary_key=True),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_telemetry_worker_heartbeats_heartbeat_at",
        "telemetry_worker_heartbeats",
        ["heartbeat_at"],
    )


def downgrade():
    op.drop_table("telemetry_worker_heartbeats")
