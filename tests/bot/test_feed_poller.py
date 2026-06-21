from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import discord
from lilwman.domain.feed_entities import FeedPost, FeedSubscription
from lilwman.bot.poller import FeedPoller, _make_post_embed


def _make_sub(channel_id="999", platform="instagram") -> FeedSubscription:
    return FeedSubscription(
        id=1, channel_id=channel_id, platform=platform,
        account_name="testuser", rss_url="http://example.com",
        created_at=datetime.now(timezone.utc),
    )


def _make_post(images=None, video_url=None, platform_url="https://instagram.com/p/1") -> FeedPost:
    return FeedPost(
        guid="p1", title="Test Post", url=platform_url,
        description="desc", author="testuser",
        published_at=datetime.now(timezone.utc),
        images=images or [],
        video_url=video_url,
    )


def _make_poller(channel=None, poll_uc=None):
    bot = MagicMock()
    mock_channel = channel or AsyncMock(spec=discord.TextChannel)
    bot.get_channel = MagicMock(return_value=mock_channel)
    bot.wait_until_ready = AsyncMock()
    return FeedPoller(bot, poll_uc or AsyncMock()), mock_channel


async def test_do_poll_calls_use_case():
    poll_uc = AsyncMock()
    poll_uc.execute = AsyncMock(return_value=[])
    poller, _ = _make_poller(poll_uc=poll_uc)

    await poller._do_poll()

    poll_uc.execute.assert_called_once()


async def test_post_text_only_sends_embed():
    poller, channel = _make_poller()
    await poller._post(_make_sub(), _make_post())

    channel.send.assert_called_once()
    kwargs = channel.send.call_args.kwargs
    assert "embed" in kwargs


async def test_post_single_image_embed_has_image():
    poller, channel = _make_poller()
    await poller._post(_make_sub(), _make_post(images=["https://example.com/img.jpg"]))

    kwargs = channel.send.call_args.kwargs
    assert "embed" in kwargs
    embed = kwargs["embed"]
    assert embed.image.url == "https://example.com/img.jpg"


async def test_post_multi_image_sends_paginator():
    poller, channel = _make_poller()
    post = _make_post(images=["https://example.com/img0.jpg", "https://example.com/img1.jpg"])
    await poller._post(_make_sub(), post)

    kwargs = channel.send.call_args.kwargs
    assert "view" in kwargs


async def test_post_video_twitter_sends_fix_url():
    poller, channel = _make_poller()
    sub = _make_sub(platform="twitter")
    post = _make_post(video_url="https://cdn.example.com/v.mp4",
                      platform_url="https://x.com/user/status/123")
    await poller._post(sub, post)

    channel.send.assert_called_once()
    args = channel.send.call_args.args
    assert len(args) == 1
    assert "vxtwitter.com" in args[0]


async def test_post_video_no_fix_url_sends_embed():
    poller, channel = _make_poller()
    sub = _make_sub(platform="reddit")
    post = _make_post(video_url="https://cdn.example.com/v.mp4")
    await poller._post(sub, post)

    kwargs = channel.send.call_args.kwargs
    assert "embed" in kwargs


async def test_post_missing_channel_skips_gracefully():
    poll_uc = AsyncMock()
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=None)
    bot.wait_until_ready = AsyncMock()
    poller = FeedPoller(bot, poll_uc)

    await poller._post(_make_sub(), _make_post())
    # should not raise


def test_make_post_embed_fields():
    sub = _make_sub()
    post = _make_post()
    embed = _make_post_embed(post, sub, 0xE1306C)
    assert embed.title == "Test Post"
    assert embed.url == "https://instagram.com/p/1"
    assert embed.color.value == 0xE1306C
