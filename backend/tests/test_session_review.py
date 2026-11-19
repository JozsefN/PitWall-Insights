import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.bootstrap import create_app
from modules.delivery_api.api.auth_dependencies import get_current_user
from modules.feature_metrics.domain.analysis.geometry import ReferenceLine
from modules.feature_metrics.domain.analysis.models import AnalysisData, EntryData
from modules.feature_metrics.domain.race_estimation.models import (
    RaceContext,
    RaceEstimateRequest,
)
from modules.feature_metrics.domain.race_estimation.racing import (
    TimingHistory,
    battle_snapshot,
)
from modules.feature_metrics.domain.review.observations import (
    driver_cards,
    radio_messages,
)
from modules.feature_metrics.domain.review.pace import (
    consecutive_stints,
    field_projection,
)
from modules.feature_metrics.domain.review.pit import native_net_losses, pit_review
from modules.feature_metrics.domain.review.radio import radio_archive
from modules.feature_metrics.domain.review.segments import (
    lap_segments,
    compare_segments,
)
from modules.identity_auth.domain.models import User
from modules.feature_metrics.domain.review.surface import surface_review
from modules.feature_metrics.domain.review.circuit_flags import circuit_flags
from modules.feature_metrics.domain.strategy.models import TrackProfile
from modules.ingestion.infrastructure.openf1_client import OpenF1AccessError
from scripts.register_circuit_profile import prepare_profile
from modules.session_domain.infrastructure.db_models import (
    CarTelemetrySampleRecord,
    EventSessionRecord,
    SessionEntryRecord,
)
from modules.storage.infrastructure.db import get_db
from modules.normalization.application.service import NormalizationService
from modules.session_domain.infrastructure.repository import SessionRepository
from support import isolated_database, seed_session, source_bundle


def lap(number, ms=90000, **extra):
    return {
        "lap_number": number,
        "lap_time_ms": ms,
        "lap_start_time_ms": (number - 1) * 90000,
        "lap_end_time_ms": number * 90000,
        "is_accurate": True,
        "track_status": "1",
        "compound": "SOFT",
        "stint_number": 1,
        "tyre_life": number,
        **extra,
    }


def report(car, time, **extra):
    return {"driver_number": car, "session_time_ms": time, **extra}


def racing_fixture():
    ctx = RaceContext(
        driver_ids={"1": "a", "2": "b"},
        positions=[
            report("1", 0, position=1),
            report("2", 0, position=2),
            report("1", 32000, position=2),
            report("2", 32000, position=1),
        ],
        intervals=[
            report("2", 4000 + i * 4000, interval=1.15 - 0.12 * i) for i in range(7)
        ]
        + [report("1", 40000, interval=0.42)],
        overtakes=[
            {
                "session_time_ms": 31000,
                "overtaking_driver_number": 2,
                "overtaken_driver_number": 1,
            }
        ],
    )
    data = AnalysisData(
        "s",
        0,
        60000,
        entries=[EntryData("a", "1"), EntryData("b", "2")],
        track_status=[{"session_time_ms": 0, "status": "1"}],
    )
    return data, ctx


