"""Add mailbox verification and a database-backed administrator role."""
import sqlalchemy as sa
from alembic import op

revision = "l8c593b0a712"
down_revision = "k7b482a9f601"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("role", sa.String(16), server_default="member", nullable=False))
    op.create_check_constraint("ck_users_role", "users", "role in ('member', 'admin')")
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("recipient_key", sa.String(64), nullable=False),
        sa.Column("client_key", sa.String(64), nullable=False),
        sa.Column("code_digest", sa.String(64), nullable=False),
        sa.Column("account_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("google_subject", sa.String(255)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    for column in ("email", "recipient_key", "client_key", "created_at"):
        op.create_index(f"ix_email_verifications_{column}", "email_verifications", [column])


def downgrade():
    op.drop_table("email_verifications")
    op.drop_column("users", "email_verified_at")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
