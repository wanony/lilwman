from lilwman.bot.feed_utils import get_fix_url, get_platform_colour


def test_fix_url_twitter_x_domain():
    result = get_fix_url("twitter", "https://x.com/user/status/123")
    assert result == "https://vxtwitter.com/user/status/123"


def test_fix_url_twitter_old_domain():
    result = get_fix_url("twitter", "https://twitter.com/user/status/123")
    assert result == "https://vxtwitter.com/user/status/123"


def test_fix_url_instagram():
    result = get_fix_url("instagram", "https://instagram.com/p/abc")
    assert result == "https://ddinstagram.com/p/abc"


def test_fix_url_tiktok():
    result = get_fix_url("tiktok", "https://tiktok.com/@user/video/123")
    assert result == "https://vxtiktok.com/@user/video/123"


def test_fix_url_unsupported_platform_returns_none():
    assert get_fix_url("reddit", "https://reddit.com/r/python") is None


def test_fix_url_youtube_returns_none():
    assert get_fix_url("youtube", "https://youtube.com/watch?v=abc") is None


def test_fix_url_custom_returns_none():
    assert get_fix_url("custom", "https://example.com/feed") is None


def test_platform_colour_instagram():
    assert get_platform_colour("instagram") == 0xE1306C


def test_platform_colour_tiktok():
    assert get_platform_colour("tiktok") == 0x010101


def test_platform_colour_twitter():
    assert get_platform_colour("twitter") == 0x1DA1F2


def test_platform_colour_reddit():
    assert get_platform_colour("reddit") == 0xFF4500


def test_platform_colour_unknown_fallback():
    assert get_platform_colour("unknown_platform") == 0x5865F2
