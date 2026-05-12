from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from modules.normalization.domain.models import SessionSnapshot
from modules.session_domain.domain.models import (
    CarTelemetrySampleModel,
    EntryLapModel,
    PositionSampleModel,
    SessionDetail,
    SessionEntrySummary,
    SessionSummary,
    SessionTickModel,
)
from modules.session_domain.infrastructure.models import (
    CarTelemetrySampleRecord,
    DriverRecord,
    EntryLapRecord,
    EntryResultRecord,
    EntryStintRecord,
    EventSessionRecord,
    IngestionRunRecord,
    PositionSampleRecord,
    SeasonRecord,
    SessionEntryRecord,
    SessionRaceControlMessageRecord,
    SessionStatusEventRecord,
    SessionTickRecord,
    SessionTrackStatusEventRecord,
    SessionWeatherSampleRecord,
    TeamRecord,
    WeekendRecord,
)


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def cleanup_expired_sessions(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        records = (
            self.db.query(EventSessionRecord)
            .filter(
                EventSessionRecord.expires_at < now,
                EventSessionRecord.pinned_at.is_(None),
            )
            .all()
        )
        for record in records:
            self.db.delete(record)
        if records:
            self.db.commit()
        return len(records)

    def import_snapshot(
        self,
        snapshot: SessionSnapshot,
        *,
        source_version: str | None,
        force_refresh: bool,
        job_id: str | None = None,
        started_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> str:
        existing = (
            self.db.query(EventSessionRecord)
            .filter(
                EventSessionRecord.source == snapshot.session.source,
                EventSessionRecord.source_session_key == snapshot.session.source_session_key,
            )
            .first()
        )

        needs_full_refresh = (
            snapshot.session.import_profile == "full"
            and existing is not None
            and existing.telemetry_status != "loaded"
        )

        if existing is not None and not force_refresh and not needs_full_refresh:
            existing.last_accessed_at = snapshot.session.last_accessed_at
            existing.expires_at = snapshot.session.expires_at
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing.id

        if existing is not None:
            self.db.delete(existing)
            self.db.flush()

        season = self._upsert_season(snapshot)
        weekend = self._upsert_weekend(snapshot, season)
        session = self._create_session(snapshot, weekend)
        self.db.flush()

        driver_id_map = self._upsert_drivers(snapshot)
        team_id_map = self._upsert_teams(snapshot)
        entry_id_map = self._create_entries(snapshot, session.id, driver_id_map, team_id_map)
        self._create_results(snapshot, entry_id_map)
        lap_id_map = self._create_laps(snapshot, entry_id_map)
        stint_id_map = self._create_stints(snapshot, entry_id_map)
        tick_id_map = self._create_ticks(snapshot, session.id)
        self._create_session_events(snapshot, session.id, entry_id_map)
        self._create_telemetry(snapshot, entry_id_map, lap_id_map, stint_id_map, tick_id_map)
        run_started_at = started_at or snapshot.session.imported_at
        run_finished_at = datetime.now(timezone.utc)
        run_duration_ms = duration_ms
        if run_duration_ms is None:
            run_duration_ms = max(0, int((run_finished_at - run_started_at).total_seconds() * 1000))

        self.db.add(
            IngestionRunRecord(
                session_id=session.id,
                job_id=job_id,
                source=snapshot.session.source,
                source_version=source_version,
                import_profile=snapshot.session.import_profile,
                status="completed",
                started_at=run_started_at,
                finished_at=run_finished_at,
                duration_ms=run_duration_ms,
                rows_written=snapshot.total_row_count(),
                force_refresh=force_refresh,
            )
        )
        self.db.commit()
        return session.id

    def delete_session(self, session_id: str) -> bool:
        record = (
            self.db.query(EventSessionRecord)
            .filter(EventSessionRecord.id == session_id)
            .first()
        )
        if record is None:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def list_sessions(self) -> list[SessionSummary]:
        records = (
            self.db.query(EventSessionRecord)
            .options(joinedload(EventSessionRecord.weekend))
            .order_by(EventSessionRecord.scheduled_start_utc.desc(), EventSessionRecord.imported_at.desc())
            .all()
        )
        entry_counts = self._count_by_session(SessionEntryRecord)
        tick_counts = self._count_by_session(SessionTickRecord)
        return [self._build_session_summary(record, entry_counts, tick_counts) for record in records]

    def get_session(self, session_id: str) -> SessionDetail | None:
        record = (
            self.db.query(EventSessionRecord)
            .options(joinedload(EventSessionRecord.weekend))
            .filter(EventSessionRecord.id == session_id)
            .first()
        )
        if record is None:
            return None

        entry_counts = self._count_by_session(SessionEntryRecord)
        tick_counts = self._count_by_session(SessionTickRecord)
        return SessionDetail(
            **self._build_session_summary(record, entry_counts, tick_counts).model_dump(),
            meeting_key=record.meeting_key,
            session_key=record.session_key,
            api_path=record.api_path,
            f1_api_support=record.f1_api_support,
            weather_sample_count=self._count_rows(SessionWeatherSampleRecord, record.id),
            status_event_count=self._count_rows(SessionStatusEventRecord, record.id),
            track_status_event_count=self._count_rows(SessionTrackStatusEventRecord, record.id),
            race_control_message_count=self._count_rows(SessionRaceControlMessageRecord, record.id),
        )

    def list_entries(self, session_id: str) -> list[SessionEntrySummary]:
        records = (
            self.db.query(SessionEntryRecord)
            .options(
                joinedload(SessionEntryRecord.driver),
                joinedload(SessionEntryRecord.team),
                joinedload(SessionEntryRecord.result),
            )
            .filter(SessionEntryRecord.session_id == session_id)
            .order_by(SessionEntryRecord.car_number.asc())
            .all()
        )
        return [self._build_entry_summary(record) for record in records]

    def list_entry_laps(self, session_id: str, entry_id: str) -> list[EntryLapModel]:
        self._assert_entry_belongs_to_session(session_id, entry_id)
        records = (
            self.db.query(EntryLapRecord)
            .filter(EntryLapRecord.session_entry_id == entry_id)
            .order_by(EntryLapRecord.lap_number.asc())
            .all()
        )
        return [self._build_lap_model(record) for record in records]

    def list_car_telemetry(
        self,
        session_id: str,
        entry_id: str,
        *,
        offset: int,
        limit: int,
        lap_number: int | None = None,
        session_time_from_ms: int | None = None,
        session_time_to_ms: int | None = None,
    ) -> list[CarTelemetrySampleModel]:
        self._assert_entry_belongs_to_session(session_id, entry_id)
        query = self.db.query(CarTelemetrySampleRecord).filter(
            CarTelemetrySampleRecord.session_entry_id == entry_id
        )

        if lap_number is not None:
            query = query.join(
                EntryLapRecord,
                CarTelemetrySampleRecord.lap_id == EntryLapRecord.id,
            ).filter(EntryLapRecord.lap_number == lap_number)

        if session_time_from_ms is not None:
            query = query.filter(CarTelemetrySampleRecord.session_time_ms >= session_time_from_ms)

        if session_time_to_ms is not None:
            query = query.filter(CarTelemetrySampleRecord.session_time_ms <= session_time_to_ms)

        records = (
            query.order_by(CarTelemetrySampleRecord.sample_seq.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._build_car_sample_model(record) for record in records]

    def list_position_telemetry(
        self,
        session_id: str,
        entry_id: str,
        *,
        offset: int,
        limit: int,
        lap_number: int | None = None,
        session_time_from_ms: int | None = None,
        session_time_to_ms: int | None = None,
    ) -> list[PositionSampleModel]:
        self._assert_entry_belongs_to_session(session_id, entry_id)
        query = self.db.query(PositionSampleRecord).filter(
            PositionSampleRecord.session_entry_id == entry_id
        )

        if lap_number is not None:
            query = query.join(
                EntryLapRecord,
                PositionSampleRecord.lap_id == EntryLapRecord.id,
            ).filter(EntryLapRecord.lap_number == lap_number)

        if session_time_from_ms is not None:
            query = query.filter(PositionSampleRecord.session_time_ms >= session_time_from_ms)

        if session_time_to_ms is not None:
            query = query.filter(PositionSampleRecord.session_time_ms <= session_time_to_ms)

        records = (
            query.order_by(PositionSampleRecord.sample_seq.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._build_position_sample_model(record) for record in records]

    def list_ticks(self, session_id: str, *, offset: int, limit: int) -> list[SessionTickModel]:
        records = (
            self.db.query(SessionTickRecord)
            .filter(SessionTickRecord.session_id == session_id)
            .order_by(SessionTickRecord.tick_no.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._build_tick_model(record) for record in records]

    def _upsert_season(self, snapshot: SessionSnapshot) -> SeasonRecord:
        season = self.db.get(SeasonRecord, snapshot.season.year)
        if season is None:
            season = SeasonRecord(year=snapshot.season.year, display_name=snapshot.season.display_name)
        else:
            season.display_name = snapshot.season.display_name
        self.db.add(season)
        self.db.flush()
        return season

    def _upsert_weekend(self, snapshot: SessionSnapshot, season: SeasonRecord) -> WeekendRecord:
        weekend = (
            self.db.query(WeekendRecord)
            .filter(
                WeekendRecord.source == snapshot.weekend.source,
                WeekendRecord.source_event_key == snapshot.weekend.source_event_key,
            )
            .first()
        )
        if weekend is None:
            weekend = WeekendRecord(
                source=snapshot.weekend.source,
                source_event_key=snapshot.weekend.source_event_key,
                season_year=season.year,
            )
        weekend.round_number = snapshot.weekend.round_number
        weekend.event_name = snapshot.weekend.event_name
        weekend.official_event_name = snapshot.weekend.official_event_name
        weekend.country = snapshot.weekend.country
        weekend.location = snapshot.weekend.location
        weekend.event_format = snapshot.weekend.event_format
        weekend.is_testing = snapshot.weekend.is_testing
        self.db.add(weekend)
        self.db.flush()
        return weekend

    def _create_session(self, snapshot: SessionSnapshot, weekend: WeekendRecord) -> EventSessionRecord:
        session = EventSessionRecord(
            source=snapshot.session.source,
            source_session_key=snapshot.session.source_session_key,
            weekend_id=weekend.id,
            session_name=snapshot.session.session_name,
            session_type=snapshot.session.session_type,
            import_profile=snapshot.session.import_profile,
            telemetry_status=snapshot.session.telemetry_status,
            meeting_key=snapshot.session.meeting_key,
            session_key=snapshot.session.session_key,
            api_path=snapshot.session.api_path,
            f1_api_support=snapshot.session.f1_api_support,
            scheduled_start_utc=snapshot.session.scheduled_start_utc,
            actual_start_utc=snapshot.session.actual_start_utc,
            state=snapshot.session.state,
            imported_at=snapshot.session.imported_at,
            last_accessed_at=snapshot.session.last_accessed_at,
            expires_at=snapshot.session.expires_at,
            pinned_at=None,
            deleted_at=None,
            error_message=snapshot.session.error_message,
        )
        self.db.add(session)
        return session

    def _upsert_drivers(self, snapshot: SessionSnapshot) -> dict[str, str]:
        driver_id_map: dict[str, str] = {}
        for payload in snapshot.drivers:
            record = (
                self.db.query(DriverRecord)
                .filter(
                    DriverRecord.source == payload.source,
                    DriverRecord.source_driver_key == payload.source_driver_key,
                )
                .first()
            )
            if record is None:
                record = DriverRecord(source=payload.source, source_driver_key=payload.source_driver_key)
            record.driver_number = payload.driver_number
            record.abbreviation = payload.abbreviation
            record.broadcast_name = payload.broadcast_name
            record.first_name = payload.first_name
            record.last_name = payload.last_name
            record.full_name = payload.full_name
            record.country_code = payload.country_code
            self.db.add(record)
            self.db.flush()
            driver_id_map[payload.source_driver_key] = record.id
        return driver_id_map

    def _upsert_teams(self, snapshot: SessionSnapshot) -> dict[str, str]:
        team_id_map: dict[str, str] = {}
        for payload in snapshot.teams:
            record = (
                self.db.query(TeamRecord)
                .filter(
                    TeamRecord.source == payload.source,
                    TeamRecord.source_team_key == payload.source_team_key,
                )
                .first()
            )
            if record is None:
                record = TeamRecord(
                    source=payload.source,
                    source_team_key=payload.source_team_key,
                    name=payload.name,
                )
            record.name = payload.name
            record.display_name = payload.display_name
            record.team_color = payload.team_color
            self.db.add(record)
            self.db.flush()
            team_id_map[payload.source_team_key] = record.id
        return team_id_map

    def _create_entries(
        self,
        snapshot: SessionSnapshot,
        session_id: str,
        driver_id_map: dict[str, str],
        team_id_map: dict[str, str],
    ) -> dict[str, str]:
        entry_id_map: dict[str, str] = {}
        for payload in snapshot.entries:
            record = SessionEntryRecord(
                session_id=session_id,
                driver_id=driver_id_map[payload.source_driver_key],
                team_id=team_id_map.get(payload.source_team_key) if payload.source_team_key else None,
                source_entry_key=payload.source_entry_key,
                car_number=payload.car_number,
                entry_type=payload.entry_type,
                status=payload.status,
                grid_position=payload.grid_position,
                classified_position=payload.classified_position,
            )
            self.db.add(record)
            self.db.flush()
            entry_id_map[payload.source_entry_key] = record.id
        return entry_id_map

    def _create_results(self, snapshot: SessionSnapshot, entry_id_map: dict[str, str]) -> None:
        for payload in snapshot.results:
            self.db.add(
                EntryResultRecord(
                    session_entry_id=entry_id_map[payload.source_entry_key],
                    position=payload.position,
                    classified_position=payload.classified_position,
                    points=payload.points,
                    time_status=payload.time_status,
                    status=payload.status,
                    laps_completed=payload.laps_completed,
                    q1_time_ms=payload.q1_time_ms,
                    q2_time_ms=payload.q2_time_ms,
                    q3_time_ms=payload.q3_time_ms,
                )
            )

    def _create_laps(self, snapshot: SessionSnapshot, entry_id_map: dict[str, str]) -> dict[tuple[str, int], str]:
        records: list[EntryLapRecord] = []
        for payload in snapshot.laps:
            record = EntryLapRecord(
                session_entry_id=entry_id_map[payload.source_entry_key],
                lap_number=payload.lap_number,
                lap_position=payload.lap_position,
                stint_number=payload.stint_number,
                lap_time_ms=payload.lap_time_ms,
                lap_start_time_ms=payload.lap_start_time_ms,
                lap_end_time_ms=payload.lap_end_time_ms,
                pit_out_time_ms=payload.pit_out_time_ms,
                pit_in_time_ms=payload.pit_in_time_ms,
                sector_1_time_ms=payload.sector_1_time_ms,
                sector_2_time_ms=payload.sector_2_time_ms,
                sector_3_time_ms=payload.sector_3_time_ms,
                sector_1_session_time_ms=payload.sector_1_session_time_ms,
                sector_2_session_time_ms=payload.sector_2_session_time_ms,
                sector_3_session_time_ms=payload.sector_3_session_time_ms,
                speed_i1_kph=payload.speed_i1_kph,
                speed_i2_kph=payload.speed_i2_kph,
                speed_fl_kph=payload.speed_fl_kph,
                speed_st_kph=payload.speed_st_kph,
                compound=payload.compound,
                tyre_life=payload.tyre_life,
                fresh_tyre=payload.fresh_tyre,
                track_status=payload.track_status,
                is_deleted=payload.is_deleted,
                deleted_reason=payload.deleted_reason,
                is_generated=payload.is_generated,
                is_accurate=payload.is_accurate,
            )
            records.append(record)
            self.db.add(record)
        self.db.flush()
        return {
            (payload.source_entry_key, payload.lap_number): record.id
            for payload, record in zip(snapshot.laps, records)
        }

    def _create_stints(self, snapshot: SessionSnapshot, entry_id_map: dict[str, str]) -> dict[tuple[str, int], str]:
        records: list[EntryStintRecord] = []
        for payload in snapshot.stints:
            record = EntryStintRecord(
                session_entry_id=entry_id_map[payload.source_entry_key],
                stint_number=payload.stint_number,
                compound=payload.compound,
                tyre_life_start=payload.tyre_life_start,
                tyre_life_end=payload.tyre_life_end,
                lap_start_number=payload.lap_start_number,
                lap_end_number=payload.lap_end_number,
                lap_count=payload.lap_count,
                started_session_time_ms=payload.started_session_time_ms,
                ended_session_time_ms=payload.ended_session_time_ms,
            )
            records.append(record)
            self.db.add(record)
        self.db.flush()
        return {
            (payload.source_entry_key, payload.stint_number): record.id
            for payload, record in zip(snapshot.stints, records)
        }

    def _create_ticks(self, snapshot: SessionSnapshot, session_id: str) -> dict[int, str]:
        records: list[SessionTickRecord] = []
        for index, payload in enumerate(snapshot.ticks, start=1):
            record = SessionTickRecord(
                session_id=session_id,
                tick_no=index,
                session_time_ms=payload.session_time_ms,
                source_time_utc=payload.source_time_utc,
                source_kind=payload.source_kind,
            )
            records.append(record)
            self.db.add(record)
        self.db.flush()
        return {payload.session_time_ms: record.id for payload, record in zip(snapshot.ticks, records)}

    def _create_session_events(
        self,
        snapshot: SessionSnapshot,
        session_id: str,
        entry_id_map: dict[str, str],
    ) -> None:
        for payload in snapshot.weather_samples:
            self.db.add(
                SessionWeatherSampleRecord(
                    session_id=session_id,
                    session_time_ms=payload.session_time_ms,
                    source_time_utc=payload.source_time_utc,
                    air_temp_c=payload.air_temp_c,
                    humidity_pct=payload.humidity_pct,
                    pressure_mbar=payload.pressure_mbar,
                    rainfall=payload.rainfall,
                    track_temp_c=payload.track_temp_c,
                    wind_direction_deg=payload.wind_direction_deg,
                    wind_speed_kph=payload.wind_speed_kph,
                )
            )
        for payload in snapshot.status_events:
            self.db.add(
                SessionStatusEventRecord(
                    session_id=session_id,
                    session_time_ms=payload.session_time_ms,
                    source_time_utc=payload.source_time_utc,
                    status=payload.status,
                )
            )
        for payload in snapshot.track_status_events:
            self.db.add(
                SessionTrackStatusEventRecord(
                    session_id=session_id,
                    session_time_ms=payload.session_time_ms,
                    source_time_utc=payload.source_time_utc,
                    status=payload.status,
                    message=payload.message,
                )
            )
        for payload in snapshot.race_control_messages:
            self.db.add(
                SessionRaceControlMessageRecord(
                    session_id=session_id,
                    session_entry_id=entry_id_map.get(payload.source_entry_key) if payload.source_entry_key else None,
                    session_time_ms=payload.session_time_ms,
                    source_time_utc=payload.source_time_utc,
                    category=payload.category,
                    message=payload.message,
                    flag=payload.flag,
                    scope=payload.scope,
                    sector=payload.sector,
                    lap_number=payload.lap_number,
                    driver_number=payload.driver_number,
                )
            )

    def _create_telemetry(
        self,
        snapshot: SessionSnapshot,
        entry_id_map: dict[str, str],
        lap_id_map: dict[tuple[str, int], str],
        stint_id_map: dict[tuple[str, int], str],
        tick_id_map: dict[int, str],
    ) -> None:
        for payload in snapshot.car_samples:
            self.db.add(
                CarTelemetrySampleRecord(
                    session_entry_id=entry_id_map[payload.source_entry_key],
                    tick_id=tick_id_map[payload.session_time_ms],
                    lap_id=lap_id_map.get((payload.source_entry_key, payload.lap_number)) if payload.lap_number else None,
                    stint_id=stint_id_map.get((payload.source_entry_key, payload.stint_number)) if payload.stint_number else None,
                    sample_seq=payload.sample_seq,
                    session_time_ms=payload.session_time_ms,
                    source_time_utc=payload.source_time_utc,
                    source=payload.source,
                    speed_kph=payload.speed_kph,
                    rpm=payload.rpm,
                    gear=payload.gear,
                    throttle_pct=payload.throttle_pct,
                    brake_on=payload.brake_on,
                    drs_state=payload.drs_state,
                )
            )
        for payload in snapshot.position_samples:
            self.db.add(
                PositionSampleRecord(
                    session_entry_id=entry_id_map[payload.source_entry_key],
                    tick_id=tick_id_map[payload.session_time_ms],
                    lap_id=lap_id_map.get((payload.source_entry_key, payload.lap_number)) if payload.lap_number else None,
                    stint_id=stint_id_map.get((payload.source_entry_key, payload.stint_number)) if payload.stint_number else None,
                    sample_seq=payload.sample_seq,
                    session_time_ms=payload.session_time_ms,
                    source_time_utc=payload.source_time_utc,
                    source=payload.source,
                    x=payload.x,
                    y=payload.y,
                    z=payload.z,
                    track_status=payload.track_status,
                )
            )

    def _assert_entry_belongs_to_session(self, session_id: str, entry_id: str) -> None:
        exists = (
            self.db.query(SessionEntryRecord.id)
            .filter(
                SessionEntryRecord.id == entry_id,
                SessionEntryRecord.session_id == session_id,
            )
            .first()
        )
        if exists is None:
            raise ValueError("Entry not found for session")

    def _count_by_session(self, model: type) -> dict[str, int]:
        rows = self.db.query(model.session_id, func.count(model.id)).group_by(model.session_id).all()
        return {session_id: count for session_id, count in rows}

    def _count_rows(self, model: type, session_id: str) -> int:
        return int(self.db.query(func.count(model.id)).filter(model.session_id == session_id).scalar() or 0)

    @staticmethod
    def _build_session_summary(
        record: EventSessionRecord,
        entry_counts: dict[str, int],
        tick_counts: dict[str, int],
    ) -> SessionSummary:
        weekend = record.weekend
        return SessionSummary(
            id=record.id,
            source=record.source,
            source_session_key=record.source_session_key,
            season_year=weekend.season_year,
            round_number=weekend.round_number,
            event_name=weekend.event_name,
            official_event_name=weekend.official_event_name,
            country=weekend.country,
            location=weekend.location,
            session_name=record.session_name,
            session_type=record.session_type,
            import_profile=record.import_profile,
            telemetry_status=record.telemetry_status,
            scheduled_start_utc=record.scheduled_start_utc,
            actual_start_utc=record.actual_start_utc,
            state=record.state,
            imported_at=record.imported_at,
            last_accessed_at=record.last_accessed_at,
            expires_at=record.expires_at,
            pinned_at=record.pinned_at,
            deleted_at=record.deleted_at,
            entry_count=entry_counts.get(record.id, 0),
            tick_count=tick_counts.get(record.id, 0),
        )

    @staticmethod
    def _build_entry_summary(record: SessionEntryRecord) -> SessionEntrySummary:
        return SessionEntrySummary(
            id=record.id,
            car_number=record.car_number,
            entry_type=record.entry_type,
            status=record.status,
            grid_position=record.grid_position,
            classified_position=record.classified_position,
            driver_id=record.driver.id,
            driver_number=record.driver.driver_number,
            driver_abbreviation=record.driver.abbreviation,
            driver_name=record.driver.full_name,
            team_id=record.team.id if record.team else None,
            team_name=record.team.name if record.team else None,
            team_color=record.team.team_color if record.team else None,
            result_position=record.result.position if record.result else None,
            laps_completed=record.result.laps_completed if record.result else None,
            points=record.result.points if record.result else None,
        )

    @staticmethod
    def _build_lap_model(record: EntryLapRecord) -> EntryLapModel:
        return EntryLapModel(
            id=record.id,
            lap_number=record.lap_number,
            lap_position=record.lap_position,
            stint_number=record.stint_number,
            lap_time_ms=record.lap_time_ms,
            lap_start_time_ms=record.lap_start_time_ms,
            lap_end_time_ms=record.lap_end_time_ms,
            pit_out_time_ms=record.pit_out_time_ms,
            pit_in_time_ms=record.pit_in_time_ms,
            sector_1_time_ms=record.sector_1_time_ms,
            sector_2_time_ms=record.sector_2_time_ms,
            sector_3_time_ms=record.sector_3_time_ms,
            sector_1_session_time_ms=record.sector_1_session_time_ms,
            sector_2_session_time_ms=record.sector_2_session_time_ms,
            sector_3_session_time_ms=record.sector_3_session_time_ms,
            speed_i1_kph=record.speed_i1_kph,
            speed_i2_kph=record.speed_i2_kph,
            speed_fl_kph=record.speed_fl_kph,
            speed_st_kph=record.speed_st_kph,
            compound=record.compound,
            tyre_life=record.tyre_life,
            fresh_tyre=record.fresh_tyre,
            track_status=record.track_status,
            is_deleted=record.is_deleted,
            deleted_reason=record.deleted_reason,
            is_generated=record.is_generated,
            is_accurate=record.is_accurate,
        )

    @staticmethod
    def _build_car_sample_model(record: CarTelemetrySampleRecord) -> CarTelemetrySampleModel:
        return CarTelemetrySampleModel(
            id=record.id,
            tick_id=record.tick_id,
            lap_id=record.lap_id,
            stint_id=record.stint_id,
            sample_seq=record.sample_seq,
            session_time_ms=record.session_time_ms,
            source_time_utc=record.source_time_utc,
            source=record.source,
            speed_kph=record.speed_kph,
            rpm=record.rpm,
            gear=record.gear,
            throttle_pct=record.throttle_pct,
            brake_on=record.brake_on,
            drs_state=record.drs_state,
        )

    @staticmethod
    def _build_position_sample_model(record: PositionSampleRecord) -> PositionSampleModel:
        return PositionSampleModel(
            id=record.id,
            tick_id=record.tick_id,
            lap_id=record.lap_id,
            stint_id=record.stint_id,
            sample_seq=record.sample_seq,
            session_time_ms=record.session_time_ms,
            source_time_utc=record.source_time_utc,
            source=record.source,
            x=record.x,
            y=record.y,
            z=record.z,
            track_status=record.track_status,
        )

    @staticmethod
    def _build_tick_model(record: SessionTickRecord) -> SessionTickModel:
        return SessionTickModel(
            id=record.id,
            tick_no=record.tick_no,
            session_time_ms=record.session_time_ms,
            source_time_utc=record.source_time_utc,
            source_kind=record.source_kind,
        )
