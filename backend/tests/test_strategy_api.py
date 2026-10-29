from datetime import timedelta
import unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select, update, func, event
from app.bootstrap import create_app
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.session_domain.infrastructure.db_models import (
    SessionEntryRecord,
    EntryLapRecord,
    EventSessionRecord,
    SessionTrackStatusEventRecord,
)
from modules.storage.infrastructure.db import get_db
from modules.feature_metrics.infrastructure.db_models import (
    StrategyContextRecord,
    SessionAnalysisCacheRecord,
)
from modules.feature_metrics.application.calculation_guard import _ANALYSIS_GATE
from support import isolated_database, seed_session


class StrategyApiTests(unittest.TestCase):
    def test_saved_explicit_scenario_can_rank_real_fixture_data_and_reuse_cache(self):
        self.authenticate()
        body = self.context(
            tyre_curves=[
                dict(
                    compound=name,
                    base_delta_s=0,
                    degradation_s_per_lap=rate,
                    max_valid_age_laps=50,
                    uncertainty_s_per_lap=0.2,
                    provenance="user_scenario",
                    source_uri="test:curve",
                )
                for name, rate in (("SOFT", 0.5), ("HARD", 0.1))
            ],
            tyre_inventory={
                self.ids[0]: [
                    dict(set_id="hard-one", compound="HARD", initial_age_laps=0)
                ]
            },
            pit_loss=dict(
                green_s=20,
                uncertainty_s=1,
                provenance="user_scenario",
                source_uri="test:pit",
            ),
            rules=dict(
                profile_id="test-rules",
                season_year=2025,
                minimum_distinct_compounds=2,
                source_uri="test:rules",
            ),
        )
        saved = self.client.post(self.base + "/contexts", json=body)
        self.assertEqual(saved.status_code, 201, saved.text)
        payload = self.payload(context_id=saved.json()["context_id"], remaining_laps=5)
        response = self.client.post(self.base + "/evaluate", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["recommendation_status"], "conditional_model_ranking"
        )
        self.assertEqual(
            response.json()["best_modeled_plan"]["stops"][0]["compound"], "HARD"
        )
        self.assertTrue(
            self.client.post(self.base + "/evaluate", json=payload).json()["cache_hit"]
        )

    def setUp(self):
        self.database = isolated_database()
        self.factory = self.database.__enter__()
        self.session_id = seed_session(self.factory, full=True)
        self.users = [
            User(id=str(uuid4()), email=f"strategy-{i}@example.com") for i in range(2)
        ]
        with self.factory() as db:
            self.ids = list(
                db.scalars(
                    select(SessionEntryRecord.id).order_by(
                        SessionEntryRecord.car_number
                    )
                )
            )
            db.add_all(
                [
                    UserRecord(id=user.id, email=user.email, password_hash="not-used")
                    for user in self.users
                ]
            )
            db.execute(update(EntryLapRecord).values(track_status="1"))
            db.add(
                SessionTrackStatusEventRecord(
                    session_id=self.session_id, session_time_ms=0, status="1"
                )
            )
            db.commit()
        self.app = create_app()

        def database():
            with self.factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)
        self.base = f"/api/strategy/sessions/{self.session_id}"

    def tearDown(self):
        self.client.close()
        self.database.__exit__(None, None, None)

    def authenticate(self, index=0):
        self.app.dependency_overrides[require_current_user] = lambda: self.users[index]

    def payload(self, **changes):
        return {"as_of_ms": 90000, "focus_entry_id": self.ids[0], **changes}

    def context(self, **changes):
        return {"known_at_ms": 0, "source_note": "Integration-test scenario", **changes}

    def test_auth_catalog_invalid_entries_windows_and_context_validation(self):
        self.assertEqual(self.client.get("/api/strategy/catalog").status_code, 401)
        self.assertEqual(
            self.client.post(self.base + "/evaluate", json=self.payload()).status_code,
            401,
        )
        self.authenticate()
        catalog = self.client.get("/api/strategy/catalog").json()
        self.assertTrue(
            all(
                row["formula"] and row["use"] and row["limitations"]
                for row in catalog["metrics"]
            )
        )
        for changes in (
            {"as_of_ms": -1},
            {"focus_entry_id": "foreign"},
            {"rival_entry_ids": ["foreign"]},
            {"remaining_laps": 81},
            {"max_stops": 3},
        ):
            body = self.payload()
            body.update(changes)
            self.assertEqual(
                self.client.post(self.base + "/evaluate", json=body).status_code, 422
            )
        self.assertEqual(
            self.client.post(
                self.base.replace(self.session_id, "missing") + "/evaluate",
                json=self.payload(),
            ).status_code,
            404,
        )
        response = self.client.post(
            self.base + "/contexts",
            json=self.context(
                tyre_inventory={"foreign": [{"set_id": "one", "compound": "HARD"}]}
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.client.post(
                self.base + "/contexts",
                json=self.context(
                    rules=dict(
                        profile_id="wrong-year",
                        season_year=2020,
                        minimum_distinct_compounds=2,
                        source_uri="test:rules",
                    )
                ),
            ).status_code,
            422,
        )

    def test_immutable_context_ownership_future_cutoff_and_deletion_cascade(self):
        self.authenticate()
        first = self.client.post(self.base + "/contexts", json=self.context())
        self.assertEqual(first.status_code, 201, first.text)
        key = first.json()["context_id"]
        self.assertEqual(
            self.client.get(self.base + "/contexts/" + key).status_code, 200
        )
        self.assertEqual(
            self.client.put(
                self.base + "/contexts/" + key, json=self.context()
            ).status_code,
            405,
        )
        response = self.client.post(
            self.base + "/evaluate", json=self.payload(context_id=key)
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.authenticate(1)
        self.assertEqual(
            self.client.get(self.base + "/contexts/" + key).status_code, 404
        )
        self.assertEqual(
            self.client.post(
                self.base + "/evaluate", json=self.payload(context_id=key)
            ).status_code,
            404,
        )
        self.authenticate()
        future = self.client.post(
            self.base + "/contexts", json=self.context(known_at_ms=100000)
        ).json()["context_id"]
        self.assertEqual(
            self.client.post(
                self.base + "/evaluate", json=self.payload(context_id=future)
            ).status_code,
            422,
        )
        with self.factory() as db:
            db.query(UserRecord).filter(UserRecord.id == self.users[0].id).delete()
            db.commit()
            self.assertEqual(
                db.scalar(select(func.count()).select_from(StrategyContextRecord)), 0
            )
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(SessionAnalysisCacheRecord)
                    .where(SessionAnalysisCacheRecord.owner_user_id == self.users[0].id)
                ),
                0,
            )

    def test_past_decision_cannot_see_future_lap_results_and_cache_has_no_sample_reads(
        self,
    ):
        self.authenticate()
        first = self.client.post(self.base + "/evaluate", json=self.payload())
        self.assertEqual(first.status_code, 200, first.text)
        data = first.json()
        compound = next(
            row
            for row in data["values"]
            if row["metric_id"] == "strategy_reported_tyre_age_laps"
            and row["entry_id"] == self.ids[0]
        )
        self.assertEqual(compound["value"], 1)
        self.assertEqual(data["recommendation_status"], "missing_model_inputs")
        statements = []
        bind = self.factory.kw["bind"]

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(bind, "before_cursor_execute", capture)
        try:
            cached = self.client.post(self.base + "/evaluate", json=self.payload())
        finally:
            event.remove(bind, "before_cursor_execute", capture)
        self.assertTrue(cached.json()["cache_hit"])
        self.assertFalse(
            any(
                "position_samples" in statement or "car_telemetry_samples" in statement
                for statement in statements
            )
        )
        with self.factory() as db:
            db.execute(
                update(EntryLapRecord)
                .where(EntryLapRecord.lap_number == 2)
                .values(
                    compound="FUTURE", tyre_life=99, lap_time_ms=10000, lap_position=99
                )
            )
            record = db.get(EventSessionRecord, self.session_id)
            record.imported_at += timedelta(seconds=1)
            db.commit()
        modified = self.client.post(self.base + "/evaluate", json=self.payload()).json()
        self.assertFalse(modified["cache_hit"])
        self.assertEqual(modified["values"], data["values"])
        self.assertEqual(modified["models"], data["models"])

    def test_strategy_shares_compute_gate_and_never_downloads_sources(self):
        self.authenticate()
        with patch(
            "modules.feature_metrics.infrastructure.analysis_input.MAX_SAMPLES", 5
        ):
            self.assertEqual(
                self.client.post(
                    self.base + "/evaluate", json=self.payload()
                ).status_code,
                413,
            )
        _ANALYSIS_GATE.acquire()
        try:
            self.assertEqual(
                self.client.post(
                    self.base + "/evaluate", json=self.payload()
                ).status_code,
                429,
            )
        finally:
            _ANALYSIS_GATE.release()
        with patch(
            "modules.telemetry_materialization.application.service.build_session_source",
            side_effect=AssertionError("No source downloads in strategy"),
        ):
            self.assertEqual(
                self.client.post(
                    self.base + "/evaluate", json=self.payload()
                ).status_code,
                200,
            )

    def test_empty_current_race_data_produces_explicit_unavailable_values(self):
        self.authenticate()
        body = self.payload()
        body["as_of_ms"] = 0
        response = self.client.post(self.base + "/evaluate", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIsNone(data["best_modeled_plan"])
        self.assertTrue(any(row["status"] == "unavailable" for row in data["values"]))
