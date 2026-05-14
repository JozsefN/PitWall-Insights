from fastapi import APIRouter

from modules.story_feed.application.service import StoryFeedService

router = APIRouter(prefix="/api/story-feed", tags=["story_feed"])


@router.get("/health")
def story_feed_health() -> dict:
    service = StoryFeedService()
    return {
        "module": "story_feed",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }
