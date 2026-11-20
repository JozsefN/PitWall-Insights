"""Replay extraction contracts and live API authentication/sampling regressions."""
from datetime import datetime, timedelta, timezone
import json
import secrets
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jose import jwt
from sqlalchemy import text, func
from sqlalchemy.exc import IntegrityError
from modules.identity_auth.application.security import SECRET_KEY, ALGORITHM
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.ingestion.domain.models import TelemetrySelection
from modules.ingestion.infrastructure.fastf1_adapter import FastF1Adapter
from modules.session_domain.domain.models import SessionImportRequest
from modules.session_domain.infrastructure.models import EventSessionRecord, SessionTickRecord
from modules.storage.infrastructure.db import SessionLocal
from modules.telemetry_materialization.infrastructure.repository import TelemetryMaterializationRepository
from support import create_verified_test_account


def api(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request("http://127.0.0.1:8000" + path,
                  data=json.dumps(data).encode() if data is not None else None,
                  headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


class ReplayExtractionTests(unittest.TestCase):
    def test_copy_insert_keeps_conflicts_foreign_keys_and_transaction_rollback(self):
        inserted_id = str(uuid4())
        with SessionLocal() as db:
            repository = TelemetryMaterializationRepository(db)
            session_id = db.query(EventSessionRecord.id).first()[0]
            tick_no, time_ms = db.query(func.max(SessionTickRecord.tick_no), func.max(SessionTickRecord.session_time_ms)).filter(SessionTickRecord.session_id == session_id).one()
            row = {"id": inserted_id, "session_id": session_id, "tick_no": (tick_no or 0)+1,
                   "session_time_ms": (time_ms or 0)+100000, "source_time_utc": datetime.now(timezone.utc), "source_kind": "replay-test"}
            heartbeat = MagicMock()
            self.assertEqual(repository._bulk_insert(SessionTickRecord, [row], conflict_constraint="uq_session_ticks_time", heartbeat=heartbeat), 1)
            self.assertEqual(repository._bulk_insert(SessionTickRecord, [{**row, "id":str(uuid4())}], conflict_constraint="uq_session_ticks_time"), 0)
            self.assertEqual(repository._bulk_insert(SessionTickRecord, [], conflict_constraint="uq_session_ticks_time"), 0)
            heartbeat.assert_called()
            self.assertIsNotNone(db.get(SessionTickRecord, inserted_id))
            db.rollback()
            self.assertIsNone(db.get(SessionTickRecord, inserted_id))
            with self.assertRaises(IntegrityError):
                repository._bulk_insert(SessionTickRecord, [{**row, "session_id":"missing-session"}], conflict_constraint="uq_session_ticks_time")
            db.rollback()

    def test_selection_converts_only_requested_drivers_and_reuses_parsed_source(self):
        session = SimpleNamespace(event={"EventName": "Test", "EventDate": datetime.now(timezone.utc)},
                                  drivers=["1", "2"], results=[{"DriverNumber": "1"}, {"DriverNumber": "2"}],
                                  car_data={"1": [{"Speed": 200}], "2": [{"Speed": 300}]},
                                  pos_data={"1": [{"X": 1}], "2": [{"X": 2}]}, load=MagicMock())
        adapter = FastF1Adapter()
        adapter._fastf1 = SimpleNamespace(__version__="test")
        request = SessionImportRequest(season_year=2025, round_number=1, session_name="Race", import_profile="full")
        previous = FastF1Adapter._parsed_session
        FastF1Adapter._parsed_session = None
        try:
            with patch.object(adapter, "_resolve_session", return_value=session):
                first = adapter.load_session(request, telemetry_selection=TelemetrySelection(frozenset({"1"}), frozenset({"position"})))
                second = adapter.load_session(request, telemetry_selection=TelemetrySelection(frozenset({"2"}), frozenset({"car"})))
                self.assertEqual(first.car_telemetry, {})
                self.assertEqual(first.position_data, {"1": [{"X": 1}]})
                self.assertEqual(second.car_telemetry, {"2": [{"Speed": 300}]})
                self.assertEqual(second.position_data, {})
                self.assertEqual(session.load.call_count, 1)
                request.force_refresh = True
                adapter.load_session(request)
                self.assertEqual(session.load.call_count, 2)
        finally:
            FastF1Adapter._parsed_session = previous

    def test_unavailable_source_is_not_saved_as_success(self):
        db = MagicMock()
        repository = TelemetryMaterializationRepository(db)
        job = SimpleNamespace(session_id="session", entry_ids=["driver"], kinds=["car"], scope="session", lap_number=0, force_refresh=False)
        with patch.object(repository, "_entry_source_keys", return_value={"driver": "source:1"}):
            with self.assertRaisesRegex(ValueError, "data source returned no car telemetry"):
                repository.materialize_snapshot(job, SimpleNamespace(car_samples=[], position_samples=[]), source_version=None)
        db.commit.assert_not_called()

    def test_partial_source_load_is_not_reused_on_retry(self):
        session = SimpleNamespace(event={"EventName":"Test"}, drivers=["1"], results=[{"DriverNumber":"1"}],
                                  car_data={}, pos_data={})
        def load(**kwargs):
            if session.load.call_count > 1:
                session.car_data = {"1":[{"Speed":200}]}
                session.pos_data = {"1":[{"X":1}]}
        session.load = MagicMock(side_effect=load)
        adapter = FastF1Adapter()
        adapter._fastf1 = SimpleNamespace(__version__="test")
        request = SessionImportRequest(season_year=2025, round_number=1, session_name="Race", import_profile="full")
        previous = FastF1Adapter._parsed_session
        FastF1Adapter._parsed_session = None
        try:
            with patch.object(adapter, "_resolve_session", return_value=session):
                adapter.load_session(request)
                self.assertIsNone(FastF1Adapter._parsed_session)
                retried = adapter.load_session(request)
                self.assertEqual(retried.car_telemetry, {"1":[{"Speed":200}]})
                self.assertEqual(session.load.call_count, 2)
        finally:
            FastF1Adapter._parsed_session = previous

    def test_failed_cache_is_not_ready_and_verified_empty_driver_does_not_requeue_forever(self):
        repository = TelemetryMaterializationRepository(MagicMock())
        with patch.object(repository, "_get_exact_segment", return_value=SimpleNamespace(status="failed", row_count=0)):
            self.assertIsNone(repository._find_satisfying_segment(session_id="s", entry_id="d", kind="car", scope="session", lap_number=None))
        with patch.object(repository, "_get_exact_segment", return_value=SimpleNamespace(status="completed", row_count=0)):
            self.assertIsNotNone(repository._find_satisfying_segment(session_id="s", entry_id="d", kind="car", scope="session", lap_number=None))
            # A lap or an individual DNS driver may be empty in a verified source load.
            self.assertIsNotNone(repository._find_satisfying_segment(session_id="s", entry_id="d", kind="car", scope="lap", lap_number=20))


class ReplayApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user_id = None
        cls.email = f"replay-test-{secrets.token_hex(8)}@example.com"
        password = secrets.token_urlsafe(24)
        with SessionLocal() as db:
            cls.user_id = create_verified_test_account(db, cls.email, password)
        status, auth = api("POST", "/api/auth/login", {"email": cls.email, "password": password})
        if status != 200:
            cls.tearDownClass()
            raise RuntimeError("Could not create replay test account")
        cls.token = auth["access_token"]

    @classmethod
    def tearDownClass(cls):
        if cls.user_id:
            with SessionLocal() as db:
                db.query(UserRecord).filter(UserRecord.id == cls.user_id).delete()
                db.commit()

    def test_active_token_renewal_and_expired_token_rejection(self):
        def token_at(expires):
            return jwt.encode({"sub": self.user_id, "email": self.email, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)
        near_expiry = token_at(datetime.now(timezone.utc) + timedelta(minutes=2))
        status, renewed = api("POST", "/api/auth/refresh", token=near_expiry)
        self.assertEqual(status, 200, renewed)
        claims = jwt.decode(renewed["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        self.assertEqual(claims["sub"], self.user_id)
        self.assertGreater(claims["exp"] - datetime.now(timezone.utc).timestamp(), 3500)
        self.assertEqual(api("POST", "/api/auth/refresh")[0], 401)
        self.assertEqual(api("POST", "/api/auth/refresh", token=token_at(datetime.now(timezone.utc)-timedelta(minutes=1)))[0], 401)
        deleted = jwt.encode({"sub": "missing-user", "email": self.email, "exp": datetime.now(timezone.utc)+timedelta(minutes=2)}, SECRET_KEY, algorithm=ALGORITHM)
        self.assertEqual(api("POST", "/api/auth/refresh", token=deleted)[0], 401)

    def test_sampled_replay_keeps_end_of_race_and_raw_reads_unchanged(self):
        with SessionLocal() as db:
            row = db.execute(text("select e.session_id,e.id, min(p.session_time_ms),max(p.session_time_ms) from session_entries e join position_samples p on p.session_entry_id=e.id group by e.id order by e.id limit 1")).one()
        session_id, entry_id, start, end = row
        status, timeline = api("GET", f"/api/sessions/{session_id}/replay-timeline", token=self.token)
        self.assertEqual(status, 200, timeline)
        self.assertGreater(timeline["end_time_ms"], timeline["start_time_ms"])
        base = f"/api/sessions/{session_id}/entries/{entry_id}/telemetry/position"
        status, sampled = api("GET", base+f"?limit=20000&sample_interval_ms=1000&session_time_from_ms={start}&session_time_to_ms={end}", token=self.token)
        self.assertEqual(status, 200, sampled)
        self.assertTrue(sampled)
        buckets = [sample["session_time_ms"]//1000 for sample in sampled]
        self.assertEqual(buckets, sorted(set(buckets)))
        self.assertLess(end-sampled[-1]["session_time_ms"], 1000)
        status, raw = api("GET", base+"?limit=7", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(raw), 7)
        self.assertEqual(raw[0]["session_time_ms"], start)
        self.assertEqual(api("GET", base+"?sample_interval_ms=0", token=self.token)[0], 422)
        self.assertEqual(api("GET", f"/api/sessions/{session_id}/replay-timeline")[0], 401)
