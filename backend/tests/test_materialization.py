from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.bootstrap import create_app
from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.identity_auth.domain.models import User
from modules.storage.infrastructure.db import get_db
from modules.session_domain.infrastructure.models import (
    SessionEntryRecord,
    SessionTickRecord,
    PositionSampleRecord,
    CarTelemetrySampleRecord,
    SessionRaceControlMessageRecord,
)
from modules.telemetry_materialization.application.service import (
    TelemetryMaterializationService,
)
from modules.telemetry_materialization.domain.models import (
    TelemetryMaterializationRequest,
)
from modules.telemetry_materialization.infrastructure.db_models import (
    TelemetryMaterializationJobRecord,
)
from modules.telemetry_materialization.infrastructure.repository import (
    TelemetryMaterializationRepository,
)
from support import FixtureSource, isolated_database, seed_session


class MaterializationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.database = isolated_database()
        self.factory = self.database.__enter__()
        self.session_id = seed_session(self.factory)
        with self.factory() as db:
            self.ids = [
                row[0]
                for row in db.query(SessionEntryRecord.id).order_by(
                    SessionEntryRecord.car_number
                )
            ]
        self.app = create_app()

        def database():
            with self.factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.database.__exit__(None, None, None)

    def authenticate(self):
        self.app.dependency_overrides[require_current_user] = lambda: User(
            id="test", email="test@example.com"
        )

    def payload(self, **updates):
        return {
            "session_id": self.session_id,
            "entry_ids": self.ids,
            "kinds": ["car", "position"],
            "scope": "session",
            **updates,
        }

    def run_worker(self):
        with patch(
            "modules.telemetry_materialization.application.service.build_session_source",
            return_value=FixtureSource(),
        ):
            with self.factory() as db:
                return TelemetryMaterializationService(db).run_next_job()

    def test_routing_authentication_and_validation(self):
        self.assertEqual(
            self.client.post(
                "/api/telemetry/materialization/ensure", json=self.payload()
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get("/api/telemetry/materialization/jobs").status_code, 401
        )
        self.authenticate()
        for updates in (
            {"entry_ids": []},
            {"entry_ids": ["x"] * 65},
            {"kinds": ["unknown"]},
            {"scope": "lap"},
            {"scope": "session", "lap_number": 1},
        ):
            self.assertEqual(
                self.client.post(
                    "/api/telemetry/materialization/ensure",
                    json=self.payload(**updates),
                ).status_code,
                422,
            )
        self.assertEqual(
            self.client.post(
                "/api/telemetry/materialization/ensure",
                json=self.payload(session_id="missing"),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/api/telemetry/materialization/ensure",
                json=self.payload(entry_ids=["foreign-entry"]),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/telemetry/materialization/jobs/missing").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/telemetry/materialization/jobs?limit=1000"
            ).status_code,
            422,
        )

    def test_worker_health_distinguishes_offline_stale_and_live_workers(self):
        self.assertEqual(
            self.client.get("/api/telemetry/materialization/health").status_code, 401
        )
        self.authenticate()
        self.assertEqual(
            self.client.get("/api/telemetry/materialization/health").json()["status"],
            "worker_offline",
        )
        now = datetime.now(timezone.utc)
        with self.factory() as db:
            repository = TelemetryMaterializationRepository(db)
            repository.touch_worker(
                "test-worker",
                hostname="test",
                process_id=1,
                started_at=now - timedelta(minutes=5),
                now=now - timedelta(minutes=2),
            )
        self.assertEqual(
            self.client.get("/api/telemetry/materialization/health").json()[
                "active_workers"
            ],
            0,
        )
        with self.factory() as db:
            TelemetryMaterializationRepository(db).touch_worker(
                "test-worker",
                hostname="test",
                process_id=1,
                started_at=now - timedelta(minutes=5),
                now=now,
            )
        health = self.client.get("/api/telemetry/materialization/health").json()
        self.assertEqual(health["status"], "ready")
        self.assertEqual(health["active_workers"], 1)

    def test_simultaneous_ensure_creates_one_job_and_one_segment_per_pair(self):
        self.authenticate()
        barrier = Barrier(8)

        def request(_):
            barrier.wait(timeout=10)
            response = self.client.post(
                "/api/telemetry/materialization/ensure", json=self.payload()
            )
            self.assertEqual(response.status_code, 202, response.text)
            return response.json()["job_id"]

        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(request, range(8)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(
            len(self.client.get("/api/telemetry/materialization/jobs").json()["jobs"]),
            1,
        )

    def test_real_worker_persistence_cache_reuse_lap_scope_and_force_refresh(self):
        self.authenticate()
        first = self.client.post(
            "/api/telemetry/materialization/ensure", json=self.payload()
        ).json()
        job = self.run_worker()
        self.assertEqual(job.status, "completed", job.error_message)
        self.assertEqual(job.rows_written, 480)
        self.assertEqual(
            self.client.get(
                f"/api/telemetry/materialization/jobs/{first['job_id']}"
            ).json()["status"],
            "completed",
        )
        cached = self.client.post(
            "/api/telemetry/materialization/ensure", json=self.payload()
        ).json()
        self.assertTrue(cached["ready"])
        self.assertEqual(len(cached["segments"]), 4)
        self.assertEqual(
            [segment["row_count"] for segment in cached["segments"]], [120] * 4
        )
        lap = self.client.post(
            "/api/telemetry/materialization/ensure",
            json=self.payload(scope="lap", lap_number=1),
        ).json()
        self.assertTrue(lap["ready"])
        refreshed = self.client.post(
            "/api/telemetry/materialization/ensure",
            json=self.payload(force_refresh=True),
        ).json()
        self.assertFalse(refreshed["ready"])
        self.assertNotEqual(first["job_id"], refreshed["job_id"])
        self.assertEqual(self.run_worker().rows_written, 480)
        with self.factory() as db:
            self.assertEqual(
                db.query(func.count(CarTelemetrySampleRecord.id)).scalar(), 240
            )
            self.assertEqual(
                db.query(func.count(PositionSampleRecord.id)).scalar(), 240
            )
            self.assertEqual(
                db.query(func.count(SessionTickRecord.id)).scalar(),
                db.query(
                    func.count(func.distinct(SessionTickRecord.session_time_ms))
                ).scalar(),
            )

    def test_parallel_workers_share_ticks_without_fk_or_sequence_collisions(self):
        self.authenticate()
        self.client.post(
            "/api/telemetry/materialization/ensure",
            json=self.payload(entry_ids=[self.ids[0]], kinds=["car"]),
        )
        self.client.post(
            "/api/telemetry/materialization/ensure",
            json=self.payload(entry_ids=[self.ids[1]], kinds=["position"]),
        )
        with patch(
            "modules.telemetry_materialization.application.service.build_session_source",
            return_value=FixtureSource(),
        ):

            def worker(_):
                with self.factory() as db:
                    return TelemetryMaterializationService(db).run_next_job()

            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = list(pool.map(worker, range(2)))
            # claim_next_job can initially skip locked work; process any remainder.
            if any(job is None for job in jobs):
                with self.factory() as db:
                    extra = TelemetryMaterializationService(db).run_next_job()
                jobs = [job for job in jobs if job is not None] + (
                    [extra] if extra else []
                )
        self.assertEqual(len(jobs), 2)
        self.assertTrue(
            all(job.status == "completed" for job in jobs),
            [(job.status, job.error_message) for job in jobs],
        )
        with self.factory() as db:
            self.assertEqual(
                db.query(func.count(CarTelemetrySampleRecord.id)).scalar(), 120
            )
            self.assertEqual(
                db.query(func.count(PositionSampleRecord.id)).scalar(), 120
            )

    def test_selected_driver_materialization_refreshes_messages_for_the_entire_roster(
        self,
    ):
        self.authenticate()

        class MessageSource(FixtureSource):
            def load_session(self, request, *, telemetry_selection=None):
                bundle = super().load_session(
                    request, telemetry_selection=telemetry_selection
                )
                bundle.race_control_messages = [
                    dict(
                        SessionTime=timedelta(seconds=30),
                        RacingNumber="2",
                        Message="CAR 2 INCIDENT NOTED",
                    )
                ]
                return bundle

        for refresh in (False, True):
            self.client.post(
                "/api/telemetry/materialization/ensure",
                json=self.payload(
                    entry_ids=[self.ids[0]], kinds=["car"], force_refresh=refresh
                ),
            )
            with patch(
                "modules.telemetry_materialization.application.service.build_session_source",
                return_value=MessageSource(),
            ):
                with self.factory() as db:
                    job = TelemetryMaterializationService(db).run_next_job()
                    self.assertEqual(job.status, "completed", job.error_message)
                    self.assertEqual(job.rows_written, 120)
            with self.factory() as db:
                messages = db.query(SessionRaceControlMessageRecord).all()
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0].session_entry_id, self.ids[1])

    def test_missing_source_is_failed_and_queued_work_is_recoverable(self):
        self.authenticate()
        first = self.client.post(
            "/api/telemetry/materialization/ensure", json=self.payload()
        ).json()
        with patch(
            "modules.telemetry_materialization.application.service.build_session_source",
            side_effect=RuntimeError("Provider unavailable"),
        ), self.assertLogs("pitwall.telemetry", level="ERROR"):
            with self.factory() as db:
                failed = TelemetryMaterializationService(db).run_next_job()
        self.assertEqual(failed.status, "failed")
        retry = self.client.post(
            "/api/telemetry/materialization/ensure", json=self.payload()
        ).json()
        self.assertNotEqual(retry["job_id"], first["job_id"])
        with self.factory() as db:
            record = db.get(TelemetryMaterializationJobRecord, retry["job_id"])
            record.status = "running"
            record.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=2)
            db.commit()
            self.assertEqual(
                TelemetryMaterializationService(db).recover_stale_jobs(), 1
            )
        self.assertEqual(
            self.client.get(
                f"/api/telemetry/materialization/jobs/{retry['job_id']}"
            ).json()["status"],
            "queued",
        )
        self.assertEqual(self.run_worker().status, "completed")
