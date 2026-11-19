"""Read additional review inputs from accessible, already normalized sessions."""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from .strategy_input import StrategyInputProvider
from .openf1_context import normalize_pit_reports
from ..domain.analysis.models import AnalysisRequest
from modules.session_domain.infrastructure.db_models import (
    EntryLapRecord,
    EventSessionRecord,
    SessionEntryRecord,
    WeekendRecord,
)


class ReviewInput(StrategyInputProvider):
    def end(self, session):
        last = (
            self.db.scalar(
                select(func.max(EntryLapRecord.lap_end_time_ms))
                .join(SessionEntryRecord)
                .where(SessionEntryRecord.session_id == session.id)
            )
            or 0
        )
        try:
            stamp = datetime.fromisoformat(
                (session.source_details or {})["session_end_utc"].replace("Z", "+00:00")
            )
            return max(
                last + 1000,
                round((stamp - session.session_time_origin_utc).total_seconds() * 1000),
            )
        except (KeyError, AttributeError, TypeError, ValueError):
            return last + 1000

    def identities(self, session_id):
        rows = self.db.scalars(
            select(SessionEntryRecord)
            .options(
                joinedload(SessionEntryRecord.driver),
                joinedload(SessionEntryRecord.team),
            )
            .where(SessionEntryRecord.session_id == session_id)
        )
        return {
            entry.id: {
                "name": entry.driver.full_name,
                "abbreviation": entry.driver.abbreviation,
                "team": entry.team.name if entry.team else None,
            }
            for entry in rows
        }

    def history(self, session, cutoff, *, include_older_practice=True):
        if not session.session_time_origin_utc:
            return []
        date = session.session_time_origin_utc + timedelta(milliseconds=cutoff)
        current_circuit = (session.source_details or {}).get("circuit_key")
        owner = self.db.info.get("actor_user_id")
        query = (
            select(EventSessionRecord)
            .join(WeekendRecord)
            .options(joinedload(EventSessionRecord.weekend))
            .where(
                EventSessionRecord.id != session.id,
                EventSessionRecord.deleted_at.is_(None),
                EventSessionRecord.data_provider == "openf1",
                EventSessionRecord.actual_start_utc < date,
                or_(
                    EventSessionRecord.owner_user_id.is_(None),
                    EventSessionRecord.owner_user_id == owner,
                ),
                or_(
                    WeekendRecord.id == session.weekend_id,
                    EventSessionRecord.source_details["circuit_key"].astext
                    == str(current_circuit),
                ),
            )
            .order_by(EventSessionRecord.actual_start_utc.desc())
            .limit(12)
        )
        if not include_older_practice:
            query = query.where(
                or_(
                    EventSessionRecord.weekend_id == session.weekend_id,
                    EventSessionRecord.session_name == "Race",
                )
            )
        rows = []
        for other in self.db.scalars(query):
            if other.session_name != "Race" and not other.session_name.startswith(
                "Practice"
            ):
                continue
            if not other.session_time_origin_utc:
                continue
            end = self.end(other)
            if other.session_time_origin_utc + timedelta(milliseconds=end) >= date:
                continue
            request = AnalysisRequest(start_time_ms=0, end_time_ms=end + 1)
            data = self.load(
                other.id,
                request,
                required_inputs={"laps", "track_status", "weather", "race_control"},
                as_of_ms=end,
            )
            reports = self.pit_reports(
                other, end, {entry.car_number: entry.id for entry in data.entries}
            )
            rows.append((other, data, reports))
            if len(rows) >= 8:
                break
        return rows

    @staticmethod
    def pit_reports(session, cutoff, entries):
        if (
            not session.session_time_origin_utc
            or not str(session.session_key).isdigit()
        ):
            return []
        output = []
        details = session.source_details or {}
        out_laps = {
            (entries.get(str(mark.get("driver_number"))), mark.get("lap_number"))
            for mark in details.get("pit_out_laps", [])
        }
        for row in details.get("pit_stops", []):
            try:
                values = normalize_pit_reports(
                    [row],
                    entries_by_car=entries,
                    clock_origin=session.session_time_origin_utc,
                    session_key=int(session.session_key),
                )
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            output.extend(
                {
                    **value.model_dump(mode="json"),
                    "session_id": session.id,
                    "out_lap_reported": (value.entry_id, value.lap_number + 1)
                    in out_laps,
                }
                for value in values
                if value.known_at_ms <= cutoff
            )
        return list(
            {(row["entry_id"], row["lap_number"]): row for row in output}.values()
        )
