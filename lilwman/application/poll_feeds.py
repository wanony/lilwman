from lilwman.domain.feed_entities import FeedSubscription, FeedPost
from lilwman.domain.feed_ports import FeedRepository, FeedFetcher


class PollFeedsUseCase:
    def __init__(self, repo: FeedRepository, fetcher: FeedFetcher) -> None:
        self._repo = repo
        self._fetcher = fetcher

    async def execute(self) -> list[tuple[FeedSubscription, list[FeedPost]]]:
        results = []
        subscriptions = await self._repo.list_all()
        for sub in subscriptions:
            try:
                posts = await self._fetcher.fetch(sub.rss_url)
            except Exception:
                continue
            new_posts = []
            for post in posts:
                if not await self._repo.is_seen(sub.id, post.guid):
                    new_posts.append(post)
            new_posts.sort(key=lambda p: p.published_at)
            new_posts = new_posts[:5]
            for post in new_posts:
                await self._repo.mark_seen(sub.id, post.guid)
            if new_posts:
                results.append((sub, new_posts))
        await self._repo.prune_seen(older_than_days=30)
        return results
