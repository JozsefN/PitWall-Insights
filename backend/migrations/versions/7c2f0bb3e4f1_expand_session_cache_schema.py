"""expand session cache schema

Revision ID: 7c2f0bb3e4f1
Revises: 42f2ca871af0
Create Date: 2026-04-12 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c2f0bb3e4f1"
down_revision: Union[str, None] = "42f2ca871af0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("sessions")

    op.create_table(
        "seasons",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )

    op.create_table(
        "drivers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_driver_key", sa.String(length=128), nullable=False),
        sa.Column("driver_number", sa.String(length=16), nullable=True),
        sa.Column("abbreviation", sa.String(length=16), nullable=True),
        sa.Column("broadcast_name", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_driver_key", name="uq_drivers_source_key"),
    )
    op.create_index("ix_drivers_abbreviation", "drivers", ["abbreviation"], unique=False)

    op.create_table(
        "teams",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_team_key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("team_color", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_team_key", name="uq_teams_source_key"),
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=False)

    op.create_table(
        "event_weekends",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_event_key", sa.String(length=255), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=True),
        sa.Column("event_name", sa.String(length=255), nullable=False),
        sa.Column("official_event_name", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("event_format", sa.String(length=64), nullable=True),
        sa.Column("is_testing", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["season_year"], ["seasons.year"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_event_key", name="uq_weekends_source_key"),
    )
    op.create_index("ix_weekends_season_round", "event_weekends", ["season_year", "round_number"], unique=False)

    op.create_table(
        "event_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_session_key", sa.String(length=255), nullable=False),
        sa.Column("weekend_id", sa.String(length=64), nullable=False),
        sa.Column("session_name", sa.String(length=128), nullable=False),
        sa.Column("session_type", sa.String(length=64), nullable=True),
        sa.Column("meeting_key", sa.String(length=64), nullable=True),
        sa.Column("session_key", sa.String(length=64), nullable=True),
        sa.Column("api_path", sa.String(length=255), nullable=True),
        sa.Column("f1_api_support", sa.Boolean(), nullable=True),
        sa.Column("scheduled_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["weekend_id"], ["event_weekends.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_session_key", name="uq_sessions_source_key"),
    )
    op.create_index("ix_sessions_state_expires", "event_sessions", ["state", "expires_at"], unique=False)
    op.create_index("ix_sessions_weekend_name", "event_sessions", ["weekend_id", "session_name"], unique=False)

    op.create_table(
        "session_entries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("driver_id", sa.String(length=64), nullable=False),
        sa.Column("team_id", sa.String(length=64), nullable=True),
        sa.Column("source_entry_key", sa.String(length=255), nullable=False),
        sa.Column("car_number", sa.String(length=16), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=128), nullable=True),
        sa.Column("grid_position", sa.Integer(), nullable=True),
        sa.Column("classified_position", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "car_number", name="uq_session_entries_car_number"),
    )
    op.create_index("ix_session_entries_driver", "session_entries", ["session_id", "driver_id"], unique=False)
    op.create_index("ix_session_entries_team", "session_entries", ["session_id", "team_id"], unique=False)
    op.create_index("ix_session_entries_source_entry_key", "session_entries", ["source_entry_key"], unique=False)

    op.create_table(
        "entry_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("classified_position", sa.String(length=32), nullable=True),
        sa.Column("points", sa.Float(), nullable=True),
        sa.Column("time_status", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=128), nullable=True),
        sa.Column("laps_completed", sa.Integer(), nullable=True),
        sa.Column("q1_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("q2_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("q3_time_ms", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_entry_id", name="uq_entry_results_entry"),
    )

    op.create_table(
        "entry_laps",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=False),
        sa.Column("lap_number", sa.Integer(), nullable=False),
        sa.Column("lap_position", sa.Integer(), nullable=True),
        sa.Column("stint_number", sa.Integer(), nullable=True),
        sa.Column("lap_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("lap_start_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("lap_end_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("pit_out_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("pit_in_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("sector_1_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("sector_2_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("sector_3_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("sector_1_session_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("sector_2_session_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("sector_3_session_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("speed_i1_kph", sa.Float(), nullable=True),
        sa.Column("speed_i2_kph", sa.Float(), nullable=True),
        sa.Column("speed_fl_kph", sa.Float(), nullable=True),
        sa.Column("speed_st_kph", sa.Float(), nullable=True),
        sa.Column("compound", sa.String(length=32), nullable=True),
        sa.Column("tyre_life", sa.Integer(), nullable=True),
        sa.Column("fresh_tyre", sa.Boolean(), nullable=True),
        sa.Column("track_status", sa.String(length=64), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_reason", sa.Text(), nullable=True),
        sa.Column("is_generated", sa.Boolean(), nullable=False),
        sa.Column("is_accurate", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_entry_id", "lap_number", name="uq_entry_laps_number"),
    )
    op.create_index("ix_entry_laps_session_entry", "entry_laps", ["session_entry_id", "lap_number"], unique=False)
    op.create_index("ix_entry_laps_time", "entry_laps", ["session_entry_id", "lap_start_time_ms"], unique=False)

    op.create_table(
        "entry_stints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=False),
        sa.Column("stint_number", sa.Integer(), nullable=False),
        sa.Column("compound", sa.String(length=32), nullable=True),
        sa.Column("tyre_life_start", sa.Integer(), nullable=True),
        sa.Column("tyre_life_end", sa.Integer(), nullable=True),
        sa.Column("lap_start_number", sa.Integer(), nullable=True),
        sa.Column("lap_end_number", sa.Integer(), nullable=True),
        sa.Column("lap_count", sa.Integer(), nullable=False),
        sa.Column("started_session_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("ended_session_time_ms", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_entry_id", "stint_number", name="uq_entry_stints_number"),
    )
    op.create_index("ix_entry_stints_session_entry", "entry_stints", ["session_entry_id", "stint_number"], unique=False)

    op.create_table(
        "session_ticks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("tick_no", sa.Integer(), nullable=False),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_kind", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "tick_no", name="uq_session_ticks_tick_no"),
        sa.UniqueConstraint("session_id", "session_time_ms", name="uq_session_ticks_time"),
    )
    op.create_index("ix_session_ticks_session_time", "session_ticks", ["session_id", "session_time_ms"], unique=False)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("fastf1_version", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_written", sa.Integer(), nullable=False),
        sa.Column("force_refresh", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_runs_session_started", "ingestion_runs", ["session_id", "started_at"], unique=False)

    op.create_table(
        "session_weather_samples",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("air_temp_c", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("pressure_mbar", sa.Float(), nullable=True),
        sa.Column("rainfall", sa.Boolean(), nullable=True),
        sa.Column("track_temp_c", sa.Float(), nullable=True),
        sa.Column("wind_direction_deg", sa.Integer(), nullable=True),
        sa.Column("wind_speed_kph", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_weather_time", "session_weather_samples", ["session_id", "session_time_ms"], unique=False)

    op.create_table(
        "session_status_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_status_time", "session_status_events", ["session_id", "session_time_ms"], unique=False)

    op.create_table(
        "session_track_status_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_track_status_time", "session_track_status_events", ["session_id", "session_time_ms"], unique=False)

    op.create_table(
        "session_race_control_messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=True),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("flag", sa.String(length=64), nullable=True),
        sa.Column("scope", sa.String(length=64), nullable=True),
        sa.Column("sector", sa.Integer(), nullable=True),
        sa.Column("lap_number", sa.Integer(), nullable=True),
        sa.Column("driver_number", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_race_control_time", "session_race_control_messages", ["session_id", "session_time_ms"], unique=False)

    op.create_table(
        "car_telemetry_samples",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=False),
        sa.Column("tick_id", sa.String(length=64), nullable=False),
        sa.Column("lap_id", sa.String(length=64), nullable=True),
        sa.Column("stint_id", sa.String(length=64), nullable=True),
        sa.Column("sample_seq", sa.Integer(), nullable=False),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("speed_kph", sa.Float(), nullable=True),
        sa.Column("rpm", sa.Integer(), nullable=True),
        sa.Column("gear", sa.Integer(), nullable=True),
        sa.Column("throttle_pct", sa.Float(), nullable=True),
        sa.Column("brake_on", sa.Boolean(), nullable=True),
        sa.Column("drs_state", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["lap_id"], ["entry_laps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stint_id"], ["entry_stints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tick_id"], ["session_ticks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_entry_id", "sample_seq", name="uq_car_telemetry_sample_seq"),
    )
    op.create_index("ix_car_telemetry_entry_time", "car_telemetry_samples", ["session_entry_id", "session_time_ms"], unique=False)
    op.create_index("ix_car_telemetry_tick", "car_telemetry_samples", ["tick_id"], unique=False)

    op.create_table(
        "position_samples",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_entry_id", sa.String(length=64), nullable=False),
        sa.Column("tick_id", sa.String(length=64), nullable=False),
        sa.Column("lap_id", sa.String(length=64), nullable=True),
        sa.Column("stint_id", sa.String(length=64), nullable=True),
        sa.Column("sample_seq", sa.Integer(), nullable=False),
        sa.Column("session_time_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("z", sa.Float(), nullable=True),
        sa.Column("track_status", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["lap_id"], ["entry_laps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_entry_id"], ["session_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stint_id"], ["entry_stints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tick_id"], ["session_ticks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_entry_id", "sample_seq", name="uq_position_samples_seq"),
    )
    op.create_index("ix_position_samples_entry_time", "position_samples", ["session_entry_id", "session_time_ms"], unique=False)
    op.create_index("ix_position_samples_tick", "position_samples", ["tick_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_position_samples_tick", table_name="position_samples")
    op.drop_index("ix_position_samples_entry_time", table_name="position_samples")
    op.drop_table("position_samples")
    op.drop_index("ix_car_telemetry_tick", table_name="car_telemetry_samples")
    op.drop_index("ix_car_telemetry_entry_time", table_name="car_telemetry_samples")
    op.drop_table("car_telemetry_samples")
    op.drop_index("ix_race_control_time", table_name="session_race_control_messages")
    op.drop_table("session_race_control_messages")
    op.drop_index("ix_track_status_time", table_name="session_track_status_events")
    op.drop_table("session_track_status_events")
    op.drop_index("ix_session_status_time", table_name="session_status_events")
    op.drop_table("session_status_events")
    op.drop_index("ix_session_weather_time", table_name="session_weather_samples")
    op.drop_table("session_weather_samples")
    op.drop_index("ix_ingestion_runs_session_started", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_index("ix_session_ticks_session_time", table_name="session_ticks")
    op.drop_table("session_ticks")
    op.drop_index("ix_entry_stints_session_entry", table_name="entry_stints")
    op.drop_table("entry_stints")
    op.drop_index("ix_entry_laps_time", table_name="entry_laps")
    op.drop_index("ix_entry_laps_session_entry", table_name="entry_laps")
    op.drop_table("entry_laps")
    op.drop_table("entry_results")
    op.drop_index("ix_session_entries_source_entry_key", table_name="session_entries")
    op.drop_index("ix_session_entries_team", table_name="session_entries")
    op.drop_index("ix_session_entries_driver", table_name="session_entries")
    op.drop_table("session_entries")
    op.drop_index("ix_sessions_weekend_name", table_name="event_sessions")
    op.drop_index("ix_sessions_state_expires", table_name="event_sessions")
    op.drop_table("event_sessions")
    op.drop_index("ix_weekends_season_round", table_name="event_weekends")
    op.drop_table("event_weekends")
    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_table("teams")
    op.drop_index("ix_drivers_abbreviation", table_name="drivers")
    op.drop_table("drivers")
    op.drop_table("seasons")

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("track_code", sa.String(length=64), nullable=False),
        sa.Column("driver_code", sa.String(length=64), nullable=False),
        sa.Column("lap_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
