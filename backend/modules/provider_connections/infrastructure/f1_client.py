"""Process boundary keeps FastF1 global credentials and caches out of other accounts."""
import json
import subprocess
import sys
import logging
from pathlib import Path
from .errors import ProviderAuthenticationError, ProviderUnavailableError, ProviderAccessError


def run_provider_process(operation, payload, timeout=90):
    try:
        result = subprocess.run(
            [sys.executable, "-m", "modules.provider_connections.infrastructure.f1_process", operation],
            input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True,
            timeout=timeout, cwd=Path(__file__).resolve().parents[3],
        )
        response = json.loads(result.stdout)
        if not isinstance(response, dict):
            raise ValueError()
    except (subprocess.TimeoutExpired, OSError):
        raise ProviderUnavailableError("F1 is temporarily unavailable. Your saved connection remains linked; please retry shortly.") from None
    except ValueError:
        # Upstream exceptions can contain requests or credential details. Never propagate them.
        raise ProviderUnavailableError("The F1 connector returned an invalid response. Retry or use browser sign-in in Profile.", code="f1_connector_response_invalid") from None
    if result.returncode or not response.get("ok"):
        code = response.get("code")
        known = {"f1_temporarily_unavailable", "f1_source_access_denied", "f1_subscription_required",
                 "f1_sign_in_changed", "f1_browser_token_invalid", "f1_sign_in_failed", "f1_access_expired"}
        code = code if code in known else "f1_sign_in_failed"
        logging.getLogger(__name__).warning("F1 operation=%s failure=%s", operation, code)
        if code == "f1_source_access_denied":
            raise ProviderAccessError()
        if code == "f1_temporarily_unavailable" or response.get("error_kind") == "unavailable":
            raise ProviderUnavailableError()
        messages = {
            "f1_subscription_required": "F1 returned no subscription access. Check that this account has an active F1 TV Access subscription or higher. OpenF1 history works without it.",
            "f1_sign_in_changed": "F1's sign-in flow needs browser verification or has changed. Use browser sign-in below; retyping the same password may not help.",
            "f1_browser_token_invalid": "The browser did not provide valid F1 access. Sign in again on Formula 1's website and approve the connection in the Companion extension.",
            "f1_access_expired": "Your F1 access has expired or was rejected. Reconnect in Profile, or choose OpenF1 history.",
        }
        raise ProviderAuthenticationError(messages.get(code, "F1 sign-in could not be completed. Try browser sign-in, or sign in at Formula1.com to check your account and subscription."), code=code)
    return response["result"]


class F1AccountClient:
    def authenticate(self, email, password):
        return run_provider_process("login", {"email": email, "password": password})

    def verify(self, token):
        return run_provider_process("verify", {"token": token}, timeout=30)

    def accept_browser(self, token):
        return run_provider_process("browser_token", {"token": token}, timeout=60)
