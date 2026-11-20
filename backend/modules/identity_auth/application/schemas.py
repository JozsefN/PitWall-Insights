from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from modules.identity_auth.domain.models import AccountRole


class SignUpRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def check_password_length(cls, password: str) -> str:
        if len(password.encode()) > 72:
            raise ValueError("Use a password of at most 72 bytes.")
        return password


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    status: Literal["authenticated"] = "authenticated"
    access_token: str
    token_type: str = "bearer"


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user_id: str | None = None
    email: EmailStr | None = None
    role: AccountRole | None = None
    email_verified: bool = False


class VerificationRequired(BaseModel):
    status: Literal["verification_required"] = "verification_required"
    challenge_id: str
    email: EmailStr


class VerificationChallengeRequest(BaseModel):
    challenge_id: str = Field(min_length=36, max_length=36)


class VerificationRequest(VerificationChallengeRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


AuthResult = AuthTokenResponse | VerificationRequired
