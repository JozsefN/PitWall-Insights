"""Add subscription projections, Stripe receipts and Google identity."""
import sqlalchemy as sa
from alembic import op
from secrets import token_urlsafe
from passlib.hash import bcrypt

revision = "k7b482a9f601"
down_revision = "j6a371f8e490"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.create_table(
        "billing_accounts",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(128), unique=True),
        sa.Column("subscription_id", sa.String(128), unique=True),
        sa.Column("plan_code", sa.String(16)),
        sa.Column("interval", sa.String(8)),
        sa.Column("status", sa.String(32)),
        sa.Column("paid_until", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        sa.Column("checkout_key", sa.String(64)),
        sa.Column("checkout_plan", sa.String(16)),
        sa.Column("checkout_interval", sa.String(8)),
        sa.Column("checkout_id", sa.String(128)),
        sa.Column("checkout_expires_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "billing_webhook_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("billing_accounts.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_billing_webhook_events_user_id", "billing_webhook_events", ["user_id"])
    op.create_index("ix_billing_webhook_events_processed_at", "billing_webhook_events", ["processed_at"])
    op.create_table(
        "google_identities",
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
    )
    op.create_table(
        "google_login_challenges",
        sa.Column("nonce_digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_google_login_challenges_expires_at", "google_login_challenges", ["expires_at"])


def downgrade():
    # Older code rejects passwordless login. Keep those accounts and their data.
    users = sa.table("users", sa.column("password_hash", sa.String))
    op.execute(users.update().where(users.c.password_hash.is_(None)).values(password_hash=bcrypt.hash(token_urlsafe(48))))
    op.drop_table("google_login_challenges")
    op.drop_table("google_identities")
    op.drop_table("billing_webhook_events")
    op.drop_table("billing_accounts")
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
