from lilwman.domain.feed_ports import FeedRepository


class RemoveFeedUseCase:
    def __init__(self, repo: FeedRepository) -> None:
        self._repo = repo

    async def execute(self, feed_id: int, channel_id: str) -> bool:
        return await self._repo.delete(feed_id, channel_id)
