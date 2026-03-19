from pydantic import BaseModel


class UserSession(BaseModel):
    authenticated: bool
    user_id: str | None = None
    email: str | None = None