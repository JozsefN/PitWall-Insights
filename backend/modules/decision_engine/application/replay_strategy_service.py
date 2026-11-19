"""Assemble one causal race strategy snapshot for the whole replay field."""

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from modules.feature_metrics.application.calculation_guard import (
    _ANALYSIS_GATE,
    AnalysisBusyError,
    acquire_database_lock,
)
from modules.feature_metrics.domain.analysis.common import json_safe
from modules.feature_metrics.domain.analysis.models import AnalysisRequest
from modules.feature_metrics.domain.race_estimation.braking import first_braking_plateau
from modules.feature_metrics.domain.race_estimation.racing import race_finished
from modules.feature_metrics.domain.review.pace import rain_state
from modules.feature_metrics.domain.review.replay_pit import pit_model
from modules.feature_metrics.domain.review.replay_rivals import (
    RaceTiming,
    replay_rivals,
)
from modules.feature_metrics.domain.review.replay_sectors import (
    SectorTiming,
    warmup_model,
)
from modules.feature_metrics.domain.review.replay_tyres import (
    compound_offsets,
    compound_profiles,
    stint_fits,
)
from modules.feature_metrics.domain.review.replay_warnings import replay_warnings
from modules.feature_metrics.domain.snapshot import causal_snapshot
from modules.feature_metrics.domain.strategy.common import phase_at
from modules.feature_metrics.infrastructure.review_input import ReviewInput
from modules.session_domain.domain.race_schedule import race_schedule, scheduled_race_laps
from modules.session_domain.infrastructure.db_models import CarTelemetrySampleRecord
from ..domain.replay_driver import PlanningEvidence, driver_plan
from ..domain.replay_matchup import duel_scenarios, slow_stop_window
from ..domain.weather_crossover import rain_crossover

SHARED = Path(__file__).resolve().parents[4] / "shared"


def public_data(name):
    path = SHARED / name
    return _load_public_data(path, path.stat().st_mtime_ns) if path.exists() else {}


@lru_cache(maxsize=8)
def _load_public_data(path, _revision):
    return json.loads(path.read_text(encoding="utf-8"))


class RainScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    issued_at_ms: int = Field(ge=0, le=43_199_999)
    starts_at_ms: int = Field(ge=0, le=43_199_999)
    ends_at_ms: int = Field(ge=0, le=43_199_999)
    probability_pct: float = Field(ge=0, le=100)
    intensity: Literal["rain", "heavy"]

    @model_validator(mode="after")
    def check_interval(self):
        if not self.issued_at_ms <= self.starts_at_ms < self.ends_at_ms:
            raise ValueError("Rain scenario times must follow the issue time")
        if self.ends_at_ms - self.issued_at_ms > 900_000:
            raise ValueError("Rain scenario must end within 15 minutes of issue")
        return self


class ReplayStrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of_ms: int = Field(ge=0, le=43_199_999)
    rain_scenario: RainScenario | None = None


