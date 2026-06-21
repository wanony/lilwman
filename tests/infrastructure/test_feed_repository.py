from datetime import datetime, timezone, timedelta
import pytest
from lilwman.infrastructure.db.feed_repository import SQLAlchemyFeedRepository


@pytest.fixture
def feed_repo(session_factory):
    return SQLAlchemyFeedRepository(session_factory)


async def test_save_returns_subscription(feed_repo):
    sub = await feed_repo.save("111", "instagram", "testuser", "http://bridge/feed")
    assert sub is not None
    assert sub.id is not None
    assert sub.channel_id == "111"
    assert sub.platform == "instagram"
    assert sub.account_name == "testuser"
    assert sub.rss_url == "http://bridge/feed"


async def test_save_duplicate_returns_none(feed_repo):
    await feed_repo.save("111", "instagram", "testuser", "http://bridge/feed")
    result = await feed_repo.save("111", "instagram", "testuser2", "http://bridge/feed")
    assert result is None


async def test_save_same_url_different_channel_allowed(feed_repo):
    sub1 = await feed_repo.save("111", "instagram", "testuser", "http://bridge/feed")
    sub2 = await feed_repo.save("222", "instagram", "testuser", "http://bridge/feed")
    assert sub1 is not None
    assert sub2 is not None
    assert sub1.channel_id == "111"
    assert sub2.channel_id == "222"


async def test_delete_returns_true(feed_repo):
    sub = await feed_repo.save("111", "instagram", "testuser", "http://bridge/feed")
    result = await feed_repo.delete(sub.id, "111")
    assert result is True


async def test_delete_wrong_channel_returns_false(feed_repo):
    sub = await feed_repo.save("111", "instagram", "testuser", "http://bridge/feed")
    result = await feed_repo.delete(sub.id, "999")
    assert result is False


async def test_delete_nonexistent_returns_false(feed_repo):
    result = await feed_repo.delete(999, "111")
    assert result is False


async def test_list_for_channel_returns_subs(feed_repo):
    await feed_repo.save("111", "instagram", "user1", "http://bridge/feed1")
    await feed_repo.save("111", "twitter", "user2", "http://bridge/feed2")
    await feed_repo.save("222", "reddit", "user3", "http://bridge/feed3")
    subs = await feed_repo.list_for_channel("111")
    assert len(subs) == 2
    platforms = {s.platform for s in subs}
    assert platforms == {"instagram", "twitter"}


async def test_list_for_channel_empty(feed_repo):
    subs = await feed_repo.list_for_channel("111")
    assert subs == []


async def test_list_all_returns_all(feed_repo):
    await feed_repo.save("111", "instagram", "a", "http://bridge/1")
    await feed_repo.save("222", "twitter", "b", "http://bridge/2")
    subs = await feed_repo.list_all()
    assert len(subs) == 2


async def test_is_seen_false_before_mark(feed_repo):
    sub = await feed_repo.save("111", "instagram", "user", "http://bridge/feed")
    assert await feed_repo.is_seen(sub.id, "post-001") is False


async def test_mark_seen_makes_is_seen_true(feed_repo):
    sub = await feed_repo.save("111", "instagram", "user", "http://bridge/feed")
    await feed_repo.mark_seen(sub.id, "post-001")
    assert await feed_repo.is_seen(sub.id, "post-001") is True


async def test_is_seen_different_feed_isolated(feed_repo):
    sub1 = await feed_repo.save("111", "instagram", "a", "http://bridge/1")
    sub2 = await feed_repo.save("222", "twitter", "b", "http://bridge/2")
    await feed_repo.mark_seen(sub1.id, "post-001")
    assert await feed_repo.is_seen(sub2.id, "post-001") is False


async def test_prune_seen_removes_old_entries(feed_repo):
    sub = await feed_repo.save("111", "instagram", "user", "http://bridge/feed")
    await feed_repo.mark_seen(sub.id, "old-post")
    # Manually age the seen_at — prune_seen removes entries older than N days
    # Since we can't easily time-travel in SQLite, test with 0 days (removes everything)
    await feed_repo.prune_seen(older_than_days=0)
    assert await feed_repo.is_seen(sub.id, "old-post") is False


async def test_delete_cascades_seen_posts(feed_repo):
    sub = await feed_repo.save("111", "instagram", "user", "http://bridge/feed")
    await feed_repo.mark_seen(sub.id, "post-001")
    await feed_repo.delete(sub.id, "111")
    # After deletion, re-adding the same feed and checking old guid should return False
    sub2 = await feed_repo.save("111", "instagram", "user", "http://bridge/feed")
    assert await feed_repo.is_seen(sub2.id, "post-001") is False
