from modules.identity_auth.application.email_verification import EmailVerification
from modules.identity_auth.application.schemas import AuthResult, AuthTokenResponse, VerificationRequired
from modules.identity_auth.application.security import hash_password, verify_password, create_access_token
from modules.identity_auth.infrastructure.repository import AuthRepository


class AuthService:
    def __init__(self, repository: AuthRepository) -> None:
        self.repository = repository
        self.verification = EmailVerification(repository.db)

    def signup(self, email: str, password: str, client: str) -> VerificationRequired:
        if self.repository.email_exists(email):
            raise ValueError("This email already has an account. Sign in to continue.")
        return self.verification.issue(email.lower(), client, password_hash=hash_password(password))

    def login(self, email: str, password: str, client: str) -> AuthResult:
        account = self.repository.account_by_email(email)
        if not account or not account.password_hash or not verify_password(password, account.password_hash):
            raise ValueError("Invalid credentials.")
        if account.role == "admin" or account.email_verified_at is not None:
            return AuthTokenResponse(access_token=create_access_token(account.id, account.email))
        return self.verification.issue(account.email, client, account_id=account.id)
