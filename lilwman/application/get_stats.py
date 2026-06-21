from lilwman.domain.admin_entities import BotStats
from lilwman.domain.ports import EntryRepository
from lilwman.domain.feed_ports import FeedRepository


class GetStatsUseCase:
    def __init__(self, entry_repo: EntryRepository, feed_repo: FeedRepository) -> None:
        self._entry_repo = entry_repo
        self._feed_repo = feed_repo

    async def execute(self, guild_id: str) -> BotStats:
        counts = await self._entry_repo.get_stats(guild_id)
        total_feeds = await self._feed_repo.count_for_guild(guild_id)
        return BotStats(
            total_entries=counts["total_entries"],
            entries_this_week=counts["entries_this_week"],
            entries_this_month=counts["entries_this_month"],
            total_feeds=total_feeds,
            unique_tags=counts["unique_tags"],
            top_tags=counts["top_tags"],
            top_authors=counts["top_authors"],
        )
