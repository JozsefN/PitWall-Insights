from modules.story_feed.domain.models import StoryFeedStatus


class StoryFeedService:
    def get_status(self) -> StoryFeedStatus:
        return StoryFeedStatus(
            feed_name="session_story_feed",
            status="not_implemented",
            enabled=False,
        )