from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.bootstrap import create_app
from app.config import settings
from modules.identity_auth.application.security import create_access_token, hash_password
from modules.identity_auth.infrastructure.db_models import EmailVerificationRecord, UserRecord
from modules.storage.infrastructure.db import get_db
from support import isolated_database


class EmailAuthTests(TestCase):
    password = "fixture-password-2026"

    def setUp(self):
        scope = isolated_database()
        self.factory = scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)
        app = create_app()

        def database():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.mail = self.enterContext(patch("modules.identity_auth.application.email_verification.send_verification_code"))
        self.enterContext(patch("modules.identity_auth.application.email_verification.mail_configured", return_value=True))

    def signup(self, email="test@example.net"):
        return self.client.post("/api/auth/signup", json={"email": email, "password": self.password})

    def verify(self, challenge, code):
        return self.client.post("/api/auth/verify-email", json={"challenge_id": challenge, "code": code})

    def session(self, token):
        return self.client.get("/api/auth/session", headers={"Authorization": f"Bearer {token}"}).json()

    def test_password_signup_requires_mailbox_proof_and_only_creates_a_member(self):
        result = self.signup("admin@admin.hu")
        self.assertEqual(result.status_code, 202, result.text)
        challenge = result.json()["challenge_id"]
        email, code = self.mail.call_args.args
        self.assertEqual(email, "admin@admin.hu")
        self.assertEqual(len(code), 6)
        self.assertNotIn("access_token", result.json())
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(UserRecord)))
            self.assertNotEqual(db.get(EmailVerificationRecord, challenge).code_digest, code)
        logged_in = self.verify(challenge, code)
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        session = self.session(logged_in.json()["access_token"])
        self.assertTrue(session["email_verified"])
        self.assertEqual(session["role"], "member")
        self.assertEqual(self.verify(challenge, code).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "ADMIN@admin.hu", "password": self.password}).json()["status"], "authenticated")

    def test_only_admin_role_skips_legacy_verification_and_opens_diagnostics(self):
        with self.factory() as db:
            db.add_all([UserRecord(id=role, email=f"{role}@example.net", password_hash=hash_password(self.password), role=role)
                        for role in ("admin", "member")])
            db.commit()
        self.assertFalse(self.session(create_access_token("member", "member@example.net"))["authenticated"])
        admin = self.client.post("/api/auth/login", json={"email": "admin@example.net", "password": self.password})
        self.assertEqual(admin.json()["status"], "authenticated", admin.text)
        self.mail.assert_not_called()
        member = self.client.post("/api/auth/login", json={"email": "member@example.net", "password": self.password})
        self.assertEqual(member.json()["status"], "verification_required", member.text)
        verified = self.verify(member.json()["challenge_id"], self.mail.call_args.args[1])
        path = "/api/ingestion/health"
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path, headers={"Authorization": "Bearer " + verified.json()["access_token"]}).status_code, 403)
        self.assertEqual(self.client.get(path, headers={"Authorization": "Bearer " + admin.json()["access_token"]}).status_code, 200)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_verification_attempts_and_resend_are_bounded(self):
        response = self.signup()
        challenge_id = response.json()["challenge_id"]
        code = self.mail.call_args.args[1]
        resend = {"challenge_id": challenge_id}
        self.assertEqual(self.client.post("/api/auth/resend-code", json=resend).status_code, 429)
        wrong_code = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(challenge_id, wrong_code).status_code, 400)
        self.assertEqual(self.verify(challenge_id, code).status_code, 400)
        with self.factory() as db:
            db.get(EmailVerificationRecord, challenge_id).created_at -= timedelta(minutes=2)
            db.commit()
        next_challenge = self.client.post("/api/auth/resend-code", json=resend)
        self.assertEqual(next_challenge.status_code, 200, next_challenge.text)
        self.assertEqual(self.verify(next_challenge.json()["challenge_id"], self.mail.call_args.args[1]).status_code, 200)

    def test_google_controls_mailbox_proof_for_new_accounts(self):
        with patch.object(settings, "google_client_id", "fixture.apps.googleusercontent.com"):
            def google(email):
                nonce = self.client.post("/api/auth/google/challenge", json={"action": "signin"}).json()["nonce"]
                claims = {"email": email, "email_verified": True, "sub": email, "nonce": nonce}
                with patch("modules.delivery_api.api.google_routes.verify_google", return_value=claims):
                    return self.client.post("/api/auth/google", json={"action": "signin", "nonce": nonce, "credential": "x" * 120})
            trusted = google("pitwall-test-fixture@gmail.com")
            self.assertTrue(self.session(trusted.json()["access_token"])["email_verified"])
            self.mail.assert_not_called()
            external = google("fixture@example.net")
            self.assertEqual(external.json()["status"], "verification_required", external.text)
            session = self.verify(external.json()["challenge_id"], self.mail.call_args.args[1]).json()
            self.assertTrue(self.session(session["access_token"])["email_verified"])
