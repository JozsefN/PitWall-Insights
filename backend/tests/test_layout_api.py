"""Live local API checks. Creates two temporary accounts and deletes only those accounts."""
import json
import secrets
import unittest
from copy import deepcopy
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.dashboard_layouts.infrastructure.db_models import UserDashboardLayoutRecord
from modules.dashboard_layouts.domain.validation import validate_dashboard_config, validate_widget_size, WIDGET_POLICIES
from support import create_verified_test_account

BASE = "http://127.0.0.1:8000"


def request(method, path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        with urlopen(Request(BASE + path, data=body, headers=headers, method=method), timeout=15) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        return error.code, json.loads(error.read())


def payload():
    return {"name": "API test layout", "description": "Temporary test", "audience": "session-lookback", "schemaVersion": 2,
            "config": {"id": "test-grid", "sections": [{"id": "main", "layout": {
                "type": "group", "direction": "row", "gap": 12, "grid": {"columns": 12, "rowHeight": 48},
                "children": [{"type": "widget", "widgetId": "lap-table", "instanceId": "one", "placement": {"x": 0, "y": 0, "w": 6, "h": 5}}],
            }}]}}


class LayoutApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.accounts = []
        try:
            for _ in range(2):
                email = f"layout-test-{secrets.token_hex(8)}@example.com"
                password = secrets.token_urlsafe(20)
                with SessionLocal() as db:
                    user_id = create_verified_test_account(db, email, password)
                cls.accounts.append((user_id, None))
                status, auth = request("POST", "/api/auth/login", {"email": email, "password": password})
                if status != 200:
                    raise RuntimeError(f"Test account creation failed: {status}")
                token = auth["access_token"]
                cls.accounts[-1] = (user_id, token)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        with SessionLocal() as db:
            for user_id, _ in cls.accounts:
                db.query(UserRecord).filter(UserRecord.id == user_id).delete()
            db.commit()

    def test_crud_profile_ownership_favorites_and_factory_protection(self):
        owner_id, owner = self.accounts[0]
        _, other = self.accounts[1]
        status, layout = request("POST", "/api/layouts", payload(), owner)
        self.assertEqual(status, 201, layout)
        layout_id = layout["id"]
        with SessionLocal() as db:
            self.assertEqual(db.get(UserDashboardLayoutRecord, layout_id).owner_user_id, owner_id)
        status, updated = request("PUT", f"/api/layouts/{layout_id}", {"name": "Edited layout", "description": None}, owner)
        self.assertEqual(status, 200)
        self.assertEqual(updated["name"], "Edited layout")
        self.assertIsNone(updated["description"])
        self.assertEqual(request("PUT", f"/api/layouts/{layout_id}", {"audience": "live-race"}, owner)[0], 400)
        self.assertEqual(request("GET", f"/api/layouts/{layout_id}", token=owner)[1]["config"], layout["config"])
        self.assertEqual(request("GET", "/api/layouts", token=other)[1], [])
        for method, data in [("GET", None), ("PUT", {"name": "Stolen"}), ("DELETE", None)]:
            self.assertEqual(request(method, f"/api/layouts/{layout_id}", data, other)[0], 404)
        self.assertEqual(request("PUT", "/api/layouts/favorites", {"layoutId": "user:" + layout_id, "favorite": True}, other)[0], 400)
        for key in ["builtin:compare-lap", "user:" + layout_id]:
            for _ in range(2):
                self.assertEqual(request("PUT", "/api/layouts/favorites", {"layoutId": key, "favorite": True}, owner)[0], 200)
        self.assertEqual(len(request("GET", "/api/layouts/favorites", token=owner)[1]), 2)
        self.assertEqual(request("GET", "/api/layouts/favorites", token=other)[1], [])
        self.assertEqual(request("PUT", "/api/layouts/builtin:compare-lap", {"name": "Modified factory"}, owner)[0], 404)
        self.assertEqual(request("DELETE", "/api/layouts/builtin:compare-lap", token=owner)[0], 404)
        self.assertEqual(request("DELETE", f"/api/layouts/{layout_id}", token=owner)[0], 204)
        self.assertEqual(request("GET", "/api/layouts/favorites", token=owner)[1], ["builtin:compare-lap"])
        self.assertEqual(request("PUT", "/api/layouts/favorites", {"layoutId": "builtin:compare-lap", "favorite": False}, owner)[1], [])

    def test_validation_and_authentication(self):
        _, token = self.accounts[0]
        self.assertEqual(request("GET", "/api/layouts")[0], 401)
        self.assertEqual(request("GET", "/api/layouts/favorites")[0], 401)
        bad = payload(); bad["name"] = "   "
        self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)
        bad = payload(); bad["audience"] = "live-race"
        self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)
        bad = payload(); bad["schemaVersion"] = 99
        self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 422)
        for placement in [{"x": 10, "y": 0, "w": 6, "h": 5}, {"x": 0.5, "y": 0, "w": 6, "h": 5}, {"x": 0, "y": 0, "w": 6, "h": 0}]:
            bad = payload(); bad["config"]["sections"][0]["layout"]["children"][0]["placement"] = placement
            self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)
        bad = payload(); children = bad["config"]["sections"][0]["layout"]["children"]
        children.append({**deepcopy(children[0]), "instanceId": "two"})
        self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)
        bad = payload(); bad["config"]["sections"][0]["layout"]["children"][0]["widgetId"] = "unknown"
        self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)
        bad = payload(); bad["config"]["sections"][0]["layout"]["children"][0]["options"] = {"title": {"invalid": "React title"}}
        self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)
        for widget_id, box in [
            ("health-overview", {"x": 0, "y": 0, "w": 6, "h": 5}),
            ("sessions-summary", {"x": 0, "y": 0, "w": 6, "h": 5}),
            ("stint-analysis", {"x": 0, "y": 0, "w": 6, "h": 12}),
            ("lap-time-trend", {"x": 0, "y": 0, "w": 4, "h": 4}),
        ]:
            bad = payload(); child = bad["config"]["sections"][0]["layout"]["children"][0]
            child.update(widgetId=widget_id, placement=box)
            self.assertEqual(request("POST", "/api/layouts", bad, token)[0], 400)

    def test_layout_mode_conversion_and_session_restrictions(self):
        _, token = self.accounts[0]
        body = payload()
        config = body["config"]
        child = config["sections"][0]["layout"]["children"][0]
        child["widgetId"] = "weather-history"
        status, layout = request("POST", "/api/layouts", body, token)
        self.assertEqual(status, 201, layout)
        route = f"/api/layouts/{layout['id']}"
        try:
            config.update(enabledAudiences=["session-lookback", "live-race"], sessionKind="practice")
            status, updated = request("PUT", route, {"config": config}, token)
            self.assertEqual(status, 200, updated)
            self.assertEqual(request("GET", route, token=token)[1]["config"], config)

            config["enabledAudiences"] = ["live-race"]
            child["widgetId"] = "wake-exposure"
            status, error = request("PUT", route, {"audience": "live-race", "config": config}, token)
            self.assertEqual(status, 400, error)
            self.assertIn("Grand Prix", error["detail"])

            config["sessionKind"] = "qualifying"
            child["widgetId"] = "lookback-driver-cards"
            status, error = request("PUT", route, {"audience": "live-race", "config": config}, token)
            self.assertEqual(status, 400, error)
            self.assertIn("cannot be used in Replay", error["detail"])
            self.assertEqual(request("GET", route, token=token)[1]["config"], updated["config"])
        finally:
            self.assertEqual(request("DELETE", route, token=token)[0], 204)


class ValidationTests(unittest.TestCase):
    def test_shared_widget_contract_defaults_and_constraints(self):
        for widget_id, policy in WIDGET_POLICIES.items():
            if not policy["builderEnabled"]:
                continue
            size = policy["sizing"]
            validate_widget_size(widget_id, {"x": 0, "y": 0, "w": size["defaultW"], "h": size["defaultH"]})
            with self.assertRaises(ValueError):
                validate_widget_size(widget_id, {"x": 0, "y": 0, "w": 2, "h": 2})
        for box in [None, {}, {"x": 0, "y": 0, "w": 10**1000, "h": 5}]:
            with self.assertRaises(ValueError):
                validate_widget_size("lap-table", box)

    def test_legacy_layout_and_grid_copies(self):
        legacy = {"id": "legacy", "sections": [{"id": "main", "layout": {"type": "widget", "widgetId": "lap-table"}}]}
        self.assertEqual(validate_dashboard_config(legacy), legacy)
        original = payload()["config"]
        saved = validate_dashboard_config(original, "session-lookback", 2)
        saved["id"] = "different"
        self.assertEqual(original["id"], "test-grid")


if __name__ == "__main__":
    unittest.main()
