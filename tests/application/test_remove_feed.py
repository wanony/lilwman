from lilwman.application.add_feed import AddFeedUseCase
from lilwman.application.remove_feed import RemoveFeedUseCase


async def test_remove_feed_returns_true(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub = await add.execute("111", "instagram", "testuser")
    uc = RemoveFeedUseCase(feed_repo)
    result = await uc.execute(sub.id, "111")
    assert result is True


async def test_remove_feed_wrong_channel_returns_false(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub = await add.execute("111", "instagram", "testuser")
    uc = RemoveFeedUseCase(feed_repo)
    result = await uc.execute(sub.id, "999")
    assert result is False


async def test_remove_feed_nonexistent_returns_false(feed_repo):
    uc = RemoveFeedUseCase(feed_repo)
    result = await uc.execute(9999, "111")
    assert result is False


async def test_remove_feed_second_call_returns_false(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub = await add.execute("111", "instagram", "testuser")
    uc = RemoveFeedUseCase(feed_repo)
    await uc.execute(sub.id, "111")
    result = await uc.execute(sub.id, "111")
    assert result is False
