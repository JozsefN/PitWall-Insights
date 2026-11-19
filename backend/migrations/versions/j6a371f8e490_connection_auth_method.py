"""Distinguish renewable password connections from browser token handoffs."""
from alembic import op
import sqlalchemy as sa

revision = "j6a371f8e490"
down_revision = "i5f260e7d389"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("f1_account_connections", sa.Column("auth_method", sa.String(16), nullable=False, server_default="password"))


def downgrade():
    op.drop_column("f1_account_connections", "auth_method")
