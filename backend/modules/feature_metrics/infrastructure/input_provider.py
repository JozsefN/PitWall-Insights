from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from modules.feature_metrics.domain.models import (
    FeatureMetricDataset,
    FeatureMetricDriverScoreRequest,
    FeatureMetricEntry,
    FeatureMetricInputCoverage,
    FeatureMetricLap,
    MetricInputKind,
)
from modules.session_domain.infrastructure.models import (
    EntryLapRecord,
    EventSessionRecord,
    SessionEntryRecord,
)

SUPPORTED_INPUTS: set[MetricInputKind] = {"session", "entries", "laps"}


class FeatureMetricInputProvider:
    def __init__(self, db: Session) -> None:
        self.db = db

    def load_dataset(
        self,
        session_id: str,
        *,
        request: FeatureMetricDriverScoreRequest,
        required_inputs: list[MetricInputKind],
    ) -> FeatureMetricDataset | None:
        if self.db.get(EventSessionRecord, session_id) is None:
            return None

        requested_inputs = list(dict.fromkeys(required_inputs))
        loaded_inputs = [input_kind for input_kind in requested_inputs if input_kind in SUPPORTED_INPUTS]
        missing_inputs = [input_kind for input_kind in requested_inputs if input_kind not in SUPPORTED_INPUTS]

        entries = self._list_entries(session_id, entry_ids=request.entry_ids)
        if request.entry_ids is not None and len(entries) != len(set(request.entry_ids)):
            raise ValueError("One or more entries do not belong to this session")

        entry_id_set = {entry.id for entry in entries}
        laps_by_entry_id = (
            self._list_laps_by_entry_id(session_id, entry_id_set)
            if "laps" in requested_inputs
            else {entry_id: [] for entry_id in entry_id_set}
        )

        return FeatureMetricDataset(
            session_id=session_id,
            analysis_scope=request.analysis_scope,
            entries=[self._build_entry_model(entry) for entry in entries],
            laps_by_entry_id=laps_by_entry_id,
            loaded_inputs=loaded_inputs,
            missing_inputs=missing_inputs,
        )

    def summarize_coverage(self, dataset: FeatureMetricDataset) -> FeatureMetricInputCoverage:
        return FeatureMetricInputCoverage(
            loaded_inputs=dataset.loaded_inputs,
            missing_inputs=dataset.missing_inputs,
            entry_count=len(dataset.entries),
            lap_count=sum(len(laps) for laps in dataset.laps_by_entry_id.values()),
        )

    def _list_entries(
        self,
        session_id: str,
        *,
        entry_ids: list[str] | None,
    ) -> list[SessionEntryRecord]:
        query = (
            self.db.query(SessionEntryRecord)
            .options(
                joinedload(SessionEntryRecord.driver),
                joinedload(SessionEntryRecord.team),
            )
            .filter(SessionEntryRecord.session_id == session_id)
        )
        if entry_ids is not None:
            query = query.filter(SessionEntryRecord.id.in_(entry_ids))

        return query.order_by(SessionEntryRecord.car_number.asc()).all()

    def _list_laps_by_entry_id(
        self,
        session_id: str,
        entry_ids: set[str],
    ) -> dict[str, list[FeatureMetricLap]]:
        if not entry_ids:
            return {}

        records = (
            self.db.query(EntryLapRecord)
            .join(SessionEntryRecord, EntryLapRecord.session_entry_id == SessionEntryRecord.id)
            .filter(
                SessionEntryRecord.session_id == session_id,
                EntryLapRecord.session_entry_id.in_(entry_ids),
            )
            .order_by(EntryLapRecord.session_entry_id.asc(), EntryLapRecord.lap_number.asc())
            .all()
        )
        laps_by_entry_id = {entry_id: [] for entry_id in entry_ids}
        for record in records:
            laps_by_entry_id.setdefault(record.session_entry_id, []).append(self._build_lap_model(record))
        return laps_by_entry_id

    @staticmethod
    def _build_entry_model(record: SessionEntryRecord) -> FeatureMetricEntry:
        return FeatureMetricEntry(
            id=record.id,
            car_number=record.car_number,
            driver_id=record.driver.id,
            driver_number=record.driver.driver_number,
            driver_abbreviation=record.driver.abbreviation,
            driver_name=record.driver.full_name,
            team_id=record.team.id if record.team else None,
            team_name=record.team.name if record.team else None,
            team_color=record.team.team_color if record.team else None,
        )

    @staticmethod
    def _build_lap_model(record: EntryLapRecord) -> FeatureMetricLap:
        return FeatureMetricLap(
            id=record.id,
            entry_id=record.session_entry_id,
            lap_number=record.lap_number,
            lap_time_ms=record.lap_time_ms,
            lap_start_time_ms=record.lap_start_time_ms,
            lap_end_time_ms=record.lap_end_time_ms,
            pit_out_time_ms=record.pit_out_time_ms,
            pit_in_time_ms=record.pit_in_time_ms,
            sector_1_time_ms=record.sector_1_time_ms,
            sector_2_time_ms=record.sector_2_time_ms,
            sector_3_time_ms=record.sector_3_time_ms,
            compound=record.compound,
            tyre_life=record.tyre_life,
            track_status=record.track_status,
            is_deleted=record.is_deleted,
            is_generated=record.is_generated,
            is_accurate=record.is_accurate,
        )