class ReviewMathTests(unittest.TestCase):
    def test_map_flags_keep_sector_scope_and_follow_replay_cutoff(self):
        data = AnalysisData("s", 0, 80, source="openf1")
        data.track_status = [
            {"session_time_ms": 0, "status": "1"},
            {"session_time_ms": 10, "status": "2"},
        ]
        data.race_control = [
            {
                "session_time_ms": 10,
                "scope": "Sector",
                "sector": 7,
                "flag": "DOUBLE YELLOW",
            },
            {"session_time_ms": 30, "scope": "Sector", "sector": 7, "flag": "CLEAR"},
            {"session_time_ms": 50, "scope": "Track", "flag": "RED"},
        ]
        self.assertEqual(circuit_flags(data, 5)["sectors"], [])
        self.assertEqual(
            circuit_flags(data, 20)["sectors"], [{"number": 7, "flag": "DOUBLE YELLOW"}]
        )
        self.assertIsNone(circuit_flags(data, 20)["track_flag"])
        self.assertTrue(circuit_flags(data, 40)["unlocated_caution"])
        self.assertEqual(circuit_flags(data, 70)["track_flag"], "RED")

    def test_licensed_profile_registration_keeps_surfaces_and_recovery_in_frame(self):
        rectangle = [[100, 210], [180, 210], [180, 270], [100, 270], [100, 210]]
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "geometry": {"type": "Polygon", "coordinates": [rectangle]},
                    "properties": {"kind": "gravel", "id": "trap"},
                },
                {
                    "geometry": {"type": "Polygon", "coordinates": [rectangle]},
                    "properties": {"kind": "marshal_sector", "sector_number": 7},
                },
                {
                    "geometry": {"type": "Point", "coordinates": [110, 260]},
                    "properties": {"kind": "recovery_access"},
                },
            ],
        }
        metadata = dict(
            circuit_key="fixture",
            coordinate_frame="openf1:s:xy_metres",
            source_uri="https://example.com/survey",
            source_license="Test fixture",
            valid_season_from=2025,
            valid_season_to=2025,
            circuit_length_m=5278,
            landmarks=[
                {"track_xy_m": [0, 0], "survey": [100, 200]},
                {"track_xy_m": [100, 0], "survey": [200, 200]},
                {"track_xy_m": [0, 100], "survey": [100, 300]},
            ],
        )
        profile = TrackProfile.model_validate(
            prepare_profile(geojson, metadata)["track"]
        )
        self.assertEqual(profile.zones[1].sector_number, 7)
        self.assertTrue(np.allclose(profile.recovery_points_m, [(10, 60)]))
        self.assertTrue(np.allclose(profile.zones[0].polygon_m[0], (0, 10)))
        result = surface_review(
            AnalysisData("s", 0, 100, source="openf1"), 100, profile
        )
        self.assertEqual(result["circuit_length_m"], 5278)
        self.assertEqual(result["source_license"], "Test fixture")

    def test_registered_surface_respects_position_error_and_pit_exclusion(self):
        profile = TrackProfile(
            circuit_key="fixture",
            coordinate_frame="openf1:s:xy_metres",
            source_uri="https://example.org/survey",
            valid_season_from=2025,
            valid_season_to=2025,
            position_error_m=5,
            zones=[
                {
                    "zone_id": "track",
                    "kind": "racing_surface",
                    "polygon_m": [[0, 0], [100, 0], [100, 20], [0, 20]],
                },
                {
                    "zone_id": "pit",
                    "kind": "pit_lane",
                    "polygon_m": [[0, 28], [100, 28], [100, 48], [0, 48]],
                },
                {
                    "zone_id": "gravel",
                    "kind": "gravel",
                    "polygon_m": [[0, -28], [100, -28], [100, -8], [0, -8]],
                },
            ],
        )
        entries = [
            EntryData(
                str(y),
                str(y),
                positions=[{"session_time_ms": 1000, "x": 500, "y": 10 * y}],
            )
            for y in (22, 38, -18)
        ]
        data = AnalysisData("s", 0, 1500, entries=entries)
        rows = {
            row["entry_id"]: row for row in surface_review(data, 1500, profile)["cars"]
        }
        self.assertFalse(rows["22"]["beyond_mapped_track_candidate"])
        self.assertFalse(rows["38"]["beyond_mapped_track_candidate"])
        self.assertTrue(rows["-18"]["beyond_mapped_track_candidate"])
        self.assertEqual(rows["-18"]["contained_in"], ["gravel"])
        self.assertEqual(surface_review(data, 4000, profile)["cars"], [])

    def test_rival_stop_excess_is_applied_only_to_counterfactual(self):
        entries = [
            EntryData(
                car,
                car,
                laps=[
                    lap(1),
                    lap(2, 99000, is_accurate=False),
                    lap(3, 102000, is_accurate=False),
                    lap(4),
                ],
            )
            for car in ("a", "b", "c", "d")
        ]
        data = AnalysisData(
            "s",
            0,
            400000,
            entries=entries,
            track_status=[{"session_time_ms": 0, "status": "1"}],
        )
        reports = [
            {
                "entry_id": car,
                "lap_number": 2,
                "event_time_ms": 182000,
                "known_at_ms": 370000,
                "lane_duration_s": 24 if car == "b" else 21,
                "session_id": "s",
            }
            for car in ("a", "b", "c", "d")
        ]
        field = [
            {
                "entry_id": car,
                "current_gap_to_leader_s": gap,
                "projected_elapsed_s": 450 + gap,
            }
            for car, gap in (("a", 0), ("b", 22))
        ]
        pace = [
            {"entry_id": car, "samples": 4, "median_pace_s": 90} for car in ("a", "b")
        ]
        result = pit_review(
            data,
            400000,
            [],
            reports,
            field,
            pace,
            5,
            [{"kind": "damage_report", "entry_ids": ["a"]}],
        )
        window = result["rival_windows"][0]
        self.assertEqual(
            (window["exit_margin_s"], window["normal_rival_stop_margin_s"]), (1, -2)
        )
        self.assertTrue(window["position_flip_scenario"])
        self.assertEqual(result["exit_scenarios"][0]["total_repair_stop_loss_s"], 26)
        self.assertIsNone(result["exit_scenarios"][1]["total_repair_stop_loss_s"])

    def test_sustained_battle_is_separate_from_completed_pass(self):
        data, ctx = racing_fixture()
        battles, passes = battle_snapshot(
            data, ctx, RaceEstimateRequest(as_of_ms=29500)
        )
        self.assertTrue(battles[0]["active_battle"])
        self.assertTrue(battles[0]["consistent_closing"])
        self.assertEqual(passes, [])
        _, passes = battle_snapshot(data, ctx, RaceEstimateRequest(as_of_ms=45000))
        self.assertEqual(
            [(event.entry_id, event.rival_entry_id, event.time_ms) for event in passes],
            [("b", "a", 44000)],
        )
        ctx.intervals[4]["interval"] = 2.5
        ctx.intervals[5]["interval"] = 2.5
        battles, _ = battle_snapshot(data, ctx, RaceEstimateRequest(as_of_ms=29500))
        self.assertFalse(battles[0]["consistent_closing"])

    def test_pit_and_transient_order_change_cannot_be_a_pass(self):
        data, ctx = racing_fixture()
        req = RaceEstimateRequest(as_of_ms=45000)
        ctx.pits = [report("1", 29000, known_at_ms=42000)]
        self.assertEqual(battle_snapshot(data, ctx, req)[1], [])
        ctx.pits = []
        ctx.positions += [
            report("1", 38000, position=1),
            report("2", 38000, position=2),
        ]
        self.assertEqual(battle_snapshot(data, ctx, req)[1], [])

    def test_qualifying_phase_requires_final_results_and_unique_matching_lap(self):
        data = AnalysisData(
            "s",
            0,
            300000,
            entries=[EntryData("a", "1", laps=[lap(1, 89500), lap(2, 89900)])],
        )
        details = {
            "qualifying_times": {"1": [89.5, 89.9, None]},
            "driver_headshots": {"1": "https://www.formula1.com/photo.png"},
            "qualifying_segments": [
                {
                    "driver_number": "1",
                    "lap_number": 1,
                    "sectors": [[2049, 2051], [2048], [0]],
                }
            ],
        }
        args = (data, details, {"a": {"name": "Driver A"}}, 300000, True)
        self.assertEqual(driver_cards(*args, False)[0]["qualifying"], [])
        card = driver_cards(*args, True)[0]
        self.assertEqual(
            card["qualifying"][0]["provider_colours"],
            [["green", "purple"], ["yellow"], ["unknown"]],
        )
        self.assertEqual(card["qualifying"][1]["lap_number"], 2)
        self.assertTrue(card["headshot_url"].endswith("photo.png"))
        data.entries[0].laps.append(lap(3, 89500))
        self.assertIsNone(driver_cards(*args, True)[0]["qualifying"][0]["lap_number"])

    def test_radio_cutoff_and_official_host_validation(self):
        origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = [
            {
                "date": (origin + timedelta(seconds=5)).isoformat(),
                "driver_number": 1,
                "recording_url": url,
            }
            for url in (
                "https://livetiming.formula1.com/example.mp3",
                "https://livetiming.formula1.com@example.org/example.mp3",
            )
        ]
        self.assertEqual(
            radio_messages({"team_radio": rows}, origin, {"1": "a"}, 5999), []
        )
        self.assertEqual(
            len(radio_messages({"team_radio": rows}, origin, {"1": "a"}, 6000)), 1
        )

    def test_radio_archive_estimates_recording_time_and_preserves_feed_fallback(self):
        origin = datetime(2025, 5, 18, 13, tzinfo=timezone.utc)

        def row(feed, filename):
            return {
                "date": (origin + timedelta(seconds=feed)).isoformat(),
                "driver_number": 12,
                "recording_url": f"https://livetiming.formula1.com/TeamRadio/{filename}.mp3",
            }

        rows = [
            row(40.350, "ANDANT01_12_20250518_150015"),
            row(105, "ANDANT01_12_20250518_150140"),
            row(142, "ANDANT01_12_20250518_150155"),
            row(154, "ANDANT01_12_20250518_150240"),  # Filename follows feed.
            row(170, "OTHER_99_20250518_150231"),
        ]
        ids = {"12": "driver"}
        legacy = radio_archive({"team_radio": rows}, origin, ids)
        self.assertTrue(legacy["available"])
        self.assertEqual(
            [(clip["time_ms"], clip["feed_time_ms"], clip["timing_basis"])
             for clip in legacy["clips"]],
            [(170000, 170000, "source_feed"), (154000, 154000, "source_feed"),
             (115000, 142000, "estimated_recording"), (100000, 105000, "estimated_recording"),
             (15000, 40350, "estimated_recording")],
        )
        sparse = {"team_radio": rows[:1]}
        self.assertEqual(radio_archive(sparse, origin, ids)["clips"][0]["time_ms"], 40350)
        self.assertEqual(radio_archive({**sparse, "session_gmt_offset": "02:00:00"}, origin, ids)
                         ["clips"][0]["time_ms"], 15000)
        self.assertEqual(radio_archive({**sparse, "unavailable_sources": ["team_radio"]}, origin, ids),
                         {"available": False, "clips": []})

    def test_equal_distance_segments_preserve_lap_time_and_drop_discontinuous_laps(
        self,
    ):
        theta = np.arange(0, 2 * np.pi, 2 * np.pi / 180)
        points = np.column_stack((np.cos(theta), np.sin(theta))) * 300
        reference = ReferenceLine(points)
        rows = [
            {"session_time_ms": i * 500, "x": 10 * xy[0], "y": 10 * xy[1]}
            for i, xy in enumerate(points)
        ]
        rows.append({**rows[0], "session_time_ms": 90000})
        car = [
            {
                "session_time_ms": row["session_time_ms"],
                "speed_kph": 170,
                "throttle_pct": 80,
                "brake_on": False,
            }
            for row in rows
        ]
        sectors = lap_segments(reference, lap(1), rows, car, 20)
        self.assertEqual(len(sectors), 20)
        self.assertAlmostEqual(sum(row["time_s"] for row in sectors), 90, places=2)
        self.assertEqual(sectors[2]["min_speed_kph"], 170)
        slower = [{**row, "time_s": row["time_s"] + 0.1} for row in sectors]
        compare_segments(
            [
                {"entry_id": "a", "lap_number": 1, "segments": sectors},
                {"entry_id": "b", "lap_number": 1, "segments": slower},
            ]
        )
        self.assertEqual(sectors[0]["colour"], "purple")
        self.assertAlmostEqual(slower[0]["delta_to_best_s"], 0.1)
        self.assertEqual(
            lap_segments(reference, lap(1), rows[:50] + rows[70:], car, 20), []
        )

    def test_native_pit_loss_waits_for_following_clean_lap(self):
        entry = EntryData(
            "a",
            "1",
            laps=[
                lap(1),
                lap(2, 99000, is_accurate=False),
                lap(3, 102000, is_accurate=False),
                lap(4),
            ],
        )
        data = AnalysisData(
            "s",
            0,
            360000,
            entries=[entry],
            track_status=[{"session_time_ms": 0, "status": "1"}],
        )
        stop = {
            "entry_id": "a",
            "lap_number": 2,
            "event_time_ms": 182000,
            "known_at_ms": 210000,
            "lane_duration_s": 21,
            "session_id": "s",
        }
        self.assertEqual(native_net_losses(data, 359999, [stop]), [])
        self.assertEqual(native_net_losses(data, 360000, [stop])[0]["net_loss_s"], 21)
        data.track_status.append({"session_time_ms": 182001, "status": "4"})
        self.assertEqual(native_net_losses(data, 360000, [stop]), [])

    def test_short_soft_run_is_excluded_and_fuel_scenario_is_a_component(self):
        entry = EntryData("a", "1", laps=[lap(i, 90000 + 100 * i) for i in range(1, 5)])
        data = AnalysisData("s", 0, 540000, entries=[entry])
        self.assertEqual(consecutive_stints(data, 540000, 0.045), [])
        entry.laps.extend([lap(5, 90500), lap(6, 90600)])
        result = consecutive_stints(data, 540000, 0.045)[0]
        self.assertAlmostEqual(result["observed_trend_s_per_lap"], 0.1)
        self.assertAlmostEqual(result["fuel_scenario_trend_s_per_lap"], 0.145)

    def test_field_projection_holds_lapped_uncertainty_and_fuel_gain(self):
        pace = [
            {
                "entry_id": entry,
                "median_pace_s": time,
                "samples": 4,
                "pace_scatter_s": 0.2,
            }
            for entry, time in (("a", 90), ("b", 89), ("c", 92))
        ]
        gaps = TimingHistory(
            [
                report("2", 10000, gap_to_leader=4),
                report("3", 10000, gap_to_leader="+1 LAP"),
            ]
        )
        ranks = TimingHistory([report("1", 0, position=1)])
        rows = field_projection(
            pace, gaps, ranks, {"1": "a", "2": "b", "3": "c"}, 11000, 5, True, 0.045
        )
        self.assertEqual(rows[0]["entry_id"], "b")
        self.assertAlmostEqual(rows[0]["projected_elapsed_s"], 449 - 0.675)
        self.assertIsNone(rows[-1]["projected_elapsed_s"])


