"""Private profiles, durable encrypted connections and dataset provenance."""
from alembic import op
import sqlalchemy as sa

revision = "h4e159d6c278"
down_revision = "g3d048c5b167"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("account_profiles",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(120)), sa.Column("nickname", sa.String(60)),
        sa.Column("phone_number", sa.String(32)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("f1_account_connections",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False), sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False))
    op.add_column("event_sessions", sa.Column("owner_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE")))
    op.create_index("ix_event_sessions_owner_user_id", "event_sessions", ["owner_user_id"])
    op.add_column("event_sessions", sa.Column("data_provider", sa.String(32)))
    op.add_column("event_sessions", sa.Column("session_time_origin_utc", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("event_sessions", "session_time_origin_utc")
    op.drop_column("event_sessions", "data_provider")
    op.drop_index("ix_event_sessions_owner_user_id", table_name="event_sessions")
    op.drop_column("event_sessions", "owner_user_id")
    op.drop_table("f1_account_connections")
    op.drop_table("account_profiles")