class ReplayStrategyService:
    def __init__(self, db):
        self.db = db
        self.source = ReviewInput(db)

    def evaluate(self, session_id, request):
        if not _ANALYSIS_GATE.acquire(blocking=False):
            raise AnalysisBusyError("Analytics is busy. Retry shortly.")
        try:
            if not acquire_database_lock(self.db):
                raise AnalysisBusyError("Analytics is busy. Retry shortly.")
            return json_safe(
                self._snapshot(session_id, request.as_of_ms, request.rain_scenario)
            )
        finally:
            self.db.rollback()
            _ANALYSIS_GATE.release()

    def _snapshot(self, session_id, cutoff, rain_scenario=None):
        session = self.source.session(session_id)
        if session.session_name.casefold() != "race":
            raise ValueError("Strategy calls are available for Grand Prix replay.")
        cutoff = min(cutoff, self.source.end(session))
        details = session.source_details or {}
        circuit = details.get("circuit_key")
        origin = session.session_time_origin_utc
        race_start = session.actual_start_utc or session.scheduled_start_utc
        start_ms = (
            max(0, round((race_start - origin).total_seconds() * 1000))
            if origin and race_start
            else 0
        )
        raw = self.source.load(
            session_id,
            AnalysisRequest(start_time_ms=0, end_time_ms=cutoff + 1),
            required_inputs={"laps", "weather", "track_status", "race_control"},
            as_of_ms=cutoff,
        )
        data = causal_snapshot(raw, cutoff)
        telemetry = (
            self._recent_speed(data, cutoff)
            if phase_at(data, cutoff) in ("1", "2")
            else {}
        )
        warnings, retired, incident, cohort, age_s = replay_warnings(
            data,
            cutoff,
            start_ms,
            race_start.timestamp() if race_start else 0,
            circuit,
            public_data("intervention-history.json").get("episodes", []),
            telemetry,
        )
        year = session.weekend.season_year
        total_laps = scheduled_race_laps(year, circuit)
        rules = race_schedule().get("raceRules", {}).get(f"{year}:{circuit}", {})
        completed = {
            entry.id: [
                row for row in entry.laps if row.get("lap_end_time_ms") is not None
            ]
            for entry in data.entries
        }
        leader_laps = max(
            (rows[-1]["lap_number"] for rows in completed.values() if rows), default=0
        )
        remaining = max(0, total_laps - leader_laps) if total_laps is not None else None
        rain = rain_state(data, cutoff)
        ended = race_finished(data, cutoff) or remaining == 0
        phase = incident["phase"]
        blocked = (
            "Race finished"
            if ended
            else (
                "Race suspended"
                if phase == "5"
                else (
                    "Waiting for race timing"
                    if leader_laps == 0 or phase is None
                    else (
                        "Scheduled race distance is unavailable"
                        if remaining is None
                        else (
                            "Dry-race planning needs a recent dry weather report"
                            if rain is not False
                            else None
                        )
                    )
                )
            )
        )
        history = (
            self.source.history(session, cutoff, include_older_practice=False)
            if leader_laps and not ended and phase != "5"
            else []
        )
        fits = stint_fits(data, cutoff, "current_race") if leader_laps else []
        for other, historical, _ in history:
            fits.extend(
                stint_fits(
                    historical,
                    historical.end_ms,
                    (
                        "practice"
                        if other.weekend_id == session.weekend_id
                        and other.session_name.startswith("Practice")
                        else "previous_race"
                    ),
                )
            )
        profiles = compound_profiles(fits)
        offsets = compound_offsets(fits)
        ids = {entry.car_number: entry.id for entry in data.entries}
        native = self.source.pit_reports(session, cutoff, ids) if leader_laps else []
        out_laps = defaultdict(set)
        for row in details.get("pit_out_laps", []):
            key = ids.get(str(row.get("driver_number")))
            if key:
                out_laps[key].add(row["lap_number"])
        splits = SectorTiming(raw, data, native, out_laps)
        pits = pit_model(
            [
                (data, native),
                *(
                    (past, reports)
                    for other, past, reports in history
                    if other.session_name == "Race"
                ),
            ],
            public_data("neutralisation-pace.json").get("races", []),
            race_start.timestamp() if race_start else 0,
            circuit,
            public_data("pit-sector-loss.json").get("races", []),
        )
        timing = RaceTiming(details, origin)
        gaps, headways = timing.gaps(data.entries, cutoff - 1000)
        stopped = {
            key
            for row in warnings
            if row["kind"] == "telemetry_stop"
            for key in row["entry_ids"]
        }
        forecast_input = (
            rain_scenario.model_dump()
            if rain_scenario
            and rain_scenario.issued_at_ms <= cutoff < rain_scenario.ends_at_ms
            else None
        )
        weather_archive = public_data("crossover-history.json").get("races", [])
        before_epoch = race_start.timestamp() if race_start else 0
        thermal = warmup_model(splits, weather_archive, before_epoch)
        slick_warmup = (
            sum(
                thermal.get(("SLICK", sector), {}).get("loss_s", 0) for sector in (2, 3)
            )
            if pits.get("green_basis") != "whole_laps"
            else 0.0
        )
        crossover = rain_crossover(
            data,
            splits,
            0 if ended else remaining,
            pits,
            incident,
            retired | stopped,
            weather_archive,
            before_epoch,
            forecast_input,
            thermal,
        )
        drivers = []
        evidence = PlanningEvidence(
            data,
            cutoff,
            remaining,
            rules,
            profiles,
            offsets,
            pits,
            gaps,
            headways,
            phase,
            cohort,
            age_s,
            warnings,
            incident["forecast"],
            incident["pit_entry_closed"],
            slick_warmup,
        )
        for entry in data.entries:
            rows = completed[entry.id]
            lap = rows[-1] if rows else {}
            driver_block = (
                "Retirement reported"
                if entry.id in retired
                else "Car appears stopped" if entry.id in stopped else blocked
            )
            recent = splits.latest.get(entry.id)
            if (
                not driver_block
                and recent
                and recent[1]
                and recent[0].get("lap_end_time_ms") is None
            ):
                driver_block = "On the out-lap. Use sector timing before another stop."
            drivers.append(driver_plan(entry, lap, rows, evidence, driver_block))
        models = {driver["entry_id"]: driver.pop("_plans", None) for driver in drivers}
        standings = (
            public_data("strategy-standings.json")
            .get("races", {})
            .get(str(session.session_key), {})
        )
        rivals, traffic = replay_rivals(
            data, cutoff, timing, gaps, native, standings, profiles, retired | stopped
        )
        self._attach_outlap_signals(rivals, splits, pits, incident, thermal)
        self._attach_rival_scenarios(
            drivers, models, rivals, traffic, gaps, pits["robust_scatter_s"]
        )
        self._attach_braking_evidence(drivers, cutoff)
        return {
            "version": "replay_strategy_v2",
            "session_id": session_id,
            "as_of_ms": cutoff,
            "total_laps": total_laps,
            "leader_completed_laps": leader_laps,
            "pit": pits,
            "compound_profiles": profiles,
            "warnings": warnings,
            "incident": incident,
            "crossover": crossover,
            "drivers": drivers,
            "status": blocked,
        }

    @staticmethod
    def _attach_outlap_signals(rivals, timing, pits, incident, thermal):
        readings = {entry: timing.outlap(entry, thermal) for entry in timing.current}
        phase = {"4": "sc", "6": "vsc"}.get(incident["phase"])
        for own, candidates in rivals.items():
            for row in candidates:
                reading = readings.get(row["entry_id"])
                if reading is None:
                    continue
                row["outlap"] = {**reading}
                gap, loss, green = (
                    row["gap_s"],
                    reading["remaining_loss_s"],
                    pits["median_s"],
                )
                if (
                    gap is None
                    or loss is None
                    or green is None
                    or incident["pit_entry_closed"]
                ):
                    continue
                # Use the observed timing gap once. Only the not-yet-observed loss is projected.
                cost = green - (pits["discount_s"].get(phase) or 0)
                rejoin = -gap - cost
                row["outlap"].update(
                    rejoin_margin_s=rejoin,
                    projected_rejoin_margin_s=rejoin + loss,
                    uncertain_flip=(rejoin < 0 < rejoin + loss),
                )

    @staticmethod
    def _attach_rival_scenarios(drivers, models, rivals, traffic, gaps, pit_scatter):
        for driver in drivers:
            key = driver["entry_id"]
            candidates = rivals.get(key, [])
            driver["rivals"] = candidates
            driver["following"] = traffic.get(key)
            if not (models[key] and key in gaps):
                continue
            matchups = []
            for row in [
                candidate
                for candidate in candidates
                if models.get(candidate["entry_id"]) and candidate["gap_s"] is not None
            ][:2]:
                rival = row["entry_id"]
                scenarios, call = duel_scenarios(
                    key,
                    rival,
                    models[key],
                    models[rival],
                    gaps,
                    (traffic.get(key) or {}).get("effect_s_lap", 0),
                )
                if scenarios:
                    if not matchups and call:
                        driver["call"] = call
                    can_box = any(
                        option["action"] == "box"
                        for scenario in scenarios
                        for option in scenario["choices"]
                    )
                    window = (
                        slow_stop_window(
                            row["gap_s"],
                            models[key].first_pit_cost(1),
                            row["recent_slow_stop"],
                            pit_scatter,
                        )
                        if can_box
                        else None
                    )
                    matchups.append(
                        {
                            "rival_entry_id": rival,
                            "scenarios": scenarios,
                            "slow_stop_window": window,
                        }
                    )
            driver["matchups"] = matchups

    def _recent_speed(self, data, cutoff):
        table = CarTelemetrySampleRecord
        samples = self.db.execute(
            select(table.session_entry_id, table.session_time_ms, table.speed_kph)
            .where(
                table.session_entry_id.in_([entry.id for entry in data.entries]),
                table.session_time_ms.between(max(0, cutoff - 9000), cutoff),
                table.speed_kph.between(0, 450),
            )
            .order_by(table.session_time_ms, table.sample_seq)
        ).mappings()
        grouped = defaultdict(list)
        for row in samples:
            group = grouped[row["session_entry_id"]]
            if not group or group[-1]["session_time_ms"] != row["session_time_ms"]:
                group.append(row)
        return grouped

    def _attach_braking_evidence(self, drivers, cutoff):
        lap_ids = [
            lap_id
            for row in drivers
            for lap_id in row["stint"].pop("braking_evidence_laps", [])
        ]
        if not lap_ids:
            return
        table = CarTelemetrySampleRecord
        samples = self.db.execute(
            select(
                table.session_entry_id,
                table.lap_id,
                table.session_time_ms,
                table.speed_kph,
                table.brake_on,
                table.throttle_pct,
            )
            .where(
                table.lap_id.in_(lap_ids),
                table.session_time_ms <= cutoff,
                table.speed_kph.between(0, 450),
            )
            .order_by(table.session_entry_id, table.session_time_ms, table.sample_seq)
        ).mappings()
        grouped = defaultdict(list)
        for row in samples:
            field = grouped[row["session_entry_id"]]
            if not field or field[-1]["session_time_ms"] != row["session_time_ms"]:
                field.append(row)
        for driver in drivers:
            stamp = first_braking_plateau(grouped.get(driver["entry_id"], []))
            if stamp is not None:
                driver["stint"]["loss_after_warning"] = "braking_anomaly"
                driver["stint"]["braking_evidence_ms"] = stamp
