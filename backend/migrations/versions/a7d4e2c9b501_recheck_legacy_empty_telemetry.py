"""Invalidate legacy empty session caches created before source failure checks."""
from alembic import op

revision = "a7d4e2c9b501"
down_revision = "f6c2a91d7b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Do this once: future jobs verify that the source supplied actual data.
    # A zero-row segment for one DNS/retired driver in an otherwise valid load
    # remains cacheable, avoiding an endless materialization loop for that driver.
    op.execute("""
        UPDATE telemetry_cache_segments
        SET status = 'failed',
            error_message = 'Legacy empty telemetry cache must be checked against the source again.'
        WHERE scope = 'session' AND status = 'completed' AND row_count = 0
    """)


def downgrade() -> None:
    # Data repair cannot safely reconstruct which empty caches were valid.
    pass
