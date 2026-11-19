from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from modules.provider_connections.infrastructure.db_models import F1ConnectionRecord
from modules.provider_connections.infrastructure.f1_client import F1AccountClient, ProviderAuthenticationError, ProviderUnavailableError
from modules.provider_connections.infrastructure.vault import CredentialVault


class ConnectionService:
    def __init__(self, db, *, client=None, vault=None):
        self.db = db
        self.client = client or F1AccountClient()
        self._vault = vault

    @property
    def vault(self):
        if self._vault is None:
            self._vault = CredentialVault()
        return self._vault

    def _lock(self, user_id):
        self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "f1-connection:" + user_id})

    def status(self, user_id):
        row = self.db.get(F1ConnectionRecord, user_id)
        if row is None:
            return {"status": "not_connected", "connected": False, "expires_at": None, "persistent": False}
        status = row.status
        if row.auth_method == "browser" and row.token_expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            status = "reconnect_required"
        return {"status": status, "connected": status == "connected", "expires_at": row.token_expires_at,
                "auth_method": row.auth_method, "persistent": True, "connected_at": row.connected_at, "verified_at": row.verified_at}

    def connect(self, user_id, payload):
        if not payload.personal_use_acknowledged or not payload.remember_credentials:
            raise ValueError("Consent to the persistent personal-use connection is required")
        vault = self.vault  # Fail before contacting F1 if secret storage is not configured.
        self._lock(user_id)
        now = datetime.now(timezone.utc)
        row = self.db.get(F1ConnectionRecord, user_id)
        if row and row.last_attempt_at > now - timedelta(seconds=30):
            raise ValueError("Please wait 30 seconds before reconnecting")
        result = self.client.authenticate(str(payload.email), payload.password.get_secret_value())
        expires = datetime.fromtimestamp(float(result["expires_at"]), timezone.utc)
        if expires <= now + timedelta(minutes=5):
            raise ProviderAuthenticationError("F1 returned access that expires too soon; reconnect after signing in at Formula1.com")
        if row is None:
            row = F1ConnectionRecord(user_id=user_id)
        row.encrypted_credentials = vault.encrypt(user_id, "credentials", {"email": str(payload.email), "password": payload.password.get_secret_value()})
        row.encrypted_token = vault.encrypt(user_id, "token", {"token": result["token"]})
        row.token_expires_at = expires
        row.verified_at = row.last_attempt_at = now
        row.status = "connected"
        row.auth_method = "password"
        self.db.add(row)
        self.db.commit()
        return self.status(user_id)

    def connect_browser(self, user_id, result):
        """Only a verified, server-held handoff result can reach this method."""
        vault = self.vault
        expires = datetime.fromtimestamp(float(result["expires_at"]), timezone.utc)
        now = datetime.now(timezone.utc)
        if expires <= now + timedelta(minutes=5):
            raise ProviderAuthenticationError("Browser access expires too soon. Sign in again on Formula 1's website.")
        self._lock(user_id)
        row = self.db.get(F1ConnectionRecord, user_id) or F1ConnectionRecord(user_id=user_id)
        row.encrypted_credentials = vault.encrypt(user_id, "credentials", {"method": "browser"})
        row.encrypted_token = vault.encrypt(user_id, "token", {"token": result["token"]})
        row.token_expires_at = expires
        row.verified_at = row.last_attempt_at = now
        row.status, row.auth_method = "connected", "browser"
        self.db.add(row)
        self.db.commit()
        return self.status(user_id)

    def access_token(self, user_id):
        self._lock(user_id)
        row = self.db.get(F1ConnectionRecord, user_id, populate_existing=True)
        if row is None:
            raise ProviderAuthenticationError("Connect your F1 account in Profile to load from F1, or choose OpenF1 for free historical telemetry and replay.", code="f1_connection_required")
        now = datetime.now(timezone.utc)
        if row.status == "reconnect_required":
            raise ProviderAuthenticationError("Your F1 account needs attention. Reconnect in Profile or choose OpenF1 history.", code="f1_reconnect_required")
        if row.token_expires_at <= now + timedelta(minutes=5):
            if row.auth_method == "browser":
                row.status = "reconnect_required"
                self.db.commit()
                raise ProviderAuthenticationError("Your browser-issued F1 access expired. Your account link is still saved. Sign in again in Profile, or choose OpenF1.", code="f1_reconnect_required")
            if row.last_attempt_at > now - timedelta(seconds=30):
                raise ProviderAuthenticationError("F1 access renewal is cooling down; retry shortly")
            credentials = self.vault.decrypt(user_id, "credentials", row.encrypted_credentials)
            row.last_attempt_at = now
            try:
                result = self.client.authenticate(credentials["email"], credentials["password"])
                expires = datetime.fromtimestamp(float(result["expires_at"]), timezone.utc)
                if expires <= now + timedelta(minutes=5):
                    raise ProviderAuthenticationError("F1 access renewal failed")
            except ProviderUnavailableError:
                self.db.commit()  # Keep the durable link; a provider outage is not a credential revocation.
                raise
            except ProviderAuthenticationError:
                row.status = "reconnect_required"
                self.db.commit()
                raise
            row.encrypted_token = self.vault.encrypt(user_id, "token", {"token": result["token"]})
            row.token_expires_at = expires
            row.verified_at = now
            self.db.commit()
        token = self.vault.decrypt(user_id, "token", row.encrypted_token)["token"]
        self.db.commit()  # Release the per-account lock before a long telemetry download.
        return token

    def verify(self, user_id):
        token = self.access_token(user_id)
        try:
            self.client.verify(token)
        except ProviderAuthenticationError:
            self._lock(user_id)
            row = self.db.get(F1ConnectionRecord, user_id, populate_existing=True)
            if row:
                row.status = "reconnect_required"
            self.db.commit()
            raise
        self._lock(user_id)
        row = self.db.get(F1ConnectionRecord, user_id, populate_existing=True)
        if row:
            row.verified_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.status(user_id)

    def disconnect(self, user_id):
        self._lock(user_id)
        row = self.db.get(F1ConnectionRecord, user_id)
        if row:
            self.db.delete(row)
        self.db.commit()
        return self.status(user_id)
