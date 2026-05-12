from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from modules.session_domain.domain.models import ImportProfile, SessionCatalogItem


class IngestionSourceStatus(BaseModel):
    source_name: str
    configured: bool
    status: str
    cache_dir: str | None = None
    cache_size_bytes: int | None = None
    import_timeout_seconds: int | None = None


class SourceSessionMetadata(BaseModel):
    meeting_key: str | None = None
    session_key: str | None = None
    api_path: str | None = None
    f1_api_support: bool | None = None
    actual_start_utc: datetime | None = None
    session_info: dict[str, Any] = Field(default_factory=dict)


class SourceSessionBundle(BaseModel):
    source: str = Field(min_length=1, max_length=32)
    catalog_item: SessionCatalogItem
    import_profile: ImportProfile = "core"
    metadata: SourceSessionMetadata = Field(default_factory=SourceSessionMetadata)
    drivers: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    laps: list[dict[str, Any]] = Field(default_factory=list)
    weather: list[dict[str, Any]] = Field(default_factory=list)
    session_status: list[dict[str, Any]] = Field(default_factory=list)
    track_status: list[dict[str, Any]] = Field(default_factory=list)
    race_control_messages: list[dict[str, Any]] = Field(default_factory=list)
    car_telemetry: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    position_data: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    source_version: str | None = None
