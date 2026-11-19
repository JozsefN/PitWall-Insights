"""Selective backend composition for panels and other analysis consumers."""

from ..domain.analysis.models import AnalysisRequest
from ..domain.analysis.common import json_safe
from ..domain.source_clock import timed_rows
from ..domain.snapshot import causal_snapshot
from ..domain.race_estimation.common import phase_at
from ..domain.race_estimation.engine import visible_context
from ..domain.race_estimation.models import RaceContext, RaceEstimateRequest
from ..domain.race_estimation.racing import (
    BATTLE_GAP_S,
    TimingHistory,
    battle_snapshot,
    race_finished,
)
from ..domain.review.models import REVIEW_VERSION
from ..domain.review.lapping import lapped_traffic
from ..domain.review.observations import (
    driver_cards,
    radio_messages,
    race_control_incidents,
    weather_timeline,
    incident_summary,
)
from ..domain.review.pace import (
    pace_baselines,
    track_evolution,
    field_projection,
    practice_profiles,
    consecutive_stints,
)
from ..domain.review.pit import pit_review
from ..domain.review.radio import radio_archive
from ..domain.review.segments import (
    lap_segments,
    compare_segments,
    reference_for_selected_lap,
)
from ..domain.review.surface import surface_review
from ..domain.review.circuit_flags import circuit_flags
from ..infrastructure.review_input import ReviewInput
from .calculation_guard import _ANALYSIS_GATE, AnalysisBusyError, acquire_database_lock


