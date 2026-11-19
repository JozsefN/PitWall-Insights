"""Nonduplicated provider extras and auditable independent lap quality."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "i5f260e7d389"
down_revision = "h4e159d6c278"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("event_sessions", sa.Column("source_details", JSONB(), nullable=True))


def downgrade():
    op.drop_column("event_sessions", "source_details")
