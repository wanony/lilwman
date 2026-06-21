from lilwman.domain.feed_entities import FeedSubscription
from lilwman.domain.feed_ports import FeedRepository


class ListFeedsUseCase:
    def __init__(self, repo: FeedRepository) -> None:
        self._repo = repo

    async def execute(self, channel_id: str) -> list[FeedSubscription]:
        return await self._repo.list_for_channel(channel_id)
