from abc import ABC, abstractmethod
from .feed_entities import FeedSubscription, FeedPost


class FeedRepository(ABC):
    @abstractmethod
    async def save(
        self, channel_id: str, platform: str, account_name: str, rss_url: str
    ) -> FeedSubscription | None: ...

    @abstractmethod
    async def delete(self, feed_id: int, channel_id: str) -> bool: ...

    @abstractmethod
    async def list_for_channel(self, channel_id: str) -> list[FeedSubscription]: ...

    @abstractmethod
    async def list_all(self) -> list[FeedSubscription]: ...

    @abstractmethod
    async def is_seen(self, feed_id: int, guid: str) -> bool: ...

    @abstractmethod
    async def mark_seen(self, feed_id: int, guid: str) -> None: ...

    @abstractmethod
    async def prune_seen(self, older_than_days: int) -> None: ...


class FeedFetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> list[FeedPost]: ...
