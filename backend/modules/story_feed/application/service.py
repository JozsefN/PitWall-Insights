from modules.story_feed.domain.models import StoryFeedStatus


class StoryFeedService:
    def get_status(self) -> StoryFeedStatus:
        return StoryFeedStatus(
            feed_name="season_story_feed",
            status="planned",
            enabled=False,
            planned_surfaces=[
                "official_video_wall",
                "headline_stack",
                "race_week_rhythm",
                "season_follow_up_stories",
            ],
        )
