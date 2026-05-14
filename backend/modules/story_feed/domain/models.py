from pydantic import BaseModel, Field


class StoryFeedStatus(BaseModel):
    feed_name: str
    status: str
    enabled: bool
    planned_surfaces: list[str] = Field(default_factory=list)
