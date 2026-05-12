from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from modules.ingestion.domain.models import SourceSessionBundle
from modules.normalization.domain.models import (
    CarTelemetrySamplePayload,
    DriverPayload,
    EntryLapPayload,
    EntryResultPayload,
    EntryStintPayload,
    PositionSamplePayload,
    SeasonPayload,
    SessionEntryPayload,
    SessionPayload,
    SessionRaceControlMessagePayload,
    SessionSnapshot,
    SessionStatusEventPayload,
    SessionTickPayload,
    SessionTrackStatusEventPayload,
    SessionWeatherSamplePayload,
    TeamPayload,
    WeekendPayload,
)


@dataclass(slots=True)
class _Participant:
    driver_number: str
    source_driver_key: str
    source_entry_key: str
    source_team_key: str | None
    car_number: str
    abbreviation: str | None = None
    broadcast_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    country_code: str | None = None
    team_name: str | None = None
    team_display_name: str | None = None
    team_color: str | None = None
    entry_status: str | None = None
    grid_position: int | None = None
    classified_position: int | None = None
    result_position: int | None = None
    result_classified_position: str | None = None
    points: float | None = None
    time_status: str | None = None
    result_status: str | None = None
    laps_completed: int | None = None
    q1_time_ms: int | None = None
    q2_time_ms: int | None = None
    q3_time_ms: int | None = None


