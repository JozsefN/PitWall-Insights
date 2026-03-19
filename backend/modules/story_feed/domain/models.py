from pydantic import BaseModel


class StoryFeedStatus(BaseModel):
    feed_name: str
    status: str
    enabled: bool