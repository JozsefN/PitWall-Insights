"""Add profile-scoped layout favorites."""
from alembic import op
import sqlalchemy as sa

revision = "f6c2a91d7b30"
down_revision = "e4b7c9d2a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_layout_favorites",
        sa.Column("owner_user_id", sa.String(64), nullable=False),
        sa.Column("layout_key", sa.String(160), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("owner_user_id", "layout_key"),
    )


def downgrade() -> None:
    op.drop_table("user_layout_favorites")
