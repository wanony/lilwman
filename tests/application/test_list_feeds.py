from lilwman.application.add_feed import AddFeedUseCase
from lilwman.application.list_feeds import ListFeedsUseCase


async def test_list_feeds_empty(feed_repo):
    uc = ListFeedsUseCase(feed_repo)
    subs = await uc.execute("111")
    assert subs == []


async def test_list_feeds_returns_channel_subs(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("111", "instagram", "a")
    await add.execute("111", "twitter", "b")
    await add.execute("222", "reddit", "c")
    uc = ListFeedsUseCase(feed_repo)
    subs = await uc.execute("111")
    assert len(subs) == 2
    channels = {s.channel_id for s in subs}
    assert channels == {"111"}


async def test_list_feeds_excludes_other_channels(feed_repo):
    add = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await add.execute("999", "reddit", "other")
    uc = ListFeedsUseCase(feed_repo)
    subs = await uc.execute("111")
    assert subs == []
