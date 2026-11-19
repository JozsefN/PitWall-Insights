"""Bounded, consented FastF1 Companion handoffs on this computer only.

The API owns the attempt; the extension only delivers a subscription token to a
short-lived loopback receiver. A second authenticated confirmation saves it.
No cookie, password or access token is returned to the PitWall frontend.
"""
import json
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

from .errors import ProviderAuthenticationError, ProviderUnavailableError, error_detail
from .f1_client import F1AccountClient

TTL_SECONDS = 300
MAX_BODY = 32_768
_EXTENSION_ORIGIN = re.compile(r"(?:chrome-extension://gmbpblepbcmnajgjalbmlminfnaedcig|moz-extension://[a-fA-F0-9-]{36})\Z")


class BrowserLinkAttempts:
    def __init__(self, *, client=None, ttl=TTL_SECONDS):
        self.client = client or F1AccountClient()
        self.ttl = ttl
        self._lock = threading.RLock()
        self._attempts = {}

    def start(self, owner):
        with self._lock:
            for key, attempt in list(self._attempts.items()):
                if attempt["owner"] == owner or attempt["deadline"] <= time.monotonic():
                    self._remove(key)
            if len(self._attempts) >= 16:
                raise ProviderUnavailableError("Browser sign-in is busy. Please retry shortly.")
            key = secrets.token_urlsafe(32)
            manager = self

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass  # Cookie and token payloads must never enter an access log.

                def setup(self):
                    super().setup()
                    self.connection.settimeout(3)

                def allowed(self):
                    return bool(_EXTENSION_ORIGIN.fullmatch(self.headers.get("Origin", ""))) and self.headers.get("Host") in {
                        f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}

                def reply(self, status, body):
                    self.send_response(status)
                    if self.allowed():
                        self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
                        self.send_header("Vary", "Origin")
                    self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type")
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(json.dumps(body).encode())

                def do_OPTIONS(self):
                    self.reply(200 if self.path == "/auth" and self.allowed() else 403, {})

                def do_POST(self):
                    if self.path != "/auth" or not self.allowed():
                        self.reply(403, {"status": "rejected"})
                        return
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= MAX_BODY or self.headers.get_content_type() != "application/json":
                            self.reply(413, {"status": "invalid_payload"})
                            return
                        with manager._lock:
                            current = manager._get(owner, key)
                            if current["state"] != "waiting":
                                self.reply(409, {"status": "already_received"})
                                return
                            payload = json.loads(self.rfile.read(length))
                            cookie = json.loads(unquote(payload["loginSession"]))
                            token = cookie["data"]["subscriptionToken"]
                            if not isinstance(token, str) or not 20 < len(token) < MAX_BODY:
                                raise ValueError()
                            # Drop the full session cookie immediately. Only the entitlement JWT is needed.
                            del cookie, payload
                            current["state"] = "verifying"
                        result = manager.client.accept_browser(token)
                        with manager._lock:
                            current = manager._get(owner, key)
                            current["result"], current["state"] = result, "ready"
                        self.reply(200, {"status": "ok"})
                    except (ProviderAuthenticationError, ProviderUnavailableError) as exc:
                        with manager._lock:
                            if key in manager._attempts:
                                manager._attempts[key].update(state="failed", error=error_detail(exc))
                        self.reply(400, {"status": "verification_failed"})
                    except (ValueError, KeyError, TypeError, UnicodeError):
                        self.reply(400, {"status": "invalid_payload"})

            server = HTTPServer(("127.0.0.1", 0), Handler)
            attempt = {"owner": owner, "deadline": time.monotonic() + self.ttl,
                       "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=self.ttl)).isoformat(),
                       "server": server, "state": "waiting", "result": None}
            timer = threading.Timer(self.ttl, lambda: self.cancel(owner, key))
            timer.daemon = True
            attempt["timer"] = timer
            self._attempts[key] = attempt
            threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
            timer.start()
            return {"id": key, "url": f"https://f1login.fastf1.dev?port={server.server_port}",
                    "expires_at": attempt["expires_at"], "state": "waiting"}

    def _get(self, owner, key):
        attempt = self._attempts.get(key)
        if not attempt or attempt["owner"] != owner or attempt["deadline"] <= time.monotonic():
            raise ValueError("Browser sign-in expired or was cancelled. Start again from Profile.")
        return attempt

    def status(self, owner, key):
        with self._lock:
            a = self._get(owner, key)
            result = a["result"] or {}
            return {"state": a["state"], "expires_at": a["expires_at"],
                    "account_hint": result.get("account_hint"), "error": a.get("error")}

    def consume(self, owner, key):
        with self._lock:
            a = self._get(owner, key)
            if a["state"] != "ready":
                raise ValueError("Complete Formula 1 sign-in before confirming the connection.")
            result = a["result"]
            self._remove(key)
            return result

    def _remove(self, key):
        a = self._attempts.pop(key, None)
        if a:
            a["result"] = None
            a["timer"].cancel()
            # shutdown waits on the server thread; never wait while holding the registry lock.
            def close():
                a["server"].shutdown()
                a["server"].server_close()
            threading.Thread(target=close, daemon=True).start()

    def cancel(self, owner, key):
        with self._lock:
            if key in self._attempts and self._attempts[key]["owner"] == owner:
                self._remove(key)


browser_links = BrowserLinkAttempts()
