"""Versioned authenticated encryption; a database copy alone cannot reveal provider secrets."""
import base64
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings


def default_key_path():
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return root / "pitwall-insights" / "secrets" / "provider-credentials.key"


class CredentialVault:
    def __init__(self, key: bytes | None = None):
        if key is None:
            if settings.provider_credentials_key:
                encoded = settings.provider_credentials_key.get_secret_value()
            else:
                path = Path(settings.provider_credentials_key_file) if settings.provider_credentials_key_file else default_key_path()
                try:
                    encoded = path.read_text().strip()
                except OSError:
                    raise ValueError("Provider encryption key is missing. Run scripts/init_provider_key.py on the backend host.") from None
            try:
                key = base64.urlsafe_b64decode(encoded)
            except Exception:
                raise ValueError("Invalid provider encryption key") from None
        if len(key) != 32:
            raise ValueError("Provider encryption key must contain 32 random bytes")
        self.cipher = AESGCM(key)

    @staticmethod
    def aad(user_id, purpose):
        return f"pitwall:v1:f1:{user_id}:{purpose}".encode()

    def encrypt(self, user_id, purpose, payload):
        nonce = os.urandom(12)
        data = json.dumps(payload, separators=(",", ":")).encode()
        return "v1:" + base64.urlsafe_b64encode(nonce + self.cipher.encrypt(nonce, data, self.aad(user_id, purpose))).decode()

    def decrypt(self, user_id, purpose, value):
        try:
            if not value.startswith("v1:"):
                raise ValueError()
            raw = base64.urlsafe_b64decode(value[3:])
            return json.loads(self.cipher.decrypt(raw[:12], raw[12:], self.aad(user_id, purpose)))
        except Exception:
            raise ValueError("Provider secret could not be decrypted; check the host encryption key or reconnect.") from None
