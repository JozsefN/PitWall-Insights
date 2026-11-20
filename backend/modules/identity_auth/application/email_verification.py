from datetime import datetime, timedelta, timezone
from hmac import compare_digest, digest
from secrets import randbelow
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.identity_auth.application.schemas import AuthTokenResponse, VerificationRequired
from modules.identity_auth.application.security import SECRET_KEY, create_access_token
from modules.identity_auth.infrastructure.db_models import EmailVerificationRecord, UserRecord
from modules.identity_auth.infrastructure.google_models import GoogleIdentityRecord
from modules.identity_auth.infrastructure.mailer import MailUnavailable, mail_configured, send_verification_code
from modules.identity_auth.infrastructure.repository import AuthRepository

CODE_LIFETIME = timedelta(minutes=10)
SEND_COOLDOWN = timedelta(minutes=1)
SEND_WINDOW = timedelta(hours=1)
MAX_ATTEMPTS = 5


class VerificationThrottled(Exception):
    pass


def _digest(scope: str, value: str) -> str:
    return digest(SECRET_KEY.encode(), f"pitwall:verify:{scope}:{value}".encode(), "sha256").hex()


def _retire(record: EmailVerificationRecord, now: datetime) -> None:
    record.consumed_at = now
    record.password_hash = None


class EmailVerification:
    def __init__(self, db: Session) -> None:
        self.db = db

    def issue(self, email: str, client: str, *, password_hash: str | None = None,
              account_id: str | None = None, google_subject: str | None = None,
              previous: EmailVerificationRecord | None = None) -> VerificationRequired:
        if not mail_configured():
            raise MailUnavailable("Email verification is unavailable on this instance.")
        now = datetime.now(timezone.utc)
        recipient_key = _digest("recipient", email.lower())
        client_key = _digest("client", client)
        for key in sorted((recipient_key, client_key)):
            self.db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
        recent = EmailVerificationRecord.created_at > now - SEND_WINDOW
        count = select(func.count()).select_from(EmailVerificationRecord)
        recipient = EmailVerificationRecord.recipient_key == recipient_key
        if (self.db.scalar(count.where(recipient, EmailVerificationRecord.created_at > now - SEND_COOLDOWN))
                or self.db.scalar(count.where(recipient, recent)) >= 6
                or self.db.scalar(count.where(EmailVerificationRecord.client_key == client_key, recent)) >= 30):
            raise VerificationThrottled("Too many verification requests. Wait and try again.")
        self.db.execute(delete(EmailVerificationRecord).where(EmailVerificationRecord.created_at < now - timedelta(days=1)))
        challenge_id = str(uuid4())
        code = f"{randbelow(1_000_000):06d}"
        if previous:
            _retire(previous, now)
        self.db.add(EmailVerificationRecord(
            id=challenge_id, email=email, recipient_key=recipient_key, client_key=client_key,
            code_digest=_digest(challenge_id, code), account_id=account_id, password_hash=password_hash,
            google_subject=google_subject, attempts=0, created_at=now, expires_at=now + CODE_LIFETIME,
        ))
        self.db.commit()
        send_verification_code(email, code)
        return VerificationRequired(challenge_id=challenge_id, email=email)

    def resend(self, challenge_id: str, client: str) -> VerificationRequired:
        previous = self.db.get(EmailVerificationRecord, challenge_id, with_for_update=True)
        if not previous or previous.consumed_at or previous.expires_at <= datetime.now(timezone.utc):
            raise ValueError("This verification attempt expired. Start again to request a code.")
        return self.issue(previous.email, client, password_hash=previous.password_hash,
                          account_id=previous.account_id, google_subject=previous.google_subject,
                          previous=previous)

    def verify(self, challenge_id: str, code: str) -> AuthTokenResponse:
        now = datetime.now(timezone.utc)
        record = self.db.get(EmailVerificationRecord, challenge_id, with_for_update=True)
        if not record or record.consumed_at or record.attempts >= MAX_ATTEMPTS or record.expires_at <= now:
            raise ValueError("This code has expired or reached its attempt limit. Request a new code.")
        if not compare_digest(record.code_digest, _digest(challenge_id, code)):
            record.attempts += 1
            self.db.commit()
            raise ValueError("The verification code is incorrect.")

        if record.account_id:
            account = self.db.get(UserRecord, record.account_id, with_for_update=True)
            if account is None or account.email.lower() != record.email.lower():
                raise ValueError("This verification attempt is no longer valid.")
            if record.google_subject:
                identity = self.db.get(GoogleIdentityRecord, record.google_subject)
                if not identity or identity.user_id != account.id:
                    raise ValueError("This verification attempt is no longer valid.")
        else:
            if AuthRepository(self.db).email_exists(record.email):
                _retire(record, now)
                self.db.commit()
                raise ValueError("This email already has an account. Sign in to continue.")
            account = UserRecord(email=record.email.lower(), password_hash=record.password_hash)
            self.db.add(account)

        account.email_verified_at = account.email_verified_at or now
        try:
            self.db.flush()
            if record.google_subject and not record.account_id:
                self.db.add(GoogleIdentityRecord(subject=record.google_subject, user_id=account.id))
            _retire(record, now)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ValueError("This email or Google identity already has an account. Sign in to continue.") from error
        return AuthTokenResponse(access_token=create_access_token(account.id, account.email))