class ReviewApiTests(unittest.TestCase):
    def test_core_metadata_enrichment_preserves_cached_entry_and_sample_ids(self):
        with isolated_database() as factory, factory() as db:
            bundle = source_bundle(full=True)
            bundle.source = bundle.catalog_item.source = "openf1"
            bundle.metadata.data_provider = "openf1"
            bundle.metadata.session_key = "123"
            bundle.metadata.session_info = {"lap_quality": [{"clean": True}]}
            normalizer = NormalizationService()
            repository = SessionRepository(db)
            legacy = normalizer.build_snapshot(bundle, ttl_hours=1)
            for driver, entry in zip(legacy.drivers, legacy.entries):
                driver.source_driver_key = entry.source_driver_key = f"fastf1:driver:{entry.car_number}"
            legacy.drivers[0].abbreviation = "WRONG"
            sid = repository.import_snapshot(
                legacy,
                source_version="fixture",
                force_refresh=False,
            )
            entry_ids = set(db.scalars(select(SessionEntryRecord.id)))
            sample_ids = set(db.scalars(select(CarTelemetrySampleRecord.id)))
            self.assertTrue(sample_ids)
            bundle.import_profile = "core"
            bundle.car_telemetry = bundle.position_data = {}
            bundle.metadata.session_info = {
                "team_radio": [{"fixture": True}],
                "session_gmt_offset": "02:00:00",
                "driver_headshots": {"1": "https://www.formula1.com/example"},
            }
            reuse_id = repository.import_snapshot(
                normalizer.build_snapshot(bundle, ttl_hours=1),
                source_version="fixture",
                force_refresh=False,
            )
            self.assertEqual(reuse_id, sid)
            self.assertEqual({entry.driver_abbreviation for entry in repository.list_entries(sid)}, {"D1", "D2"})
            self.assertEqual(set(db.scalars(select(SessionEntryRecord.id))), entry_ids)
            self.assertEqual(
                set(db.scalars(select(CarTelemetrySampleRecord.id))), sample_ids
            )
            details = db.get(EventSessionRecord, sid).source_details
            self.assertEqual(details["lap_quality"], [{"clean": True}])
            self.assertEqual(details["team_radio"], [{"fixture": True}])
            self.assertEqual(details["session_gmt_offset"], "02:00:00")

    def test_openf1_car_number_reuse_does_not_rename_previous_roster(self):
        with isolated_database() as factory, factory() as db:
            bundle = source_bundle()
            bundle.source = bundle.catalog_item.source = "openf1"
            bundle.metadata.data_provider = "openf1"
            normalizer, repository = NormalizationService(), SessionRepository(db)
            first_sid = repository.import_snapshot(
                normalizer.build_snapshot(bundle, ttl_hours=1), source_version="fixture", force_refresh=False
            )
            bundle.catalog_item.source_event_key = "test:2026:event"
            bundle.catalog_item.source_session_key = "test:2026:session"
            bundle.catalog_item.season_year = 2026
            bundle.drivers[0].update(Abbreviation="NEW", FullName="New Driver")
            second_sid = repository.import_snapshot(
                normalizer.build_snapshot(bundle, ttl_hours=1), source_version="fixture", force_refresh=False
            )
            older = next(entry for entry in repository.list_entries(first_sid) if entry.car_number == "1")
            newer = next(entry for entry in repository.list_entries(second_sid) if entry.car_number == "1")
            self.assertEqual((older.driver_abbreviation, newer.driver_abbreviation), ("D1", "NEW"))
            self.assertNotEqual(older.driver_id, newer.driver_id)

    def test_selective_groups_require_identity_and_keep_report_cutoff(self):
        with isolated_database() as factory:
            sid = seed_session(factory, full=True)
            when = datetime(2025, 1, 1, tzinfo=timezone.utc)
            with factory() as db:
                session = db.get(EventSessionRecord, sid)
                session.session_time_origin_utc = when
                session.source_details = {
                    "team_radio": [
                        {
                            "date": (when + timedelta(seconds=30)).isoformat(),
                            "driver_number": 1,
                            "recording_url": "https://livetiming.formula1.com/clip.mp3",
                        }
                    ]
                }
                db.commit()
                entry = db.scalar(
                    select(SessionEntryRecord.id).where(
                        SessionEntryRecord.session_id == sid,
                        SessionEntryRecord.car_number == "1",
                    )
                )
            app = create_app()

            def db_override():
                with factory() as db:
                    yield db

            app.dependency_overrides[get_db] = db_override
            with TestClient(app) as client:
                url = f"/api/feature-metrics/sessions/{sid}/review"
                timeline_url = f"/api/feature-metrics/sessions/{sid}/radio-timeline"
                self.assertEqual(client.post(url, json={}).status_code, 401)
                self.assertEqual(client.get(timeline_url).status_code, 401)
                self.assertEqual(client.post(timeline_url).status_code, 401)
                app.dependency_overrides[get_current_user] = lambda: User(
                    id="test", email="test@example.com"
                )
                payload = {"groups": ["radio"], "entry_ids": [entry], "as_of_ms": 30000}
                self.assertEqual(
                    client.post(url, json=payload).json()["groups"],
                    {"radio": {"available": True, "clips": []}},
                )
                payload["as_of_ms"] = 31000
                body = client.post(url, json=payload)
                self.assertEqual(body.status_code, 200, body.text)
                self.assertEqual(
                    body.json()["groups"]["radio"]["clips"][0]["entry_id"], entry
                )
                timeline = client.get(timeline_url)
                self.assertEqual(timeline.status_code, 200, timeline.text)
                self.assertEqual(timeline.json(), {"available": True, "clips": [{
                    "entry_id": entry, "time_ms": 30000, "feed_time_ms": 30000,
                    "timing_basis": "source_feed",
                    "recording_url": "https://livetiming.formula1.com/clip.mp3",
                }]})
                with factory() as db:
                    session = db.get(EventSessionRecord, sid)
                    session.data_provider = "openf1"
                    session.session_key = "1234"
                    original_rows = session.source_details["team_radio"]
                    session.source_details = {"unavailable_sources": ["team_radio", "weather"], "preserved": True}
                    db.commit()
                    samples = set(db.scalars(select(CarTelemetrySampleRecord.id)))
                self.assertFalse(client.get(timeline_url).json()["available"])
                with patch("modules.session_import.application.radio.OpenF1Client") as source:
                    get_radio = source.return_value.get
                    get_radio.side_effect = [OpenF1AccessError("Busy, retry later"), original_rows]
                    failed = client.post(timeline_url)
                    self.assertEqual(failed.status_code, 503, failed.text)
                    self.assertFalse(client.get(timeline_url).json()["available"])
                    recovered = client.post(timeline_url)
                    self.assertEqual(recovered.status_code, 200, recovered.text)
                    self.assertEqual(recovered.json(), timeline.json())
                    self.assertEqual(client.post(timeline_url).json(), timeline.json())
                    self.assertEqual(get_radio.call_count, 2)
                    get_radio.assert_called_with("team_radio", session_key="1234")
                with factory() as db:
                    details = db.get(EventSessionRecord, sid).source_details
                    self.assertEqual(details["unavailable_sources"], ["weather"])
                    self.assertTrue(details["preserved"])
                    self.assertEqual(samples, set(db.scalars(select(CarTelemetrySampleRecord.id))))
                self.assertEqual(
                    client.post(
                        url, json={**payload, "entry_ids": ["foreign"]}
                    ).status_code,
                    422,
                )
