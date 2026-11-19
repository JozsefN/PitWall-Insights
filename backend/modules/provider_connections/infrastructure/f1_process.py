"""Secrets enter on stdin, never argv. No provider state survives this process."""
import json
import sys
import contextlib


def verify_archive(token):
    from datetime import datetime, timezone
    import requests
    response = requests.get(
        f"https://livetiming.formula1.com/static/{datetime.now(timezone.utc).year}/Index.json",
        headers={"Authorization": "Bearer " + token}, timeout=(5, 20))
    response.raise_for_status()
    if not isinstance(response.json(), dict):
        raise ValueError("Invalid source response")


def failure_code(error, operation):
    """Only finite codes cross the subprocess boundary; messages can contain secrets."""
    import requests
    cause = error
    for _ in range(5):
        if cause is None:
            break
        status = getattr(getattr(cause, "response", None), "status_code", None)
        if isinstance(cause, (requests.Timeout, requests.ConnectionError)) or status == 429 or (status and status >= 500):
            return "f1_temporarily_unavailable"
        if status == 403:
            return "f1_source_access_denied" if operation != "login" else "f1_sign_in_changed"
        if status == 401:
            return "f1_access_expired" if operation != "login" else "f1_sign_in_failed"
        cause = cause.__cause__
    message = str(error).lower()
    if "no subscription token" in message or "active f1tv subscription" in message:
        return "f1_subscription_required"
    if any(marker in message for marker in ("config object", "config scrape", "unexpected response", "state mismatch")):
        return "f1_sign_in_changed"
    return "f1_browser_token_invalid" if operation == "browser_token" else "f1_sign_in_failed"


def main():
    payload = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        if sys.argv[1] == "login":
            from fastf1.internals.f1account.login import login
            token = login(payload["email"], payload["password"])
            try:
                verify_archive(token.value)
            except Exception as exc:
                # Preserve the data-access stage: an archive 403 is not a password failure.
                print(json.dumps({"ok": False, "code": failure_code(exc, "verify")}), file=sys.__stdout__)
                return
            result = {"token": token.value, "expires_at": token.expires_at}
        elif sys.argv[1] == "verify":
            verify_archive(payload["token"])
            result = {"verified": True}
        elif sys.argv[1] == "browser_token":
            from fastf1.internals.f1account.browser import _verify_jwt
            from fastf1.internals.f1account.tokens import SubscriptionToken
            claims = _verify_jwt(payload["token"])
            token = SubscriptionToken.from_jwt(payload["token"])
            verify_archive(token.value)
            email = claims.get("email")
            result = {"token": token.value, "expires_at": token.expires_at,
                      "account_hint": email if isinstance(email, str) and "@" in email else None}
        elif sys.argv[1] == "load":
            from datetime import timedelta
            from fastf1.internals.f1account import token_manager
            from fastf1.internals.f1account.tokens import SubscriptionToken
            # This child has one account. Never load/store FastF1's machine-wide token file.
            token = SubscriptionToken.from_jwt(payload["token"])
            token_manager.get = lambda *a, **k: token if token.is_valid() else (_ for _ in ()).throw(ValueError("Expired F1 token"))
            token_manager.clear = lambda: None
            from modules.ingestion.infrastructure.fastf1_adapter import FastF1Adapter
            from modules.session_domain.domain.models import SessionImportRequest
            from modules.ingestion.domain.models import TelemetrySelection
            request = SessionImportRequest.model_validate(payload["request"])
            selection = payload.get("selection")
            selected = TelemetrySelection(frozenset(selection["drivers"]), frozenset(selection["kinds"])) if selection else None
            bundle = FastF1Adapter(cache_dir=payload["cache_dir"]).load_session(request, telemetry_selection=selected)
            result = bundle.model_dump(mode="python")
        else:
            raise ValueError("Unsupported operation")
    from modules.provider_connections.infrastructure.wire_format import pack
    print(json.dumps({"ok": True, "result": pack(result)}, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not print provider exceptions, tracebacks, tokens or credential-bearing URLs.
        print(json.dumps({"ok": False, "code": failure_code(error, sys.argv[1])}))
        sys.exit(1)
