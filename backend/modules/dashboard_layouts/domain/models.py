from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DashboardAudience = Literal["session-lookback", "live-race"]


class LayoutCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=600)
    audience: DashboardAudience
    schema_version: int = Field(
        default=1,
        alias="schemaVersion",
        serialization_alias="schemaVersion",
        ge=1,
    )
    config: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


class LayoutUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=600)
    audience: DashboardAudience | None = None
    schema_version: int | None = Field(
        default=None,
        alias="schemaVersion",
        serialization_alias="schemaVersion",
        ge=1,
    )
    config: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class LayoutRecord(BaseModel):
    id: str
    name: str
    description: str | None = None
    source: Literal["user"] = "user"
    audience: DashboardAudience
    schema_version: int = Field(alias="schemaVersion", serialization_alias="schemaVersion")
    config: dict[str, Any]
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
