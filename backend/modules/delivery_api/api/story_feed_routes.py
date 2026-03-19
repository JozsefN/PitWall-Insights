from fastapi import APIRouter

from modules.story_feed.application.service import StoryFeedService

router = APIRouter(prefix="/api/story-feed", tags=["story_feed"])

service = StoryFeedService()


@router.get("/health")
def story_feed_health() -> dict:
    return {
        "module": "story_feed",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }