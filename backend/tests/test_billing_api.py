from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import unittest
from unittest.mock import patch

import stripe
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.bootstrap import create_app
from app.config import settings
from modules.billing.infrastructure.db_models import BillingAccountRecord, BillingWebhookEventRecord
from modules.billing.infrastructure.stripe_gateway import StripeGateway
from modules.identity_auth.application.security import create_access_token, hash_password
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.session_domain.infrastructure.db_models import SessionTrackStatusEventRecord
from modules.storage.infrastructure.db import get_db
from support import isolated_database, paid_membership, seed_session


def now():
    return datetime.now(timezone.utc)


def stripe_object(data):
    return stripe.StripeObject.construct_from(data, None)


class SandboxFixture:
    prices = {("analyst", "month"): "price_analyst_month"}
    verify_event = StripeGateway.verify_event
    check_price = StripeGateway.check_price

    def __init__(self):
        self.status = None
        self.invoice_status = "paid"
        self.canceling = False
        self.checkout_calls = 0
        self.subscription_reads = 0

    def create_customer(self, user_id, email):
        return "cus_" + user_id

    def create_checkout(self, customer, plan, interval, key, expires):
        self.checkout_calls += 1
        return self.get_checkout("cs_test_fixture")

    def get_checkout(self, checkout_id):
        return stripe_object({"id": checkout_id, "livemode": False, "customer": "cus_free",
                              "url": "https://checkout.stripe.com/example", "status": "open"})

    def subscriptions(self, customer):
        self.subscription_reads += 1
        if self.status:
            yield stripe_object({"id": "sub_fixture", "status": self.status})

    def subscription(self, subscription_id):
        return stripe_object({"id": subscription_id, "status": self.status, "livemode": False,
                              "customer": "cus_free", "cancel_at": None, "cancel_at_period_end": self.canceling,
                              "latest_invoice": {"status": self.invoice_status}, "items": {"has_more": False, "data": [
                                  {"quantity": 1, "current_period_end": int((now() + timedelta(days=30)).timestamp()),
                                   "price": {"id": "price_analyst_month", "livemode": False, "currency": "huf",
                                             "unit_amount": 149000, "recurring": {"interval": "month", "interval_count": 1}}}
                              ]}})

    def cancel_renewal(self, subscription_id):
        self.canceling = True


