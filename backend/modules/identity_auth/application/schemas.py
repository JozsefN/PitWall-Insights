from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user_id: str | None = None
    email: EmailStr | None = None