"""Complete missing FK indexes without duplicating existing prefix indexes."""

from alembic import op

revision = "e1b826a3f945"
down_revision = "d0a715f2e834"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_session_entries_driver_id", "session_entries", "driver_id"),
    ("ix_session_entries_team_id", "session_entries", "team_id"),
    (
        "ix_session_race_control_messages_session_entry_id",
        "session_race_control_messages",
        "session_entry_id",
    ),
)


def upgrade():
    with op.get_context().autocommit_block():
        for name, table, column in INDEXES:
            op.create_index(
                name, table, [column], postgresql_concurrently=True, if_not_exists=True
            )


def downgrade():
    with op.get_context().autocommit_block():
        for name, table, _ in reversed(INDEXES):
            op.drop_index(
                name, table_name=table, postgresql_concurrently=True, if_exists=True
            )
