from pydantic import BaseModel


class User(BaseModel):
    id: str
    email: str


class UserSession(BaseModel):
    authenticated: bool
    user_id: str | None = None
    email: str | None = None