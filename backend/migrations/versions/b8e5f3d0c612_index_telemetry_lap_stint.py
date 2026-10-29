"""Add telemetry relationship indexes declared by the models but missing from DB."""
from alembic import op

revision = "b8e5f3d0c612"
down_revision = "a7d4e2c9b501"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_car_telemetry_samples_lap_id", "car_telemetry_samples", "lap_id"),
    ("ix_car_telemetry_samples_stint_id", "car_telemetry_samples", "stint_id"),
    ("ix_position_samples_lap_id", "position_samples", "lap_id"),
    ("ix_position_samples_stint_id", "position_samples", "stint_id"),
)


def upgrade() -> None:
    # Existing caches contain millions of rows: permit normal reads/writes while
    # these indexes are built. IF NOT EXISTS also permits resuming a partial run.
    with op.get_context().autocommit_block():
        for name, table, column in INDEXES:
            op.create_index(name, table, [column], unique=False,
                            postgresql_concurrently=True, if_not_exists=True)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, _ in reversed(INDEXES):
            op.drop_index(name, table_name=table, postgresql_concurrently=True, if_exists=True)
