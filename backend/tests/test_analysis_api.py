from datetime import timedelta
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import event, select, func
from app.bootstrap import create_app
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.storage.infrastructure.db import get_db
from modules.session_domain.infrastructure.db_models import (
    SessionEntryRecord,
    EventSessionRecord,
    SessionRaceControlMessageRecord,
)
from modules.session_domain.infrastructure.race_control import refresh_race_control
from modules.normalization.application.service import NormalizationService
from modules.feature_metrics.infrastructure.db_models import SessionAnalysisCacheRecord
from modules.feature_metrics.domain.analysis.catalog import DEFINITIONS
from modules.feature_metrics.application.analysis_service import _ANALYSIS_GATE
from support import isolated_database, seed_session, source_bundle


class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        self.database = isolated_database()
        self.factory = self.database.__enter__()
        self.session_id = seed_session(self.factory, full=True)
        with self.factory() as db:
            self.ids = list(
                db.scalars(
                    select(SessionEntryRecord.id).order_by(
                        SessionEntryRecord.car_number
                    )
                )
            )
        self.app = create_app()

        def database():
            with self.factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)
        self.url = f"/api/feature-metrics/sessions/{self.session_id}/analytics"

    def tearDown(self):
        self.client.close()
        self.database.__exit__(None, None, None)

    def authenticate(self):
        self.app.dependency_overrides[require_current_user] = lambda: User(
            id="test", email="test@example.com"
        )

    def test_auth_catalog_validation_and_session_membership(self):
        self.assertEqual(self.client.post(self.url, json={}).status_code, 401)
        self.assertEqual(
            self.client.get("/api/feature-metrics/analytics/catalog").status_code, 401
        )
        self.assertEqual(
            self.client.get(
                f"/api/feature-metrics/sessions/{self.session_id}/state?at_ms=30000"
            ).status_code,
            401,
        )
        self.authenticate()
        catalog = self.client.get("/api/feature-metrics/analytics/catalog").json()
        self.assertEqual(catalog["metric_count"], len(DEFINITIONS))
        for payload in (
            {"entry_ids": []},
            {"entry_ids": ["foreign"]},
            {"metric_ids": ["unknown"]},
            {"groups": ["unknown"]},
            {"start_time_ms": 20, "end_time_ms": 10},
            {"sample_interval_ms": 0},
            {"options": {"rapid_drop_kph": float("inf")}},
            {"options": {"unexpected": 1}},
            {"entry_ids": ["x"] * 65},
        ):
            # JSON transport correctly rejects infinities; model validation is tested separately.
            if payload.get("options", {}).get("rapid_drop_kph") == float("inf"):
                continue
            response = self.client.post(self.url, json=payload)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            self.client.post(
                self.url.replace(self.session_id, "missing"), json={}
            ).status_code,
            404,
        )

    def test_all_metrics_persist_cache_and_cache_hit_does_not_read_samples(self):
        self.authenticate()
        with patch(
            "modules.telemetry_materialization.application.service.build_session_source",
            side_effect=AssertionError("Analytics must not load providers"),
        ):
            first = self.client.post(self.url, json={})
        self.assertEqual(first.status_code, 200, first.text)
        response = first.json()
        self.assertFalse(response["cache_hit"])
        expected = sum(
            1 if definition.scope == "session" else 2
            for definition in DEFINITIONS.values()
        )
        self.assertEqual(len(response["metrics"]), expected)
        self.assertEqual(response["coverage"]["sampled_car_records"], 240)
        self.assertEqual(response["coverage"]["sampled_position_records"], 240)
        values = {
            row["metric_id"]: row
            for row in response["metrics"]
            if row["entry_id"] == self.ids[0]
        }
        self.assertEqual(values["lap_count"]["value"], 2)
        self.assertEqual(values["reported_drs_open_pct"]["value"], 100)
        statements = []
        with self.factory() as db:
            bind = db.get_bind()

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(bind, "before_cursor_execute", capture)
        try:
            second = self.client.post(self.url, json={})
        finally:
            event.remove(bind, "before_cursor_execute", capture)
        self.assertTrue(second.json()["cache_hit"])
        self.assertFalse(
            any(
                "car_telemetry_samples" in statement or "position_samples" in statement
                for statement in statements
            )
        )
        self.assertEqual(second.json()["computed_at"], response["computed_at"])
        with self.factory() as db:
            self.assertEqual(
                db.scalar(select(func.count()).select_from(SessionAnalysisCacheRecord)),
                1,
            )
            session = db.get(EventSessionRecord, self.session_id)
            session.imported_at += timedelta(seconds=1)
            db.commit()
        third = self.client.post(self.url, json={})
        self.assertFalse(third.json()["cache_hit"])
        self.assertNotEqual(
            third.json()["data_fingerprint"], response["data_fingerprint"]
        )

    def test_filtering_time_lap_windows_and_unavailable_telemetry(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            json={
                "entry_ids": [self.ids[0]],
                "groups": ["laps"],
                "lap_from": 2,
                "lap_to": 2,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data["start_time_ms"], data["end_time_ms"]), (60000, 120000))
        self.assertEqual(len(data["metrics"]), 25)
        self.assertEqual(
            next(
                row["value"]
                for row in data["metrics"]
                if row["metric_id"] == "lap_count"
            ),
            1,
        )
        self.assertEqual(data["coverage"]["sampled_car_records"], 0)
        scoped = self.client.post(
            self.url,
            json={
                "metric_ids": ["mean_speed_kph"],
                "start_time_ms": 30000,
                "end_time_ms": 40000,
            },
        ).json()
        self.assertEqual(len(scoped["metrics"]), 2)
        self.assertEqual(scoped["coverage"]["sampled_car_records"], 20)
        empty = self.client.post(
            self.url,
            json={"groups": ["speed"], "start_time_ms": 130000, "end_time_ms": 150000},
        ).json()
        self.assertTrue(all(row["status"] == "unavailable" for row in empty["metrics"]))
        self.assertEqual(
            self.client.post(self.url, json={"lap_from": 100}).status_code, 422
        )

    def test_point_in_time_state_does_not_peek_and_marks_stale_data(self):
        self.authenticate()
        url = f"/api/feature-metrics/sessions/{self.session_id}/state"
        response = self.client.get(url + "?at_ms=30000")
        self.assertEqual(response.status_code, 200, response.text)
        entries = response.json()["entries"]
        self.assertEqual(len(entries), 2)
        self.assertTrue(
            all(
                row["position_time_ms"] <= 30000 and row["car_time_ms"] <= 30000
                for row in entries
            )
        )
        self.assertTrue(all(row["reported_position"] is None for row in entries))
        self.assertTrue(all(not row["position_is_stale"] for row in entries))
        self.assertAlmostEqual(entries[0]["x_m"], 30.1)
        completed = self.client.get(url + "?at_ms=61000").json()["entries"]
        self.assertEqual(completed[0]["reported_position_time_ms"], 60000)
        self.assertEqual(completed[0]["current_lap_number"], 2)
        stale = self.client.get(url + "?at_ms=125000").json()["entries"]
        self.assertTrue(
            all(row["position_is_stale"] and row["car_is_stale"] for row in stale)
        )
        self.assertEqual(
            self.client.get(url + "?at_ms=100&entry_ids=foreign").status_code, 422
        )
        self.assertEqual(self.client.get(url + "?at_ms=-1").status_code, 422)

    def test_database_gate_blocks_same_schema_and_allows_independent_schemas(self):
        self.authenticate()

        def hold(db, schema):
            self.assertTrue(
                db.scalar(
                    select(
                        func.pg_try_advisory_xact_lock(
                            func.hashtextextended("pitwall:analysis:" + schema, 0)
                        )
                    )
                )
            )

        with isolated_database() as other_factory:
            with other_factory() as other:
                hold(
                    other,
                    other_factory.kw["bind"].get_execution_options()[
                        "schema_translate_map"
                    ][None],
                )
                self.assertEqual(
                    self.client.post(self.url, json={"groups": ["laps"]}).status_code,
                    200,
                )
        with self.factory() as same:
            hold(
                same,
                self.factory.kw["bind"].get_execution_options()["schema_translate_map"][
                    None
                ],
            )
            response = self.client.post(self.url, json={"groups": ["speed"]})
            self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(
            self.client.post(self.url, json={"groups": ["speed"]}).status_code, 200
        )

    def test_cache_variants_have_a_storage_bound(self):
        self.authenticate()
        with patch(
            "modules.feature_metrics.application.analysis_service.MAX_CACHE_VARIANTS", 2
        ):
            for group in ("laps", "speed", "controls"):
                self.assertEqual(
                    self.client.post(self.url, json={"groups": [group]}).status_code,
                    200,
                )
        with self.factory() as db:
            self.assertEqual(
                db.scalar(select(func.count()).select_from(SessionAnalysisCacheRecord)),
                2,
            )

    def test_work_limits_busy_and_concurrent_source_change_are_explicit(self):
        self.authenticate()
        with patch(
            "modules.feature_metrics.infrastructure.analysis_input.MAX_SAMPLES", 10
        ):
            self.assertEqual(self.client.post(self.url, json={}).status_code, 413)
        _ANALYSIS_GATE.acquire()
        try:
            response = self.client.post(self.url, json={})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["retry-after"], "5")
        finally:
            _ANALYSIS_GATE.release()
        with patch(
            "modules.feature_metrics.infrastructure.analysis_input.AnalysisInputProvider.fingerprint",
            side_effect=["old", "new"],
        ):
            response = self.client.post(self.url, json={})
            self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.post(self.url, json={}).status_code, 200)

    def test_message_refresh_is_idempotent_links_entire_roster_and_invalidates_cache(
        self,
    ):
        self.authenticate()
        original = self.client.post(self.url, json={}).json()
        bundle = source_bundle()
        bundle.race_control_messages = [
            dict(
                SessionTime=timedelta(seconds=30),
                RacingNumber="2",
                Message="CAR 2 INCIDENT NOTED",
            )
        ] * 2
        payloads = (
            NormalizationService()
            .build_snapshot(bundle, ttl_hours=1)
            .race_control_messages
        )
        for _ in range(2):
            with self.factory() as db:
                self.assertEqual(refresh_race_control(db, self.session_id, payloads), 1)
                db.commit()
        with self.factory() as db:
            messages = list(db.scalars(select(SessionRaceControlMessageRecord)))
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].session_entry_id, self.ids[1])
            self.assertEqual(refresh_race_control(db, self.session_id, []), 0)
            self.assertEqual(
                db.scalar(
                    select(func.count()).select_from(SessionRaceControlMessageRecord)
                ),
                1,
            )
        response = self.client.post(self.url, json={}).json()
        self.assertFalse(response["cache_hit"])
        self.assertNotEqual(original["data_fingerprint"], response["data_fingerprint"])
        self.assertEqual(
            next(
                row["value"]
                for row in response["metrics"]
                if row["metric_id"] == "reported_incident_message_count"
                and row["entry_id"] == self.ids[1]
            ),
            1,
        )
