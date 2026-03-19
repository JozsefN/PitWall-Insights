from datetime import datetime
from pydantic import BaseModel


class SessionSummary(BaseModel):
    id: str
    name: str
    track_code: str
    driver_code: str
    started_at: datetime | None = None
    lap_count: int = 0