"""Persist versioned analytics and repair FastF1 wind-speed units once."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0a715f2e834"
down_revision = "c9f604e1d723"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session_analysis_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("event_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("data_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_session_analysis_cache_session_expires",
        "session_analysis_cache",
        ["session_id", "expires_at"],
    )
    op.execute(
        "UPDATE session_weather_samples AS w SET wind_speed_kph=w.wind_speed_kph*3.6 FROM event_sessions AS s WHERE s.id=w.session_id AND s.source='fastf1' AND w.wind_speed_kph IS NOT NULL"
    )


def downgrade():
    op.execute(
        "UPDATE session_weather_samples AS w SET wind_speed_kph=w.wind_speed_kph/3.6 FROM event_sessions AS s WHERE s.id=w.session_id AND s.source='fastf1' AND w.wind_speed_kph IS NOT NULL"
    )
    op.drop_table("session_analysis_cache")
