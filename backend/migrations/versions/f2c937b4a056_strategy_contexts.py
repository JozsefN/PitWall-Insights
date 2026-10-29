"""Immutable per-profile strategy calibration and geometry context."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f2c937b4a056"
down_revision = "e1b826a3f945"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_context_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("event_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("known_at_ms", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_strategy_context_owner_session",
        "strategy_context_versions",
        ["owner_user_id", "session_id", "created_at"],
    )


def downgrade():
    op.drop_table("strategy_context_versions")
