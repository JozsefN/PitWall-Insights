import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=120)
    nickname: str | None = Field(default=None, max_length=60)
    phone_number: str | None = Field(default=None, max_length=32)

    @field_validator("name", "nickname", "phone_number")
    @classmethod
    def clean(cls, value):
        if value is None:
            return None
        value = value.strip()
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not allowed")
        return value or None

    @field_validator("phone_number")
    @classmethod
    def phone(cls, value):
        if value and not re.fullmatch(r"\+?[0-9 ()\-]{6,32}", value):
            raise ValueError("Use a valid telephone number")
        return value