class ReviewService:
    def __init__(self, db):
        self.db = db
        self.input = ReviewInput(db)

    def radio_timeline(self, session_id):
        session = self.input.session(session_id)
        ids = {entry.car_number: entry.id for entry in self.input.entries(session_id)}
        return radio_archive(
            session.source_details or {}, session.session_time_origin_utc, ids
        )

    def compute(self, session_id, request):
        if not _ANALYSIS_GATE.acquire(blocking=False):
            raise AnalysisBusyError("Analysis is busy. Retry shortly.")
        try:
            if not acquire_database_lock(self.db):
                raise AnalysisBusyError("Analysis is busy. Retry shortly.")
            return json_safe(self._compute(session_id, request))
        finally:
            self.db.rollback()
            _ANALYSIS_GATE.release()

    def _compute(self, session_id, request):
        session = self.input.session(session_id)
        selected = set(request.entry_ids or [])
        self.input.entries(
            session_id, list(selected | {lap.entry_id for lap in request.laps}) or None
        )
        details = session.source_details or {}
        qualifying = any(
            word in session.session_name.lower() for word in ("qualifying", "shootout")
        )
        racing = session.session_name in ("Race", "Sprint")
        end = self.input.end(session)
        cutoff = end if request.as_of_ms is None else min(end, request.as_of_ms)
        groups = set(request.groups)
        inputs = (
            {"laps"} if groups - {"radio", "weather", "flags", "surface"} else set()
        )
        if groups & {"pace", "pit", "weather"}:
            inputs.add("weather")
        if groups & {"racecraft", "pace", "pit", "incidents", "flags"}:
            inputs.update(("track_status", "race_control"))
        data = self.input.load(
            session_id,
            AnalysisRequest(start_time_ms=0, end_time_ms=cutoff + 1),
            required_inputs=inputs,
            as_of_ms=cutoff,
        )
        data = causal_snapshot(data, cutoff)
        ids = {entry.car_number: entry.id for entry in data.entries}
        output = {
            "version": REVIEW_VERSION,
            "session_id": session_id,
            "as_of_ms": cutoff,
            "qualifying": qualifying,
            "entry_ids": sorted(selected),
            "groups": {},
        }
        result = output["groups"]
        if "drivers" in groups:
            cards = driver_cards(
                data,
                details,
                self.input.identities(session_id),
                cutoff,
                qualifying,
                request.as_of_ms is None or cutoff >= end,
            )
            result["drivers"] = [
                card for card in cards if not selected or card["entry_id"] in selected
            ]
        if "radio" in groups:
            radio = radio_messages(
                details, session.session_time_origin_utc, ids, cutoff
            )
            result["radio"] = {
                "available": "team_radio" in details
                and "team_radio" not in details.get("unavailable_sources", []),
                "clips": [
                    row for row in radio if not selected or row["entry_id"] in selected
                ][:200],
            }
        if "weather" in groups:
            result["weather"] = weather_timeline(data, cutoff)
        if "flags" in groups:
            result["flags"] = circuit_flags(data, cutoff)
        if "segments" in groups:
            result["segments"] = self._segments(data, request, cutoff)
        if "surface" in groups:
            profile = None
            if request.context_id:
                _, context = self.input.context(
                    request.context_id,
                    self.db.info.get("actor_user_id"),
                    session_id,
                    cutoff,
                )
                profile = context.track
                expected = (
                    f"{session.data_provider or session.source}:{session_id}:xy_metres"
                )
                if profile and (
                    profile.coordinate_frame != expected
                    or not profile.valid_season_from
                    <= session.weekend.season_year
                    <= profile.valid_season_to
                ):
                    raise ValueError(
                        "Track profile frame or season differs from this session"
                    )
            surface_data = (
                self.input.load(
                    session_id,
                    AnalysisRequest(
                        start_time_ms=max(0, cutoff - 2000),
                        end_time_ms=cutoff + 1,
                        entry_ids=request.entry_ids,
                    ),
                    required_inputs={"position"},
                    as_of_ms=cutoff,
                )
                if profile
                else data
            )
            result["surface"] = surface_review(surface_data, cutoff, profile)
        if groups & {"racecraft", "pace", "pit", "incidents"}:
            self._race_groups(
                session, data, details, cutoff, request, ids, groups, result, racing
            )
        return output

    def _segments(self, data, request, cutoff):
        entries = {entry.id: entry for entry in data.entries}
        selections = []
        for item in request.laps:
            lap = next(
                (
                    row
                    for row in entries[item.entry_id].laps
                    if row["lap_number"] == item.lap_number
                    and row.get("lap_end_time_ms") is not None
                ),
                None,
            )
            if (
                lap is None
                or lap.get("is_deleted")
                or lap.get("pit_in_time_ms") is not None
                or lap.get("pit_out_time_ms") is not None
            ):
                continue
            selections.append((item.entry_id, lap))
        rows = []
        if selections:
            selected_data = self.input.load(
                data.session_id,
                AnalysisRequest(
                    entry_ids=sorted({entry for entry, _ in selections}),
                    start_time_ms=0,
                    end_time_ms=cutoff + 1,
                    sample_interval_ms=250,
                ),
                required_inputs={"car", "position", "reference_line"},
                as_of_ms=cutoff,
                telemetry_lap_ids=[lap["id"] for _, lap in selections],
            )
            by_id = {entry.id: entry for entry in selected_data.entries}
            reference = selected_data.reference
            if reference is None:
                # A reported qualifying lap can be a usable shape even when lap
                # quality rules exclude it as a race pace baseline.
                for entry_id, lap in sorted(
                    selections, key=lambda item: item[1]["lap_end_time_ms"]
                ):
                    reference = reference_for_selected_lap(
                        lap, by_id[entry_id].positions
                    )
                    if reference is not None:
                        break
            for entry_id, lap in selections:
                entry = by_id[entry_id]
                rows.append(
                    {
                        "entry_id": entry_id,
                        "lap_number": lap["lap_number"],
                        "lap_time_s": lap["lap_time_ms"] / 1000,
                        "segments": lap_segments(
                            reference,
                            lap,
                            entry.positions,
                            entry.car,
                            request.segment_count,
                        ),
                    }
                )
        compare_segments(rows)
        return {
            "laps": rows,
            "requested": len(request.laps),
            "supported": sum(bool(row["segments"]) for row in rows),
            "method": "Equal-distance comparison on a shared reference. Colours apply to the selected laps. Source timing colours are available separately on the driver cards.",
        }

    def _race_groups(
        self, session, data, details, cutoff, request, ids, groups, result, racing
    ):
        selected = set(request.entry_ids or [])
        origin = session.session_time_origin_utc
        ctx = RaceContext(
            driver_ids=ids,
            intervals=timed_rows(details.get("intervals"), origin),
            positions=timed_rows(details.get("race_positions"), origin),
            overtakes=timed_rows(details.get("overtakes"), origin),
        )
        current_pits = self.input.pit_reports(session, cutoff, ids)
        inverse = {entry: car for car, entry in ids.items()}
        ctx.pits = [
            {
                **row,
                "driver_number": inverse[row["entry_id"]],
                "session_time_ms": row["event_time_ms"],
            }
            for row in current_pits
        ]
        ctx = visible_context(ctx, cutoff, 1000)
        fuel_gain = (request.fuel_burn_kg_per_lap or 0) * (
            request.fuel_time_s_per_kg or 0
        )
        paces = (
            pace_baselines(data, cutoff, ctx.intervals, fuel_gain)
            if groups & {"pace", "pit", "racecraft", "incidents"}
            else []
        )
        field = (
            field_projection(
                paces,
                TimingHistory(ctx.intervals),
                TimingHistory(ctx.positions),
                ids,
                cutoff - 1000,
                request.horizon_laps,
                racing
                and phase_at(data.track_status, cutoff) == "1"
                and not race_finished(data, cutoff),
                fuel_gain,
            )
            if groups & {"pace", "pit"}
            else []
        )
        history = (
            self.input.history(session, cutoff)
            if racing and groups & {"pace", "pit"}
            else []
        )
        if "pace" in groups:
            traffic = []
            if any(row.get("laps_down_reported") for row in field):
                geometry = self.input.load(
                    session.id,
                    AnalysisRequest(
                        start_time_ms=max(0, cutoff - 2000), end_time_ms=cutoff + 1
                    ),
                    required_inputs={"position", "reference_line"},
                    as_of_ms=cutoff,
                )
                traffic = lapped_traffic(
                    geometry, field, paces, cutoff, request.horizon_laps
                )
            result["pace"] = {
                "drivers": [
                    row for row in paces if not selected or row["entry_id"] in selected
                ],
                "practice_profiles": practice_profiles(
                    [
                        past
                        for other, past, _ in history
                        if other.weekend_id == session.weekend_id
                        and other.session_name.startswith("Practice")
                    ],
                    fuel_gain,
                ),
                "current_long_runs": [
                    row
                    for row in consecutive_stints(data, cutoff, fuel_gain)
                    if not selected or row["entry_id"] in selected
                ],
                "track_evolution": track_evolution(data, cutoff),
                "field_projection": field,
                "horizon_laps": request.horizon_laps,
                "lapped_traffic_scenarios": traffic,
                "fuel_scenario_gain_s_per_lap": fuel_gain or None,
            }
        if "racecraft" in groups:
            data.start_ms = max(data.start_ms, cutoff - 1800000)
            battles, passes = (
                battle_snapshot(data, ctx, RaceEstimateRequest(as_of_ms=cutoff))
                if racing
                else ([], [])
            )
            by_pace = {row["entry_id"]: row for row in paces if row["samples"] >= 3}
            for battle in battles:
                follower, ahead = (
                    by_pace.get(battle[key]) for key in ("follower_id", "ahead_id")
                )
                if follower and ahead:
                    advantage = ahead["median_pace_s"] - follower["median_pace_s"]
                    battle.update(
                        pace_advantage_s_per_lap=advantage,
                        follower_compound=follower["compound"],
                        ahead_compound=ahead["compound"],
                        follower_tyre_age_laps=follower["tyre_age_laps"],
                        ahead_tyre_age_laps=ahead["tyre_age_laps"],
                        pace_match=(
                            "large_follower_advantage"
                            if advantage >= 0.75
                            else (
                                "large_leader_advantage"
                                if advantage <= -0.75
                                else "similar_observed_pace"
                            )
                        ),
                    )
            result["racecraft"] = {
                "close_following_threshold_s": BATTLE_GAP_S,
                "battles": [
                    row
                    for row in battles
                    if not selected or {row["follower_id"], row["ahead_id"]} & selected
                ],
                "passes": [
                    item.model_dump(mode="json")
                    for item in passes[-150:]
                    if not selected or {item.entry_id, item.rival_entry_id} & selected
                ],
            }
        incidents = (
            race_control_incidents(data, ids, cutoff)
            if groups & {"incidents", "pit"}
            else []
        )
        if "incidents" in groups:
            visible_incidents = [
                row
                for row in incidents
                if not selected or selected.intersection(row["entry_ids"])
            ]
            result["incidents"] = {
                "reports": visible_incidents,
                **incident_summary(data, visible_incidents, cutoff),
                "damage_estimation": "Requires a report or separately corroborated sustained loss. Timing alone cannot measure damage or contact.",
            }
        if "pit" in groups:
            benchmark_reports = [
                *current_pits,
                *(row for _, _, reports in history for row in reports),
            ]
            result["pit"] = pit_review(
                data,
                cutoff,
                [past for _, past, _ in history],
                benchmark_reports,
                field,
                paces,
                request.repair_extra_s,
                incidents,
            )
