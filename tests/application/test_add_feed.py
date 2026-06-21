import pytest
from lilwman.application.add_feed import AddFeedUseCase, build_rss_url, SUPPORTED_PLATFORMS


def test_build_rss_url_instagram():
    url = build_rss_url("http://localhost:3000", "instagram", "testuser")
    assert url == "http://localhost:3000/?action=display&bridge=Instagram&username=testuser&format=Atom"


def test_build_rss_url_reddit():
    url = build_rss_url("http://localhost:3000", "reddit", "python")
    assert url == "http://localhost:3000/?action=display&bridge=Reddit&r=python&format=Atom"


def test_build_rss_url_twitter():
    url = build_rss_url("http://localhost:3000", "twitter", "elonmusk")
    assert url == "http://localhost:3000/?action=display&bridge=Twitter&u=elonmusk&format=Atom"


def test_build_rss_url_youtube():
    url = build_rss_url("http://localhost:3000", "youtube", "UCabcdef")
    assert url == "http://localhost:3000/?action=display&bridge=YouTube&channel=UCabcdef&format=Atom"


def test_supported_platforms_contains_expected():
    assert "instagram" in SUPPORTED_PLATFORMS
    assert "twitter" in SUPPORTED_PLATFORMS
    assert "tiktok" in SUPPORTED_PLATFORMS
    assert "reddit" in SUPPORTED_PLATFORMS
    assert "youtube" in SUPPORTED_PLATFORMS
    assert "twitch" in SUPPORTED_PLATFORMS
    assert "hackernews" in SUPPORTED_PLATFORMS


async def test_add_feed_saves_subscription(feed_repo):
    uc = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub = await uc.execute("111", "instagram", "testuser")
    assert sub is not None
    assert sub.id is not None
    assert sub.platform == "instagram"
    assert sub.account_name == "testuser"
    assert "Instagram" in sub.rss_url
    assert "testuser" in sub.rss_url


async def test_add_feed_duplicate_returns_none(feed_repo):
    uc = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await uc.execute("111", "instagram", "testuser")
    result = await uc.execute("111", "instagram", "testuser")
    assert result is None


async def test_add_feed_same_account_different_channel_allowed(feed_repo):
    uc = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub1 = await uc.execute("111", "instagram", "testuser")
    sub2 = await uc.execute("222", "instagram", "testuser")
    assert sub1 is not None
    assert sub2 is not None


async def test_add_feed_custom_url(feed_repo):
    uc = AddFeedUseCase(feed_repo, "http://localhost:3000")
    sub = await uc.execute_custom_url("111", "https://example.com/feed.xml")
    assert sub is not None
    assert sub.platform == "custom"
    assert sub.rss_url == "https://example.com/feed.xml"


async def test_add_feed_custom_url_duplicate_returns_none(feed_repo):
    uc = AddFeedUseCase(feed_repo, "http://localhost:3000")
    await uc.execute_custom_url("111", "https://example.com/feed.xml")
    result = await uc.execute_custom_url("111", "https://example.com/feed.xml")
    assert result is None


async def test_execute_passes_guild_id_to_repo(feed_repo):
    uc = AddFeedUseCase(feed_repo, "http://bridge.local")
    sub = await uc.execute("ch1", "reddit", "python", guild_id="g123")
    assert sub is not None
    assert sub.guild_id == "g123"
