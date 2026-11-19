"""Exercise Companion's HTTP handoff in a real Chromium extension context.

The upstream entitlement verifier is a fixture. No F1 website, cookie or real
credentials are accessed. Install Playwright in the interpreter running this.
"""
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from modules.provider_connections.infrastructure.browser_link import BrowserLinkAttempts


class FixtureVerifier:
    def accept_browser(self, token):
        assert token == "fixture-subscription-token-for-protocol-check"
        return {"token": token, "expires_at": time.time() + 3600, "account_hint": "fixture@example.com"}


def main():
    links = BrowserLinkAttempts(client=FixtureVerifier(), ttl=30)
    attempt = links.start("protocol-fixture-owner")
    port = parse_qs(urlparse(attempt["url"]).query)["port"][0]
    try:
        with tempfile.TemporaryDirectory(prefix="pitwall-companion-protocol-") as directory:
            root = Path(directory)
            extension = root / "extension"
            extension.mkdir()
            (extension / "manifest.json").write_text(json.dumps({"manifest_version": 3,
                "name": "PitWall protocol fixture", "version": "1.0", "host_permissions": ["http://localhost/*"],
                "background": {"service_worker": "worker.js"}}))
            (extension / "worker.js").write_text("chrome.runtime.onInstalled.addListener(() => {});")
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(str(root / "profile"), channel="chromium", headless=True,
                    args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"])
                try:
                    worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                    send = """url => fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                        loginSession:encodeURIComponent(JSON.stringify({data:{subscriptionToken:'fixture-subscription-token-for-protocol-check'}}))
                    })}).then(r => r.status)"""
                    callback = f"http://localhost:{port}/auth"
                    assert worker.evaluate(send, callback) == 403, "An unknown extension must be rejected"
                    # Test-only allowlist substitution: production accepts only the real Companion Chrome ID.
                    origin = "chrome-extension://" + urlparse(worker.url).netloc
                    with patch("modules.provider_connections.infrastructure.browser_link._EXTENSION_ORIGIN", re.compile(re.escape(origin) + r"\Z")):
                        assert worker.evaluate(send, callback) == 200
                    status = links.status("protocol-fixture-owner", attempt["id"])
                    assert status["state"] == "ready"
                    assert "subscription-token" not in json.dumps(status)
                    links.consume("protocol-fixture-owner", attempt["id"])
                finally:
                    context.close()
    finally:
        links.cancel("protocol-fixture-owner", attempt["id"])
    report = {"chromium_extension_handoff": "passed", "unknown_extension_rejected": True,
              "real_extension_origin_and_cors": True, "upstream_subscription_verifier_simulated": True,
              "real_f1_credentials_or_cookies_used": False}
    (ROOT / "docs/testing/profile-browser/companion-protocol.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
