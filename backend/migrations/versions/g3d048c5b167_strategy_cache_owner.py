"""Cascade private strategy results when their profile is removed; shared diagnostics remain shared."""

from alembic import op
import sqlalchemy as sa

revision = "g3d048c5b167"
down_revision = "f2c937b4a056"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "session_analysis_cache",
        sa.Column("owner_user_id", sa.String(64), nullable=True),
    )
    op.create_foreign_key(
        "fk_analysis_cache_owner_user_id",
        "session_analysis_cache",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_analysis_cache_owner_session",
        "session_analysis_cache",
        ["owner_user_id", "session_id"],
    )


def downgrade():
    op.drop_index(
        "ix_analysis_cache_owner_session", table_name="session_analysis_cache"
    )
    op.drop_constraint(
        "fk_analysis_cache_owner_user_id", "session_analysis_cache", type_="foreignkey"
    )
    op.drop_column("session_analysis_cache", "owner_user_id")
