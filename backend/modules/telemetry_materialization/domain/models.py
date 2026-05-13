from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


TelemetryKind = Literal["car", "position"]
TelemetryScope = Literal["session", "lap"]
TelemetryMaterializationStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
TelemetryMaterializationStage = Literal[
    "queued",
    "loading_source",
    "normalizing",
    "persisting",
    "completed",
    "failed",
]


class TelemetryMaterializationRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    entry_ids: list[str] = Field(min_length=1)
    kinds: list[TelemetryKind] = Field(min_length=1)
    scope: TelemetryScope = "session"
    lap_number: int | None = Field(default=None, ge=1)
    force_refresh: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> "TelemetryMaterializationRequest":
        if self.scope == "lap" and self.lap_number is None:
            raise ValueError("lap_number is required for lap-scoped telemetry")
        if self.scope == "session" and self.lap_number is not None:
            raise ValueError("lap_number is only valid for lap-scoped telemetry")
        self.entry_ids = list(dict.fromkeys(self.entry_ids))
        self.kinds = list(dict.fromkeys(self.kinds))
        return self


class TelemetrySegmentRead(BaseModel):
    id: str
    session_id: str
    session_entry_id: str
    kind: TelemetryKind
    scope: TelemetryScope
    lap_number: int | None = None
    status: TelemetryMaterializationStatus
    row_count: int
    source_version: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None


class TelemetryMaterializationJobRead(BaseModel):
    id: str
    session_id: str
    entry_ids: list[str]
    kinds: list[TelemetryKind]
    scope: TelemetryScope
    lap_number: int | None = None
    status: TelemetryMaterializationStatus
    progress_stage: TelemetryMaterializationStage
    attempt_count: int
    force_refresh: bool
    source_version: str | None = None
    rows_written: int | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = None


class TelemetryMaterializationEnsureResponse(BaseModel):
    ready: bool
    job_id: str | None = None
    segments: list[TelemetrySegmentRead] = Field(default_factory=list)


class TelemetryMaterializationJobListResponse(BaseModel):
    jobs: list[TelemetryMaterializationJobRead] = Field(default_factory=list)
