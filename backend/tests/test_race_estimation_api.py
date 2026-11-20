import copy
import unittest
from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select, event
from app.bootstrap import create_app
from modules.delivery_api.api.auth_dependencies import get_current_user
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.storage.infrastructure.db import get_db
from modules.session_domain.infrastructure.db_models import (
    EventSessionRecord,
    SessionEntryRecord,
)
from modules.feature_metrics.infrastructure.db_models import SessionAnalysisCacheRecord
from modules.feature_metrics.application.calculation_guard import _ANALYSIS_GATE
from modules.feature_metrics.domain.race_estimation.catalog import DEFINITIONS
from modules.dashboard_layouts.domain.validation import validate_dashboard_config
from support import isolated_database, paid_membership, seed_session


class RaceEstimationApiTests(unittest.TestCase):
    def setUp(self):
        self.scope = isolated_database()
        self.factory = self.scope.__enter__()
        self.sid = seed_session(self.factory, full=True)
        with self.factory() as db:
            db.add_all(
                [
                    UserRecord(
                        id=name, email=name + "@example.com", password_hash="fixture"
                    )
                    for name in ("alice", "bob")
                ]
            )
            db.flush()
            for name in ("alice", "bob"):
                paid_membership(db, name)
            self.ids = list(
                db.scalars(
                    select(SessionEntryRecord.id).order_by(
                        SessionEntryRecord.car_number
                    )
                )
            )
            db.commit()
        self.app = create_app()

        def database():
            with self.factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)
        self.url = f"/api/feature-metrics/sessions/{self.sid}/race-estimates"

    def tearDown(self):
        self.client.close()
        self.scope.__exit__(None, None, None)

    def user(self, name="alice"):
        self.app.dependency_overrides[get_current_user] = lambda: User(
            id=name, email=name + "@example.com"
        )

    def test_auth_catalog_validation_and_private_dataset_guard(self):
        self.assertEqual(
            self.client.post(self.url, json={"as_of_ms": 90000}).status_code, 401
        )
        self.user()
        catalog = self.client.get("/api/feature-metrics/race-estimates/catalog")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()["metric_count"], len(DEFINITIONS))
        for payload in (
            {},
            {"as_of_ms": -1},
            {"as_of_ms": 90000, "entry_ids": ["foreign"]},
            {"as_of_ms": 90000, "lookback_ms": 1800001},
            {"as_of_ms": 90000, "assumptions": {"invented": 1}},
            {"as_of_ms": 90000, "assumptions": {"close_gap_s": 0}},
        ):
            response = self.client.post(self.url, json=payload)
            self.assertEqual(response.status_code, 422, response.text)
        with self.factory() as db:
            db.get(EventSessionRecord, self.sid).owner_user_id = "alice"
            db.commit()
        self.user("bob")
        self.assertEqual(
            self.client.post(self.url, json={"as_of_ms": 90000}).status_code, 404
        )

    def test_db_only_owner_scoped_cache_hit_and_fingerprint_invalidation(self):
        self.user()
        payload = {"as_of_ms": 90000, "entry_ids": self.ids[:1]}
        with patch(
            "modules.telemetry_materialization.application.service.build_session_source",
            side_effect=AssertionError("No network download in estimator"),
        ):
            first = self.client.post(self.url, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertFalse(body["cache_hit"])
        self.assertEqual([row["entry_id"] for row in body["drivers"]], self.ids[:1])
        self.assertEqual(set(body["drivers"][0]["metrics"]), set(DEFINITIONS))
        self.assertTrue(
            all(row["time_ms"] <= payload["as_of_ms"] for row in body["events"])
        )
        statements = []
        with self.factory() as db:
            bind = db.get_bind()

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(bind, "before_cursor_execute", capture)
        try:
            second = self.client.post(self.url, json=payload)
        finally:
            event.remove(bind, "before_cursor_execute", capture)
        self.assertTrue(second.json()["cache_hit"])
        self.assertFalse(
            any(
                "car_telemetry_samples" in sql or "position_samples" in sql
                for sql in statements
            )
        )
        self.user("bob")
        self.assertFalse(self.client.post(self.url, json=payload).json()["cache_hit"])
        with self.factory() as db:
            self.assertEqual(
                set(db.scalars(select(SessionAnalysisCacheRecord.owner_user_id))),
                {"alice", "bob"},
            )
            db.get(EventSessionRecord, self.sid).imported_at += timedelta(seconds=1)
            db.commit()
        third = self.client.post(self.url, json=payload).json()
        self.assertFalse(third["cache_hit"])
        self.assertNotEqual(body["fingerprint"], third["fingerprint"])

    def test_busy_failure_releases_guard_and_missing_data_is_not_invented(self):
        self.user()
        _ANALYSIS_GATE.acquire()
        try:
            response = self.client.post(self.url, json={"as_of_ms": 90000})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["Retry-After"], "2")
        finally:
            _ANALYSIS_GATE.release()
        response = self.client.post(self.url, json={"as_of_ms": 200000})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(
            all(
                row["metrics"]["current_speed_kph"]["value"] is None
                for row in response.json()["drivers"]
            )
        )
        self.assertTrue(_ANALYSIS_GATE.acquire(blocking=False))
        _ANALYSIS_GATE.release()

    def test_notification_settings_save_reload_and_reject_invalid_categories(self):
        self.user()
        config = {
            "id": "feed",
            "sections": [
                {
                    "id": "main",
                    "layout": {
                        "type": "group",
                        "direction": "row",
                        "grid": {"columns": 12, "rowHeight": 48},
                        "children": [
                            {
                                "type": "widget",
                                "widgetId": "race-notifications",
                                "instanceId": "feed",
                                "placement": {"x": 0, "y": 0, "w": 6, "h": 7},
                                "options": {
                                    "eventTypes": ["overtake", "yellow_flag"],
                                    "includeCandidates": False,
                                    "maxItems": 3,
                                    "minSeverity": "info",
                                    "driverScope": "selected",
                                    "lookbackMinutes": 3,
                                },
                            }
                        ],
                    },
                }
            ],
        }
        payload = {
            "name": "Race feed",
            "audience": "live-race",
            "schema_version": 2,
            "config": config,
        }
        created = self.client.post("/api/layouts", json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        layout_id = created.json()["id"]
        loaded = self.client.get(f"/api/layouts/{layout_id}").json()
        self.assertEqual(loaded["config"], config)
        for options in (
            {"eventTypes": ["confirmed_crash"]},
            {"eventTypes": ["overtake", "overtake"]},
            {"eventTypes": None},
            {"maxItems": True},
            {"maxItems": 2},
            {"minSeverity": "urgent"},
            {"lookbackMinutes": 30},
            {"includeCandidates": "yes"},
        ):
            bad = copy.deepcopy(config)
            bad["sections"][0]["layout"]["children"][0]["options"] = options
            with self.assertRaises(ValueError):
                validate_dashboard_config(bad, "live-race", 2)


if __name__ == "__main__":
    unittest.main()
