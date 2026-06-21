from unittest.mock import AsyncMock
from datetime import datetime, timezone, timedelta
from lilwman.application.add_feed import AddFeedUseCase
from lilwman.application.poll_feeds import PollFeedsUseCase
from lilwman.domain.feed_entities import FeedPost


def _make_post(guid: str, hours_ago: int = 0) -> FeedPost:
    return FeedPost(
        guid=guid,
        title=f"Post {guid}",
        url=f"https://example.com/{guid}",
        description="desc",
        author="user",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


async def test_poll_returns_new_posts(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "testuser")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=[_make_post("p1"), _make_post("p2")])
    uc = PollFeedsUseCase(feed_repo, fetcher)
    results = await uc.execute()

    assert len(results) == 1
    sub, posts = results[0]
    assert sub.account_name == "testuser"
    assert len(posts) == 2
    assert {p.guid for p in posts} == {"p1", "p2"}


async def test_poll_deduplicates_seen_posts(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "testuser")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=[_make_post("p1")])
    uc = PollFeedsUseCase(feed_repo, fetcher)

    await uc.execute()           # first poll — marks p1 seen
    results = await uc.execute() # second poll — p1 already seen
    assert results == []


async def test_poll_caps_at_5_posts(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "testuser")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=[_make_post(f"p{i}") for i in range(8)])
    uc = PollFeedsUseCase(feed_repo, fetcher)
    results = await uc.execute()

    _, posts = results[0]
    assert len(posts) == 5


async def test_poll_skips_failed_feeds(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "failuser")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(side_effect=Exception("connection timeout"))
    uc = PollFeedsUseCase(feed_repo, fetcher)
    results = await uc.execute()
    assert results == []


async def test_poll_sorts_oldest_first(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "testuser")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=[
        _make_post("new", hours_ago=0),
        _make_post("old", hours_ago=5),
    ])
    uc = PollFeedsUseCase(feed_repo, fetcher)
    results = await uc.execute()

    _, posts = results[0]
    assert posts[0].guid == "old"
    assert posts[1].guid == "new"


async def test_poll_marks_posts_seen(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub = await add.execute("111", "instagram", "testuser")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=[_make_post("p1")])
    uc = PollFeedsUseCase(feed_repo, fetcher)
    await uc.execute()

    assert await feed_repo.is_seen(sub.id, "p1") is True


async def test_poll_multiple_feeds_isolated(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "a")
    await add.execute("222", "twitter", "b")

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=[_make_post("shared-guid")])
    uc = PollFeedsUseCase(feed_repo, fetcher)
    results = await uc.execute()

    # Both feeds get the post since seen tracking is per-feed
    assert len(results) == 2
    for _, posts in results:
        assert len(posts) == 1