class FastF1SessionSnapshotBuilder:
    source_name = "fastf1"

    def build(self, bundle: SourceSessionBundle, ttl_hours: int) -> SessionSnapshot:
        now = datetime.now(timezone.utc)
        participants, participants_by_number, participants_by_abbreviation = self._build_participants(bundle)
        laps_by_entry, laps = self._build_laps(
            bundle=bundle,
            participants_by_number=participants_by_number,
            participants_by_abbreviation=participants_by_abbreviation,
        )
        stints_by_entry, stints = self._build_stints(laps_by_entry)

        weather_samples = self._build_weather_samples(bundle)
        status_events = self._build_status_events(bundle)
        track_status_events = self._build_track_status_events(bundle)
        race_control_messages = self._build_race_control_messages(bundle, participants_by_number)
        car_samples = self._build_car_samples(bundle, participants_by_number, laps_by_entry, stints_by_entry)
        position_samples = self._build_position_samples(bundle, participants_by_number, laps_by_entry, stints_by_entry)
        ticks = self._build_ticks(
            laps=laps,
            weather_samples=weather_samples,
            status_events=status_events,
            track_status_events=track_status_events,
            race_control_messages=race_control_messages,
            car_samples=car_samples,
            position_samples=position_samples,
        )

        catalog = bundle.catalog_item
        metadata = bundle.metadata
        telemetry_status = "loaded" if bundle.import_profile == "full" else "not_loaded"

        return SessionSnapshot(
            season=SeasonPayload(year=catalog.season_year, display_name=str(catalog.season_year)),
            weekend=WeekendPayload(
                source=bundle.source,
                source_event_key=catalog.source_event_key,
                season_year=catalog.season_year,
                round_number=catalog.round_number,
                event_name=catalog.event_name,
                official_event_name=catalog.official_event_name,
                country=catalog.country,
                location=catalog.location,
                event_format=catalog.event_format,
                is_testing=catalog.is_testing,
            ),
            session=SessionPayload(
                source=bundle.source,
                source_session_key=catalog.source_session_key,
                source_event_key=catalog.source_event_key,
                session_name=catalog.session_name,
                session_type=catalog.session_type,
                import_profile=bundle.import_profile,
                telemetry_status=telemetry_status,
                meeting_key=metadata.meeting_key,
                session_key=metadata.session_key,
                api_path=metadata.api_path,
                f1_api_support=metadata.f1_api_support,
                scheduled_start_utc=catalog.scheduled_start_utc,
                actual_start_utc=metadata.actual_start_utc or catalog.scheduled_start_utc,
                state="cached",
                imported_at=now,
                last_accessed_at=now,
                expires_at=now + timedelta(hours=ttl_hours),
            ),
            drivers=self._build_driver_payloads(bundle.source, participants),
            teams=self._build_team_payloads(bundle.source, participants),
            entries=self._build_entry_payloads(participants),
            results=self._build_result_payloads(participants),
            laps=laps,
            stints=stints,
            ticks=ticks,
            weather_samples=weather_samples,
            status_events=status_events,
            track_status_events=track_status_events,
            race_control_messages=race_control_messages,
            car_samples=car_samples,
            position_samples=position_samples,
        )

    def _build_participants(
        self,
        bundle: SourceSessionBundle,
    ) -> tuple[list[_Participant], dict[str, _Participant], dict[str, _Participant]]:
        participants_by_number: dict[str, _Participant] = {}
        participants_by_abbreviation: dict[str, _Participant] = {}

        for row in bundle.drivers:
            participant = self._ensure_participant(bundle, participants_by_number, row)
            if participant.abbreviation:
                participants_by_abbreviation[participant.abbreviation] = participant

        for row in bundle.results:
            participant = self._ensure_participant(bundle, participants_by_number, row)
            participant.entry_status = participant.entry_status or self._as_text(
                row.get("Status") or row.get("ClassifiedStatus")
            )
            participant.grid_position = participant.grid_position or self._as_int(row.get("GridPosition"))
            participant.classified_position = participant.classified_position or self._as_int(row.get("Position"))
            participant.result_position = self._as_int(row.get("Position"))
            participant.result_classified_position = self._as_text(
                row.get("ClassifiedPosition") or row.get("Position")
            )
            participant.points = self._as_float(row.get("Points"))
            participant.time_status = self._as_text(row.get("Time"))
            participant.result_status = self._as_text(row.get("Status") or row.get("ClassifiedStatus"))
            participant.laps_completed = self._as_int(row.get("Laps") or row.get("LapsCompleted"))
            participant.q1_time_ms = self._as_duration_ms(row.get("Q1"))
            participant.q2_time_ms = self._as_duration_ms(row.get("Q2"))
            participant.q3_time_ms = self._as_duration_ms(row.get("Q3"))
            if participant.abbreviation:
                participants_by_abbreviation[participant.abbreviation] = participant

        for row in bundle.laps:
            participant = self._find_participant(participants_by_number, participants_by_abbreviation, row)
            if participant is None:
                continue
            participant.team_name = participant.team_name or self._as_text(row.get("Team"))
            participant.source_team_key = participant.source_team_key or self._build_team_key(
                bundle.catalog_item.season_year,
                participant.team_name,
            )

        for driver_number in set(bundle.car_telemetry) | set(bundle.position_data):
            if driver_number:
                self._ensure_participant(bundle, participants_by_number, {"DriverNumber": driver_number})

        participants = sorted(participants_by_number.values(), key=lambda item: item.car_number)
        return participants, participants_by_number, participants_by_abbreviation

    def _ensure_participant(
        self,
        bundle: SourceSessionBundle,
        participants_by_number: dict[str, _Participant],
        row: dict[str, Any],
    ) -> _Participant:
        driver_number = self._coerce_driver_number(row) or self._as_text(row.get("Driver")) or "unknown"
        participant = participants_by_number.get(driver_number)

        if participant is None:
            participant = _Participant(
                driver_number=driver_number,
                source_driver_key=self._build_driver_key(driver_number),
                source_entry_key=f"{bundle.catalog_item.source_session_key}:{driver_number}",
                source_team_key=None,
                car_number=driver_number,
            )
            participants_by_number[driver_number] = participant

        participant.abbreviation = participant.abbreviation or self._as_text(
            row.get("Abbreviation") or row.get("Driver")
        )
        participant.broadcast_name = participant.broadcast_name or self._as_text(row.get("BroadcastName"))
        participant.first_name = participant.first_name or self._as_text(row.get("FirstName"))
        participant.last_name = participant.last_name or self._as_text(row.get("LastName"))
        participant.full_name = participant.full_name or self._as_text(row.get("FullName"))
        if participant.full_name is None:
            participant.full_name = " ".join(filter(None, [participant.first_name, participant.last_name])) or None
        participant.country_code = participant.country_code or self._as_text(row.get("CountryCode"))
        participant.team_name = participant.team_name or self._as_text(row.get("TeamName") or row.get("Team"))
        participant.team_display_name = participant.team_display_name or participant.team_name
        participant.team_color = participant.team_color or self._as_text(row.get("TeamColor"))
        participant.source_team_key = participant.source_team_key or self._build_team_key(
            bundle.catalog_item.season_year,
            participant.team_name,
        )
        return participant

    def _find_participant(
        self,
        participants_by_number: dict[str, _Participant],
        participants_by_abbreviation: dict[str, _Participant],
        row: dict[str, Any],
    ) -> _Participant | None:
        driver_number = self._coerce_driver_number(row)
        if driver_number and driver_number in participants_by_number:
            return participants_by_number[driver_number]

        abbreviation = self._as_text(row.get("Driver") or row.get("Abbreviation"))
        if abbreviation and abbreviation in participants_by_abbreviation:
            return participants_by_abbreviation[abbreviation]

        return None

    def _build_driver_payloads(self, source: str, participants: list[_Participant]) -> list[DriverPayload]:
        return [
            DriverPayload(
                source=source,
                source_driver_key=participant.source_driver_key,
                driver_number=participant.driver_number,
                abbreviation=participant.abbreviation,
                broadcast_name=participant.broadcast_name,
                first_name=participant.first_name,
                last_name=participant.last_name,
                full_name=participant.full_name,
                country_code=participant.country_code,
            )
            for participant in participants
        ]

    def _build_team_payloads(self, source: str, participants: list[_Participant]) -> list[TeamPayload]:
        payloads: list[TeamPayload] = []
        seen: set[str] = set()
        for participant in participants:
            if not participant.source_team_key or not participant.team_name:
                continue
            if participant.source_team_key in seen:
                continue
            seen.add(participant.source_team_key)
            payloads.append(
                TeamPayload(
                    source=source,
                    source_team_key=participant.source_team_key,
                    name=participant.team_name,
                    display_name=participant.team_display_name,
                    team_color=participant.team_color,
                )
            )
        return payloads

    def _build_entry_payloads(self, participants: list[_Participant]) -> list[SessionEntryPayload]:
        return [
            SessionEntryPayload(
                source_entry_key=participant.source_entry_key,
                source_driver_key=participant.source_driver_key,
                source_team_key=participant.source_team_key,
                car_number=participant.car_number,
                entry_type="driver_car",
                status=participant.entry_status or participant.result_status,
                grid_position=participant.grid_position,
                classified_position=participant.classified_position or participant.result_position,
            )
            for participant in participants
        ]

    def _build_result_payloads(self, participants: list[_Participant]) -> list[EntryResultPayload]:
        return [
            EntryResultPayload(
                source_entry_key=participant.source_entry_key,
                position=participant.result_position,
                classified_position=participant.result_classified_position,
                points=participant.points,
                time_status=participant.time_status,
                status=participant.result_status or participant.entry_status,
                laps_completed=participant.laps_completed,
                q1_time_ms=participant.q1_time_ms,
                q2_time_ms=participant.q2_time_ms,
                q3_time_ms=participant.q3_time_ms,
            )
            for participant in participants
        ]

    def _build_laps(
        self,
        *,
        bundle: SourceSessionBundle,
        participants_by_number: dict[str, _Participant],
        participants_by_abbreviation: dict[str, _Participant],
    ) -> tuple[dict[str, list[EntryLapPayload]], list[EntryLapPayload]]:
        laps_by_entry: dict[str, list[EntryLapPayload]] = {
            participant.source_entry_key: []
            for participant in participants_by_number.values()
        }

        for row in bundle.laps:
            participant = self._find_participant(participants_by_number, participants_by_abbreviation, row)
            if participant is None:
                continue
            lap_number = self._as_int(row.get("LapNumber"))
            if lap_number is None:
                continue

            lap_time_ms = self._as_duration_ms(row.get("LapTime"))
            lap_end_time_ms = self._as_duration_ms(row.get("Time"))
            lap_start_time_ms = self._as_duration_ms(row.get("LapStartTime"))
            if lap_start_time_ms is None and lap_end_time_ms is not None and lap_time_ms is not None:
                lap_start_time_ms = max(0, lap_end_time_ms - lap_time_ms)

            laps_by_entry[participant.source_entry_key].append(
                EntryLapPayload(
                    source_entry_key=participant.source_entry_key,
                    lap_number=lap_number,
                    lap_position=self._as_int(row.get("Position")),
                    stint_number=self._as_int(row.get("Stint")),
                    lap_time_ms=lap_time_ms,
                    lap_start_time_ms=lap_start_time_ms,
                    lap_end_time_ms=lap_end_time_ms,
                    pit_out_time_ms=self._as_duration_ms(row.get("PitOutTime")),
                    pit_in_time_ms=self._as_duration_ms(row.get("PitInTime")),
                    sector_1_time_ms=self._as_duration_ms(row.get("Sector1Time")),
                    sector_2_time_ms=self._as_duration_ms(row.get("Sector2Time")),
                    sector_3_time_ms=self._as_duration_ms(row.get("Sector3Time")),
                    sector_1_session_time_ms=self._as_duration_ms(row.get("Sector1SessionTime")),
                    sector_2_session_time_ms=self._as_duration_ms(row.get("Sector2SessionTime")),
                    sector_3_session_time_ms=self._as_duration_ms(row.get("Sector3SessionTime")),
                    speed_i1_kph=self._as_float(row.get("SpeedI1")),
                    speed_i2_kph=self._as_float(row.get("SpeedI2")),
                    speed_fl_kph=self._as_float(row.get("SpeedFL")),
                    speed_st_kph=self._as_float(row.get("SpeedST")),
                    compound=self._as_text(row.get("Compound")),
                    tyre_life=self._as_int(row.get("TyreLife")),
                    fresh_tyre=self._as_bool(row.get("FreshTyre")),
                    track_status=self._as_text(row.get("TrackStatus")),
                    is_deleted=bool(row.get("Deleted", False)),
                    deleted_reason=self._as_text(row.get("DeletedReason")),
                    is_generated=bool(row.get("FastF1Generated", False)),
                    is_accurate=False if row.get("IsAccurate") is False else True,
                )
            )

        all_laps: list[EntryLapPayload] = []
        for entry_laps in laps_by_entry.values():
            entry_laps.sort(key=lambda item: item.lap_number)
            self._repair_lap_times(entry_laps)
            all_laps.extend(entry_laps)

        return laps_by_entry, all_laps

    @staticmethod
    def _repair_lap_times(laps: list[EntryLapPayload]) -> None:
        previous_end: int | None = None
        for lap in laps:
            if lap.lap_start_time_ms is None:
                lap.lap_start_time_ms = previous_end if previous_end is not None else 0
            if lap.lap_end_time_ms is None and lap.lap_start_time_ms is not None and lap.lap_time_ms is not None:
                lap.lap_end_time_ms = lap.lap_start_time_ms + lap.lap_time_ms
            previous_end = lap.lap_end_time_ms or previous_end

    def _build_stints(
        self,
        laps_by_entry: dict[str, list[EntryLapPayload]],
    ) -> tuple[dict[str, list[EntryStintPayload]], list[EntryStintPayload]]:
        stints_by_entry: dict[str, list[EntryStintPayload]] = {}
        all_stints: list[EntryStintPayload] = []

        for entry_key, laps in laps_by_entry.items():
            derived_stints: list[EntryStintPayload] = []
            current: EntryStintPayload | None = None

            for lap in laps:
                stint_number = lap.stint_number
                if stint_number is None:
                    stint_number = current.stint_number if current else 1
                    if current and lap.compound and current.compound and lap.compound != current.compound:
                        stint_number = current.stint_number + 1
                    lap.stint_number = stint_number

                if current is None or current.stint_number != stint_number:
                    current = EntryStintPayload(
                        source_entry_key=entry_key,
                        stint_number=stint_number,
                        compound=lap.compound,
                        tyre_life_start=lap.tyre_life,
                        tyre_life_end=lap.tyre_life,
                        lap_start_number=lap.lap_number,
                        lap_end_number=lap.lap_number,
                        lap_count=0,
                        started_session_time_ms=lap.lap_start_time_ms,
                        ended_session_time_ms=lap.lap_end_time_ms,
                    )
                    derived_stints.append(current)

                current.compound = current.compound or lap.compound
                current.tyre_life_end = lap.tyre_life or current.tyre_life_end
                current.lap_end_number = lap.lap_number
                current.ended_session_time_ms = lap.lap_end_time_ms or current.ended_session_time_ms
                current.lap_count += 1

            stints_by_entry[entry_key] = derived_stints
            all_stints.extend(derived_stints)

        return stints_by_entry, all_stints

    def _build_weather_samples(self, bundle: SourceSessionBundle) -> list[SessionWeatherSamplePayload]:
        payloads: list[SessionWeatherSamplePayload] = []
        for row in bundle.weather:
            session_time_ms = self._extract_session_time_ms(row)
            if session_time_ms is None:
                continue
            payloads.append(
                SessionWeatherSamplePayload(
                    session_time_ms=session_time_ms,
                    source_time_utc=self._as_datetime(row.get("Date")),
                    air_temp_c=self._as_float(row.get("AirTemp")),
                    humidity_pct=self._as_float(row.get("Humidity")),
                    pressure_mbar=self._as_float(row.get("Pressure")),
                    rainfall=self._as_bool(row.get("Rainfall")),
                    track_temp_c=self._as_float(row.get("TrackTemp")),
                    wind_direction_deg=self._as_int(row.get("WindDirection")),
                    wind_speed_kph=self._as_float(row.get("WindSpeed")),
                )
            )
        return payloads

    def _build_status_events(self, bundle: SourceSessionBundle) -> list[SessionStatusEventPayload]:
        payloads: list[SessionStatusEventPayload] = []
        for row in bundle.session_status:
            session_time_ms = self._extract_session_time_ms(row)
            status = self._as_text(row.get("Status"))
            if session_time_ms is None or not status:
                continue
            payloads.append(
                SessionStatusEventPayload(
                    session_time_ms=session_time_ms,
                    source_time_utc=self._as_datetime(row.get("Date")),
                    status=status,
                )
            )
        return payloads

    def _build_track_status_events(self, bundle: SourceSessionBundle) -> list[SessionTrackStatusEventPayload]:
        payloads: list[SessionTrackStatusEventPayload] = []
        for row in bundle.track_status:
            session_time_ms = self._extract_session_time_ms(row)
            status = self._as_text(row.get("Status"))
            if session_time_ms is None or not status:
                continue
            payloads.append(
                SessionTrackStatusEventPayload(
                    session_time_ms=session_time_ms,
                    source_time_utc=self._as_datetime(row.get("Date")),
                    status=status,
                    message=self._as_text(row.get("Message")),
                )
            )
        return payloads

    def _build_race_control_messages(
        self,
        bundle: SourceSessionBundle,
        participants_by_number: dict[str, _Participant],
    ) -> list[SessionRaceControlMessagePayload]:
        payloads: list[SessionRaceControlMessagePayload] = []
        for row in bundle.race_control_messages:
            session_time_ms = self._extract_session_time_ms(row)
            message = self._as_text(row.get("Message"))
            if session_time_ms is None or not message:
                continue
            driver_number = self._as_text(row.get("DriverNumber") or row.get("Driver"))
            participant = participants_by_number.get(driver_number) if driver_number else None
            payloads.append(
                SessionRaceControlMessagePayload(
                    session_time_ms=session_time_ms,
                    source_time_utc=self._as_datetime(row.get("Date")),
                    source_entry_key=participant.source_entry_key if participant else None,
                    category=self._as_text(row.get("Category")),
                    message=message,
                    flag=self._as_text(row.get("Flag")),
                    scope=self._as_text(row.get("Scope")),
                    sector=self._as_int(row.get("Sector")),
                    lap_number=self._as_int(row.get("Lap")),
                    driver_number=driver_number,
                )
            )
        return payloads

    def _build_car_samples(
        self,
        bundle: SourceSessionBundle,
        participants_by_number: dict[str, _Participant],
        laps_by_entry: dict[str, list[EntryLapPayload]],
        stints_by_entry: dict[str, list[EntryStintPayload]],
    ) -> list[CarTelemetrySamplePayload]:
        payloads: list[CarTelemetrySamplePayload] = []
        for driver_number, rows in bundle.car_telemetry.items():
            participant = participants_by_number.get(driver_number)
            if participant is None:
                continue
            for index, row in enumerate(sorted(rows, key=self._telemetry_sort_key), start=1):
                session_time_ms = self._extract_session_time_ms(row)
                if session_time_ms is None:
                    continue
                lap_number, stint_number = self._assign_lap_and_stint(
                    session_time_ms,
                    laps_by_entry.get(participant.source_entry_key, []),
                    stints_by_entry.get(participant.source_entry_key, []),
                )
                payloads.append(
                    CarTelemetrySamplePayload(
                        source_entry_key=participant.source_entry_key,
                        sample_seq=index,
                        session_time_ms=session_time_ms,
                        source_time_utc=self._as_datetime(row.get("Date")),
                        source=self._as_text(row.get("Source")),
                        lap_number=lap_number,
                        stint_number=stint_number,
                        speed_kph=self._as_float(row.get("Speed")),
                        rpm=self._as_int(row.get("RPM")),
                        gear=self._as_int(row.get("nGear") or row.get("Gear")),
                        throttle_pct=self._as_float(row.get("Throttle")),
                        brake_on=self._as_bool(row.get("Brake")),
                        drs_state=self._as_int(row.get("DRS")),
                    )
                )
        return payloads

    def _build_position_samples(
        self,
        bundle: SourceSessionBundle,
        participants_by_number: dict[str, _Participant],
        laps_by_entry: dict[str, list[EntryLapPayload]],
        stints_by_entry: dict[str, list[EntryStintPayload]],
    ) -> list[PositionSamplePayload]:
        payloads: list[PositionSamplePayload] = []
        for driver_number, rows in bundle.position_data.items():
            participant = participants_by_number.get(driver_number)
            if participant is None:
                continue
            for index, row in enumerate(sorted(rows, key=self._telemetry_sort_key), start=1):
                session_time_ms = self._extract_session_time_ms(row)
                if session_time_ms is None:
                    continue
                lap_number, stint_number = self._assign_lap_and_stint(
                    session_time_ms,
                    laps_by_entry.get(participant.source_entry_key, []),
                    stints_by_entry.get(participant.source_entry_key, []),
                )
                payloads.append(
                    PositionSamplePayload(
                        source_entry_key=participant.source_entry_key,
                        sample_seq=index,
                        session_time_ms=session_time_ms,
                        source_time_utc=self._as_datetime(row.get("Date")),
                        source=self._as_text(row.get("Source")),
                        lap_number=lap_number,
                        stint_number=stint_number,
                        x=self._as_float(row.get("X")),
                        y=self._as_float(row.get("Y")),
                        z=self._as_float(row.get("Z")),
                        track_status=self._as_text(row.get("Status")),
                    )
                )
        return payloads

    def _build_ticks(
        self,
        *,
        laps: list[EntryLapPayload],
        weather_samples: list[SessionWeatherSamplePayload],
        status_events: list[SessionStatusEventPayload],
        track_status_events: list[SessionTrackStatusEventPayload],
        race_control_messages: list[SessionRaceControlMessagePayload],
        car_samples: list[CarTelemetrySamplePayload],
        position_samples: list[PositionSamplePayload],
    ) -> list[SessionTickPayload]:
        tick_index: dict[int, dict[str, Any]] = {}

        def add_tick(session_time_ms: int | None, source_time_utc: datetime | None, kind: str) -> None:
            if session_time_ms is None:
                return
            bucket = tick_index.setdefault(session_time_ms, {"source_time_utc": None, "kinds": set()})
            bucket["kinds"].add(kind)
            if bucket["source_time_utc"] is None and source_time_utc is not None:
                bucket["source_time_utc"] = source_time_utc

        for lap in laps:
            add_tick(lap.lap_start_time_ms, None, "lap_boundary")
            add_tick(lap.lap_end_time_ms, None, "lap_boundary")
            add_tick(lap.pit_out_time_ms, None, "lap_boundary")
            add_tick(lap.pit_in_time_ms, None, "lap_boundary")
            add_tick(lap.sector_1_session_time_ms, None, "sector")
            add_tick(lap.sector_2_session_time_ms, None, "sector")
            add_tick(lap.sector_3_session_time_ms, None, "sector")

        for sample in weather_samples:
            add_tick(sample.session_time_ms, sample.source_time_utc, "weather")
        for event in status_events:
            add_tick(event.session_time_ms, event.source_time_utc, "session_status")
        for event in track_status_events:
            add_tick(event.session_time_ms, event.source_time_utc, "track_status")
        for message in race_control_messages:
            add_tick(message.session_time_ms, message.source_time_utc, "race_control")
        for sample in car_samples:
            add_tick(sample.session_time_ms, sample.source_time_utc, "car_telemetry")
        for sample in position_samples:
            add_tick(sample.session_time_ms, sample.source_time_utc, "position")

        return [
            SessionTickPayload(
                session_time_ms=session_time_ms,
                source_time_utc=tick_index[session_time_ms]["source_time_utc"],
                source_kind=",".join(sorted(tick_index[session_time_ms]["kinds"])),
            )
            for session_time_ms in sorted(tick_index)
        ]

    @staticmethod
    def _assign_lap_and_stint(
        session_time_ms: int,
        laps: list[EntryLapPayload],
        stints: list[EntryStintPayload],
    ) -> tuple[int | None, int | None]:
        lap_number: int | None = None
        for index, lap in enumerate(laps):
            start = lap.lap_start_time_ms
            end = laps[index + 1].lap_start_time_ms if index + 1 < len(laps) else lap.lap_end_time_ms
            if start is None:
                continue
            if end is None and session_time_ms >= start:
                lap_number = lap.lap_number
            elif end is not None and start <= session_time_ms < end:
                lap_number = lap.lap_number
                break

        stint_number: int | None = None
        for stint in stints:
            start = stint.started_session_time_ms
            end = stint.ended_session_time_ms
            if start is None:
                continue
            if end is None and session_time_ms >= start:
                stint_number = stint.stint_number
            elif end is not None and start <= session_time_ms <= end:
                stint_number = stint.stint_number
                break

        if stint_number is None and lap_number is not None:
            for lap in laps:
                if lap.lap_number == lap_number:
                    stint_number = lap.stint_number
                    break

        return lap_number, stint_number

    @staticmethod
    def _telemetry_sort_key(row: dict[str, Any]) -> tuple[int, datetime | None]:
        return (
            FastF1SessionSnapshotBuilder._extract_session_time_ms(row) or -1,
            FastF1SessionSnapshotBuilder._as_datetime(row.get("Date")),
        )

    @staticmethod
    def _extract_session_time_ms(row: dict[str, Any]) -> int | None:
        for key in ("SessionTime", "Time"):
            value = FastF1SessionSnapshotBuilder._as_duration_ms(row.get(key))
            if value is not None:
                return value
        return None

    @staticmethod
    def _coerce_driver_number(row: dict[str, Any]) -> str | None:
        return FastF1SessionSnapshotBuilder._as_text(row.get("DriverNumber") or row.get("driver_number"))

    @staticmethod
    def _build_driver_key(driver_number: str) -> str:
        return f"fastf1:driver:{driver_number}"

    @staticmethod
    def _build_team_key(season_year: int, team_name: str | None) -> str | None:
        if not team_name:
            return None
        return f"fastf1:team:{season_year}:{team_name.strip().lower().replace(' ', '-')}"

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"nan", "nat", "none"}:
            return None
        return text

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            text = str(value).strip().lower()
            if text in {"", "nan", "nat", "none"}:
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
            if math.isnan(number):
                return None
            return number
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_bool(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
        return None

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if hasattr(value, "to_pydatetime"):
            try:
                converted = value.to_pydatetime()
                return converted if converted.tzinfo else converted.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    @staticmethod
    def _as_duration_ms(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, timedelta):
            return int(value.total_seconds() * 1000)
        if hasattr(value, "to_pytimedelta"):
            try:
                return int(value.to_pytimedelta().total_seconds() * 1000)
            except Exception:
                return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and math.isnan(value):
                return None
            return int(value)
        return None
