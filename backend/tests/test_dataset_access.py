import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.bootstrap import create_app
from modules.delivery_api.api.auth_dependencies import get_current_user
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.normalization.application.service import NormalizationService
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.session_domain.infrastructure.models import SessionEntryRecord
from modules.storage.infrastructure.db import get_db
from support import isolated_database, source_bundle


class DatasetAccessTests(unittest.TestCase):
    def setUp(self):
        self.scope = isolated_database()
        self.factory = self.scope.__enter__()
        with self.factory() as db:
            db.add_all([UserRecord(id=u,email=u+"@example.com",password_hash="fixture") for u in ("alice","bob")])
            db.commit()
            bundle = source_bundle(full=True)
            bundle.metadata.owner_user_id = "alice"
            bundle.metadata.data_provider = "f1tv"
            bundle.catalog_item.source_session_key += "~f1:alice"
            snapshot = NormalizationService().build_snapshot(bundle, ttl_hours=1)
            self.sid = SessionRepository(db).import_snapshot(snapshot,source_version="fixture",force_refresh=False)
            self.entry = db.query(SessionEntryRecord.id).filter_by(session_id=self.sid).first()[0]
        self.app = create_app()
        def database():
            with self.factory() as db:
                yield db
        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)
        self.user("bob")

    def user(self, name):
        self.app.dependency_overrides[get_current_user] = lambda: User(id=name,email=name+"@example.com")

    def tearDown(self):
        self.client.close()
        self.scope.__exit__(None,None,None)

    def test_other_profile_cannot_read_telemetry_laps_or_derive_metrics_from_private_dataset(self):
        for path in (f"/api/sessions/{self.sid}", f"/api/sessions/{self.sid}/entries",
                     f"/api/sessions/{self.sid}/entries/{self.entry}/telemetry/car",
                     f"/api/sessions/{self.sid}/source-details/pit_stops"):
            self.assertEqual(self.client.get(path).status_code,404,path)
        self.assertEqual(self.client.post(f"/api/feature-metrics/sessions/{self.sid}/analytics",json={}).status_code,404)
        self.assertEqual(self.client.post(f"/api/strategy/sessions/{self.sid}/evaluate",json={"focus_entry_id":self.entry,"as_of_ms":1000}).status_code,404)
        self.assertEqual(self.client.get("/api/sessions").json(),[])
        self.user("alice")
        self.assertEqual(self.client.get(f"/api/sessions/{self.sid}").status_code,200)
        self.assertEqual(len(self.client.get("/api/sessions").json()),1)

    def test_body_based_queue_requests_cannot_bypass_dataset_owner(self):
        payload = {"session_id":self.sid,"entry_ids":[self.entry],"kinds":["car"],"scope":"session"}
        self.assertEqual(self.client.post("/api/telemetry/materialization/ensure",json=payload).status_code,404)
        self.assertEqual(self.client.post("/api/session-import/jobs",json={"season_year":2025,"round_number":1,"session_name":"Race","source_session_key":"fixture~f1:alice"}).status_code,404)
        self.user("alice")
        self.assertEqual(self.client.post("/api/telemetry/materialization/ensure",json=payload).status_code,202)
