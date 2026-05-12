from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from modules.session_domain.domain.models import ImportProfile


ImportJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ImportJobStage = Literal[
    "queued",
    "loading_source",
    "normalizing",
    "persisting",
    "completed",
    "failed",
]


class ImportJobRead(BaseModel):
    id: str
    source: str
    source_session_key: str | None = None
    season_year: int
    round_number: int
    session_name: str
    import_profile: ImportProfile
    status: ImportJobStatus
    progress_stage: ImportJobStage
    attempt_count: int
    force_refresh: bool
    created_by_user_id: str | None = None
    session_id: str | None = None
    source_version: str | None = None
    rows_written: int | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime


class ImportJobListResponse(BaseModel):
    jobs: list[ImportJobRead] = Field(default_factory=list)
