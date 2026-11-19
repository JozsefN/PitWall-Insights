from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REVIEW_GROUPS = (
    "drivers",
    "segments",
    "radio",
    "racecraft",
    "pace",
    "pit",
    "incidents",
    "weather",
    "surface",
    "flags",
)
REVIEW_VERSION = "session_review_v1"


class LapSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: str = Field(min_length=1, max_length=100)
    lap_number: int = Field(ge=1, le=1000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    # Omit the cutoff only for a completed-session lookback.
    as_of_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    entry_ids: list[str] | None = Field(default=None, min_length=1, max_length=64)
    groups: list[
        Literal[
            "drivers",
            "segments",
            "radio",
            "racecraft",
            "pace",
            "pit",
            "incidents",
            "weather",
            "surface",
            "flags",
        ]
    ] = Field(default_factory=lambda: list(REVIEW_GROUPS), min_length=1, max_length=10)
    laps: list[LapSelection] = Field(default_factory=list, max_length=12)
    segment_count: int = Field(default=20, ge=6, le=40)
    horizon_laps: int = Field(default=5, ge=1, le=20)
    fuel_burn_kg_per_lap: float | None = Field(default=None, gt=0, le=5)
    fuel_time_s_per_kg: float | None = Field(default=None, gt=0, le=0.2)
    repair_extra_s: float | None = Field(default=None, gt=0, le=60)
    context_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_fuel(self):
        if (self.fuel_burn_kg_per_lap is None) != (self.fuel_time_s_per_kg is None):
            raise ValueError(
                "A fuel scenario requires both burn and lap-time sensitivity"
            )
        return self
