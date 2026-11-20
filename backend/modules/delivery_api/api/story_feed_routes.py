from fastapi import APIRouter, Depends

from modules.delivery_api.api.auth_dependencies import require_admin

from modules.story_feed.application.service import StoryFeedService

router = APIRouter(prefix="/api/story-feed", tags=["story_feed"])


@router.get("/health", dependencies=[Depends(require_admin)])
def story_feed_health() -> dict:
    service = StoryFeedService()
    return {
        "module": "story_feed",
        "status": "ok",
        "details": service.get_status().model_dump(),
    }
