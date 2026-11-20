from typing import Literal

from pydantic import BaseModel

AccountRole = Literal["member", "admin"]


class User(BaseModel):
    id: str
    email: str
    role: AccountRole = "member"
    email_verified: bool = False