class BillingApiTests(unittest.TestCase):
    def setUp(self):
        scope = isolated_database()
        self.factory = scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)
        self.sid = seed_session(self.factory, full=True)
        with self.factory() as db:
            db.add_all([UserRecord(id=name, email=f"{name}@example.com", password_hash=hash_password("test-password"), email_verified_at=now())
                        for name in ("free", "analyst", "pro")])
            db.flush()
            paid_membership(db, "analyst")
            paid_membership(db, "pro", "pro")
            db.commit()
        app = create_app()

        def database():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    @staticmethod
    def auth(user="free"):
        return {"Authorization": f"Bearer {create_access_token(user, user + '@example.com')}"}

    @staticmethod
    def layout(count=1):
        return {"name": "Quota fixture", "audience": "session-lookback", "config": {"id": "test", "sections": [
            {"id": "panels", "layout": {"type": "group", "direction": "row", "children": [
                {"type": "widget", "widgetId": "lap-table"} for _ in range(count)
            ]}}
        ]}}

    def test_quota_concurrency_and_legacy_downgrade(self):
        path = "/api/layouts"
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: self.client.post(path, json=self.layout(), headers=self.auth()).status_code, range(3)))
        self.assertCountEqual(results, [201, 201, 403])
        self.assertEqual(self.client.post(path, json=self.layout(5), headers=self.auth()).status_code, 403)
        paid_panel = self.layout()
        paid_panel["config"]["sections"][0]["layout"]["children"][0]["widgetId"] = "pace-context"
        denied = self.client.post(path, json=paid_panel, headers=self.auth())
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertIn("requires Analyst", denied.json()["detail"])
        self.assertEqual(self.client.post(path, json=self.layout(11), headers=self.auth("analyst")).status_code, 403)
        pro = self.client.post(path, json=self.layout(11), headers=self.auth("pro"))
        self.assertEqual(pro.status_code, 201, pro.text)
        with self.factory() as db:
            db.get(BillingAccountRecord, "pro").paid_until = now() - timedelta(seconds=1)
            db.commit()
        saved = path + "/" + pro.json()["id"]
        self.assertEqual(self.client.get(saved, headers=self.auth("pro")).status_code, 200)
        self.assertEqual(self.client.put(saved, json={"name": "Still too large"}, headers=self.auth("pro")).status_code, 403)
        self.assertEqual(self.client.put(saved, json={"config": self.layout()["config"]}, headers=self.auth("pro")).status_code, 200)

    def test_free_reports_and_server_denial_of_paid_outputs(self):
        base = f"/api/feature-metrics/sessions/{self.sid}"
        payload = {"as_of_ms": 90000}
        with self.factory() as db:
            db.add_all([
                SessionTrackStatusEventRecord(session_id=self.sid, session_time_ms=80000, status="4"),
                SessionTrackStatusEventRecord(session_id=self.sid, session_time_ms=100000, status="1"),
            ])
            db.commit()
        self.assertEqual(self.client.post(base + "/race-estimates", json=payload, headers=self.auth()).status_code, 403)
        self.assertEqual(self.client.post(base + "/review", json={"groups": ["flags", "pit"]}, headers=self.auth()).status_code, 403)
        self.assertEqual(self.client.post(f"/api/strategy/sessions/{self.sid}/replay", json=payload, headers=self.auth()).status_code, 403)
        first = self.client.post(base + "/race-estimates?view=reports", json=payload, headers=self.auth())
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["drivers"], [])
        self.assertEqual(first.json()["pairs"], [])
        self.assertEqual(first.json()["assumptions"], {})
        self.assertEqual(first.json()["conditions"], {"track_status": "4"})
        rewound = self.client.post(base + "/race-estimates?view=reports", json={"as_of_ms": 75000}, headers=self.auth())
        self.assertNotEqual(rewound.json()["conditions"]["track_status"], "4")
        self.assertLessEqual(max((item["time_ms"] for item in first.json()["events"]), default=0), 90000)
        self.assertEqual(self.client.get(base + "/timing-tower", headers=self.auth()).status_code, 200)
        self.assertEqual(self.client.post(base + "/race-estimates", json=payload, headers=self.auth("analyst")).status_code, 200)

    def test_checkout_signed_webhook_renewal_and_idempotency(self):
        gateway = SandboxFixture()
        environment = dict(stripe_test_secret_key=SecretStr("sk_test_fixture"), stripe_webhook_secret=SecretStr("whsec_fixture"),
                           stripe_analyst_month_price="price_analyst_month", stripe_analyst_year_price="price_analyst_year",
                           stripe_pro_month_price="price_pro_month", stripe_pro_year_price="price_pro_year")

        def webhook(event_id, livemode=False, signature_valid=True):
            body = json.dumps({"id": event_id, "object": "event", "livemode": livemode,
                               "type": "invoice.paid", "data": {"object": {"customer": "cus_free"}}})
            stamp = int(now().timestamp())
            signature = hmac.new(b"whsec_fixture", f"{stamp}.{body}".encode(), sha256).hexdigest() if signature_valid else "bad"
            return self.client.post("/api/billing/webhook", content=body, headers={"Stripe-Signature": f"t={stamp},v1={signature}"})

        with patch.multiple(settings, **environment), patch("modules.delivery_api.api.billing_routes.StripeGateway", return_value=gateway), patch("modules.storage.infrastructure.db.SessionLocal", self.factory):
            checkout = {"plan": "analyst", "interval": "month"}
            self.assertEqual(self.client.post("/api/billing/checkout", json=checkout).status_code, 401)
            self.assertEqual(self.client.post("/api/billing/checkout", json={**checkout, "price_id": "price_other"}, headers=self.auth()).status_code, 422)
            for _ in range(2):
                self.assertEqual(self.client.post("/api/billing/checkout", json=checkout, headers=self.auth()).status_code, 200)
            self.assertEqual(gateway.checkout_calls, 1)
            self.assertEqual(self.client.get("/api/billing/me", headers=self.auth()).json()["plan"]["code"], "free")
            self.assertEqual(webhook("evt_forged", signature_valid=False).status_code, 400)
            self.assertEqual(webhook("evt_live", livemode=True).status_code, 400)
            gateway.status = "active"
            self.assertEqual(webhook("evt_paid").status_code, 204)
            self.assertTrue(self.client.get("/api/billing/me", headers=self.auth()).json()["can_cancel"])
            reads = gateway.subscription_reads
            self.assertEqual(webhook("evt_paid").status_code, 204)
            self.assertEqual(gateway.subscription_reads, reads)
            result = self.client.post("/api/billing/cancel", headers=self.auth())
            self.assertEqual(result.status_code, 200, result.text)
            self.assertTrue(result.json()["cancel_at_period_end"])
            self.assertFalse(result.json()["can_cancel"])
            self.assertEqual(result.json()["plan"]["code"], "analyst")
            gateway.status = "past_due"
            self.assertEqual(webhook("evt_late").status_code, 204)
            self.assertEqual(self.client.get("/api/billing/me", headers=self.auth()).json()["plan"]["code"], "free")
            with self.factory() as db:
                self.assertCountEqual(db.scalars(select(BillingWebhookEventRecord.event_id)).all(), ["evt_paid", "evt_late"])

    def test_google_nonce_reuse_and_explicit_link(self):
        def challenge(action, headers=None):
            response = self.client.post("/api/auth/google/challenge", json={"action": action}, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()["nonce"]

        def google(action, nonce, claims, headers=None, password=None):
            with patch("modules.delivery_api.api.google_routes.verify_google", return_value={**claims, "nonce": nonce}):
                return self.client.post("/api/auth/google", json={"action": action, "nonce": nonce,
                                        "credential": "test-only-credential" * 10, "password": password}, headers=headers)

        with patch.object(settings, "google_client_id", "fixture.apps.googleusercontent.com"):
            claims = {"sub": "google-subject", "email_verified": True, "email": "free@example.com"}
            self.assertEqual(google("signin", challenge("signin"), claims).status_code, 400)
            link = challenge("link", self.auth())
            self.assertEqual(google("link", link, claims, self.auth("analyst"), "test-password").status_code, 400)
            self.assertEqual(google("link", link, claims, self.auth(), "test-password").status_code, 200)
            self.assertEqual(google("link", link, claims, self.auth(), "test-password").status_code, 400)
            response = google("signin", challenge("signin"), {**claims, "email": "changed@example.com"})
            self.assertEqual(response.status_code, 200, response.text)
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
            self.assertEqual(self.client.get("/api/profile", headers=headers).json()["user_id"], "free")
