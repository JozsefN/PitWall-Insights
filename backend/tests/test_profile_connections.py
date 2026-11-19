import unittest
from fastapi.testclient import TestClient
from app.bootstrap import create_app
from modules.storage.infrastructure.db import get_db
from modules.delivery_api.api.auth_dependencies import require_current_user, get_current_user
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.db_models import UserRecord
from support import isolated_database


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.scope = isolated_database()
        self.factory = self.scope.__enter__()
        with self.factory() as db:
            db.add_all([UserRecord(id=u, email=u+"@example.com", password_hash="fixture") for u in ("alice", "bob")])
            db.commit()
        self.app = create_app()
        def database():
            with self.factory() as db: yield db
        self.app.dependency_overrides[get_db] = database
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.scope.__exit__(None,None,None)

    def user(self, name="alice"):
        for dependency in (require_current_user, get_current_user):
            self.app.dependency_overrides[dependency] = lambda: User(id=name,email=name+"@example.com")

    def test_authenticated_profile_updates_persist_and_are_private(self):
        self.assertEqual(self.client.get("/api/profile").status_code,401)
        self.user()
        response=self.client.patch("/api/profile",json={"name":" Alice ","nickname":"A","phone_number":"+36 30 123 4567"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["name"],"Alice")
        self.assertEqual(self.client.get("/api/profile").json()["nickname"],"A")
        self.assertNotIn("f1_connection",response.json())
        self.assertFalse(response.json()["subscription"]["billing_available"])
        self.user("bob")
        self.assertIsNone(self.client.get("/api/profile").json()["name"])

    def test_profile_validation_rejects_invalid_fields_and_membership_changes(self):
        self.user()
        for payload in ({"plan":"paid"},{"phone_number":"garbage"}):
            self.assertEqual(self.client.patch("/api/profile",json=payload).status_code,422)

    def test_external_account_endpoints_are_not_exposed(self):
        self.user()
        for suffix in ("", "/verify", "/browser", "/browser/fixture/confirm"):
            response=self.client.post("/api/profile/connections/f1"+suffix,json={})
            self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get("/api/profile/connections/f1/browser").status_code,404)

    def test_only_openf1_capabilities_and_requests_are_supported(self):
        self.user()
        response=self.client.get("/api/ingestion/capabilities").json()
        self.assertEqual(response["source"],"openf1")
        rows={row["feature"]:row for row in response["features"]}
        for name in ("Brake trace","Track map and historical replay","Historical strategy calculations"):
            self.assertIs(rows[name]["supported"],True)
        self.assertIs(rows["Live race viewer"]["supported"],False)
        self.assertNotIn("with_f1",str(rows))
        request={"season_year":2025,"round_number":1,"session_name":"Race","data_provider":"f1tv"}
        self.assertEqual(self.client.post("/api/sessions/import",json=request).status_code,422)
        self.assertEqual(self.client.get("/api/sessions/catalog?season=2022").status_code,422)
