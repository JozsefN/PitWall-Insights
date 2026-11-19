import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import quote, urlparse, parse_qs

import requests
from modules.provider_connections.infrastructure.browser_link import BrowserLinkAttempts, MAX_BODY
from modules.provider_connections.infrastructure.f1_client import run_provider_process
from modules.provider_connections.infrastructure.errors import ProviderAccessError, ProviderAuthenticationError, ProviderUnavailableError
from modules.provider_connections.infrastructure.f1_process import failure_code

ORIGIN = "chrome-extension://gmbpblepbcmnajgjalbmlminfnaedcig"


class BrowserHandoffTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.accept_browser.return_value = {"token": "private-token-" * 5,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(), "account_hint": "fixture@example.com"}
        self.links = BrowserLinkAttempts(client=self.client, ttl=30)
        self.attempt = self.links.start("alice")
        self.key = self.attempt["id"]
        port = parse_qs(urlparse(self.attempt["url"]).query)["port"][0]
        self.url = f"http://127.0.0.1:{port}/auth"
        self.payload = {"loginSession": quote(json.dumps({"data": {"subscriptionToken": "browser-token-" * 5}, "other": "discard-me"}))}

    def tearDown(self):
        self.links.cancel("alice", self.key)

    def post(self, **kwargs):
        return requests.post(self.url, headers={"Origin": ORIGIN}, timeout=5, **kwargs)

    def test_verified_handoff_needs_explicit_confirmation_and_is_owner_bound_one_time(self):
        self.assertEqual(self.post(json=self.payload).status_code, 200)
        self.client.accept_browser.assert_called_once_with("browser-token-" * 5)
        status = self.links.status("alice", self.key)
        self.assertEqual(status["state"], "ready")
        self.assertNotIn("private-token", json.dumps(status))
        self.assertNotIn("discard-me", json.dumps(self.links._attempts[self.key], default=str))
        with self.assertRaises(ValueError): self.links.status("bob", self.key)
        with self.assertRaises(ValueError): self.links.consume("bob", self.key)
        self.assertEqual(self.post(json=self.payload).status_code, 409)
        self.assertEqual(self.links.consume("alice", self.key)["token"], "private-token-" * 5)
        with self.assertRaises(ValueError): self.links.consume("alice", self.key)

    def test_untrusted_or_missing_origin_and_host_are_rejected_before_provider_called(self):
        for headers in ({}, {"Origin": "https://attacker.example"}, {"Origin": "null"}, {"Origin": ORIGIN, "Host": "attacker.example"}):
            r = requests.post(self.url, json=self.payload, headers=headers, timeout=5)
            self.assertEqual(r.status_code, 403)
        self.client.accept_browser.assert_not_called()

    def test_companion_preflight_is_scoped_to_origin_and_auth_path(self):
        r = requests.options(self.url, headers={"Origin": ORIGIN}, timeout=5)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], ORIGIN)
        self.assertEqual(requests.options(self.url + "/other", headers={"Origin": ORIGIN}, timeout=5).status_code, 403)
        r = requests.options(self.url, headers={"Origin": "https://evil.example"}, timeout=5)
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)

    def test_bad_or_oversized_cookie_cannot_consume_attempt(self):
        for body in ({}, {"loginSession": "not-json"}, {"loginSession": quote('{"data":{"subscriptionToken":null}}')}):
            self.assertEqual(self.post(json=body).status_code, 400)
        self.assertEqual(self.post(json={"padding": "x" * MAX_BODY}).status_code, 413)
        self.assertEqual(self.links.status("alice", self.key)["state"], "waiting")
        self.client.accept_browser.assert_not_called()

    def test_cancellation_expiry_and_restarting_clear_pending_token(self):
        with self.assertRaises(ValueError): self.links.consume("alice", self.key)
        self.links.cancel("bob", self.key)
        self.assertEqual(self.links.status("alice", self.key)["state"], "waiting")
        next_attempt = self.links.start("alice")
        with self.assertRaises(ValueError): self.links.status("alice", self.key)
        self.key = next_attempt["id"]
        self.links._attempts[self.key]["deadline"] = time.monotonic() - 1
        with self.assertRaises(ValueError): self.links.status("alice", self.key)
        with self.assertRaises(ValueError): self.links.consume("alice", self.key)

    def test_network_or_entitlement_failure_does_not_create_a_verified_token(self):
        self.client.accept_browser.side_effect = ProviderAccessError()
        self.assertEqual(self.post(json=self.payload).status_code, 400)
        status = self.links.status("alice", self.key)
        self.assertEqual(status["state"], "failed")
        self.assertEqual(status["error"]["code"], "f1_source_access_denied")
        with self.assertRaises(ValueError): self.links.consume("alice", self.key)


class ProviderFailureTests(unittest.TestCase):
    def http_failure(self, status):
        response = requests.Response()
        response.status_code = status
        return requests.HTTPError("secret-upstream-message", response=response)

    def test_classifies_signin_subscription_archive_denial_and_outage_separately(self):
        self.assertEqual(failure_code(self.http_failure(403), "login"), "f1_sign_in_changed")
        self.assertEqual(failure_code(self.http_failure(403), "verify"), "f1_source_access_denied")
        self.assertEqual(failure_code(self.http_failure(401), "verify"), "f1_access_expired")
        self.assertEqual(failure_code(self.http_failure(503), "verify"), "f1_temporarily_unavailable")
        self.assertEqual(failure_code(ValueError("Access token contains no subscription token"), "login"), "f1_subscription_required")
        self.assertEqual(failure_code(ValueError("Unexpected response when starting the sign-in"), "login"), "f1_sign_in_changed")

    def test_sanitized_process_failures_explain_action_without_returning_provider_text(self):
        for code, expected in (("f1_source_access_denied", ProviderAccessError), ("f1_temporarily_unavailable", ProviderUnavailableError), ("f1_subscription_required", ProviderAuthenticationError)):
            with self.subTest(code=code), patch("modules.provider_connections.infrastructure.f1_client.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout=json.dumps({"ok": False, "code": code}), stderr="private password")):
                with self.assertRaises(expected) as error: run_provider_process("login", {"password": "private password"})
                self.assertNotIn("private password", str(error.exception))
                self.assertEqual(error.exception.code, code)
